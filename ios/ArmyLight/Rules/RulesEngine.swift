//
//  RulesEngine.swift
//  ARMY Light
//
//  Holds the rule list (persisted as JSON in UserDefaults) and drives the
//  idle/alert-hold behavior against the WandController. All foreground:
//  firing a rule sets the wand to the alert color, holds for `holdSeconds`,
//  then returns it to the idle/resting color.
//

import Foundation
import Observation

@MainActor
@Observable
final class RulesEngine {
    private(set) var rules: [ColorRule]
    /// The rule currently holding an alert color, if any.
    private(set) var activeRuleID: UUID?

    private let wand: WandController
    private let settings: AppSettings
    private let defaults: UserDefaults
    private var holdTask: Task<Void, Never>?

    private static let storageKey = "colorRules"

    init(wand: WandController, settings: AppSettings, defaults: UserDefaults = .standard) {
        self.wand = wand
        self.settings = settings
        self.defaults = defaults
        if let data = defaults.data(forKey: Self.storageKey),
           let saved = try? JSONDecoder().decode([ColorRule].self, from: data) {
            self.rules = saved
        } else {
            self.rules = ColorRule.starter
        }
    }

    // MARK: - Rule list editing

    func add(_ rule: ColorRule) { rules.append(rule); persist() }

    func update(_ rule: ColorRule) {
        if let i = rules.firstIndex(where: { $0.id == rule.id }) { rules[i] = rule; persist() }
    }

    func remove(at offsets: IndexSet) { rules.remove(atOffsets: offsets); persist() }

    func move(from source: IndexSet, to destination: Int) {
        rules.move(fromOffsets: source, toOffset: destination)
        persist()
    }

    private func persist() {
        if let data = try? JSONEncoder().encode(rules) {
            defaults.set(data, forKey: Self.storageKey)
        }
    }

    // MARK: - Behavior

    /// Set the wand to the resting/idle color now and clear any active hold.
    func goIdle() {
        holdTask?.cancel()
        holdTask = nil
        activeRuleID = nil
        wand.setColor(settings.idleColor)
    }

    /// Fire a rule: show its alert color, hold for `holdSeconds`, then return to
    /// idle. A new fire supersedes any in-progress hold.
    func fire(_ rule: ColorRule) {
        guard rule.enabled else { return }
        holdTask?.cancel()
        activeRuleID = rule.id
        wand.setColor(rule.color)

        let hold = rule.holdSeconds
        holdTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: UInt64(hold * 1_000_000_000))
            guard !Task.isCancelled, let self else { return }
            // Only return to idle if this rule is still the active one.
            if self.activeRuleID == rule.id {
                self.activeRuleID = nil
                self.wand.setColor(self.settings.idleColor)
            }
        }
    }
}
