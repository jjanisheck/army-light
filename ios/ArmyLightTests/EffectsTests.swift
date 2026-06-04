//
//  EffectsTests.swift
//  ARMY LightTests
//
//  Mirrors the Python tests/test_effects.py — effects are iterators of
//  (rgb, transition, delay) steps, pure logic, so we sample the first few.
//

import XCTest
@testable import ArmyLight

final class EffectsTests: XCTestCase {
    private func take(_ it: AnyIterator<EffectStep>, _ n: Int) -> [EffectStep] {
        (0..<n).compactMap { _ in it.next() }
    }

    func testBlinkAlternatesColorAndOff() {
        let steps = take(Effects.blink(RGB(255, 0, 0)), 4)
        XCTAssertEqual(steps.map(\.rgb), [RGB(255, 0, 0), .off, RGB(255, 0, 0), .off])
        XCTAssertTrue(steps.allSatisfy { $0.transition == 0 })   // hard cuts
        XCTAssertTrue(steps.allSatisfy { (0.2...2.0).contains($0.delay) })
    }

    func testBreathFadesColorAndOff() {
        let steps = take(Effects.breath(RGB(0, 0, 255)), 4)
        XCTAssertEqual(steps[0].rgb, RGB(0, 0, 255))
        XCTAssertEqual(steps[1].rgb, .off)
        for s in steps {
            XCTAssertGreaterThan(s.transition, 0)               // smooth
            XCTAssertGreaterThanOrEqual(s.delay, Double(s.transition) / 100.0)
        }
    }

    func testStrobeIsFastHardFlashing() {
        let steps = take(Effects.strobe(RGB(255, 0, 0)), 4)
        XCTAssertEqual(steps[0].rgb, RGB(255, 0, 0))
        XCTAssertEqual(steps[1].rgb, .off)
        XCTAssertTrue(steps.allSatisfy { $0.transition == 0 && (0.05...0.3).contains($0.delay) })
    }

    func testDuoFadeAlternatesTheTwoColorsSmoothly() {
        let a = RGB(130, 60, 255), b = RGB(255, 40, 150)
        let steps = take(Effects.duoFade(a, b), 4)
        XCTAssertEqual(steps.map(\.rgb), [a, b, a, b])
        XCTAssertTrue(steps.allSatisfy { $0.transition > 0 })
    }

    func testCycleWalksTheHueWheelAndRepeats() {
        let steps = take(Effects.cycle(), 48)
        let first = steps[0..<24].map(\.rgb), second = steps[24..<48].map(\.rgb)
        XCTAssertEqual(Set(first).count, 24)                    // all distinct hues
        XCTAssertEqual(first, second)                           // loops exactly
        XCTAssertTrue(first.contains { $0.r > 200 && $0.b < 60 })  // reaches reds
        XCTAssertTrue(first.contains { $0.b > 200 && $0.r < 60 })  // and blues
    }

    func testRainbowMarchesROYGBIVInOrder() {
        let steps = take(Effects.rainbow(), 14)
        XCTAssertEqual(steps.map(\.rgb), Effects.roygbiv + Effects.roygbiv)
        XCTAssertTrue(steps.allSatisfy { $0.transition > 0 })
    }

    func testGlowCycleBreathesBrightnessThroughTheHues() {
        let steps = take(Effects.glowCycle(), 24)               // 12 hues x (bright, dim)
        for i in stride(from: 0, to: 24, by: 2) {
            let bright = steps[i], dim = steps[i + 1]
            XCTAssertGreaterThanOrEqual(Int(max(bright.rgb.r, max(bright.rgb.g, bright.rgb.b))), 200)
            let dimMax = Int(max(dim.rgb.r, max(dim.rgb.g, dim.rgb.b)))
            XCTAssertTrue((1...40).contains(dimMax), "dim step should be low but not off")
            XCTAssertGreaterThan(bright.transition, 0)
            XCTAssertGreaterThan(dim.transition, 0)
        }
        let brights = stride(from: 0, to: 24, by: 2).map { steps[$0].rgb }
        XCTAssertEqual(Set(brights).count, brights.count)       // hue advances
    }

    func testCandleFlickersWarmAndGentle() {
        let steps = take(Effects.candle(), 40)
        for s in steps {
            XCTAssertTrue(s.rgb.r > s.rgb.g && s.rgb.g > s.rgb.b, "warm ordering")
            XCTAssertLessThanOrEqual(s.transition, 30)
            XCTAssertTrue((0.05...0.5).contains(s.delay))
        }
        XCTAssertGreaterThan(Set(steps.map(\.rgb.r)).count, 3)  // actually flickers
    }

    func testPartyJumpsBetweenDistinctColors() {
        let steps = take(Effects.party(), 40)
        XCTAssertGreaterThan(Set(steps.map(\.rgb)).count, 10)
        for (a, b) in zip(steps, steps.dropFirst()) {
            XCTAssertNotEqual(a.rgb, b.rgb)                     // always moves
        }
        let transitions = Set(steps.map(\.transition))
        XCTAssertTrue(transitions.contains(0) && transitions.contains { $0 > 0 })
    }

    func testJungleStaysInPalette() {
        let steps = take(Effects.jungle(), 40)
        XCTAssertTrue(Set(steps.map(\.rgb)).isSubset(of: Set(Effects.jungleColors)))
        XCTAssertGreaterThanOrEqual(Set(steps.map(\.rgb)).count, 4)
    }

    func testIceShimmersAndSparklesWhite() {
        let steps = take(Effects.ice(), 16)
        XCTAssertTrue(Set(steps.map(\.rgb)).isSubset(of: Set(Effects.iceColors)))
        XCTAssertTrue(steps.map(\.rgb).contains(.white))        // guaranteed sparkle
    }

    func testRegistryLabelsAndArity() {
        let expected: [(String, Int)] = [
            ("Blink", 1), ("Breath", 1), ("Strobe", 1), ("Duo Fade", 2),
            ("Color Cycle", 0), ("Rainbow", 0), ("Glow Cycle", 0),
            ("Candle", 0), ("Party", 0), ("Jungle", 0), ("Ice", 0),
        ]
        XCTAssertEqual(Effects.all.map { ($0.label, $0.arity) }.map { "\($0) \($1)" },
                       expected.map { "\($0.0) \($0.1)" })
        // Every factory produces a valid first step at its arity.
        for e in Effects.all {
            let colors = [RGB(255, 0, 0), RGB(0, 0, 255)].prefix(e.arity)
            let step = e.make(Array(colors)).next()
            XCTAssertNotNil(step, e.label)
            XCTAssertGreaterThan(step!.delay, 0, e.label)
        }
    }

    func testLEDTrueSaturatesScreenPastels() {
        XCTAssertEqual(RGB(255, 77, 77).ledTrue, RGB(255, 0, 0))      // soft red → pure
        XCTAssertEqual(RGB(255, 255, 255).ledTrue, .white)             // white stays
        XCTAssertEqual(RGB(27, 27, 32).ledTrue, RGB(27, 27, 32))       // near-black stays
        let jin = RGB(255, 143, 200).ledTrue                           // pink stays pink, vivid
        XCTAssertEqual(jin.r, 255)
        XCTAssertEqual(jin.g, 0)
        XCTAssertGreaterThan(jin.b, 100)
    }
}
