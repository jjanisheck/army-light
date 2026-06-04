//
//  BLEEngine.swift
//  ARMY Light
//
//  Low-level CoreBluetooth wrapper. All CB state is confined to a private serial
//  queue; the public surface is async/await wrappers over the delegate callbacks.
//  Higher-level policy (reconnect-per-write, white wake packet, serialization)
//  lives in WandController, mirroring the Python `controller.py`.
//
//  Each asynchronous operation parks a `Void` continuation in a `Slot`, arms a
//  timeout work item on the same serial queue, and is resumed by exactly one of:
//  the matching delegate callback (success/failure) or the timeout. Routing all
//  resumption through `resume(_:throwing:)` on the queue keeps it race-free and
//  guarantees every continuation resumes exactly once.
//

import CoreBluetooth
import Foundation

enum WandError: LocalizedError {
    case bluetoothUnavailable(CBManagerState)
    case wandNotFound
    case connectFailed(String)
    case characteristicMissing
    case writeFailed(String)
    case timeout(String)

    var errorDescription: String? {
        switch self {
        case .bluetoothUnavailable(let s): return "Bluetooth unavailable (\(s.label))"
        case .wandNotFound: return "Wand not found — is it on, in Bluetooth mode, and unpaired from the phone app?"
        case .connectFailed(let m): return "Connect failed: \(m)"
        case .characteristicMissing: return "Write characteristic not found"
        case .writeFailed(let m): return "Write failed: \(m)"
        case .timeout(let what): return "Timed out: \(what)"
        }
    }
}

extension CBManagerState {
    var label: String {
        switch self {
        case .poweredOn: return "on"
        case .poweredOff: return "off"
        case .unauthorized: return "unauthorized"
        case .unsupported: return "unsupported"
        case .resetting: return "resetting"
        case .unknown: return "unknown"
        @unknown default: return "unknown"
        }
    }
}

/// CoreBluetooth, wrapped in async/await. Callers (WandController) serialize use.
///
/// `@unchecked Sendable` is sound here: every mutable property is touched only on
/// the private serial `queue` (delegate callbacks run there; the public API hops
/// onto it), so there is no concurrent access despite the type crossing into
/// `@Sendable` timeout/continuation closures.
final class BLEEngine: NSObject, @unchecked Sendable {
    private let queue = DispatchQueue(label: "com.example.armylight.ble")
    private var central: CBCentralManager!

    private var peripheral: CBPeripheral?
    private var writeChar: CBCharacteristic?
    private var commitChar: CBCharacteristic?

    private var scanResult: CBPeripheral?     // handed back out of the scan slot
    private var nameMatch = ""
    private var targetService: CBUUID?
    private var wantedChar: CBUUID?
    private var wantedCommitChar: CBUUID?

    /// One pending operation per slot; all continuations are `Void`-typed and
    /// resumed only via `resume(_:throwing:)` on `queue`.
    private enum Slot: Hashable { case ready, scan, connect, services, chars, write, writeRoom }
    private var conts: [Slot: CheckedContinuation<Void, Error>] = [:]
    private var timeouts: [Slot: DispatchWorkItem] = [:]

