// The Home Screen widget (status, Open, Close) and two Control Center buttons.
import AppIntents
import SwiftUI
import WidgetKit

struct RoomLine: Hashable { let name: String; let status: String; let closed: Double }
struct TiltEntry: TimelineEntry {
    let date: Date
    let rooms: [RoomLine]
    let paired: Bool
    var moving: Bool { rooms.contains { $0.status == "Moving" } }
}

struct TiltProvider: TimelineProvider {
    func placeholder(in context: Context) -> TiltEntry { TiltEntry(date: .now, rooms: [RoomLine(name: "Living Room", status: "Open", closed: 0)], paired: true) }
    func getSnapshot(in context: Context, completion: @escaping (TiltEntry) -> Void) {
        if context.isPreview { completion(placeholder(in: context)) } else { Task { completion(await load()) } }
    }
    func getTimeline(in context: Context, completion: @escaping (Timeline<TiltEntry>) -> Void) {
        Task {
            let e = await load()
            completion(Timeline(entries: [e], policy: .after(.now + (e.moving ? 20 : 900))))     // look again soon while a blind is moving
        }
    }
    private func load() async -> TiltEntry {
        let links = TiltActions.links()
        var rooms: [RoomLine] = []
        for (rec, link) in links {
            if let s: ControllerState = try? await link.json("/api/s") {
                let tilts = s.b.filter(\.ready).compactMap(\.tilt)
                let closed = tilts.isEmpty ? 0 : tilts.map { abs($0) }.reduce(0, +) / Double(tilts.count) / 100
                rooms.append(RoomLine(name: s.name, status: TiltActions.words(s), closed: closed))
            } else {
                rooms.append(RoomLine(name: rec.name, status: "Not reachable", closed: 0))
            }
        }
        return TiltEntry(date: .now, rooms: rooms, paired: !links.isEmpty)
    }
}

/// A tiny blind: three slats that get thicker as it closes.
struct MiniBlind: View {
    let closed: Double
    var body: some View {
        VStack(spacing: 3) {
            ForEach(0..<4, id: \.self) { _ in Capsule().fill(.white).frame(height: 2.5 + 5.5 * closed) }
        }
        .frame(width: 30, height: 34)
    }
}

struct TiltWidgetView: View {
    @Environment(\.widgetFamily) private var family
    let entry: TiltEntry
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            if !entry.paired {
                Spacer()
                Text("Open Tilt to add your blinds").font(.subheadline.weight(.semibold)).foregroundStyle(.white)
                Spacer()
            } else {
                ForEach(entry.rooms.prefix(family == .systemSmall ? 1 : 2), id: \.self) { r in
                    HStack(spacing: 10) {
                        MiniBlind(closed: r.closed)
                        VStack(alignment: .leading, spacing: 1) {
                            Text(r.name).font(.subheadline.weight(.semibold)).lineLimit(1)
                            Text(r.status).font(.caption).opacity(0.85).lineLimit(1)
                        }
                    }
                    .foregroundStyle(.white)
                }
                Spacer(minLength: 0)
                HStack(spacing: 8) {
                    Button(intent: OpenBlindsIntent()) { Label("Open", systemImage: "sun.max.fill").font(.caption.weight(.semibold)).frame(maxWidth: .infinity) }
                    Button(intent: CloseBlindsIntent()) { Label("Close", systemImage: "moon.fill").font(.caption.weight(.semibold)).frame(maxWidth: .infinity) }
                }
                .labelStyle(family == .systemSmall ? AnyLabelStyle(.iconOnly) : AnyLabelStyle(.titleAndIcon))
                .buttonStyle(.borderedProminent).tint(.white.opacity(0.25)).foregroundStyle(.white)
            }
        }
        .containerBackground(for: .widget) {
            LinearGradient(colors: [Color(red: 0.99, green: 0.68, blue: 0.38), Color(red: 0.22, green: 0.58, blue: 0.70), Color(red: 0.06, green: 0.36, blue: 0.50)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        }
    }
}

/// Lets one line pick between two label styles.
struct AnyLabelStyle: LabelStyle {
    enum Kind { case iconOnly, titleAndIcon }
    let kind: Kind
    init(_ k: Kind) { kind = k }
    func makeBody(configuration: Configuration) -> some View {
        switch kind {
        case .iconOnly: configuration.icon
        case .titleAndIcon: HStack(spacing: 5) { configuration.icon; configuration.title }
        }
    }
}

struct TiltWidget: Widget {
    var body: some WidgetConfiguration {
        StaticConfiguration(kind: "TiltWidget", provider: TiltProvider()) { TiltWidgetView(entry: $0) }
            .configurationDisplayName("Blinds")
            .description("See your blinds and open or close them.")
            .supportedFamilies([.systemSmall, .systemMedium])
    }
}

struct OpenBlindsControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "app.tilt.blinds.open") {
            ControlWidgetButton(action: OpenBlindsIntent()) { Label("Open Blinds", systemImage: "sun.max.fill") }
        }
        .displayName("Open Blinds").description("Opens all your blinds.")
    }
}
struct CloseBlindsControl: ControlWidget {
    var body: some ControlWidgetConfiguration {
        StaticControlConfiguration(kind: "app.tilt.blinds.close") {
            ControlWidgetButton(action: CloseBlindsIntent()) { Label("Close Blinds", systemImage: "moon.fill") }
        }
        .displayName("Close Blinds").description("Closes all your blinds.")
    }
}

@main
struct TiltWidgets: WidgetBundle {
    var body: some Widget {
        TiltWidget()
        OpenBlindsControl()
        CloseBlindsControl()
    }
}
