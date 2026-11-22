// Laying cards out in columns that change with the width of the screen.
import SwiftUI

/// How many cards go side by side for the width at hand.
enum Layout {
    static func count(_ width: CGFloat, phone: Int, medium: Int, large: Int, from: CGFloat = 600, to: CGFloat = 1000) -> Int {
        width < from ? phone : width < to ? medium : large
    }
}

/// Cards in equal columns. Unlike a lazy grid, every card keeps its identity when the number of columns or the width
/// changes, so a change of layout slides the cards to their new places instead of popping them in and out.
struct CardFlow: SwiftUI.Layout {
    var columns: Int
    var spacing: CGFloat
    private func cell(_ width: CGFloat) -> CGFloat { max(0, (width - spacing * CGFloat(columns - 1)) / CGFloat(max(columns, 1))) }
    private func rows(_ subviews: Subviews, _ w: CGFloat) -> [CGFloat] {
        stride(from: 0, to: subviews.count, by: max(columns, 1)).map { i in
            subviews[i..<min(i + columns, subviews.count)].map { $0.sizeThatFits(ProposedViewSize(width: w, height: nil)).height }.max() ?? 0
        }
    }
    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 0, h = rows(subviews, cell(width))
        return CGSize(width: width, height: h.reduce(0, +) + spacing * CGFloat(max(h.count - 1, 0)))
    }
    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let w = cell(bounds.width), h = rows(subviews, w)
        var y = bounds.minY
        for (i, v) in subviews.enumerated() {
            let c = i % max(columns, 1), r = i / max(columns, 1)
            if c == 0, r > 0 { y += h[r - 1] + spacing }
            v.place(at: CGPoint(x: bounds.minX + CGFloat(c) * (w + spacing), y: y), anchor: .topLeading, proposal: ProposedViewSize(width: w, height: nil))
        }
    }
}
