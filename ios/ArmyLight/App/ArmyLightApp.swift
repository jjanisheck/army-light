//
//  ArmyLightApp.swift
//  ARMY Light
//
//  App entry. Owns the long-lived AppSettings, WandController, and RulesEngine,
//  and hosts the three-tab UI.
//

import SwiftUI

@main
struct ArmyLightApp: App {
    @State private var settings: AppSettings
    @State private var wand: WandController
    @State private var rules: RulesEngine

    init() {
        let settings = AppSettings()
        let wand = WandController(settings: settings)
        _settings = State(initialValue: settings)
        _wand = State(initialValue: wand)
        _rules = State(initialValue: RulesEngine(wand: wand, settings: settings))
    }

    var body: some Scene {
        WindowGroup {
            RootView(settings: settings, wand: wand, rules: rules)
        }
    }
}

struct RootView: View {
    let settings: AppSettings
    let wand: WandController
    let rules: RulesEngine

    var body: some View {
        TabView {
            ControlView(wand: wand)
                .tabItem { Label("Control", systemImage: "wand.and.stars") }

            RulesView(engine: rules)
                .tabItem { Label("Rules", systemImage: "bell.badge") }

            SettingsView(settings: settings, wand: wand)
                .tabItem { Label("Settings", systemImage: "gearshape") }
        }
        .tint(Color(red: 160/255, green: 0, blue: 1))
    }
}
