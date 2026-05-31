//
//  Settings.swift
//  ARMY Light
//
//  Persistent settings — a Swift port of the Python `army_light/config.py`
//  Settings dataclass, backed by UserDefaults instead of a JSON file. Defaults
//  are the values verified against the Fanlight family.
//

import Foundation
import Observation

@Observable
final class AppSettings {
    // How to find the wand. The Fanlight service UUID is the robust matcher on
    // Apple platforms (CoreBluetooth resolves by service, not hardware MAC).
    var serviceUUID: String {
        didSet { defaults.set(serviceUUID, forKey: "serviceUUID") }
    }
    var wandNameMatch: String {
        didSet { defaults.set(wandNameMatch, forKey: "wandNameMatch") }
    }

    // The write target + encoding.
    var colorCharUUID: String {
        didSet { defaults.set(colorCharUUID, forKey: "colorCharUUID") }
    }
    var packetFormat: PacketFormat {
        didSet { defaults.set(packetFormat.rawValue, forKey: "packetFormat") }
    }
    /// The official app writes without response; we retry with-response on failure.
    var writeWithResponse: Bool {
        didSet { defaults.set(writeWithResponse, forKey: "writeWithResponse") }
    }

    /// Mimic the official app: send a white "wake" packet right after connect and
    /// subscribe to notifications on the write char to keep the link stable.
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
        self.serviceUUID = defaults.string(forKey: "serviceUUID")
            ?? "00010203-0405-0607-0809-0a0b0c0d1911"
        self.wandNameMatch = defaults.string(forKey: "wandNameMatch") ?? "ARMY"
        self.colorCharUUID = defaults.string(forKey: "colorCharUUID")
            ?? "00010203-0405-0607-0809-0a0b0c0d2b19"
        self.packetFormat = (defaults.string(forKey: "packetFormat")
            .flatMap(PacketFormat.init(rawValue:))) ?? .fanlight
        self.writeWithResponse = defaults.object(forKey: "writeWithResponse") as? Bool ?? false
        self.wakeOnConnect = defaults.object(forKey: "wakeOnConnect") as? Bool ?? true
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
