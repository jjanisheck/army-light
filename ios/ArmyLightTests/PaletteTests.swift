//
//  PaletteTests.swift
//  ARMY LightTests
//
//  Mirrors the Python color-parsing tests.
//

import XCTest
@testable import ArmyLight

final class PaletteTests: XCTestCase {
    func testNamedColor() {
        XCTAssertEqual(Palette.parse("red"), RGB(255, 0, 0))
        XCTAssertEqual(Palette.parse("  Purple "), RGB(160, 0, 255))
        XCTAssertEqual(Palette.parse("OFF"), RGB(0, 0, 0))
    }

    func testHex() {
        XCTAssertEqual(Palette.parse("#ff0000"), RGB(255, 0, 0))
        XCTAssertEqual(Palette.parse("#A000FF"), RGB(160, 0, 255))
    }

    func testCommaSeparated() {
        XCTAssertEqual(Palette.parse("255,0,0"), RGB(255, 0, 0))
        XCTAssertEqual(Palette.parse("0, 200, 255"), RGB(0, 200, 255))
    }

    func testRejectsBadInput() {
        XCTAssertNil(Palette.parse("not-a-color"))
        XCTAssertNil(Palette.parse("300,0,0"))   // out of range
        XCTAssertNil(Palette.parse("#fff"))      // wrong length
        XCTAssertNil(Palette.parse("1,2"))       // too few
    }

    func testPaletteMatchesMacOSOrder() {
        XCTAssertEqual(Palette.all.map(\.label),
                       ["Red", "Orange", "Yellow", "Green", "Cyan", "Blue", "Purple", "Pink", "White", "Off"])
    }

    func testHexString() {
        XCTAssertEqual(RGB(160, 0, 255).hexString, "#A000FF")
    }
}
