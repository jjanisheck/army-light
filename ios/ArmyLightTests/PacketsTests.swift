//
//  PacketsTests.swift
//  ARMY LightTests
//
//  Mirrors the Python tests for packet bytes/checksum — the protocol must match
//  the verified Fanlight encoding exactly.
//

import XCTest
@testable import ArmyLight

final class PacketsTests: XCTestCase {
    private func hex(_ data: Data) -> String {
        data.map { String(format: "%02x", $0) }.joined(separator: " ")
    }

    func testFanlightRed() {
        // 01 01 0B 00 00 FF 00 00 00 00 CK, CK = (0x0B + 0xFF) & 0xFF = 0x0A
        let packet = PacketFormat.fanlight.build(RGB(255, 0, 0))
        XCTAssertEqual(hex(packet), "01 01 0b 00 00 ff 00 00 00 00 0a")
    }

    func testFanlightChecksumIsLowByteOfSum() {
        for rgb in [RGB(255, 255, 255), RGB(160, 0, 255), RGB(0, 200, 255), RGB(1, 2, 3)] {
            let packet = [UInt8](PacketFormat.fanlight.build(rgb))
            XCTAssertEqual(packet.count, 11)
            let expected = (0x0B + Int(rgb.r) + Int(rgb.g) + Int(rgb.b)) & 0xFF
            XCTAssertEqual(Int(packet.last!), expected, "checksum mismatch for \(rgb)")
            // Checksum equals the low byte of the sum of bytes[2..9].
            let body = packet[2..<10].reduce(0) { $0 + Int($1) }
            XCTAssertEqual(Int(packet.last!), body & 0xFF)
        }
    }

    func testFanlightOff() {
        let packet = PacketFormat.fanlight.build(.off)
        XCTAssertEqual(hex(packet), "01 01 0b 00 00 00 00 00 00 00 0b")
    }

    func testOtherFormats() {
        XCTAssertEqual(hex(PacketFormat.triones.build(RGB(10, 20, 30))), "56 0a 14 1e 00 f0 aa")
        XCTAssertEqual(hex(PacketFormat.elkBledom.build(RGB(10, 20, 30))), "7e 00 05 03 0a 14 1e 00 ef")
        XCTAssertEqual(hex(PacketFormat.rawRGB.build(RGB(10, 20, 30))), "0a 14 1e")
    }

    func testFormatRawValuesMatchPython() {
        XCTAssertEqual(PacketFormat.btsV4.rawValue, "bts_v4")
        XCTAssertEqual(PacketFormat.fanlight.rawValue, "fanlight")
        XCTAssertEqual(PacketFormat.elkBledom.rawValue, "elk_bledom")
        XCTAssertEqual(PacketFormat.rawRGB.rawValue, "raw_rgb")
    }

    // MARK: - BTS Ver. 4 (verified on a real BTS_V4 LS unit, 2026-06-03)

    func testBtsV4ExactBytes() {
        // 4 bytes RR GG BB TT — no header, no checksum. TT = fade (10ms units).
        XCTAssertEqual(hex(PacketFormat.btsV4.build(RGB(255, 0, 0))), "ff 00 00 00")
        XCTAssertEqual(hex(PacketFormat.btsV4.build(RGB(0, 255, 0))), "00 ff 00 00")
        XCTAssertEqual(hex(PacketFormat.btsV4.build(.white)), "ff ff ff 00")
        XCTAssertEqual(hex(PacketFormat.btsV4.build(.off)), "00 00 00 00")
    }

    func testBtsV4TransitionByte() {
        XCTAssertEqual(hex(PacketFormat.btsV4.build(RGB(255, 0, 0), transition: 120)), "ff 00 00 78")
        // Other formats ignore the transition parameter.
        XCTAssertEqual(hex(PacketFormat.fanlight.build(RGB(255, 0, 0), transition: 120)),
                       "01 01 0b 00 00 ff 00 00 00 00 0a")
    }

    func testBtsV4CommitByte() {
        XCTAssertEqual(hex(Packets.btsV4Commit), "01")
    }
}
