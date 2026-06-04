//
//  Effects.swift
//  ARMY Light
//
//  App-driven effect step generators — a Swift port of the Python
//  `army_light/effects.py` (the source of truth). The V4's firmware effect
//  registers are guarded over BLE, so all effects are driven by the app over
//  the verified color+latch path: each effect is an infinite iterator of
//  (rgb, transition, delay) steps; the controller's effect task does the I/O.
//

import Foundation

/// One effect frame: write `rgb` with the hardware fade `transition`
/// (10ms units, 0 = hard cut), then sleep `delay` seconds.
struct EffectStep: Equatable {
    var rgb: RGB
    var transition: UInt8
    var delay: TimeInterval
}

enum Effects {
    // MARK: - palettes

    /// The classic seven, in order.
    static let roygbiv: [RGB] = [
        RGB(255, 0, 0), RGB(255, 80, 0), RGB(255, 210, 0), RGB(0, 255, 0),
        RGB(0, 0, 255), RGB(75, 0, 130), RGB(160, 0, 255),
    ]

    static let jungleColors: [RGB] = [
        RGB(10, 120, 25),    // deep canopy
        RGB(40, 200, 30),    // leaf green
        RGB(120, 220, 40),   // sunlit lime
        RGB(0, 160, 90),     // fern
        RGB(210, 160, 20),   // golden sunlight
        RGB(255, 120, 0),    // tropical flower
        RGB(0, 140, 120),    // rainforest teal
    ]

    static let iceColors: [RGB] = [
        RGB(160, 220, 255),  // pale ice blue
        RGB(90, 170, 255),   // glacier blue
        RGB(0, 200, 255),    // cyan
        RGB(200, 235, 255),  // frost
        RGB(60, 100, 220),   // deep cold blue
        RGB(255, 255, 255),  // sparkle white
    ]

    static func hsv(_ h: Double, _ s: Double = 1.0, _ v: Double = 1.0) -> RGB {
        let h6 = (h.truncatingRemainder(dividingBy: 1.0) + 1).truncatingRemainder(dividingBy: 1.0) * 6
        let i = Int(h6) % 6
        let f = h6 - Double(Int(h6))
        let p = v * (1 - s), q = v * (1 - s * f), t = v * (1 - s * (1 - f))
        let (r, g, b): (Double, Double, Double)
        switch i {
        case 0: (r, g, b) = (v, t, p)
        case 1: (r, g, b) = (q, v, p)
        case 2: (r, g, b) = (p, v, t)
        case 3: (r, g, b) = (p, q, v)
        case 4: (r, g, b) = (t, p, v)
        default: (r, g, b) = (v, p, q)
        }
        return RGB(Int((r * 255).rounded()), Int((g * 255).rounded()), Int((b * 255).rounded()))
    }

    // MARK: - generators (mirroring effects.py timings exactly)

    static func blink(_ rgb: RGB) -> AnyIterator<EffectStep> {
        var on = true
        return AnyIterator {
            defer { on.toggle() }
            return EffectStep(rgb: on ? rgb : .off, transition: 0, delay: 0.6)
        }
    }

    static func breath(_ rgb: RGB) -> AnyIterator<EffectStep> {
        var on = true
        return AnyIterator {
            defer { on.toggle() }
            return EffectStep(rgb: on ? rgb : .off, transition: 120, delay: 1.3)
        }
    }

    static func strobe(_ rgb: RGB) -> AnyIterator<EffectStep> {
        var on = true
        return AnyIterator {
            defer { on.toggle() }
            return EffectStep(rgb: on ? rgb : .off, transition: 0, delay: 0.15)
        }
    }

    static func duoFade(_ a: RGB, _ b: RGB) -> AnyIterator<EffectStep> {
        var first = true
        return AnyIterator {
            defer { first.toggle() }
            return EffectStep(rgb: first ? a : b, transition: 100, delay: 1.1)
        }
    }

    static func cycle(steps: Int = 24) -> AnyIterator<EffectStep> {
        let wheel = (0..<steps).map { hsv(Double($0) / Double(steps)) }
        var i = 0
        return AnyIterator {
            defer { i = (i + 1) % wheel.count }
            return EffectStep(rgb: wheel[i], transition: 50, delay: 0.5)
        }
    }

    static func rainbow() -> AnyIterator<EffectStep> {
        var i = 0
        return AnyIterator {
            defer { i = (i + 1) % roygbiv.count }
            return EffectStep(rgb: roygbiv[i], transition: 80, delay: 2.0)
        }
    }

