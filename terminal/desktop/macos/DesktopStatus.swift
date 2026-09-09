import Foundation
import Darwin

// Foundation's dictionary decoders accept duplicate keys. Check their decoded
// spelling before projecting a snapshot, including escaped duplicate spellings.
enum UniqueJSONKeys {
    static func accepts(_ data: Data) -> Bool {
        struct Container { var object: Bool; var expectsKey = true; var keys = Set<String>() }
        let bytes = Array(data)
        var stack: [Container] = []
        var index = 0
        while index < bytes.count {
            switch bytes[index] {
            case 123: stack.append(Container(object: true))
            case 91: stack.append(Container(object: false))
            case 125, 93: if !stack.isEmpty { stack.removeLast() }
            case 44: if !stack.isEmpty { stack[stack.count - 1].expectsKey = true }
            case 34:
                let start = index
                index += 1
                while index < bytes.count && bytes[index] != 34 {
                    if bytes[index] == 92 { index += 1 }
                    index += 1
                }
                guard index < bytes.count else { return false }
                if let container = stack.last, container.object && container.expectsKey {
                    guard let key = try? JSONDecoder().decode(String.self, from: Data(bytes[start...index])) else { return false }
                    guard stack[stack.count - 1].keys.insert(key).inserted else { return false }
                    stack[stack.count - 1].expectsKey = false
                }
            default: break
            }
            index += 1
        }
        return true
    }
}

// Read-only consumer of dharma.helm.desktop_status.v1. This process never owns
// sessions or infers that a requested model has actually served a response.
struct DesktopOwner: Decodable { let id: String; let pid: Int32; let epoch: String }
struct DesktopRoute: Decodable {
    let requested_provider_id: String?
    let requested_model_id: String?
}
struct DesktopSeat: Decodable { let tmux_socket: String?; let tmux_session: String? }
struct DesktopSnapshot: Decodable {
    let schema_version: String
    let authority: String
    let owner: DesktopOwner
    let sequence: Int
    let observed_at: String
    let expires_at: String
    let phase: String
    let session_id: String?
    let request_id: String?
    let route: DesktopRoute
    let pending_approvals: Int?
    let repo_root: String
    let seat: DesktopSeat
}

struct DesktopObservation {
    let availability: String
    let reason: String
    var snapshot: DesktopSnapshot? = nil

    var title: String {
        if availability == "fresh", let snapshot { return "Helm · \(snapshot.phase)" }
        return "Helm · \(availability == "stale" ? "stale" : "offline")"
    }

    var diagnostic: [String: Any] {
        var result: [String: Any] = ["availability": availability, "reason": reason,
                                    "title": title, "authority": "observation_only"]
        if let snapshot {
            result["owner_id"] = snapshot.owner.id
            result["owner_epoch"] = snapshot.owner.epoch
            result["phase"] = snapshot.phase
            result["sequence"] = snapshot.sequence
        }
        return result
    }
}

enum DesktopStatusReader {
    static let maximumBytes = 65_536
    static let dateWithFractions: ISO8601DateFormatter = {
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return formatter
    }()
    static let dateWithoutFractions = ISO8601DateFormatter()

    static func date(_ value: String) -> Date? {
        dateWithFractions.date(from: value) ?? dateWithoutFractions.date(from: value)
    }

    static func matches(_ value: String, _ pattern: String) -> Bool {
        value.range(of: pattern, options: .regularExpression) != nil
    }

    static func exactFields(_ value: Any?, _ fields: [String]) -> Bool {
        guard let object = value as? [String: Any] else { return false }
        return Set(object.keys) == Set(fields)
    }

