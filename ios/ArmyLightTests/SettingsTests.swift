//
//  SettingsTests.swift
//  ARMY LightTests
//
//  Defaults must match the protocol verified on a real BTS ARMY Bomb Ver. 4
//  (2026-06-03), and stored pre-V4 settings must migrate forward.
//

import XCTest
@testable import ArmyLight

final class SettingsTests: XCTestCase {
    private var defaults: UserDefaults!

    override func setUp() {
        super.setUp()
        defaults = UserDefaults(suiteName: "SettingsTests")!
        defaults.removePersistentDomain(forName: "SettingsTests")
    }

    func testDefaultsMatchVerifiedV4Protocol() {
        let s = AppSettings(defaults: defaults)
        XCTAssertEqual(s.wandNameMatch, "BTS")
        XCTAssertEqual(s.serviceUUID.lowercased(), "0001fe01-0000-1000-8000-00805f9800c4")
        XCTAssertEqual(s.colorCharUUID.lowercased(), "0001ff01-0000-1000-8000-00805f9800c4")
        XCTAssertEqual(s.commitCharUUID.lowercased(), "0001ff13-0000-1000-8000-00805f9800c4")
        XCTAssertEqual(s.packetFormat, .btsV4)
        // ff01 only accepts with-response writes; the wand silently drops the rest.
        XCTAssertTrue(s.writeWithResponse)
        // No white wake for V4 — it would flash white before every color.
        XCTAssertFalse(s.wakeOnConnect)
    }

    func testStoredFanlightSettingsMigrateToV4() {
        // Simulate an install that persisted the old Fanlight defaults.
        defaults.set("00010203-0405-0607-0809-0a0b0c0d1911", forKey: "serviceUUID")
        defaults.set("00010203-0405-0607-0809-0a0b0c0d2b19", forKey: "colorCharUUID")
        defaults.set("fanlight", forKey: "packetFormat")
        defaults.set("ARMY", forKey: "wandNameMatch")
        defaults.set(false, forKey: "writeWithResponse")
        let s = AppSettings(defaults: defaults)
        XCTAssertEqual(s.packetFormat, .btsV4)
        XCTAssertEqual(s.wandNameMatch, "BTS")
        XCTAssertEqual(s.colorCharUUID.lowercased(), "0001ff01-0000-1000-8000-00805f9800c4")
        XCTAssertTrue(s.writeWithResponse)
    }

    func testUserCustomizationsSurviveAfterMigration() {
        // After the migration has run once, later custom values stick.
        _ = AppSettings(defaults: defaults)
        defaults.set("MYWAND", forKey: "wandNameMatch")
        let s = AppSettings(defaults: defaults)
        XCTAssertEqual(s.wandNameMatch, "MYWAND")
    }
}
