import AppKit

final class Section: NSView {
    var env: () -> [String: String] = { [:] }
    var onOwn: ((pid_t, Bool) -> Void)?
    private var pid: pid_t?               // the group this app started
    private var api = false               // something answers on the API port, started here or elsewhere
    private var state = Progress()
    private var stopping = false
    private var failure: String?
    private var probing = false
    private var generation = 0            // drops a probe that began before the process went away

    private let light = StatusLight()
    private let spinner = NSProgressIndicator()
    private let title = label("", size: 13, weight: .semibold)
    private let button = NSButton(title: "Start", target: nil, action: nil)
    private let qr = QRView()
    private let caption = label("", size: 11, weight: .medium, color: .secondaryLabelColor)
    private let address = NSTextField(labelWithString: "")
    private let copy = NSButton(title: "Copy", target: nil, action: nil)
    private let open = NSButton(title: "Open", target: nil, action: nil)
    private let note = NSTextField(wrappingLabelWithString: "")
    private let log = link("Show Log")

    init() {
        super.init(frame: .zero)
        build()
    }
    required init?(coder: NSCoder) { fatalError() }

    private func build() {
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        button.bezelStyle = .push
        button.controlSize = .large
        button.target = self
        button.action = #selector(toggle)
        let mark = NSView()   // the light and the spinner share one spot
        for v in [light, spinner] as [NSView] {
            v.translatesAutoresizingMaskIntoConstraints = false
            mark.addSubview(v)
            v.centerXAnchor.constraint(equalTo: mark.centerXAnchor).isActive = true
            v.centerYAnchor.constraint(equalTo: mark.centerYAnchor).isActive = true
        }
        let head = NSStackView(views: [mark, title, NSView(), button])
        head.spacing = 8

        address.font = .monospacedSystemFont(ofSize: 12.5, weight: .medium)
        address.lineBreakMode = .byTruncatingMiddle
        address.isSelectable = true
        for (b, sel) in [(copy, #selector(copyAddress)), (open, #selector(openPage))] {
            b.bezelStyle = .push
            b.controlSize = .small
            b.target = self
            b.action = sel
        }
        copy.image = NSImage(systemSymbolName: "doc.on.doc", accessibilityDescription: nil)
        open.image = NSImage(systemSymbolName: "arrow.up.right.square", accessibilityDescription: nil)
        copy.imagePosition = .imageLeading
        open.imagePosition = .imageLeading
        let actions = NSStackView(views: [copy, open])
        actions.spacing = 6
        note.font = .systemFont(ofSize: 11.5)
        note.textColor = .secondaryLabelColor
        note.maximumNumberOfLines = 2
        log.target = self
        log.action = #selector(openLog)
        let info = NSStackView(views: [caption, address, actions, note, NSView(), log])
        info.orientation = .vertical
        info.alignment = .leading
        info.spacing = 6
        info.setCustomSpacing(10, after: address)
        info.setCustomSpacing(10, after: actions)

        let card = Card()
        let body = NSStackView(views: [qr, info])
        body.alignment = .top
        body.spacing = 16
        body.translatesAutoresizingMaskIntoConstraints = false
        card.addSubview(body)

        let stack = NSStackView(views: [head, card])
        stack.orientation = .vertical
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false
        addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: leadingAnchor), stack.trailingAnchor.constraint(equalTo: trailingAnchor),
            stack.topAnchor.constraint(equalTo: topAnchor), stack.bottomAnchor.constraint(equalTo: bottomAnchor),
            head.widthAnchor.constraint(equalTo: stack.widthAnchor),
            card.widthAnchor.constraint(equalTo: stack.widthAnchor),
            body.leadingAnchor.constraint(equalTo: card.leadingAnchor, constant: 14),
            body.trailingAnchor.constraint(equalTo: card.trailingAnchor, constant: -14),
            body.topAnchor.constraint(equalTo: card.topAnchor, constant: 14),
            body.bottomAnchor.constraint(equalTo: card.bottomAnchor, constant: -14),
            qr.widthAnchor.constraint(equalToConstant: 136), qr.heightAnchor.constraint(equalToConstant: 136),
            info.heightAnchor.constraint(equalTo: qr.heightAnchor),
            info.widthAnchor.constraint(equalTo: body.widthAnchor, constant: -152),
            address.widthAnchor.constraint(equalTo: info.widthAnchor),
            note.widthAnchor.constraint(equalTo: info.widthAnchor),
            mark.widthAnchor.constraint(equalToConstant: 16), mark.heightAnchor.constraint(equalToConstant: 16),
            light.widthAnchor.constraint(equalToConstant: 9), light.heightAnchor.constraint(equalToConstant: 9),
            button.widthAnchor.constraint(equalToConstant: 84),
        ])
        render()
    }

    func poll() {
        guard !probing else { return }
        probing = true
        let gen = generation
        DispatchQueue.global().async {
            let up = listening(apiPort), p = progress()
            DispatchQueue.main.async {
                self.probing = false
                guard gen == self.generation else { return }
                self.api = up
                self.state = p
                self.render()
            }
        }
    }

    func render() {
        var head = "Stopped", color = NSColor.tertiaryLabelColor, busy = false
        var cap = "PHONE", url: String?, text = "Start the server to get an address you can open from anywhere."
        var textColor = NSColor.secondaryLabelColor, logged = false
        let external = pid == nil && api
        if stopping {
            head = "Stopping…"; busy = true; text = "Closing the tunnel."
        } else if pid != nil && !(state.ready && api) {
            head = "Starting…"; busy = true; logged = true
            text = "Starting the API and opening a tunnel. This takes about half a minute."
        } else if pid != nil {
            head = state.deploying ? "Deploying…" : "Running"; color = .systemGreen; busy = state.deploying; logged = true
            cap = "OPEN ON YOUR PHONE"
            url = state.address
            text = state.deploying ? "Publishing the changed screens. Reload in about a minute."
                                   : "Edits go live by themselves: the server restarts, screens redeploy."
        } else if external {
            head = "Running Elsewhere"; color = .systemOrange
            text = "An API on port 8000 was started outside this app. Stop it there first."
        } else if let f = failure {
            head = "Failed to Start"; color = .systemRed; logged = true
            text = f; textColor = .systemRed
        }
        title.stringValue = head
        light.color = color
        light.isHidden = busy
        if busy { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }

        caption.stringValue = cap
        address.stringValue = url.map { $0.replacingOccurrences(of: "https://", with: "") } ?? "—"
        address.textColor = url == nil ? .tertiaryLabelColor : .labelColor
        address.toolTip = url
        copy.isEnabled = url != nil
        open.isEnabled = url != nil
        note.stringValue = text
        note.textColor = textColor
        note.toolTip = text
        log.isHidden = !(logged && FileManager.default.fileExists(atPath: logURL.path))
        qr.text = url

        button.title = pid != nil ? "Stop" : "Start"
        button.bezelColor = pid != nil ? nil : .controlAccentColor
        button.keyEquivalent = pid != nil ? "" : "\r"
        // serve.cjs refuses to start beside an API it did not start
        button.isEnabled = !stopping && !external
    }

    @objc private func copyAddress() {
        guard let a = state.address else { return }
        NSPasteboard.general.clearContents()
        NSPasteboard.general.setString(a, forType: .string)
        copy.title = "Copied"
        copy.image = NSImage(systemSymbolName: "checkmark", accessibilityDescription: nil)
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
            self.copy.title = "Copy"
            self.copy.image = NSImage(systemSymbolName: "doc.on.doc", accessibilityDescription: nil)
        }
    }

    @objc private func openPage() {
        if let a = state.address, let u = URL(string: a) { NSWorkspace.shared.open(u) }
    }

    @objc private func openLog() {
        NSWorkspace.shared.open(logURL)
    }

    @objc private func toggle() {
        if pid != nil { stop() } else { start() }
    }

    private func start() {
        failure = nil
        state = Progress()
        do {
            let p = try spawn(env: env())
            pid = p
            onOwn?(p, true)
            DispatchQueue.global().async {
                var status: Int32 = 0
                waitpid(p, &status, 0)
                DispatchQueue.main.async { self.exited(p) }
            }
        } catch {
            failure = error.localizedDescription
        }
        render()
    }

    private func exited(_ p: pid_t) {
        guard pid == p else { return }
        if !stopping {
            failure = failureLine()
            // serve.cjs gave up on its own; an API still waiting on a model would otherwise outlive it
            DispatchQueue.global().async { stopGroup(p) }
        }
        pid = nil
        api = false
        generation += 1
        onOwn?(p, false)
        render()
    }

    private func stop() {
        guard let p = pid else { return }
        stopping = true
        failure = nil
        render()
        DispatchQueue.global().async {
            stopGroup(p)
            DispatchQueue.main.async {
                self.stopping = false
                if self.pid == p {
                    self.pid = nil
                    self.onOwn?(p, false)
                }
                self.api = false
                self.state = Progress()
                self.generation += 1
                self.render()
                self.poll()
            }
        }
    }
}