    static func glowCycle(steps: Int = 12) -> AnyIterator<EffectStep> {
        var i = 0, bright = true
        return AnyIterator {
            let hue = Double(i) / Double(steps)
            defer {
                if !bright { i = (i + 1) % steps }
                bright.toggle()
            }
            return EffectStep(rgb: hsv(hue, 1.0, bright ? 1.0 : 0.10),
                              transition: 130, delay: 1.4)
        }
    }

    static func candle() -> AnyIterator<EffectStep> {
        AnyIterator {
            let v = Double.random(in: 0.55...1.0)
            let h = Double.random(in: 0.085...0.11)
            return EffectStep(rgb: hsv(h, 1.0, v),
                              transition: UInt8.random(in: 5...25),
                              delay: .random(in: 0.1...0.45))
        }
    }

    static func party() -> AnyIterator<EffectStep> {
        var hue = Double.random(in: 0..<1)
        return AnyIterator {
            hue = (hue + .random(in: 0.15...0.6)).truncatingRemainder(dividingBy: 1.0)
            let transition: UInt8 = Double.random(in: 0..<1) < 0.7 ? 0 : 40
            return EffectStep(rgb: hsv(hue), transition: transition, delay: 0.45)
        }
    }

    static func jungle() -> AnyIterator<EffectStep> {
        AnyIterator {
            let rgb = jungleColors.randomElement()!
            if Double.random(in: 0..<1) < 0.2 {                 // quick flutter
                return EffectStep(rgb: rgb, transition: 10, delay: .random(in: 0.2...0.5))
            }
            let t = UInt8.random(in: 80...180)                  // slow canopy drift
            return EffectStep(rgb: rgb, transition: t,
                              delay: Double(t) / 100.0 + .random(in: 0.2...1.0))
        }
    }

    static func ice() -> AnyIterator<EffectStep> {
        var sinceSparkle = 0
        let shimmer = iceColors.filter { $0 != .white }
        return AnyIterator {
            if sinceSparkle >= 5 || (sinceSparkle > 1 && Double.random(in: 0..<1) < 0.15) {
                sinceSparkle = 0
                return EffectStep(rgb: .white, transition: 0, delay: 0.25)  // sharp glint
            }
            sinceSparkle += 1
            let t = UInt8.random(in: 60...150)
            return EffectStep(rgb: shimmer.randomElement()!, transition: t,
                              delay: Double(t) / 100.0 + .random(in: 0.2...0.8))
        }
    }

    // MARK: - registry (UI order; arity = colors the effect takes)

    struct Effect {
        let label: String
        let arity: Int
        let make: ([RGB]) -> AnyIterator<EffectStep>
    }

    static let all: [Effect] = [
        Effect(label: "Blink", arity: 1) { blink($0[0]) },
        Effect(label: "Breath", arity: 1) { breath($0[0]) },
        Effect(label: "Strobe", arity: 1) { strobe($0[0]) },
        Effect(label: "Duo Fade", arity: 2) { duoFade($0[0], $0[1]) },
        Effect(label: "Color Cycle", arity: 0) { _ in cycle() },
        Effect(label: "Rainbow", arity: 0) { _ in rainbow() },
        Effect(label: "Glow Cycle", arity: 0) { _ in glowCycle() },
        Effect(label: "Candle", arity: 0) { _ in candle() },
        Effect(label: "Party", arity: 0) { _ in party() },
        Effect(label: "Jungle", arity: 0) { _ in jungle() },
        Effect(label: "Ice", arity: 0) { _ in ice() },
    ]

    static func named(_ label: String) -> Effect? {
        all.first { $0.label == label }
    }
}

// MARK: - LED-true color mapping (port of app.py led_rgb)

extension RGB {
    /// Map a screen swatch color to an LED-true color: screens flatter pastels,
    /// but on the wand the embedded white component renders as a washed glow
    /// with a white pool at the diffuser base. Fully saturate colorful picks
    /// (same hue); keep whites/blacks/grays neutral.
    var ledTrue: RGB {
        let rf = Double(r) / 255, gf = Double(g) / 255, bf = Double(b) / 255
        let maxC = max(rf, gf, bf), minC = min(rf, gf, bf)
        let sat = maxC == 0 ? 0 : (maxC - minC) / maxC
        if sat <= 0.12 { return Effects.hsv(0, 0, maxC) }       // neutral stays
        guard sat < 1.0, sat >= 0.25 else { return self }
        let delta = maxC - minC
        var hue: Double
        if maxC == rf { hue = ((gf - bf) / delta).truncatingRemainder(dividingBy: 6) }
        else if maxC == gf { hue = (bf - rf) / delta + 2 }
        else { hue = (rf - gf) / delta + 4 }
        hue /= 6
        if hue < 0 { hue += 1 }
        return Effects.hsv(hue, 1.0, maxC)
    }
}
