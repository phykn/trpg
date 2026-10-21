import AppKit

let size = 1024.0
let img = NSImage(size: NSSize(width: size, height: size))
img.lockFocus()
// the macOS icon grid puts an 824pt tile on the 1024pt canvas
let tile = NSBezierPath(roundedRect: NSRect(x: 100, y: 100, width: 824, height: 824), xRadius: 185, yRadius: 185)
NSGraphicsContext.current?.saveGraphicsState()
let shadow = NSShadow()
shadow.shadowColor = NSColor.black.withAlphaComponent(0.3)
shadow.shadowBlurRadius = 24
shadow.shadowOffset = NSSize(width: 0, height: -10)
shadow.set()
NSColor.black.setFill()
tile.fill()
NSGraphicsContext.current?.restoreGraphicsState()
// the client's canvas colors (client/design/tokens.js)
NSGradient(colors: [NSColor(red: 0.04, green: 0.08, blue: 0.09, alpha: 1),
                    NSColor(red: 0.12, green: 0.22, blue: 0.25, alpha: 1)])!.draw(in: tile, angle: -60)

// a die in the client's gold, its middle pip the server light
let gold = NSColor(red: 0.90, green: 0.74, blue: 0.46, alpha: 1)
let die = NSRect(x: 252, y: 252, width: 520, height: 520)
let face = NSBezierPath(roundedRect: die, xRadius: 112, yRadius: 112)
NSColor.white.withAlphaComponent(0.07).setFill()
face.fill()
gold.setStroke()
face.lineWidth = 18
face.stroke()

func pip(_ x: Double, _ y: Double, _ color: NSColor, glow: Bool = false) {
    let r = 46.0
    let dot = NSRect(x: die.minX + die.width * x - r, y: die.minY + die.height * y - r, width: r * 2, height: r * 2)
    if glow {
        NSGraphicsContext.current?.saveGraphicsState()
        let halo = NSShadow()
        halo.shadowColor = color.withAlphaComponent(0.9)
        halo.shadowBlurRadius = 56
        halo.set()
        color.setFill()
        NSBezierPath(ovalIn: dot).fill()
        NSGraphicsContext.current?.restoreGraphicsState()
    }
    color.setFill()
    NSBezierPath(ovalIn: dot).fill()
}
for (x, y) in [(0.26, 0.26), (0.74, 0.26), (0.26, 0.74), (0.74, 0.74)] { pip(x, y, gold) }
pip(0.5, 0.5, NSColor(red: 0.20, green: 0.84, blue: 0.42, alpha: 1), glow: true)

img.unlockFocus()
let rep = NSBitmapImageRep(data: img.tiffRepresentation!)!
try! rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: CommandLine.arguments[1]))
