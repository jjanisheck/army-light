//
//  Settings.swift
//  ARMY Light
//
//  Persistent settings — a Swift port of the Python `army_light/config.py`
//  Settings dataclass, backed by UserDefaults instead of a JSON file. Defaults
//  are the values verified end-to-end on a real BTS ARMY Bomb Ver. 4
//  ("BTS_V4 LS", 2026-06-03). A protocol-version stamp migrates installs that
//  stored the older Fanlight guesses.
//

import Foundation
import Observation

@Observable
final class AppSettings {
    /// Bumped when verified protocol defaults change; stored values from an
    /// older protocol generation are overwritten on first launch.
    static let protocolVersion = 2  // 1 = Fanlight guesses, 2 = verified V4

    // How to find the wand. The V4 advertises as "BTS_V4 LS" with NO service
    // UUIDs in the advertisement, so the name substring is the working matcher;
    // the service UUID still helps retrieve already-connected peripherals.
    var serviceUUID: String {
        didSet { defaults.set(serviceUUID, forKey: "serviceUUID") }
    }
    var wandNameMatch: String {
        didSet { defaults.set(wandNameMatch, forKey: "wandNameMatch") }
    }

    // The write target + encoding (V4: 4-byte color to ff01, with-response).
    var colorCharUUID: String {
        didSet { defaults.set(colorCharUUID, forKey: "colorCharUUID") }
    }
    /// The V4 latch char (ff13): written once per fresh connection to apply the
    /// color and leave the pairing animation; the wand then restarts its session.
    /// Empty string disables the latch dance (non-V4 formats).
    var commitCharUUID: String {
        didSet { defaults.set(commitCharUUID, forKey: "commitCharUUID") }
    }
    var packetFormat: PacketFormat {
        didSet { defaults.set(packetFormat.rawValue, forKey: "packetFormat") }
    }
    /// ff01 accepts with-response writes ONLY — the stack silently drops
    /// no-response writes to it (no error, no color change).
    var writeWithResponse: Bool {
        didSet { defaults.set(writeWithResponse, forKey: "writeWithResponse") }
    }

    /// Send a white "wake" packet right after connect (Fanlight-family
    /// behaviour; keep off for V4 — it would flash white before every color).
    var wakeOnConnect: Bool {
        didSet { defaults.set(wakeOnConnect, forKey: "wakeOnConnect") }
    }

    // Behaviour.
    var scanTimeout: TimeInterval {
        didSet { defaults.set(scanTimeout, forKey: "scanTimeout") }
    }
    var connectTimeout: TimeInterval {
        didSet { defaults.set(connectTimeout, forKey: "connectTimeout") }
    }
    /// The resting color the wand returns to when no alert is active.
    var idleColor: RGB {
        didSet { defaults.set(idleColor.encoded, forKey: "idleColor") }
    }

    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        // Migrate installs that persisted an older protocol generation: wipe the
        // protocol keys so the verified V4 defaults below take effect.
        if defaults.integer(forKey: "protocolVersion") < Self.protocolVersion {
            for key in ["serviceUUID", "wandNameMatch", "colorCharUUID",
                        "commitCharUUID", "packetFormat", "writeWithResponse",
                        "wakeOnConnect"] {
                defaults.removeObject(forKey: key)
            }
            defaults.set(Self.protocolVersion, forKey: "protocolVersion")
        }
        self.serviceUUID = defaults.string(forKey: "serviceUUID")
            ?? "0001fe01-0000-1000-8000-00805f9800c4"
        self.wandNameMatch = defaults.string(forKey: "wandNameMatch") ?? "BTS"
        self.colorCharUUID = defaults.string(forKey: "colorCharUUID")
            ?? "0001ff01-0000-1000-8000-00805f9800c4"
        self.commitCharUUID = defaults.string(forKey: "commitCharUUID")
            ?? "0001ff13-0000-1000-8000-00805f9800c4"
        self.packetFormat = (defaults.string(forKey: "packetFormat")
            .flatMap(PacketFormat.init(rawValue:))) ?? .btsV4
        self.writeWithResponse = defaults.object(forKey: "writeWithResponse") as? Bool ?? true
        self.wakeOnConnect = defaults.object(forKey: "wakeOnConnect") as? Bool ?? false
        self.scanTimeout = defaults.object(forKey: "scanTimeout") as? TimeInterval ?? 8.0
        self.connectTimeout = defaults.object(forKey: "connectTimeout") as? TimeInterval ?? 12.0
        self.idleColor = (defaults.string(forKey: "idleColor").flatMap(RGB.init(encoded:))) ?? .off
    }
}

// Compact "r,g,b" encoding for UserDefaults storage of an RGB.
private extension RGB {
    var encoded: String { "\(r),\(g),\(b)" }

    init?(encoded: String) {
        let parts = encoded.split(separator: ",").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        self.init(parts[0], parts[1], parts[2])
    }
}
