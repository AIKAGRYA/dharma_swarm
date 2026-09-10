import AppKit
import Foundation
import Darwin

struct MenuConfiguration {
    var values: [String: String] = [:]
    var checkStatus = false
    var checkLifecycle = false

    init(_ arguments: [String]) throws {
        var index = 0
        let allowed = ["--status-file", "--python", "--cli", "--state-dir", "--repo-root", "--profile", "--socket", "--session", "--exec-path", "--build-id", "--check-action-result", "--exit-code"]
        while index < arguments.count {
            let key = arguments[index]
            if key == "--check-status" { checkStatus = true; index += 1; continue }
            if key == "--check-lifecycle" { checkLifecycle = true; index += 1; continue }
            guard allowed.contains(key), index + 1 < arguments.count else {
                throw NSError(domain: "HelmMenu", code: 2,
                              userInfo: [NSLocalizedDescriptionKey: "Unknown or incomplete argument: \(key)"])
            }
            values[key] = arguments[index + 1]
            index += 2
        }
        if checkLifecycle || values["--check-action-result"] != nil { return }
        guard values["--status-file"]?.hasPrefix("/") == true else {
            throw NSError(domain: "HelmMenu", code: 2,
                          userInfo: [NSLocalizedDescriptionKey: "--status-file requires an absolute path"])
        }
        if !checkStatus {
            for key in ["--python", "--cli", "--state-dir", "--repo-root"] {
                guard values[key]?.hasPrefix("/") == true else {
                    throw NSError(domain: "HelmMenu", code: 2,
                                  userInfo: [NSLocalizedDescriptionKey: "\(key) requires an absolute path"])
                }
            }
        }
    }

    func observe() -> DesktopObservation {
        let observation = DesktopStatusReader.read(values["--status-file"]!)
        if let snapshot = observation.snapshot, let repo = values["--repo-root"],
           snapshot.repo_root != repo || snapshot.seat.tmux_socket != (values["--socket"] ?? "CODEX_MANAGED_helm_desktop") ||
            snapshot.seat.tmux_session != (values["--session"] ?? "helm_desktop") {
            return DesktopObservation(availability: "invalid", reason: "snapshot_owner_mismatch")
        }
        return observation
    }
}

final class HelmMenu: NSObject, NSApplicationDelegate {
    let configuration: MenuConfiguration
    var item: NSStatusItem!
    var directoryWatcher: DispatchSourceFileSystemObject?
    var timer: Timer?
    var instance: DesktopMenuInstance?
    lazy var refreshScheduler = DesktopRefreshScheduler { [weak self] in self?.refresh() }
    var actionRunning = false
    var lastMenuKey = ""
    var observation = DesktopObservation(availability: "unavailable", reason: "starting")