    static func read(_ path: String, now: Date? = nil) -> DesktopObservation {
        func invalid(_ reason: String) -> DesktopObservation {
            DesktopObservation(availability: "invalid", reason: reason)
        }
        guard path.hasPrefix("/"), !path.split(separator: "/").contains(".."),
              !path.contains("\n"), !path.contains("\r") else {
            return invalid("unsafe_status_path")
        }
        // Resolve each directory through its descriptor, avoiding ancestor link
        // races as well as symlink leaves. The bridge publishes with renameat.
        let components = path.split(separator: "/").map(String.init)
        guard let leaf = components.last else { return invalid("unsafe_status_path") }
        var parent = Darwin.open("/", O_RDONLY | O_DIRECTORY | O_CLOEXEC)
        for component in components.dropLast() {
            let next = openat(parent, component, O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC)
            Darwin.close(parent)
            guard next >= 0 else {
                return DesktopObservation(availability: errno == ENOENT ? "unavailable" : "invalid", reason: "status_unreadable")
            }
            parent = next
        }
        let descriptor = openat(parent, leaf, O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        let openError = errno
        Darwin.close(parent)
        guard descriptor >= 0 else {
            return DesktopObservation(availability: openError == ELOOP ? "invalid" : "unavailable", reason: "status_unreadable")
        }
        defer { Darwin.close(descriptor) }
        var info = stat()
        guard fstat(descriptor, &info) == 0,
              (info.st_mode & S_IFMT) == S_IFREG, info.st_uid == getuid(), info.st_nlink == 1,
              (info.st_mode & 0o077) == 0, info.st_size > 0,
              info.st_size <= maximumBytes else { return invalid("unsafe_status_file") }
        var bytes = [UInt8](repeating: 0, count: maximumBytes + 1)
        let count = Darwin.read(descriptor, &bytes, bytes.count)
        guard count > 0, count <= maximumBytes else { return invalid("invalid_status_size") }
        let data = Data(bytes.prefix(count))
        guard UniqueJSONKeys.accepts(data),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              exactFields(object, ["schema_version", "authority", "owner", "sequence", "observed_at", "expires_at", "phase", "session_id", "request_id", "route", "pending_approvals", "repo_root", "seat"]),
              exactFields(object["owner"], ["id", "pid", "epoch"]),
              exactFields(object["route"], ["requested_provider_id", "requested_model_id"]),
              exactFields(object["seat"], ["tmux_socket", "tmux_session"]),
              let snapshot = try? JSONDecoder().decode(DesktopSnapshot.self, from: data) else {
            return invalid("invalid_status_json")
        }
        let clock = now ?? Date()
        let identifier = "^[A-Za-z0-9][A-Za-z0-9._:/@+\\-]{0,255}$"
        let identifiers = [snapshot.owner.id, snapshot.owner.epoch, snapshot.session_id,
                           snapshot.request_id, snapshot.route.requested_provider_id,
                           snapshot.route.requested_model_id].compactMap { $0 }
        guard snapshot.schema_version == "dharma.helm.desktop_status.v1",
              snapshot.authority == "observation_only", identifiers.allSatisfy({ matches($0, identifier) }),
              snapshot.owner.pid > 0, snapshot.sequence > 0,
              ["starting", "idle", "running", "cancelling", "closed"].contains(snapshot.phase),
              snapshot.repo_root.hasPrefix("/"), snapshot.repo_root.count <= 4096,
              !snapshot.repo_root.unicodeScalars.contains(where: { $0.value < 32 }),
              snapshot.pending_approvals == nil || (snapshot.pending_approvals! >= 0 && snapshot.pending_approvals! < 2_147_483_648),
              [snapshot.observed_at, snapshot.expires_at].allSatisfy({ $0.count <= 40 && ($0.hasSuffix("Z") || $0.hasSuffix("+00:00")) }),
              let observed = date(snapshot.observed_at), let expires = date(snapshot.expires_at),
              expires > observed, expires.timeIntervalSince(observed) <= 3.000001,
              observed <= clock else { return invalid("invalid_status_schema") }
        let seat = snapshot.seat
        if let socket = seat.tmux_socket, let session = seat.tmux_session {
            guard matches(socket, "^CODEX_MANAGED_[A-Za-z0-9_-]{1,100}$"),
                  matches(session, "^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$") else {
                return invalid("invalid_status_seat")
            }
        } else if seat.tmux_socket != nil || seat.tmux_session != nil {
            return invalid("invalid_status_seat")
        }
        if snapshot.phase == "closed" {
            return DesktopObservation(availability: "stale", reason: "owner_closed", snapshot: snapshot)
        }
        if expires <= clock {
            return DesktopObservation(availability: "stale", reason: "status_expired", snapshot: snapshot)
        }
        if kill(snapshot.owner.pid, 0) != 0 {
            return DesktopObservation(availability: errno == ESRCH ? "stale" : "unavailable",
                                      reason: errno == ESRCH ? "owner_not_running" : "owner_not_verifiable", snapshot: snapshot)
        }
        return DesktopObservation(availability: "fresh", reason: "owner_observed", snapshot: snapshot)
    }
}
