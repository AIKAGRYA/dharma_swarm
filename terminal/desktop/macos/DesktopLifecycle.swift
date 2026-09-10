import AppKit
import Foundation
import Darwin

// One pending trailing refresh keeps bursts bounded without dropping the last
// owner update. Common-mode timers continue while AppKit tracks the menu.
final class DesktopRefreshScheduler {
    private let interval: TimeInterval
    private let action: () -> Void
    private var lastFire = -Double.infinity
    private var pending: Timer?

    init(interval: TimeInterval = 0.02, action: @escaping () -> Void) {
        self.interval = interval; self.action = action
    }

    static func commonTimer(interval: TimeInterval, repeats: Bool, action: @escaping () -> Void) -> Timer {
        let timer = Timer(timeInterval: interval, repeats: repeats) { _ in action() }
        RunLoop.main.add(timer, forMode: .common)
        return timer
    }

    func request() {
        let remaining = interval - (ProcessInfo.processInfo.systemUptime - lastFire)
        if remaining <= 0 {
            pending?.invalidate(); pending = nil
            fire()
        } else if pending == nil {
            pending = Self.commonTimer(interval: remaining, repeats: false) { [weak self] in
                self?.pending = nil
                self?.fire()
            }
        }
    }

    private func fire() { lastFire = ProcessInfo.processInfo.systemUptime; action() }
    deinit { pending?.invalidate() }
}

struct DesktopActionNotice {
    let title: String
    let detail: String
    let failed: Bool

    static func parse(_ data: Data, exitStatus: Int32) -> DesktopActionNotice? {
        let object = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
        let failed = exitStatus != 0 || object?["ok"] as? Bool == false
        let outcome = object?["outcome"] as? String ?? ""
        guard failed || outcome == "attached_elsewhere" || outcome == "attachment_pending" else { return nil }
        let title = failed ? "Helm could not complete this action" :
            outcome == "attached_elsewhere" ? "Helm is attached in another terminal" : "Helm attachment is still pending"
        let fallback = failed ? (String(data: data, encoding: .utf8) ?? "Desktop action failed") :
            "The existing Helm seat is unchanged. Check the terminal where it is already attached."
        let detail = object?["error"] as? String ?? object?["detail"] as? String ?? fallback
        return DesktopActionNotice(title: title, detail: String(detail.prefix(1200)), failed: failed)
    }

    var diagnostic: [String: Any] { ["title": title, "detail": detail, "failed": failed] }
}

// The lock proves only that this private menu instance is alive. Configuration
// identity permits reuse; it never grants authority to execute another action.
final class DesktopMenuInstance {
    private let directory: Int32
    private let lock: Int32

    init(stateDirectory: String, configuration: [String: String]) throws {
        func failure(_ message: String) -> NSError {
            NSError(domain: "HelmMenu", code: 3, userInfo: [NSLocalizedDescriptionKey: message])
        }
        guard stateDirectory.hasPrefix("/"), !stateDirectory.split(separator: "/").contains("..") else {
            throw failure("Menu state directory must be an absolute private path")
        }
        var parent = Darwin.open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        for component in stateDirectory.split(separator: "/") {
            let next = openat(parent, String(component), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            Darwin.close(parent)
            guard next >= 0 else { throw failure("Menu state directory is missing or unsafe") }
            parent = next
        }
        let descriptor = openat(parent, "menu-instance.lock", O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0o600)
        var info = stat()
        guard descriptor >= 0, fstat(descriptor, &info) == 0, (info.st_mode & S_IFMT) == S_IFREG,
              info.st_uid == getuid(), info.st_nlink == 1, (info.st_mode & 0o077) == 0,
              flock(descriptor, LOCK_EX | LOCK_NB) == 0 else {
            if descriptor >= 0 { Darwin.close(descriptor) }; Darwin.close(parent)
            throw failure("A menu already owns this state directory, or its lock is unsafe")
        }
        directory = parent; lock = descriptor
        let receipt: [String: Any] = ["schema": "dharma.helm.menu_instance.v1", "pid": getpid(),
                                      "configuration": configuration]
        let temporary = ".menu-instance-\(UUID().uuidString).json"
        let output = openat(directory, temporary, O_CREAT | O_EXCL | O_WRONLY | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard output >= 0 else { throw failure("Could not create the menu instance receipt") }
        defer { Darwin.close(output); unlinkat(directory, temporary, 0) }
        let data = try JSONSerialization.data(withJSONObject: receipt, options: [.sortedKeys])
        let written = data.withUnsafeBytes { Darwin.write(output, $0.baseAddress, $0.count) }
        guard written == data.count, fsync(output) == 0,
              renameat(directory, temporary, directory, "menu-instance.json") == 0 else {
            throw failure("Could not publish the menu instance receipt")
        }
    }

    deinit { Darwin.close(lock); Darwin.close(directory) }
}

func checkDesktopLifecycle() throws -> [String: Any] {
    // AppKit marks tracking as a common mode. The headless probe registers that
    // relationship explicitly without creating an application or status item.
    CFRunLoopAddCommonMode(CFRunLoopGetCurrent(), CFRunLoopMode(rawValue: RunLoop.Mode.eventTracking.rawValue as CFString))
    var refreshTimes: [TimeInterval] = []
    let scheduler = DesktopRefreshScheduler { refreshTimes.append(ProcessInfo.processInfo.systemUptime) }
    let started = ProcessInfo.processInfo.systemUptime
    scheduler.request()
    scheduler.request()
    scheduler.request()
    var timerTicks = 0
    let expiryTimer = DesktopRefreshScheduler.commonTimer(interval: 0.005, repeats: true) { timerTicks += 1 }
    while ProcessInfo.processInfo.systemUptime - started < 0.09 {
        _ = RunLoop.current.run(mode: .eventTracking, before: Date().addingTimeInterval(0.01))
    }
    expiryTimer.invalidate()
    return ["measurement": "headless_common_mode_lifecycle", "refresh_count": refreshTimes.count,
            "trailing_refresh_seconds": refreshTimes.count > 1 ? refreshTimes[1] - started : -1,
            "expiry_ticks_during_menu_tracking": timerTicks]
}