    init(configuration: MenuConfiguration) { self.configuration = configuration }

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        refreshScheduler.request()
        watchDirectory()
        timer = DesktopRefreshScheduler.commonTimer(interval: 1, repeats: true) { [weak self] in
            self?.refreshScheduler.request()
            if self?.directoryWatcher == nil { self?.watchDirectory() }
        }
    }

    func watchDirectory() {
        let directory = URL(fileURLWithPath: configuration.values["--status-file"]!).deletingLastPathComponent().path
        let descriptor = Darwin.open(directory, O_EVTONLY | O_CLOEXEC | O_NOFOLLOW)
        guard descriptor >= 0 else { return }
        let source = DispatchSource.makeFileSystemObjectSource(fileDescriptor: descriptor,
                                                               eventMask: [.write, .rename, .delete], queue: .main)
        source.setEventHandler { [weak self] in
            guard let self else { return }
            if self.directoryWatcher?.data.contains(.delete) == true || self.directoryWatcher?.data.contains(.rename) == true {
                self.directoryWatcher?.cancel(); self.directoryWatcher = nil
            }
            self.refreshScheduler.request()
        }
        source.setCancelHandler { Darwin.close(descriptor) }
        directoryWatcher = source
        source.resume()
    }

    func refresh() {
        observation = configuration.observe()
        let menuKey = [observation.title, observation.reason, String(actionRunning),
                       observation.snapshot?.route.requested_provider_id ?? "",
                       observation.snapshot?.route.requested_model_id ?? "",
                       observation.snapshot?.pending_approvals.map(String.init) ?? "unknown"].joined(separator: "\n")
        guard menuKey != lastMenuKey else { return }
        lastMenuKey = menuKey
        item.button?.title = "Helm"
        let menu = NSMenu()
        addAction(menu, title: "Open Workbench", selector: #selector(workbench), key: "h")
        addAction(menu, title: "Close Workbench Window", selector: #selector(closeWorkbench), key: "w")
        menu.addItem(.separator())
        addAction(menu, title: "Open Diagnostics Cockpit", selector: #selector(focus), key: "d")
        addAction(menu, title: "Close Diagnostics Window", selector: #selector(closeDiagnostics), key: "")
        let status = NSMenuItem(title: "Diagnostics: \(observation.availability)", action: nil, keyEquivalent: "")
        status.isEnabled = false
        menu.addItem(status)
        if let snapshot = observation.snapshot {
            let requested = [snapshot.route.requested_provider_id, snapshot.route.requested_model_id]
                .compactMap { $0 }.joined(separator: " / ")
            if !requested.isEmpty { menu.addItem(withTitle: "Diagnostic chat: \(requested)", action: nil, keyEquivalent: "") }
        }
        menu.addItem(.separator())
        addAction(menu, title: "Open Workspace", selector: #selector(workspace), key: "r")
        menu.addItem(.separator())
        addAction(menu, title: "Quit Menu", selector: #selector(quit), key: "q")
        item.menu = menu
    }

    func addAction(_ menu: NSMenu, title: String, selector: Selector, key: String) {
        let entry = NSMenuItem(title: title, action: selector, keyEquivalent: key)
        entry.target = self
        entry.isEnabled = !actionRunning || selector == #selector(quit)
        menu.addItem(entry)
    }

    @objc func focus() { runAction(["focus"]) }
    @objc func workbench() { runAction(["workbench", "open"]) }
    @objc func closeWorkbench() { runAction(["workbench", "close"]) }
    @objc func closeDiagnostics() { runAction(["close"]) }
    @objc func workspace() { runAction(["workspace", "open"]) }
    @objc func quit() { NSApp.terminate(nil) }

    func runAction(_ arguments: [String]) {
        guard !actionRunning else { return }
        actionRunning = true
        refreshScheduler.request()
        let process = Process()
        process.executableURL = URL(fileURLWithPath: configuration.values["--python"]!)
        process.currentDirectoryURL = URL(fileURLWithPath: configuration.values["--repo-root"]!)
        var environment = ProcessInfo.processInfo.environment
        environment["PATH"] = configuration.values["--exec-path"] ?? "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
        environment["DHARMA_PYTHON"] = configuration.values["--python"]!
        process.environment = environment
        process.arguments = [configuration.values["--cli"]!, "--json",
                             "--state-dir", configuration.values["--state-dir"]!,
                             "--repo-root", configuration.values["--repo-root"]!,
                             "--socket", configuration.values["--socket"] ?? "CODEX_MANAGED_helm_desktop",
                             "--session", configuration.values["--session"] ?? "helm_desktop",
                             "--profile", configuration.values["--profile"] ?? "research"] + arguments
        let output = Pipe()
        process.standardOutput = output
        process.standardError = output
        do { try process.run() } catch {
            finishAction(DesktopActionNotice(title: "Helm could not start this action", detail: error.localizedDescription, failed: true))
            return
        }
        // All waiting and pipe draining happen off the AppKit thread. No shell
        // interpolation and no process is launched merely to refresh status.
        DispatchQueue.global(qos: .userInitiated).async {
            var retained = Data()
            while let chunk = try? output.fileHandleForReading.read(upToCount: 8192), !chunk.isEmpty {
                if retained.count < 65_536 { retained.append(chunk.prefix(65_536 - retained.count)) }
            }
            process.waitUntilExit()
            let notice = DesktopActionNotice.parse(retained, exitStatus: process.terminationStatus)
            let result = (try? JSONSerialization.jsonObject(with: retained)) as? [String: Any]
            DispatchQueue.main.async {
                // Bring the dedicated GUI forward, including from another Space.
                // A generic "open WezTerm" can focus the operator's other window.
                if arguments == ["workbench", "open"], result?["ok"] as? Bool == true,
                   let pid = result?["gui_pid"] as? Int32,
                   let app = NSRunningApplication(processIdentifier: pid),
                   app.bundleIdentifier == "com.github.wez.wezterm" {
                    app.activate(options: [.activateAllWindows])
                }
                self.finishAction(notice)
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 45) { if process.isRunning { process.terminate() } }
    }

    func finishAction(_ notice: DesktopActionNotice?) {
        actionRunning = false
        refreshScheduler.request()
        if let notice {
            let alert = NSAlert()
            alert.alertStyle = notice.failed ? .warning : .informational
            alert.messageText = notice.title
            alert.informativeText = notice.detail
            alert.runModal()
        }
    }
}

do {
    let configuration = try MenuConfiguration(Array(CommandLine.arguments.dropFirst()))
    if configuration.checkStatus || configuration.checkLifecycle || configuration.values["--check-action-result"] != nil {
        let result: [String: Any]
        if configuration.checkLifecycle { result = try checkDesktopLifecycle() }
        else if let file = configuration.values["--check-action-result"] {
            let data = try Data(contentsOf: URL(fileURLWithPath: file))
            guard data.count <= 65_536 else { throw NSError(domain: "HelmMenu", code: 2) }
            let notice = DesktopActionNotice.parse(data, exitStatus: Int32(configuration.values["--exit-code"] ?? "0") ?? 0)
            result = notice?.diagnostic ?? ["notice": NSNull()]
        } else { result = configuration.observe().diagnostic }
        let data = try JSONSerialization.data(withJSONObject: result, options: [.sortedKeys])
        print(String(decoding: data, as: UTF8.self))
    } else {
        let instance = try DesktopMenuInstance(stateDirectory: configuration.values["--state-dir"]!, configuration: configuration.values)
        let application = NSApplication.shared
        let delegate = HelmMenu(configuration: configuration)
        delegate.instance = instance
        application.delegate = delegate
        application.run()
        withExtendedLifetime(delegate) {}
    }
} catch {
    FileHandle.standardError.write(Data("\(error.localizedDescription)\n".utf8))
    exit(2)
}
