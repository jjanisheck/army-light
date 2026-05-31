//
//  ControlView.swift
//  ARMY Light
//
//  The main control surface: a tap-to-set palette grid plus a custom color
//  picker. Mirrors the macOS menu's palette, top to bottom.
//

import SwiftUI

struct ControlView: View {
    @Bindable var wand: WandController
    @State private var customColor: Color = .purple

    private let columns = [GridItem(.adaptive(minimum: 96), spacing: 14)]

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 24) {
                    statusCard

                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(Palette.all) { item in
                            ColorTile(item: item) { wand.setColor(item.rgb) }
                        }
                    }

                    customPicker
                }
                .padding()
            }
            .navigationTitle("ARMY Light")
        }
    }

    private var statusCard: some View {
        HStack(spacing: 12) {
            Circle()
                .fill(statusColor)
                .frame(width: 12, height: 12)
            Text(wand.statusText)
                .font(.callout)
                .foregroundStyle(.secondary)
            Spacer()
            if let rgb = wand.lastRGB {
                RoundedRectangle(cornerRadius: 6)
                    .fill(rgb.color)
                    .frame(width: 28, height: 20)
                    .overlay(RoundedRectangle(cornerRadius: 6).stroke(.quaternary))
            }
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }

    private var statusColor: Color {
        switch wand.state {
        case .connected: return .green
        case .scanning, .connecting: return .yellow
        case .error: return .red
        case .idle: return .gray
        }
    }

    private var customPicker: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Custom color").font(.headline)
            HStack(spacing: 16) {
                ColorPicker("Pick a color", selection: $customColor, supportsOpacity: false)
                    .labelsHidden()
                Button {
                    wand.setColor(RGB(color: customColor))
                } label: {
                    Label("Send", systemImage: "paperplane.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
            }
        }
        .padding()
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 12))
    }
}

private struct ColorTile: View {
    let item: PaletteColor
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            VStack(spacing: 8) {
                RoundedRectangle(cornerRadius: 12)
                    .fill(item.rgb.color)
                    .frame(height: 64)
                    .overlay(
                        RoundedRectangle(cornerRadius: 12)
                            .stroke(.quaternary, lineWidth: item.label == "Off" ? 1 : 0)
                    )
                    .shadow(color: item.rgb.color.opacity(0.4), radius: 6, y: 2)
                Text(item.label)
                    .font(.caption)
                    .foregroundStyle(.primary)
            }
        }
        .buttonStyle(.plain)
    }
}
