import AppKit

// The server's own model tables and the addresses `--local` uses, so the app keeps no copy of either.
private let configScript = """
import json, run_api
from src.models.decision import DECISION_MODELS
from src.models.llm import LLM_MODELS
cfg = run_api.local_settings()
print(json.dumps({
    "decision": {"url": cfg.decision_base_url + "/v1/models", "models": {k: [v.run] for k, v in DECISION_MODELS.items()}},
    "llm": {"url": cfg.llm_base_url + "/models", "models": {k: list(v.ids) for k, v in LLM_MODELS.items()}},
}))
"""

private struct Config: Decodable {
    struct Role: Decodable { let url: String; let models: [String: [String]] }
    let decision: Role
    let llm: Role
}

// Shows which engine model each model server has loaded, and hands those names to the API at start, so it runs
// with whatever LOCAL-MODELS loaded. The API still checks them itself (DecisionClient.check, LLMClient.resolve_model).
final class ModelBar: NSView {
    private enum State { case unknown, off, empty, other([String]), on(String) }

    private final class Role {
        let env: String
        let title: String
        var url: URL?
        var models: [String: [String]] = [:]
        var state = State.unknown
        var probing = false
        let light = StatusLight()
        let name = label("", size: 12)
        // each server lists its models in its own shape
        let loaded: ([String: Any]) -> [String]

        init(env: String, title: String, loaded: @escaping ([String: Any]) -> [String]) {
            self.env = env
            self.title = title
            self.loaded = loaded
        }

        var key: String? { if case .on(let k) = state { k } else { nil } }
    }

    private let roles = [
        Role(env: "DECISION_MODEL", title: "Decision") { obj in
            (obj["models"] as? [[String: Any]] ?? []).compactMap { $0["run"] as? String }
        },
        Role(env: "LLM_MODEL", title: "Narration") { obj in
            let ms = obj["data"] as? [[String: Any]] ?? []
            return ms.filter { $0["loaded"] as? Bool ?? (ms.count == 1) }.compactMap { $0["id"] as? String }
        },
    ]
    private let error = label("", size: 12, color: .systemRed)

    var env: [String: String] {
        Dictionary(uniqueKeysWithValues: roles.compactMap { r in r.key.map { (r.env, $0) } })
    }

    init() {
        super.init(frame: .zero)
        let title = label("Models", size: 12, weight: .medium, color: .secondaryLabelColor)
        var views: [NSView] = [title]
        for r in roles {
            let item = NSStackView(views: [r.light, label(r.title, size: 12, color: .secondaryLabelColor), r.name])
            item.spacing = 6
            item.setCustomSpacing(5, after: r.light)
            r.light.widthAnchor.constraint(equalToConstant: 8).isActive = true
            r.light.heightAnchor.constraint(equalToConstant: 8).isActive = true
            views.append(item)
        }
        error.isHidden = true
        let row = NSStackView(views: views + [error, NSView()])
        row.spacing = 18
        row.setCustomSpacing(14, after: title)
        row.translatesAutoresizingMaskIntoConstraints = false
        addSubview(row)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: leadingAnchor), row.trailingAnchor.constraint(equalTo: trailingAnchor),
            row.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        render()
    }
    required init?(coder: NSCoder) { fatalError() }

    // off the main thread: it waits for Python
    func load() {
        let p = Process()
        p.executableURL = root.appendingPathComponent(".venv/bin/python")
        p.arguments = ["-c", configScript]
        p.currentDirectoryURL = root.appendingPathComponent("server")
        let out = Pipe(), err = Pipe()
        p.standardOutput = out
        p.standardError = err
        var cfg: Config?
        var why = ""
        do {
            try p.run()
            let o = out.fileHandleForReading.readDataToEndOfFile(), e = err.fileHandleForReading.readDataToEndOfFile()
            p.waitUntilExit()
            cfg = try? JSONDecoder().decode(Config.self, from: o)
            why = String(data: e, encoding: .utf8)?.split(separator: "\n").last.map(String.init) ?? ""
        } catch {
            why = error.localizedDescription
        }
        DispatchQueue.main.async {
            guard let cfg else {
                self.error.stringValue = "Can't read the model config"
                self.error.toolTip = why
                self.error.isHidden = false
                self.roles.forEach { $0.light.superview?.isHidden = true }
                return
            }
            for (r, c) in zip(self.roles, [cfg.decision, cfg.llm]) {
                r.url = URL(string: c.url)
                r.models = c.models
            }
            self.poll()
        }
    }

    func poll() {
        for r in roles {
            guard let url = r.url, !r.probing else { continue }
            r.probing = true
            var req = URLRequest(url: url)
            req.timeoutInterval = 3
            URLSession.shared.dataTask(with: req) { data, resp, err in
                DispatchQueue.main.async {
                    r.probing = false
                    // a server busy writing answers late; only a refused connection means it is down
                    if (err as? URLError)?.code == .timedOut { return }
                    guard err == nil, (resp as? HTTPURLResponse)?.statusCode == 200, let data,
                          let obj = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
                        r.state = err == nil ? .other([]) : .off
                        self.render()
                        return
                    }
                    let ids = r.loaded(obj)
                    let key = r.models.keys.sorted().first { k in
                        r.models[k]!.contains { p in ids.contains { $0.lowercased().contains(p.lowercased()) } }
                    }
                    r.state = key.map { .on($0) } ?? (ids.isEmpty ? .empty : .other(ids))
                    self.render()
                }
            }.resume()
        }
    }

    private func render() {
        for r in roles {
            var text = "", color = NSColor.tertiaryLabelColor, tip = r.url?.absoluteString ?? ""
            switch r.state {
            case .unknown: break
            case .off: text = "Off"
            case .empty: text = "Nothing loaded"; color = .systemOrange
            case .other(let ids):
                text = "Other model"; color = .systemOrange
                if !ids.isEmpty { tip += "\n" + ids.joined(separator: "\n") }
            case .on(let k): text = k; color = .systemGreen
            }
            r.name.stringValue = text
            r.name.textColor = color == .systemGreen ? .labelColor : .secondaryLabelColor
            r.light.color = color
            r.light.superview?.toolTip = tip
        }
    }
}
