// Home: one card per room (controller). Tap a room to see and move its blinds.
import SwiftUI

struct BlindsTab: View {
    @Environment(AppModel.self) private var model
    @State private var adding = false
    @State private var path: [String] = []
    @State private var width: CGFloat = 400
    /// Wide screens: the room that is open beside the rooms.
    @State private var opened: String?
    /// Wide screens, with a room open: the rooms column is tucked away.
    @State private var sideHidden = false
    /// The room that was open last, so a swipe on the home page can go back to it.
    @State private var lastOpened: String?

    var body: some View {
        let wide = width >= 600
        let room = wide ? model.controllers.first(where: { $0.id == opened }) : nil
        let split = room != nil                                  // rooms on the left, the open room on the right
        let side = min(340, width * 0.4)
        let cols = split ? 1 : Layout.count(width, phone: 1, medium: 2, large: 3)
        let cardW = max(120, ((split ? side : width) - 36 - 18 * CGFloat(cols - 1)) / CGFloat(cols))      // each room card, exactly
        // One page for every size. On a phone a room pushes its own page. On a wide screen the rooms stay put and
        // narrow into a column on the left while the room comes in from the right.
        NavigationStack(path: $path) {
            HStack(alignment: .top, spacing: 0) {
                if !(split && sideHidden) {
                    ScrollView {
                        VStack(alignment: .leading, spacing: 18) {
                            HStack(alignment: .top) {
                                GreetingHeader()
                                Spacer(minLength: 0)
                                if split { Button("Hide Rooms", systemImage: "sidebar.left") { withAnimation(.smooth(duration: 0.3)) { sideHidden = true } }.labelStyle(.iconOnly).buttonStyle(.glass).padding(.top, 6) }
                            }
                            if model.controllers.isEmpty && model.waiting.isEmpty {
                                VStack(spacing: 16) {
                                    SlatView(tilt: 30).frame(width: 150, height: 170)
                                    Text("Bring your blinds to life").font(.title2.weight(.semibold))
                                    Text("Add your first blinds controller to open, close and schedule your blinds from here.").font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center)
                                    Button { adding = true } label: { Label("Add a New Device", systemImage: "plus").padding(.horizontal, 8) }.buttonStyle(.glassProminent).controlSize(.large)
                                    Button("No controller yet? Try the Demo") { withAnimation { model.addDemo() } }.font(.subheadline)
                                }
                                .frame(maxWidth: .infinity).padding(28).card()
                            }
                            // One room across on a phone or in the side column, two on a folded-open or small tablet screen, three on a big one.
                            CardFlow(columns: cols, spacing: 18) {
                                ForEach(model.controllers) { c in
                                    RoomCard(controller: c, compact: split, width: cardW, onOpen: wide ? { withAnimation(.smooth(duration: 0.35)) { opened = c.id; sideHidden = false } } : nil)
                                        .overlay { RoundedRectangle(cornerRadius: 26, style: .continuous).strokeBorder(.tint, lineWidth: 2).opacity(split && c.id == opened ? 1 : 0) }
                                }
                                ForEach(model.waiting) { c in WaitingCard(controller: c) }
                            }
                            // Scenes live under the rooms on the home page: scroll down to them.
                            if !split, !model.controllers.isEmpty {
                                VStack(alignment: .leading, spacing: 10) {
                                    Text("Scenes").font(.title3.weight(.semibold))
                                    ScrollView(.horizontal, showsIndicators: false) { ScenesRow().padding(.horizontal, 18) }.padding(.horizontal, -18)
                                }
                                .padding(.top, 8)
                                .transition(.opacity)
                            }
                        }
                        .padding(.horizontal, 18).padding(.bottom, 30)
                    }
                    // Every room at once, from the home page.
                    .safeAreaInset(edge: .bottom) {
                        if !split, model.controllers.contains(where: { $0.state?.b.contains(where: \.ready) == true }) {
                          VStack(spacing: 10) {
                            MoveBar(controllers: model.controllers).controlSize(.large).frame(maxWidth: 520).padding(.horizontal, 18).padding(.bottom, wide ? 6 : 16)
                                // gone at once when a room opens: its own bar slides in over the same spot, and two sets of buttons would overlap
                          }
                                .transition(.asymmetric(insertion: .opacity, removal: .opacity.animation(.linear(duration: 0.06))))
                        }
                    }
                    .frame(width: split ? side : nil)
                    .frame(maxWidth: split ? nil : .infinity)
                    .transition(.move(edge: .leading).combined(with: .opacity))
                }
                if let room {
                    RoomView(controller: room, embedded: true, fitWidth: width - (sideHidden ? 0 : side)).id(room.id)
                        .frame(maxWidth: .infinity)
                        .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }
            // Fill the whole screen and draw the sky behind the bars too: after turning the device, the space beside a
            // side tab bar changes, and a page sized once would leave that strip bare.
            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
            .background(AppBackground().ignoresSafeArea())
            .navigationDestination(for: String.self) { id in
                if let c = model.controllers.first(where: { $0.id == id }) { RoomView(controller: c) }
            }
            .toolbar {
                if split, sideHidden {
                    ToolbarItem(placement: .topBarLeading) { Button("Show Rooms", systemImage: "sidebar.left") { withAnimation(.smooth(duration: 0.3)) { sideHidden = false } } }
                }
                // Adding a device belongs to the home page (and Settings), not to a room that is open.
                if !split { ToolbarItem(placement: .topBarTrailing) { Button("Add a New Device", systemImage: "plus") { adding = true } } }
            }
            // Swipes on a wide screen with a room open. To the right brings back what is on the left: first the rooms
            // column, then the home page (a long swipe goes straight home). To the left gives the room the whole screen.
            .simultaneousGesture(DragGesture(minimumDistance: 30).onEnded { g in
                let dx = g.translation.width
                guard abs(dx) > 70, abs(dx) > abs(g.translation.height) * 1.6 else { return }
                if !split {                               // on the home page: a swipe to the left reopens the room you were last in
                    guard dx < 0, path.isEmpty, let last = lastOpened, model.controllers.contains(where: { $0.id == last }) else { return }
                    if wide { withAnimation(.smooth(duration: 0.35)) { opened = last; sideHidden = false } } else { path = [last] }
                    return
                }
                withAnimation(.smooth(duration: 0.35)) {
                    if dx < 0 { sideHidden = true }
                    else if sideHidden && dx < width * 0.5 { sideHidden = false }
                    else { opened = nil; sideHidden = false }
                }
            })
        }
        .onReceive(NotificationCenter.default.publisher(for: .tiltBlindsHome)) { _ in withAnimation(.smooth(duration: 0.35)) { opened = nil; sideHidden = false; path = [] } }
        .onGeometryChange(for: CGFloat.self) { $0.size.width } action: { width = $0 }
        .onChange(of: model.controllers.count) { was, now in if now < was { path = []; opened = nil } }     // a room was removed: back to the rooms
        // Folding or unfolding keeps you where you were: the home page stays the home page, an open room stays open.
        .onChange(of: width >= 600) { _, wide in
            // No animation of our own here: the system is already animating the change of screen, and a page sliding
            // off or on at the same moment looks like a glitch.
            var quiet = Transaction(); quiet.disablesAnimations = true
            withTransaction(quiet) {
                if wide { if let last = path.last { opened = last; sideHidden = false; path = [] } }
                else if let o = opened { opened = nil; path = [o] }
            }
        }
        .onChange(of: opened) { _, o in if let o { lastOpened = o } }
        .onChange(of: path) { _, p in if let l = p.last { lastOpened = l } }
        .sheet(isPresented: $adding) { AddControllerSheet() }
    }
}

/// The date and the greeting at the top of the rooms.
struct GreetingHeader: View {
    var compact = false
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(Date.now.formatted(.dateTime.weekday(.wide).month().day()).uppercased()).font(.caption.weight(.semibold)).foregroundStyle(.secondary).kerning(0.6)
            Text(Greeting.text()).font(.system(size: compact ? 26 : 34, weight: .bold, design: .rounded))
        }
        .padding(.top, 6)
    }
}