    /// Notification payloads from the wand, surfaced for diagnostics.
    var onNotify: ((Data) -> Void)?

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: queue)
    }

    var isConnected: Bool {
        queue.sync { peripheral?.state == .connected && writeChar != nil }
    }

    // MARK: - Slot plumbing (all calls on `queue`)

    private func resume(_ slot: Slot, throwing error: Error? = nil) {
        timeouts[slot]?.cancel(); timeouts[slot] = nil
        guard let cont = conts[slot] else { return }
        conts[slot] = nil
        if let error { cont.resume(throwing: error) } else { cont.resume() }
    }

    /// Park a continuation in `slot`, arm a timeout, then run `start()`.
    private func perform(_ slot: Slot, timeout: TimeInterval, label: String,
                        start: @escaping () -> Void) async throws {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            queue.async {
                // A stale continuation in this slot should never happen (callers
                // serialize), but fail it rather than leak if it does.
                if let stale = self.conts[slot] {
                    self.conts[slot] = nil
                    self.timeouts[slot]?.cancel(); self.timeouts[slot] = nil
                    stale.resume(throwing: WandError.timeout(label))
                }
                self.conts[slot] = cont
                let item = DispatchWorkItem { [weak self] in
                    guard let self, self.conts[slot] != nil else { return }
                    if slot == .scan { self.central.stopScan() }
                    self.resume(slot, throwing: WandError.timeout(label))
                }
                self.timeouts[slot] = item
                self.queue.asyncAfter(deadline: .now() + timeout, execute: item)
                start()
            }
        }
    }

    // MARK: - Public async API

    /// Resolve once Bluetooth is powered on (or throw if it can't be).
    func waitUntilReady(timeout: TimeInterval) async throws {
        if central.state == .poweredOn { return }
        try await perform(.ready, timeout: timeout, label: "bluetooth power-on") {
            // centralManagerDidUpdateState resolves this; if already terminal, fail now.
            switch self.central.state {
            case .poweredOn: self.resume(.ready)
            case .poweredOff, .unauthorized, .unsupported:
                self.resume(.ready, throwing: WandError.bluetoothUnavailable(self.central.state))
            default: break // unknown/resetting — wait for the delegate
            }
        }
    }

    /// Scan for the wand and connect. The V4 advertises NO service UUIDs, so
    /// the scan is unfiltered and a peripheral matches by advertised-name
    /// substring (or by advertising `serviceUUID`, for firmwares that do).
    func connect(
        serviceUUID: CBUUID,
        nameMatch: String,
        charUUID: CBUUID,
        commitCharUUID: CBUUID?,
        scanTimeout: TimeInterval,
        connectTimeout: TimeInterval
    ) async throws {
        // Reuse a peripheral the system already holds for this service, if any
        // (works for V4: the service is in GATT even though it isn't advertised).
        let preconnected = queue.sync {
            central.retrieveConnectedPeripherals(withServices: [serviceUUID]).first
        }
        let target: CBPeripheral
        if let preconnected {
            target = preconnected
        } else {
            try await perform(.scan, timeout: scanTimeout, label: "scan") {
                self.scanResult = nil
                self.nameMatch = nameMatch.lowercased()
                self.targetService = serviceUUID
                self.central.scanForPeripherals(withServices: nil, options: nil)
            }
            guard let found = queue.sync(execute: { scanResult }) else { throw WandError.wandNotFound }
            target = found
        }

        try await perform(.connect, timeout: connectTimeout, label: "connect") {
            self.peripheral = target
            target.delegate = self
            self.central.connect(target, options: nil)
        }

        try await perform(.services, timeout: 10, label: "discover services") {
            self.peripheral?.discoverServices(nil)
        }

        try await perform(.chars, timeout: 10, label: "discover characteristics") {
            self.wantedChar = charUUID
            self.wantedCommitChar = commitCharUUID
            guard let p = self.peripheral, let services = p.services, !services.isEmpty else {
                self.resume(.chars, throwing: WandError.characteristicMissing); return
            }
            for s in services { p.discoverCharacteristics(nil, for: s) }
        }

        if queue.sync(execute: { writeChar }) == nil { throw WandError.characteristicMissing }
    }

    /// Subscribe to notifications on the write characteristic (best-effort).
    func startNotifications() {
        queue.async {
            guard let p = self.peripheral, let c = self.writeChar,
                  c.properties.contains(.notify) || c.properties.contains(.indicate)
            else { return }
            p.setNotifyValue(true, for: c)
        }
    }

    /// Write to the resolved characteristic. `.withoutResponse` mirrors the
    /// official app; the caller retries with the other mode on failure.
    func write(_ data: Data, withResponse: Bool) async throws {
        guard isConnected else { throw WandError.writeFailed("not connected") }
        if withResponse {
            try await perform(.write, timeout: 5, label: "write") {
                guard let p = self.peripheral, let c = self.writeChar else {
                    self.resume(.write, throwing: WandError.characteristicMissing); return
                }
                p.writeValue(data, for: c, type: .withResponse)
            }
        } else {
            // Wait briefly for flow-control room, then fire-and-forget (no ack).
            try? await perform(.writeRoom, timeout: 2, label: "write room") {
                if self.peripheral?.canSendWriteWithoutResponse ?? true {
                    self.resume(.writeRoom)
                }
                // else peripheralIsReady(toSendWriteWithoutResponse:) resolves it,
                // or the 2s timeout does — either way we then write below.
            }
            try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
                queue.async {
                    guard let p = self.peripheral, let c = self.writeChar else {
                        cont.resume(throwing: WandError.characteristicMissing); return
                    }
                    p.writeValue(data, for: c, type: .withoutResponse)
                    cont.resume()
                }
            }
        }
    }

    /// Write the V4 latch byte to the commit characteristic (fire-and-forget,
    /// write-without-response — the wand drops the link shortly after anyway).
    func writeCommit(_ data: Data) {
        queue.async {
            guard let p = self.peripheral, let c = self.commitChar else { return }
            p.writeValue(data, for: c, type: .withoutResponse)
        }
    }

    func disconnect() {
        queue.async {
            if let p = self.peripheral { self.central.cancelPeripheralConnection(p) }
            self.peripheral = nil
            self.writeChar = nil
            self.commitChar = nil
        }
    }
}

