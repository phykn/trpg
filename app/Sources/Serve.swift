import Foundation

// app/build.sh writes both into Info.plist; PATH is the building shell's, so `node` and `cloudflared` resolve as there.
let root = URL(fileURLWithPath: Bundle.main.infoDictionary?["ProjectRoot"] as? String ?? "")
let shellPath = Bundle.main.infoDictionary?["Path"] as? String ?? "/usr/bin:/bin"
let logURL = root.appendingPathComponent("logs/server.log")
let apiPort: UInt16 = 8000

// client/scripts/serve.cjs runs the API, a tunnel to it and the watchers, and writes how far it got to this file.
private let stateURL = root.appendingPathComponent("logs/serve.json")

struct ServeState: Decodable {
    var ready = false
    var address: String?
    var deploying = false
    var error: String?
}

func readServeState() -> ServeState {
    guard let data = try? Data(contentsOf: stateURL) else { return ServeState() }
    return (try? JSONDecoder().decode(ServeState.self, from: data)) ?? ServeState()
}

// In its own process group, so a stop also reaches what the script spawned; output goes to the log.
func spawnServe(env extra: [String: String]) throws -> pid_t {
    try FileManager.default.createDirectory(at: logURL.deletingLastPathComponent(), withIntermediateDirectories: true)
    try? FileManager.default.removeItem(at: stateURL)   // a file left by the last run would read as this run's
    var env = ProcessInfo.processInfo.environment
    env["PATH"] = shellPath
    env["PYTHONUNBUFFERED"] = "1"   // so the log shows the API's lines as they happen
    env.merge(extra) { $1 }

    var actions: posix_spawn_file_actions_t?
    posix_spawn_file_actions_init(&actions)
    defer { posix_spawn_file_actions_destroy(&actions) }
    posix_spawn_file_actions_addopen(&actions, 0, "/dev/null", O_RDONLY, 0)
    posix_spawn_file_actions_addopen(&actions, 1, logURL.path, O_WRONLY | O_CREAT | O_TRUNC, 0o644)
    posix_spawn_file_actions_adddup2(&actions, 1, 2)
    posix_spawn_file_actions_addchdir(&actions, root.appendingPathComponent("client").path)
    var attr: posix_spawnattr_t?
    posix_spawnattr_init(&attr)
    defer { posix_spawnattr_destroy(&attr) }
    posix_spawnattr_setflags(&attr, Int16(POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_CLOEXEC_DEFAULT))
    posix_spawnattr_setpgroup(&attr, 0)

    let argv = (["/usr/bin/env", "node", "scripts/serve.cjs"] as [String]).map { strdup($0) } + [nil]
    let envp = env.map { strdup("\($0.key)=\($0.value)") } + [nil]
    defer { (argv + envp).forEach { free($0) } }
    var pid: pid_t = 0
    let rc = posix_spawn(&pid, "/usr/bin/env", &actions, &attr, argv, envp)
    guard rc == 0 else { throw POSIXError(POSIXErrorCode(rawValue: rc) ?? .EIO) }
    return pid
}

// The script gets SIGTERM alone first: it stops its own children and clears the tunnel URL from KV, which takes a
// few seconds. Whatever is left of the group after that is killed. Blocks until the group is gone: call it off the
// main thread.
func stopGroup(_ pg: pid_t) {
    kill(pg, SIGTERM)
    var waited = 0
    while kill(-pg, 0) == 0 && waited < 150 {
        usleep(100_000)
        waited += 1
    }
    kill(-pg, SIGKILL)
}

// "localhost" resolves to both loopbacks: uvicorn binds 127.0.0.1, Expo may bind ::1.
func isListening(_ port: UInt16) -> Bool {
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
