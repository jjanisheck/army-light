//
//  WandController.swift
//  ARMY Light
//
//  Owns the BLE link and the UI-readable connection state. A Swift port of the
//  Python `army_light/controller.py` policy:
//
//    - No persistent connection: the wand idle-disconnects, so each write
//      resolves + connects if needed, writes, and drops the link on failure so
//      the next call reconnects cleanly.
//    - Writes are serialized (the Python asyncio.Lock; here an actor).
//    - On connect, optionally subscribe to notifications and send a white "wake"
//      packet, mimicking the official app.
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
                try await self.ensureConnected()
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

    private func ensureConnected() async throws {
        if engine.isConnected { return }
        try await engine.waitUntilReady(timeout: settings.connectTimeout)

        state = .scanning
        let service = CBUUID(string: settings.serviceUUID)
        let char = CBUUID(string: settings.colorCharUUID)
        try await engine.connect(
            serviceUUID: service,
            nameMatch: settings.wandNameMatch,
            charUUID: char,
            scanTimeout: settings.scanTimeout,
            connectTimeout: settings.connectTimeout
        )
        state = .connecting

        if settings.wakeOnConnect {
            engine.startNotifications()
            try? await writeRaw(settings.packetFormat.build(.white))
        }
        state = .connected
    }

    private func writeColor(_ rgb: RGB) async throws {
        try await writeRaw(settings.packetFormat.build(rgb))
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
