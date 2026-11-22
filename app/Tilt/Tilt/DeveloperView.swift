// Developer mode: everything the controller knows, live.
import SwiftUI

struct DeveloperView: View {
    let controller: Controller
    @State private var dev: [String: Any] = [:]
    @State private var log: [String] = []
    @State private var page = 0

    var body: some View {
        List {
            Group {
            Picker("Page", selection: $page) { Text("Live").tag(0); Text("System").tag(1); Text("Log").tag(2) }.pickerStyle(.segmented).listRowBackground(Color.clear)
            if page == 1 {
                Section {
                    Button("Send a Test Low-Battery Alert", systemImage: "bell.badge") { BatteryAlerts.test(name: controller.state?.name ?? controller.record.name) }
                } footer: { Text("It arrives in 5 seconds. Go to the Home Screen or lock the phone to see it.") }
            }
            if page == 0 {
                Section("Power") {
                    row("Battery", "pwr.rest", "%.2f V"); row("Under load", "pwr.vbat", "%.2f V"); row("Input", "pwr.vin", "%.2f V"); row("3.3 V rail", "pwr.vdd", "%.2f V")
                    LabeledContent("Source", value: num("pwr.powered") == 1 ? "Input power" : "Battery")
                }
                ForEach(0..<((value("p") as? [Any])?.count ?? ControllerLimits.fallback.ports), id: \.self) { i in      // one per Port
                    Section("Port \(i + 1)") {
                        LabeledContent("Sensor", value: (str("p.\(i).sig") ?? "") + (num("p.\(i).pres") == 1 ? "" : " · nothing plugged in"))
                        row("Angle", "p.\(i).ang", "%.1f°")
                        LabeledContent("Tilt", value: controller.state?.b[safe: i]?.tilt.map { String(format: "%.0f", $0) } ?? "—")
                        LabeledContent("Marks (up / open / down)", value: ["up", "open", "down"].map { num("p.\(i).\($0)").map { String(format: "%.0f°", $0) } ?? "—" }.joined(separator: " / "))
                        LabeledContent("Moves / stalls", value: "\(Int(num("p.\(i).moves") ?? 0)) / \(Int(num("p.\(i).stalls") ?? 0))")
                        LabeledContent("Last result", value: controller.state?.b[safe: i]?.last ?? "")
                    }
                }
                Section("Stall sensing") {
                    row("Wait after reversing", "tune.grace", "%.0f ms"); row("Must move every", "tune.stall", "%.0f ms"); row("Longest move", "tune.max", "%.0f s")
                }
            } else if page == 1 {
                Section("Firmware") {
                    text("Version", "sys.fw"); text("Built", "sys.build"); text("ESP-IDF", "sys.idf"); text("Running from", "sys.part"); text("Last start", "sys.rst")
                    LabeledContent("Program", value: "\(Int((num("sys.app") ?? 0) / 1024)) kB of \(Int((num("sys.appMax") ?? 0) / 1024)) kB")
                    row("Chip temperature", "sys.temp", "%.0f °C"); LabeledContent("Free memory", value: "\(Int((num("sys.heap") ?? 0) / 1024)) kB")
                }
                Section("Network") {
                    text("Wi-Fi", "wifi.ssid"); text("Address", "wifi.ip"); row("Signal", "wifi.rssi", "%.0f dBm"); text("MAC", "sys.mac")
                }
                Section("Counters") {
                    row("Starts", "st.boots", "%.0f"); row("Brownouts", "st.brown", "%.0f"); row("Crashes", "st.crash", "%.0f"); row("Updates kept", "st.ota", "%.0f")
                }
                Section { Button("Restart Controller", role: .destructive) { controller.run { try await $0.restart() } } }
            } else {
                Section("Newest first") {
                    ForEach(Array(log.reversed().enumerated()), id: \.offset) { _, l in Text(l).font(.caption.monospaced()) }
                }
            }
        }
            .listRowBackground(RowGlass())      // rows are glass over the sky, not solid white
        }
        .skyPage()
        .navigationTitle("Developer").navigationBarTitleDisplayMode(.inline)
        .task {
            while !Task.isCancelled {
                dev = await controller.client.developerInfo()
                if page == 2 { log = await controller.client.log() }
                try? await Task.sleep(for: .milliseconds(700))
            }
        }
    }

    private func value(_ path: String) -> Any? {
        var cur: Any? = dev
        for k in path.split(separator: ".") {
            if let i = Int(k), let a = cur as? [Any] { cur = a.indices.contains(i) ? a[i] : nil } else { cur = (cur as? [String: Any])?[String(k)] }
        }
        return cur is NSNull ? nil : cur
    }
    private func num(_ p: String) -> Double? { (value(p) as? NSNumber)?.doubleValue }
    private func str(_ p: String) -> String? { value(p) as? String }
    private func row(_ title: String, _ p: String, _ fmt: String) -> some View { LabeledContent(title, value: num(p).map { String(format: fmt, $0) } ?? "—").monospacedDigit() }
    private func text(_ title: String, _ p: String) -> some View { LabeledContent(title, value: str(p) ?? "—") }
}
