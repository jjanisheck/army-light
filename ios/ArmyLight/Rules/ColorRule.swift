//
//  ColorRule.swift
//  ARMY Light
//
//  A foreground "notification rule": when fired, the wand holds an alert color
//  for a fixed interval, then returns to the resting/idle color. This is the
//  iOS-safe shape of the macOS app's "next phase" idea — evaluated only while the
//  app is in the foreground (iOS gives no reliable background BLE guarantees).
//

import Foundation

struct ColorRule: Identifiable, Codable, Hashable {
    var id: UUID
    var name: String
    var color: RGB
    /// How long to hold the alert color before returning to idle, in seconds.
    var holdSeconds: Double
    var enabled: Bool

    init(id: UUID = UUID(), name: String, color: RGB, holdSeconds: Double = 5, enabled: Bool = true) {
        self.id = id
        self.name = name
        self.color = color
        self.holdSeconds = holdSeconds
        self.enabled = enabled
    }

    static let starter: [ColorRule] = [
        ColorRule(name: "Purple flash", color: RGB(160, 0, 255), holdSeconds: 5),
        ColorRule(name: "Red alert", color: RGB(255, 0, 0), holdSeconds: 8),
    ]
}
