//
//  Packets.swift
//  ARMY Light
//
//  Packet-format registry — a Swift port of the Python `army_light/packets.py`,
//  which remains the protocol source-of-truth. The wand's encoding is pluggable
//  so we can switch formats via Settings without code edits. `fanlight` is the
//  verified ARMY Bomb / Fanlight-family format; the others are generic fallbacks.
//

import Foundation

/// An RGB triple, components clamped 0...255.
struct RGB: Equatable, Hashable, Codable {
    var r: UInt8
    var g: UInt8
    var b: UInt8

    init(_ r: Int, _ g: Int, _ b: Int) {
        self.r = UInt8(clamping: r)
        self.g = UInt8(clamping: g)
        self.b = UInt8(clamping: b)
    }

    init(r: UInt8, g: UInt8, b: UInt8) {
        self.r = r; self.g = g; self.b = b
    }

    static let off = RGB(0, 0, 0)
    static let white = RGB(255, 255, 255)
}

enum PacketFormat: String, CaseIterable, Codable {
    case fanlight
    case triones
    case elkBledom = "elk_bledom"
    case rawRGB = "raw_rgb"

    /// Build the on-wire color packet for this format.
    func build(_ rgb: RGB) -> Data {
        let r = Int(rgb.r), g = Int(rgb.g), b = Int(rgb.b)
        switch self {
        case .fanlight:
            // BTS ARMY Bomb / Fanlight family:
            //   01 01 0B 00 00 RR GG BB 00 00 CK
            //   CK = (sum of bytes[2..9]) & 0xFF == (0x0B + R + G + B) & 0xFF
            let body: [Int] = [0x0B, 0x00, 0x00, r, g, b, 0x00, 0x00]
            let checksum = body.reduce(0, +) & 0xFF
            return Data(([0x01, 0x01] + body + [checksum]).map { UInt8($0) })
        case .triones:
            // Common "Triones"/"magic" bulbs: 56 RR GG BB 00 F0 AA
            return Data([0x56, rgb.r, rgb.g, rgb.b, 0x00, 0xF0, 0xAA])
        case .elkBledom:
            // ELK-BLEDOM strips: 7E 00 05 03 RR GG BB 00 EF
            return Data([0x7E, 0x00, 0x05, 0x03, rgb.r, rgb.g, rgb.b, 0x00, 0xEF])
        case .rawRGB:
            // Bare three-byte RGB, no header/checksum.
            return Data([rgb.r, rgb.g, rgb.b])
        }
    }
}

/// Non-color Fanlight query packets (01 01 06 50 XX CK, CK = byte2+byte3+byte4).
/// Handy for eliciting a notification response from the wand.
enum Query {
    static let battery = Data([0x01, 0x01, 0x06, 0x50, 0x07, 0x5D])
    static let firmware = Data([0x01, 0x01, 0x06, 0x50, 0x03, 0x59])
    static let hardware = Data([0x01, 0x01, 0x06, 0x50, 0x04, 0x5A])
}
