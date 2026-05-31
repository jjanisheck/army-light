//
//  SettingsView.swift
//  ARMY Light
//
//  Idle color, connection behavior, and the advanced BLE protocol knobs (the
//  iOS equivalent of the macOS config.json the discovery CLI writes).
//

import SwiftUI

struct SettingsView: View {
    @Bindable var settings: AppSettings
    @Bindable var wand: WandController
    @State private var idleSwiftColor: Color

    init(settings: AppSettings, wand: WandController) {
        self.settings = settings
        self.wand = wand
        _idleSwiftColor = State(initialValue: settings.idleColor.color)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Connection") {
                    LabeledContent("Status", value: wand.statusText)
                    Button("Disconnect") { wand.disconnect() }
                        .disabled(!wand.isConnected)
                }

                Section {
                    ColorPicker("Idle color", selection: $idleSwiftColor, supportsOpacity: false)
                        .onChange(of: idleSwiftColor) { _, newValue in
                            settings.idleColor = RGB(color: newValue)
                        }
                    Button("Set wand to idle now") {
                        wand.setColor(settings.idleColor)
                    }
                } header: {
                    Text("Resting color")
                } footer: {
                    Text("The color the wand returns to after a rule's hold expires.")
                }

                Section {
                    Toggle("Send wake packet on connect", isOn: $settings.wakeOnConnect)
                    Toggle("Write with response", isOn: $settings.writeWithResponse)
                } header: {
                    Text("Behavior")
                } footer: {
                    Text("The official app writes without a response and sends a white wake packet right after connecting. Change these only if a color tap does nothing.")
                }

                Section("Protocol (advanced)") {
                    Picker("Packet format", selection: $settings.packetFormat) {
                        ForEach(PacketFormat.allCases, id: \.self) { fmt in
                            Text(fmt.rawValue).tag(fmt)
                        }
                    }
                    LabeledContent("Service UUID") {
                        Text(settings.serviceUUID).font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                    LabeledContent("Write char") {
                        Text(settings.colorCharUUID).font(.caption.monospaced()).foregroundStyle(.secondary)
                    }
                    LabeledContent("Name match", value: settings.wandNameMatch)
                }
            }
            .navigationTitle("Settings")
        }
    }
}
