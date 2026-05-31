//
//  RulesView.swift
//  ARMY Light
//
//  Manage foreground rules and simulate events. Tapping "Simulate" fires a rule:
//  the wand holds the alert color, then returns to idle after the hold interval.
//

import SwiftUI

struct RulesView: View {
    @Bindable var engine: RulesEngine
    @State private var editing: ColorRule?
    @State private var showingAdd = false

    var body: some View {
        NavigationStack {
            List {
                Section {
                    Button {
                        engine.goIdle()
                    } label: {
                        Label("Return to idle now", systemImage: "moon.zzz.fill")
                    }
                } footer: {
                    Text("Rules run while the app is open. Firing a rule holds its color, then returns the wand to the idle color set in Settings.")
                }

                Section("Rules") {
                    ForEach(engine.rules) { rule in
                        RuleRow(
                            rule: rule,
                            isActive: engine.activeRuleID == rule.id,
                            onFire: { engine.fire(rule) },
                            onEdit: { editing = rule }
                        )
                    }
                    .onDelete { engine.remove(at: $0) }
                    .onMove { engine.move(from: $0, to: $1) }
                }
            }
            .navigationTitle("Rules")
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { EditButton() }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { showingAdd = true } label: { Image(systemName: "plus") }
                }
            }
            .sheet(isPresented: $showingAdd) {
                RuleEditor(rule: ColorRule(name: "New rule", color: RGB(160, 0, 255))) {
                    engine.add($0)
                }
            }
            .sheet(item: $editing) { rule in
                RuleEditor(rule: rule) { engine.update($0) }
            }
        }
    }
}

private struct RuleRow: View {
    let rule: ColorRule
    let isActive: Bool
    let onFire: () -> Void
    let onEdit: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 6)
                .fill(rule.color.color)
                .frame(width: 28, height: 28)
                .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
            VStack(alignment: .leading) {
                Text(rule.name)
                Text("Hold \(rule.holdSeconds, format: .number.precision(.fractionLength(0...1)))s")
                    .font(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            if isActive {
                Image(systemName: "dot.radiowaves.left.and.right")
                    .foregroundStyle(.tint)
            }
            Button("Simulate", action: onFire)
                .buttonStyle(.bordered)
                .disabled(!rule.enabled)
        }
        .contentShape(Rectangle())
        .onTapGesture(perform: onEdit)
    }
}

private struct RuleEditor: View {
    @Environment(\.dismiss) private var dismiss
    @State private var draft: ColorRule
    @State private var swiftColor: Color
    private let onSave: (ColorRule) -> Void

    init(rule: ColorRule, onSave: @escaping (ColorRule) -> Void) {
        _draft = State(initialValue: rule)
        _swiftColor = State(initialValue: rule.color.color)
        self.onSave = onSave
    }

    var body: some View {
        NavigationStack {
            Form {
                TextField("Name", text: $draft.name)
                Toggle("Enabled", isOn: $draft.enabled)
                ColorPicker("Alert color", selection: $swiftColor, supportsOpacity: false)
                VStack(alignment: .leading) {
                    Text("Hold \(draft.holdSeconds, format: .number.precision(.fractionLength(0...1)))s")
                    Slider(value: $draft.holdSeconds, in: 1...60, step: 1)
                }
            }
            .navigationTitle(draft.name.isEmpty ? "Rule" : draft.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        draft.color = RGB(color: swiftColor)
                        onSave(draft)
                        dismiss()
                    }
                }
            }
        }
    }
}
