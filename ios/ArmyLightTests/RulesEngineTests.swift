//
//  RulesEngineTests.swift
//  ARMY LightTests
//
//  Covers rule-list editing, persistence, and the active-rule bookkeeping that
//  drives the idle/alert hold. BLE itself is exercised separately on device.
//

import XCTest
@testable import ArmyLight

@MainActor
final class RulesEngineTests: XCTestCase {
    private func makeDefaults() -> UserDefaults {
        let suite = "test-\(UUID().uuidString)"
        let d = UserDefaults(suiteName: suite)!
        d.removePersistentDomain(forName: suite)
        return d
    }

    private func makeEngine(_ defaults: UserDefaults) -> RulesEngine {
        let settings = AppSettings(defaults: defaults)
        let wand = WandController(settings: settings)
        return RulesEngine(wand: wand, settings: settings, defaults: defaults)
    }

    func testStartsWithStarterRules() {
        let engine = makeEngine(makeDefaults())
        XCTAssertEqual(engine.rules.count, ColorRule.starter.count)
    }

    func testAddRemovePersists() {
        let defaults = makeDefaults()
        let engine = makeEngine(defaults)
        let before = engine.rules.count
        engine.add(ColorRule(name: "Test", color: RGB(1, 2, 3), holdSeconds: 3))
        XCTAssertEqual(engine.rules.count, before + 1)

        // A fresh engine over the same defaults sees the saved rule.
        let reloaded = makeEngine(defaults)
        XCTAssertEqual(reloaded.rules.count, before + 1)
        XCTAssertTrue(reloaded.rules.contains { $0.name == "Test" })
    }

    func testGoIdleClearsActiveRule() {
        let engine = makeEngine(makeDefaults())
        engine.fire(ColorRule(name: "x", color: RGB(255, 0, 0), holdSeconds: 30))
        XCTAssertNotNil(engine.activeRuleID)
        engine.goIdle()
        XCTAssertNil(engine.activeRuleID)
    }

    func testFireDisabledRuleIsNoOp() {
        let engine = makeEngine(makeDefaults())
        engine.fire(ColorRule(name: "x", color: RGB(255, 0, 0), holdSeconds: 30, enabled: false))
        XCTAssertNil(engine.activeRuleID)
    }

    func testHoldReturnsToIdle() async throws {
        let engine = makeEngine(makeDefaults())
        engine.fire(ColorRule(name: "x", color: RGB(255, 0, 0), holdSeconds: 0.2))
        XCTAssertNotNil(engine.activeRuleID)
        try await Task.sleep(nanoseconds: 500_000_000)
        XCTAssertNil(engine.activeRuleID, "hold should clear the active rule and return to idle")
    }
}
