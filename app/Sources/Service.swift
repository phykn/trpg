import Foundation

// app/build.sh writes both into Info.plist; PATH is the building shell's, so `node` and `cloudflared` resolve as there
let root = URL(fileURLWithPath: Bundle.main.infoDictionary?["ProjectRoot"] as? String ?? "")
let shellPath = Bundle.main.infoDictionary?["Path"] as? String ?? "/usr/bin:/bin"
let logURL = root.appendingPathComponent("logs/server.log")

// client/scripts/serve.cjs runs the API, a tunnel to it and the file watchers that restart the API or redeploy the page
let script = "scripts/serve.cjs"
let apiPort: UInt16 = 8000

// what serve.cjs prints, read back from its log
struct Progress { var ready = false; var address: String?; var deploying = false }
func progress() -> Progress {
    var p = Progress()
    guard let text = try? String(contentsOf: logURL, encoding: .utf8) else { return p }
    var deployed = false
    for line in text.split(separator: "\n").reversed() {
        if line.hasPrefix("화면 배포") { deployed = true }   // 완료 or 실패: the latest redeploy is over
        if line.hasPrefix("화면 코드가 바뀌어 배포합니다") && !deployed { p.deploying = true }
        if line.hasPrefix("외부 접속 준비 완료") {
            p.ready = true
            p.address = line.range(of: #"https://\S+\.workers\.dev"#, options: .regularExpression).map { String(line[$0]) }
            break
        }
    }
    return p
}

// Its own process group, so a stop also reaches what the script spawned.
func spawn(env extra: [String: String]) throws -> pid_t {
    try FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    var env = ProcessInfo.processInfo.environment
    env["PATH"] = shellPath
    env["PYTHONUNBUFFERED"] = "1"   // so the log shows the API's lines as they happen
    env.merge(extra) { $1 }

    var fa: posix_spawn_file_actions_t?
    posix_spawn_file_actions_init(&fa)
    defer { posix_spawn_file_actions_destroy(&fa) }
    posix_spawn_file_actions_addopen(&fa, 0, "/dev/null", O_RDONLY, 0)
    posix_spawn_file_actions_addopen(&fa, 1, logURL.path, O_WRONLY | O_CREAT | O_TRUNC, 0o644)
    posix_spawn_file_actions_adddup2(&fa, 1, 2)
    posix_spawn_file_actions_addchdir(&fa, root.appendingPathComponent("client").path)
    var attr: posix_spawnattr_t?
    posix_spawnattr_init(&attr)
    defer { posix_spawnattr_destroy(&attr) }
    posix_spawnattr_setflags(&attr, Int16(POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_CLOEXEC_DEFAULT))
    posix_spawnattr_setpgroup(&attr, 0)

    let argv = ["/usr/bin/env", "node", script].map { strdup($0) } + [nil]
    let envp = env.map { strdup("\($0.key)=\($0.value)") } + [nil]
    defer { (argv + envp).forEach { free($0) } }
    var pid: pid_t = 0
    let rc = posix_spawn(&pid, "/usr/bin/env", &fa, &attr, argv, envp)
    guard rc == 0 else { throw POSIXError(POSIXErrorCode(rawValue: rc) ?? .EIO) }
    return pid
}

// The script gets SIGTERM alone first: it stops its own children, and serve.cjs also clears the tunnel URL from KV,
// which takes a few seconds. Whatever is left of the group after that is killed.
// Blocks until the group is gone: call it off the main thread.
func stopGroup(_ pg: pid_t) {
    kill(pg, SIGTERM)
    var waited = 0
    while kill(-pg, 0) == 0 && waited < 150 {
        usleep(100_000)
        waited += 1
    }
    kill(-pg, SIGKILL)
}

// "localhost" resolves to both loopbacks: uvicorn binds 127.0.0.1, Expo may bind ::1
func listening(_ port: UInt16) -> Bool {
    var hints = addrinfo()
    hints.ai_socktype = SOCK_STREAM
    var res: UnsafeMutablePointer<addrinfo>?
    guard getaddrinfo("localhost", String(port), &hints, &res) == 0 else { return false }
    defer { freeaddrinfo(res) }
    var ai = res
    while let a = ai {
        let fd = socket(a.pointee.ai_family, a.pointee.ai_socktype, a.pointee.ai_protocol)
        if fd >= 0 {
            defer { close(fd) }
            if connect(fd, a.pointee.ai_addr, a.pointee.ai_addrlen) == 0 { return true }
        }
        ai = a.pointee.ai_next
    }
    return false
}

// A Python traceback ends with its exception, and uvicorn follows it with a generic "startup failed" line.
func failureLine() -> String {
    guard let text = try? String(contentsOf: logURL, encoding: .utf8) else { return "" }
    // serve.cjs signs off with its shutdown notice, which says nothing about why
    let lines = text.split(separator: "\n").map(String.init)
        .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty && !$0.hasPrefix("서버를 내렸습니다") }
    if let tb = lines.lastIndex(where: { $0.hasSuffix("Traceback (most recent call last):") }),
       let exc = lines[(tb + 1)...].first(where: { !$0.hasPrefix(" ") }) {
        return exc.replacingOccurrences(of: #"^[\w.]+\."#, with: "", options: .regularExpression)
    }
    return lines.last ?? ""
}
