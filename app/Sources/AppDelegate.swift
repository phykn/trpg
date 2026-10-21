import AppKit

let ownedFile = root.appendingPathComponent("logs/app-owned")

final class AppDelegate: NSObject, NSApplicationDelegate {
    let window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 420, height: 100),
                          styleMask: [.titled, .closable, .miniaturizable, .fullSizeContentView], backing: .buffered, defer: false)
    let server = Section()
    let models = ModelBar()
    private var owned: [pid_t] = []

    func applicationDidFinishLaunching(_ note: Notification) {
        // a list left by an earlier run whose watchdog never ran, e.g. across a reboot; this run started none of those
        try? FileManager.default.removeItem(at: ownedFile)
        buildWindow()
        window.center()
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        server.onOwn = { [weak self] pid, on in self?.own(pid, on) }
        server.env = { [models] in models.env }
        DispatchQueue.global().async { self.models.load() }
        startWatchdog()
        refresh()
        Timer.scheduledTimer(withTimeInterval: 2, repeats: true) { [weak self] _ in self?.refresh() }
    }

    func refresh() {
        server.poll()
        models.poll()
    }

    func buildWindow() {
        window.title = "TRPG"
        window.titlebarAppearsTransparent = true
        window.isMovableByWindowBackground = true
        let bg = NSVisualEffectView()
        bg.material = .underWindowBackground
        bg.blendingMode = .behindWindow
        bg.state = .active
        window.contentView = bg

        let rule = NSBox()
        rule.boxType = .separator
        let stack = NSStackView(views: [server, rule, models])
        stack.orientation = .vertical
        stack.spacing = 18
        stack.setCustomSpacing(0, after: rule)
        stack.edgeInsets = NSEdgeInsets(top: 38, left: 0, bottom: 0, right: 0)   // below the title bar
        stack.translatesAutoresizingMaskIntoConstraints = false
        bg.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: bg.leadingAnchor), stack.trailingAnchor.constraint(equalTo: bg.trailingAnchor),
            stack.topAnchor.constraint(equalTo: bg.topAnchor), stack.bottomAnchor.constraint(equalTo: bg.bottomAnchor),
            bg.widthAnchor.constraint(equalToConstant: 420),
            rule.widthAnchor.constraint(equalTo: stack.widthAnchor),
            models.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -40),
            models.heightAnchor.constraint(equalToConstant: 44),
            server.widthAnchor.constraint(equalTo: stack.widthAnchor, constant: -40),
        ])
    }

    func own(_ pid: pid_t, _ on: Bool) {
        owned.removeAll { $0 == pid }
        if on { owned.append(pid) }
        try? FileManager.default.createDirectory(at: ownedFile.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? owned.map { "\($0)\n" }.joined().write(to: ownedFile, atomically: true, encoding: .utf8)
    }

    // serve.cjs clears its tunnel URL from KV on SIGTERM, so the script alone gets it first.
    // applicationWillTerminate runs only on a normal quit. A child process outlives the app (macOS does not kill
    // children with their parent), so it can stop the app's servers after a force quit or crash too.
    func startWatchdog() {
        let p = Process()
        p.executableURL = URL(fileURLWithPath: "/bin/sh")
        p.arguments = ["-c", """
            app=$1; f=$2; while kill -0 "$app" 2>/dev/null; do sleep 1; done
            [ -f "$f" ] || exit 0
            pgs=$(cat "$f"); rm -f "$f"
            for pg in $pgs; do kill -TERM "$pg" 2>/dev/null; done
            sleep 15
            for pg in $pgs; do kill -KILL -- "-$pg" 2>/dev/null; done
            """, "watchdog", String(getpid()), ownedFile.path]
        p.standardOutput = FileHandle.nullDevice
        p.standardError = FileHandle.nullDevice
        try? p.run()
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ app: NSApplication) -> Bool { true }
}
