import AppKit

func label(_ s: String, size: CGFloat, weight: NSFont.Weight = .regular, color: NSColor = .labelColor) -> NSTextField {
    let l = NSTextField(labelWithString: s)
    l.font = .systemFont(ofSize: size, weight: weight)
    l.textColor = color
    l.lineBreakMode = .byTruncatingTail
    return l
}

func link(_ title: String) -> NSButton {
    let b = NSButton(title: title, target: nil, action: nil)
    b.isBordered = false
    b.font = .systemFont(ofSize: 11.5, weight: .medium)
    b.contentTintColor = .linkColor
    return b
}

// resolved when drawn, so they follow light and dark mode
extension NSColor {
    static let groupFill = NSColor(name: nil) { $0.isDark ? .white.withAlphaComponent(0.05) : .white.withAlphaComponent(0.7) }
    static let groupStroke = NSColor(name: nil) { $0.isDark ? .white.withAlphaComponent(0.09) : .black.withAlphaComponent(0.09) }
}

extension NSAppearance {
    var isDark: Bool { bestMatch(from: [.aqua, .darkAqua]) == .darkAqua }
}

final class Card: NSView {
    override func draw(_ r: NSRect) {
        let box = NSBezierPath(roundedRect: bounds.insetBy(dx: 0.5, dy: 0.5), xRadius: 12, yRadius: 12)
        NSColor.groupFill.setFill()
        box.fill()
        NSColor.groupStroke.setStroke()
        box.stroke()
    }
}

final class StatusLight: NSView {
    var color = NSColor.tertiaryLabelColor { didSet { needsDisplay = true } }
    override var intrinsicContentSize: NSSize { NSSize(width: 8, height: 8) }
    override func draw(_ r: NSRect) {
        color.setFill()
        NSBezierPath(ovalIn: bounds).fill()
    }
}

// A QR code needs dark modules on a light ground to scan, whatever the window's appearance.
final class QRView: NSView {
    var text: String? { didSet { if text != oldValue { image = text.flatMap(QRView.render); needsDisplay = true } } }
    private var image: CGImage?

    private static func render(_ s: String) -> CGImage? {
        guard let f = CIFilter(name: "CIQRCodeGenerator") else { return nil }
        f.setValue(Data(s.utf8), forKey: "inputMessage")
        f.setValue("M", forKey: "inputCorrectionLevel")
        guard let ci = f.outputImage else { return nil }
        return CIContext().createCGImage(ci, from: ci.extent)
    }

    override func draw(_ r: NSRect) {
        let tile = NSBezierPath(roundedRect: bounds, xRadius: 8, yRadius: 8)
        (image == nil ? NSColor.labelColor.withAlphaComponent(0.06) : .white).setFill()
        tile.fill()
        guard let ctx = NSGraphicsContext.current?.cgContext else { return }
        guard let image else {
            let cfg = NSImage.SymbolConfiguration(pointSize: 40, weight: .ultraLight)
                .applying(.init(paletteColors: [.tertiaryLabelColor]))
            let mark = NSImage(systemSymbolName: "qrcode", accessibilityDescription: nil)!.withSymbolConfiguration(cfg)!
            mark.draw(at: NSPoint(x: bounds.midX - mark.size.width / 2, y: bounds.midY - mark.size.height / 2),
                      from: .zero, operation: .sourceOver, fraction: 1)
            return
        }
        ctx.interpolationQuality = .none   // keeps the modules sharp
        ctx.draw(image, in: bounds.insetBy(dx: 10, dy: 10))
    }
}
