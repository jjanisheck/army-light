//
//  ControlView.swift
//  ARMY Light
//
//  The main control surface — matches the macOS panel design (Claude Design
//  handoff): premium dark shell, glowing hero wand, a 3x7 color grid whose top
//  row is the seven members in their signature colors with initials, grouped
//  effects (Ambient / High energy), and a brightness slider. Colors are sent
//  LED-true (`.ledTrue`) so the wand shows pure hues, not screen pastels.
//

import SwiftUI

private let accent = Color(red: 200/255, green: 155/255, blue: 255/255)  // #c89bff
private let panelBG = Color(red: 18/255, green: 18/255, blue: 23/255)
private let cardBG = Color.white.opacity(0.05)
private let cardBorder = Color.white.opacity(0.08)

private let defaultEffectRGB = RGB(154, 108, 255)   // ARMY Purple fallback
private let defaultDuoRGB = RGB(255, 143, 200)      // Pink — Duo Fade's pair

private let fxGroups: [(String, [String])] = [
    ("AMBIENT", ["Breath", "Candle", "Ice", "Color Cycle", "Rainbow", "Glow Cycle"]),
    ("HIGH ENERGY", ["Blink", "Strobe", "Duo Fade", "Party", "Jungle"]),
]

struct ControlView: View {
    @Bindable var wand: WandController
    @State private var selected: RGB?
    @State private var recents: [RGB] = []      // last two picks (Duo Fade pair)
    @State private var brightness: Double = 1.0
    @State private var customColor: Color = .purple

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    header
                    HeroWand(rgb: heroRGB, glow: heroGlow)
                        .frame(maxWidth: .infinity)
                    heroMeta
                    colorsSection
                    effectsSection
                    brightnessSection
                    footer
                }
                .padding(18)
            }
            .background(panelBG.ignoresSafeArea())
            .preferredColorScheme(.dark)
            .toolbar(.hidden, for: .navigationBar)
        }
    }

    // MARK: - header

    private var header: some View {
        HStack(spacing: 11) {
            Circle()
                .fill(accent)
                .frame(width: 12, height: 12)
                .shadow(color: accent, radius: 7)
            VStack(alignment: .leading, spacing: 2) {
                Text("ARMY Light").font(.system(size: 17, weight: .bold))
                HStack(spacing: 6) {
                    Circle()
                        .fill(wand.isConnected ? Color(red: 69/255, green: 224/255, blue: 138/255)
                                               : Color(red: 1, green: 97/255, blue: 97/255))
                        .frame(width: 7, height: 7)
                        .shadow(color: wand.isConnected ? .green : .red, radius: 4)
                    Text(statusLine)
                        .font(.system(size: 12))
                        .foregroundStyle(.white.opacity(0.5))
                        .lineLimit(1)
                }
            }
            Spacer()
            Button("Reconnect") { wand.reconnect() }
                .font(.system(size: 13))
                .buttonStyle(.bordered)
                .tint(.white.opacity(0.6))
        }
    }

    private var statusLine: String {
        switch wand.state {
        case .connected: return "Connected · BTS v4"
        case .scanning: return "Searching for wand…"
        case .connecting: return "Connecting…"
        case .error: return wand.lastError ?? "Error"
        case .idle: return "Not connected — pick a color"
        }
    }

    // MARK: - hero

    private var heroRGB: RGB {
        let rgb = wand.lastRGB ?? defaultEffectRGB
        return rgb == .off ? RGB(20, 20, 24) : rgb
    }

    private var heroGlow: Double {
        wand.lastRGB == .off ? 0 : wand.brightness
    }

    private var heroMeta: some View {
        VStack(spacing: 2) {
            Text(wand.lastRGB == .off ? "Off" : (wand.currentEffect ?? "Solid color"))
                .font(.system(size: 15, weight: .semibold))
            Text("\(Int((wand.brightness * 100).rounded()))% brightness")
                .font(.system(size: 12))
                .foregroundStyle(.white.opacity(0.42))
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - colors (3 x 7: members on top)

    private var colorsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            sectionLabel("COLORS")
            let cols = Array(repeating: GridItem(.flexible(), spacing: 8), count: 7)
            LazyVGrid(columns: cols, spacing: 8) {
                ForEach(Palette.members) { m in
                    swatch(m.rgb) {
                        Text(m.name)
                            .font(.system(size: 8.5, weight: .bold))
                            .foregroundStyle(m.text.color)
                            .minimumScaleFactor(0.6)
                            .lineLimit(1)
                    }
                }
                ForEach(Array(Palette.extras.enumerated()), id: \.offset) { _, rgb in
                    swatch(rgb) { EmptyView() }
                }
            }
        }
    }

    @ViewBuilder
    private func swatch(_ rgb: RGB, @ViewBuilder label: () -> some View) -> some View {
        let isSelected = selected == rgb
        Button {
            pick(rgb)
        } label: {
            RoundedRectangle(cornerRadius: 9)
                .fill(rgb.color)
                .aspectRatio(1, contentMode: .fit)
                .overlay(label())
                .overlay(RoundedRectangle(cornerRadius: 9)
                    .stroke(isSelected ? accent : .white.opacity(0.08),
                            lineWidth: isSelected ? 2 : 1))
                .shadow(color: isSelected ? rgb.color.opacity(0.8) : .clear, radius: 7)
        }
        .buttonStyle(.plain)
    }

    private func pick(_ rgb: RGB) {
        selected = rgb
        recents.removeAll { $0 == rgb }
        recents.append(rgb)
        recents = Array(recents.suffix(2))
        wand.setColor(rgb.ledTrue)
    }

    // MARK: - effects

    private var effectsSection: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                sectionLabel("EFFECTS")
                Spacer()
                Button("Stop") { wand.stopEffect() }
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(accent)
                    .buttonStyle(.plain)
            }
            ForEach(fxGroups, id: \.0) { caption, labels in
                VStack(alignment: .leading, spacing: 7) {
                    Text(caption)
                        .font(.system(size: 10, weight: .medium))
                        .kerning(1)
                        .foregroundStyle(.white.opacity(0.32))
                    let cols = Array(repeating: GridItem(.flexible(), spacing: 8), count: 2)
                    LazyVGrid(columns: cols, spacing: 8) {
                        ForEach(labels, id: \.self) { label in
                            effectButton(label)
                        }
                    }
                }
            }
        }
    }

    private func effectButton(_ label: String) -> some View {
        let active = wand.currentEffect == label
        return Button {
            if active { wand.stopEffect() } else { startEffect(label) }
        } label: {
            HStack(spacing: 8) {
                Circle()
                    .fill(active ? accent : .white.opacity(0.45))
                    .frame(width: 8, height: 8)
                Text(label).font(.system(size: 14))
            }
            .frame(maxWidth: .infinity, minHeight: 40)
            .background(active ? Color.white.opacity(0.08) : cardBG,
                        in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10)
                .stroke(active ? accent.opacity(0.9) : cardBorder, lineWidth: 1))
        }
        .buttonStyle(.plain)
        .foregroundStyle(.white.opacity(0.9))
    }

    private func startEffect(_ label: String) {
        guard let effect = Effects.named(label) else { return }
        switch effect.arity {
        case 0:
            wand.startEffect(label)
        case 1:
            wand.startEffect(label, colors: [(selected ?? defaultEffectRGB).ledTrue])
        default:
            var pair = recents
            if pair.count < 2 {
                let base = pair.first ?? defaultEffectRGB
                pair = [base, base == defaultDuoRGB ? defaultEffectRGB : defaultDuoRGB]
            }
            wand.startEffect(label, colors: pair.map(\.ledTrue))
        }
    }

    // MARK: - brightness / footer

    private var brightnessSection: some View {
        VStack(alignment: .leading, spacing: 8) {
            sectionLabel("BRIGHTNESS")
            HStack(spacing: 10) {
                Image(systemName: "sun.min").font(.system(size: 11))
                    .foregroundStyle(.white.opacity(0.4))
                Slider(value: $brightness, in: 0.05...1.0) { editing in
                    if !editing { wand.setBrightness(brightness) }
                }
                .onChange(of: brightness) { _, v in wand.setBrightness(v, apply: false) }
                .tint(accent)
                Image(systemName: "sun.max").font(.system(size: 15))
                    .foregroundStyle(.white.opacity(0.55))
                Text("\(Int((brightness * 100).rounded()))")
                    .font(.system(size: 12).monospacedDigit())
                    .foregroundStyle(.white.opacity(0.5))
                    .frame(width: 30, alignment: .trailing)
            }
        }
    }

    private var footer: some View {
        VStack(spacing: 12) {
            Divider().overlay(.white.opacity(0.05))
            HStack(spacing: 10) {
                Button {
                    selected = nil
                    wand.setColor(.off)
                } label: {
                    Text("Off").frame(maxWidth: .infinity, minHeight: 38)
                }
                .background(cardBG, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(cardBorder, lineWidth: 1))
                .buttonStyle(.plain)

                HStack(spacing: 10) {
                    ColorPicker("Custom", selection: $customColor, supportsOpacity: false)
                        .labelsHidden()
                    Button("Send") { wand.setColor(RGB(color: customColor)) }
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(accent)
                        .buttonStyle(.plain)
                }
                .frame(maxWidth: .infinity, minHeight: 38)
                .background(cardBG, in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(cardBorder, lineWidth: 1))
            }
        }
    }

    private func sectionLabel(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 11, weight: .semibold))
            .kerning(1.3)
            .foregroundStyle(.white.opacity(0.42))
    }
}

