// Draws the app icon: three slats of a blind seen from the side.
// Run: swift make_icon.swift
import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers

let n = 1024
let cs = CGColorSpace(name: CGColorSpace.sRGB)!
let ctx = CGContext(data: nil, width: n, height: n, bitsPerComponent: 8, bytesPerRow: 0, space: cs, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
func rgb(_ r: CGFloat, _ g: CGFloat, _ b: CGFloat, _ a: CGFloat = 1) -> CGColor { CGColor(colorSpace: cs, components: [r, g, b, a])! }

// sky: amber at the top, teal at the bottom
let sky = CGGradient(colorsSpace: cs, colors: [rgb(1.00, 0.76, 0.42), rgb(0.98, 0.62, 0.36), rgb(0.20, 0.58, 0.70), rgb(0.06, 0.36, 0.50)] as CFArray, locations: [0, 0.3, 0.75, 1])!
ctx.drawLinearGradient(sky, start: CGPoint(x: 200, y: 1024), end: CGPoint(x: 824, y: 0), options: [.drawsBeforeStartLocation, .drawsAfterEndLocation])
let glow = CGGradient(colorsSpace: cs, colors: [rgb(1, 1, 1, 0.45), rgb(1, 1, 1, 0)] as CFArray, locations: [0, 1])!
ctx.drawRadialGradient(glow, startCenter: CGPoint(x: 300, y: 820), startRadius: 0, endCenter: CGPoint(x: 300, y: 820), endRadius: 620, options: [])

// three slats seen end-on: straight, tilted, stacked one right above the other
let cx: CGFloat = 512, dx: CGFloat = 215, dy: CGFloat = 78
ctx.setLineCap(.round)
ctx.setShadow(offset: CGSize(width: 0, height: -14), blur: 28, color: rgb(0, 0.15, 0.25, 0.35))
ctx.setStrokeColor(rgb(1, 1, 1)); ctx.setLineWidth(72)
for y in [742, 512, 282] as [CGFloat] {
    ctx.move(to: CGPoint(x: cx - dx, y: y + dy)); ctx.addLine(to: CGPoint(x: cx + dx, y: y - dy)); ctx.strokePath()
}

let out = URL(fileURLWithPath: "Tilt/Assets.xcassets/AppIcon.appiconset/icon.png")
let dest = CGImageDestinationCreateWithURL(out as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(dest, ctx.makeImage()!, nil)
print(CGImageDestinationFinalize(dest) ? "wrote icon" : "failed")
