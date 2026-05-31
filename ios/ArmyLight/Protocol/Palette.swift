//
//  Palette.swift
//  ARMY Light
//
//  The color palette and named-color lookup — a Swift port of the Python
//  `army_light/palette.py`. Menu order is preserved so the iOS grid matches
//  the macOS menu.
//

import Foundation
import SwiftUI

/// A labeled palette color.
struct PaletteColor: Identifiable, Hashable {
    let label: String
    let rgb: RGB
    var id: String { label }
}

enum Palette {
    /// Grid order, top to bottom / left to right.
    static let all: [PaletteColor] = [
        PaletteColor(label: "Red",    rgb: RGB(255, 0, 0)),
        PaletteColor(label: "Orange", rgb: RGB(255, 80, 0)),
        PaletteColor(label: "Yellow", rgb: RGB(255, 200, 0)),
        PaletteColor(label: "Green",  rgb: RGB(0, 255, 0)),
        PaletteColor(label: "Cyan",   rgb: RGB(0, 200, 255)),
        PaletteColor(label: "Blue",   rgb: RGB(0, 0, 255)),
        PaletteColor(label: "Purple", rgb: RGB(160, 0, 255)),
        PaletteColor(label: "Pink",   rgb: RGB(255, 40, 150)),
        PaletteColor(label: "White",  rgb: RGB(255, 255, 255)),
        PaletteColor(label: "Off",    rgb: RGB(0, 0, 0)),
    ]

    /// Lowercased name -> rgb.
    static let byName: [String: RGB] = Dictionary(
        uniqueKeysWithValues: all.map { ($0.label.lowercased(), $0.rgb) }
    )

    /// Accept a palette name ("red"), "r,g,b", or "#rrggbb". Returns nil if unparseable.
    static func parse(_ text: String) -> RGB? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if let named = byName[t] { return named }
        if t.hasPrefix("#"), t.count == 7 {
            let hex = t.dropFirst()
            let s = hex.startIndex
            guard
                let r = Int(hex[s..<hex.index(s, offsetBy: 2)], radix: 16),
                let g = Int(hex[hex.index(s, offsetBy: 2)..<hex.index(s, offsetBy: 4)], radix: 16),
                let b = Int(hex[hex.index(s, offsetBy: 4)..<hex.index(s, offsetBy: 6)], radix: 16)
            else { return nil }
            return RGB(r, g, b)
        }
        if t.contains(",") {
            let parts = t.split(separator: ",").map { Int($0.trimmingCharacters(in: .whitespaces)) }
            if parts.count == 3, parts.allSatisfy({ $0 != nil && (0...255).contains($0!) }) {
                return RGB(parts[0]!, parts[1]!, parts[2]!)
            }
        }
        return nil
    }
}

// MARK: - SwiftUI bridging

extension RGB {
    /// A SwiftUI Color for this triple.
    var color: Color {
        Color(red: Double(r) / 255, green: Double(g) / 255, blue: Double(b) / 255)
    }

    /// "#RRGGBB" uppercase.
    var hexString: String { String(format: "#%02X%02X%02X", r, g, b) }

    /// Build from a SwiftUI Color (best-effort via its resolved RGB).
    init(color: Color) {
        let resolved = color.resolve(in: EnvironmentValues())
        self.init(
            Int((resolved.red * 255).rounded()),
            Int((resolved.green * 255).rounded()),
            Int((resolved.blue * 255).rounded())
        )
    }
}
