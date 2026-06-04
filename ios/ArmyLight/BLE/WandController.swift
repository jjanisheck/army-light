//
//  WandController.swift
//  ARMY Light
//
//  Owns the BLE link and the UI-readable connection state. A Swift port of the
//  Python `army_light/controller.py` policy, verified on a real V4 unit:
//
//    - Latch once per fresh connection: write the requested color plus the ff13
//      session-restart byte (the wand applies it, exits its pairing animation,
//      and DROPS the link ~1-2s later), then reconnect. After that, plain ff01
//      color writes apply instantly over a persistent link — never write ff13
//      per color (the reconnect storm wedges the wand's BLE stack).
//    - Writes are serialized (the Python asyncio.Lock; here an actor).
//    - On write failure the link is dropped so the next call reconnects (and
//      re-latches) cleanly.
//

import CoreBluetooth
import Foundation
import Observation

@MainActor
@Observable
final class WandController {
    enum ConnState: Equatable {
        case idle, scanning, connecting, connected, error
    }

    private(set) var state: ConnState = .idle
    private(set) var lastError: String?
    private(set) var lastRGB: RGB?

    var isConnected: Bool { state == .connected }

    var statusText: String {
        switch state {
        case .idle: return "Not connected"
        case .scanning: return "Searching for wand…"
        case .connecting: return "Connecting…"
        case .connected:
            if let rgb = lastRGB { return "Connected — \(rgb.hexString)" }
            return "Connected"
        case .error: return lastError ?? "Error"
        }
    }

    private let settings: AppSettings
    private let engine = BLEEngine()
    private let gate = WriteGate()

    init(settings: AppSettings) {
        self.settings = settings
        engine.onNotify = { data in
            #if DEBUG
            print("notify:", data.map { String(format: "%02x", $0) }.joined(separator: " "))
            #endif
        }
    }

    /// Schedule a color write. Serialized; reconnects as needed. Never throws to
    /// the caller — failures land in `lastError` / `state` for the UI to read.
    func setColor(_ rgb: RGB) {
        Task { await self.performSetColor(rgb) }
    }

    private func performSetColor(_ rgb: RGB) async {
        await gate.run {
            do {
                try await self.ensureConnected(latchColor: rgb)
                try await self.writeColor(rgb)
                self.lastRGB = rgb
                self.lastError = nil
                self.state = .connected
            } catch {
                self.lastError = error.localizedDescription
                self.state = .error
                self.engine.disconnect()
            }
        }
    }

    /// Connected, latched, ready for plain color writes. A fresh V4 connection
    /// needs one latch — the requested color (so there's no color flash) plus
    /// the ff13 restart byte; the wand drops the link and we reconnect.
    private func ensureConnected(latchColor: RGB) async throws {
        if engine.isConnected { return }
        try await engine.waitUntilReady(timeout: settings.connectTimeout)
        try await connectOnce()

        if !settings.commitCharUUID.isEmpty {
            try? await writeRaw(settings.packetFormat.build(latchColor))
            engine.writeCommit(Packets.btsV4Commit)
            try? await Task.sleep(nanoseconds: 1_200_000_000)  // session restart
            engine.disconnect()
            try await connectOnce()
        }

        if settings.wakeOnConnect {  // Fanlight-family behaviour; off for V4
            engine.startNotifications()
            try? await writeRaw(settings.packetFormat.build(.white))
        }
        state = .connected
    }

    private func connectOnce() async throws {
        state = .scanning
        try await engine.connect(
            serviceUUID: CBUUID(string: settings.serviceUUID),
            nameMatch: settings.wandNameMatch,
            charUUID: CBUUID(string: settings.colorCharUUID),
            commitCharUUID: settings.commitCharUUID.isEmpty
                ? nil : CBUUID(string: settings.commitCharUUID),
            scanTimeout: settings.scanTimeout,
            connectTimeout: settings.connectTimeout
        )
        state = .connecting
    }

    private func writeColor(_ rgb: RGB, transition: UInt8 = 0) async throws {
        try await writeRaw(settings.packetFormat.build(rgb, transition: transition))
    }

    /// Write with the configured response mode; retry with the other mode once,
    /// mirroring the Python `_write`.
    private func writeRaw(_ packet: Data) async throws {
        let primary = settings.writeWithResponse
        do {
            try await engine.write(packet, withResponse: primary)
        } catch {
            try await engine.write(packet, withResponse: !primary)
        }
    }

    func disconnect() {
        engine.disconnect()
        state = .idle
    }
}

/// Serializes writes the way the Python controller's `asyncio.Lock` does.
private actor WriteGate {
    func run(_ body: @MainActor @Sendable () async -> Void) async {
        await body()
    }
}