// MARK: - hero wand (glass sphere on a dark handle; port of the macOS WandView)

struct HeroWand: View {
    let rgb: RGB
    let glow: Double   // brightness 0..1; 0 = off

    var body: some View {
        let color = rgb.color
        let g = max(0.06, glow)
        VStack(spacing: -12) {
            ZStack {
                // outer aura
                Circle()
                    .fill(RadialGradient(colors: [color.opacity(g * 0.4), .clear],
                                         center: .center, startRadius: 0, endRadius: 95))
                    .frame(width: 190, height: 190)
                // glass sphere
                Circle()
                    .fill(RadialGradient(colors: [Color(red: 34/255, green: 34/255, blue: 41/255),
                                                  Color(red: 11/255, green: 11/255, blue: 14/255)],
                                         center: .init(x: 0.36, y: 0.32),
                                         startRadius: 4, endRadius: 75))
                    .frame(width: 120, height: 120)
                // colored core
                Circle()
                    .fill(RadialGradient(colors: [color.opacity(min(1.0, 0.25 + g * 0.9)), .clear],
                                         center: .center, startRadius: 0, endRadius: 52))
                    .frame(width: 102, height: 102)
                // emblem: soft bar + orb outline (original, abstract)
                Capsule()
                    .fill(.white.opacity(0.35 + g * 0.4))
                    .frame(width: 13, height: 54)
                Circle()
                    .stroke(.white.opacity(0.3 + g * 0.35), lineWidth: 2)
                    .frame(width: 32, height: 32)
                // gloss highlight
                Ellipse()
                    .fill(RadialGradient(colors: [.white.opacity(0.5), .clear],
                                         center: .center, startRadius: 0, endRadius: 22))
                    .frame(width: 46, height: 30)
                    .offset(x: -22, y: -34)
                // rim
                Circle()
                    .stroke(.white.opacity(0.1), lineWidth: 1.5)
                    .frame(width: 120, height: 120)
            }
            // handle with a glowing ring
            RoundedRectangle(cornerRadius: 7)
                .fill(LinearGradient(colors: [Color(red: 5/255, green: 5/255, blue: 6/255),
                                              Color(red: 74/255, green: 74/255, blue: 82/255),
                                              Color(red: 42/255, green: 42/255, blue: 48/255),
                                              Color(red: 5/255, green: 5/255, blue: 6/255)],
                                     startPoint: .leading, endPoint: .trailing))
                .frame(width: 36, height: 64)
                .overlay(alignment: .top) {
                    RoundedRectangle(cornerRadius: 2)
                        .fill(color.opacity(0.25 + g * 0.7))
                        .frame(width: 20, height: 4)
                        .padding(.top, 14)
                        .shadow(color: color, radius: 3 + g * 7)
                }
                .zIndex(-1)
        }
        .animation(.easeInOut(duration: 0.3), value: rgb)
        .animation(.easeInOut(duration: 0.3), value: glow)
    }
}