// MARK: - CBCentralManagerDelegate

extension BLEEngine: CBCentralManagerDelegate {
    func centralManagerDidUpdateState(_ central: CBCentralManager) {
        switch central.state {
        case .poweredOn: resume(.ready)
        case .poweredOff, .unauthorized, .unsupported:
            resume(.ready, throwing: WandError.bluetoothUnavailable(central.state))
        default: break // still settling
        }
    }

    func centralManager(_ central: CBCentralManager, didDiscover peripheral: CBPeripheral,
                        advertisementData: [String: Any], rssi RSSI: NSNumber) {
        // Unfiltered scan (the V4 advertises no service UUIDs): a peripheral
        // must positively match by name substring, or by advertising the
        // target service (other firmwares).
        let name = (peripheral.name
            ?? advertisementData[CBAdvertisementDataLocalNameKey] as? String ?? "").lowercased()
        let nameOK = !nameMatch.isEmpty && name.contains(nameMatch)
        let advServices = advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID] ?? []
        let serviceOK = targetService.map(advServices.contains) ?? false
        guard nameOK || serviceOK else { return }
        central.stopScan()
        scanResult = peripheral
        resume(.scan)
    }

    func centralManager(_ central: CBCentralManager, didConnect peripheral: CBPeripheral) {
        resume(.connect)
    }

    func centralManager(_ central: CBCentralManager, didFailToConnect peripheral: CBPeripheral, error: Error?) {
        resume(.connect, throwing: WandError.connectFailed(error?.localizedDescription ?? "unknown"))
    }

    func centralManager(_ central: CBCentralManager, didDisconnectPeripheral peripheral: CBPeripheral, error: Error?) {
        if peripheral == self.peripheral {
            self.peripheral = nil
            self.writeChar = nil
            self.commitChar = nil
        }
    }
}

// MARK: - CBPeripheralDelegate

extension BLEEngine: CBPeripheralDelegate {
    func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        if let error { resume(.services, throwing: WandError.connectFailed(error.localizedDescription)) }
        else { resume(.services) }
    }

    func peripheral(_ peripheral: CBPeripheral, didDiscoverCharacteristicsFor service: CBService, error: Error?) {
        for char in service.characteristics ?? [] {
            if char.uuid == wantedChar { writeChar = char }
            if let wanted = wantedCommitChar, char.uuid == wanted { commitChar = char }
        }
        // Resolve once the color char (and the commit char, if expected) are in
        // hand, or once every service has reported back.
        let allReported = peripheral.services?.allSatisfy { $0.characteristics != nil } ?? true
        let haveAll = writeChar != nil && (wantedCommitChar == nil || commitChar != nil)
        if haveAll || allReported {
            // Fall back to any writable char if the exact UUID never appeared.
            if writeChar == nil {
                writeChar = peripheral.services?
                    .compactMap { $0.characteristics }.joined()
                    .first { $0.properties.contains(.write) || $0.properties.contains(.writeWithoutResponse) }
            }
            resume(.chars)
        }
    }

    func peripheral(_ peripheral: CBPeripheral, didWriteValueFor characteristic: CBCharacteristic, error: Error?) {
        if let error { resume(.write, throwing: WandError.writeFailed(error.localizedDescription)) }
        else { resume(.write) }
    }

    func peripheralIsReady(toSendWriteWithoutResponse peripheral: CBPeripheral) {
        resume(.writeRoom)
    }

    func peripheral(_ peripheral: CBPeripheral, didUpdateValueFor characteristic: CBCharacteristic, error: Error?) {
        if let data = characteristic.value { onNotify?(data) }
    }
}
