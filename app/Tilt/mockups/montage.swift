import CoreGraphics
import Foundation
import ImageIO
import UniformTypeIdentifiers
let a = CommandLine.arguments, out = a[1], ins = Array(a[2...])
let imgs = ins.map { CGImageSourceCreateImageAtIndex(CGImageSourceCreateWithURL(URL(fileURLWithPath: $0) as CFURL, nil)!, 0, nil)! }
let s: CGFloat = 0.42, gap: CGFloat = 16
let w = CGFloat(imgs[0].width) * s, h = CGFloat(imgs[0].height) * s
let W = Int(CGFloat(imgs.count) * (w + gap) + gap), H = Int(h + 2 * gap)
let ctx = CGContext(data: nil, width: W, height: H, bitsPerComponent: 8, bytesPerRow: 0, space: CGColorSpace(name: CGColorSpace.sRGB)!, bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue)!
ctx.setFillColor(CGColor(gray: 0.12, alpha: 1)); ctx.fill(CGRect(x: 0, y: 0, width: W, height: H))
ctx.interpolationQuality = .high
for (i, im) in imgs.enumerated() { ctx.draw(im, in: CGRect(x: gap + CGFloat(i) * (w + gap), y: gap, width: w, height: h)) }
let d = CGImageDestinationCreateWithURL(URL(fileURLWithPath: out) as CFURL, UTType.png.identifier as CFString, 1, nil)!
CGImageDestinationAddImage(d, ctx.makeImage()!, nil); print(CGImageDestinationFinalize(d))
