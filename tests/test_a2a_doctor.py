import asyncio
import json
import sys
import types

from scripts.runtime import a2a_doctor
from scripts.runtime import pr_merge_control


def test_ca_pem_uses_bundled_fallback(tmp_path, monkeypatch):
    bundled = tmp_path / "agni-ws-ca.pem"
    bundled.write_text("BUNDLED-CA", encoding="utf-8")
    monkeypatch.setattr(pr_merge_control, "DEFAULT_NATS_CA_PEM_PATH", bundled)
    monkeypatch.delenv("DEVIN_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("DHARMA_NATS_CA_PEM", raising=False)
    monkeypatch.delenv("NATS_CA_PEM", raising=False)

    assert a2a_doctor._ca_pem() == "BUNDLED-CA\n"  # noqa: SLF001


def test_probe_outbound_reachability_reports_allowed_denied_and_no_stream(monkeypatch):
    reg = {
        "callsign": "devin",
        "metadata": {
            "coordination_peers": ["codex", "perplexity-computer", "warp_oz", "fable_composer"],
        }
    }
    calls: list[dict[str, object]] = []

    class FakeSubscription:
        async def unsubscribe(self):
            return None

    class FakeJetStream:
        def __init__(self, conn):
            self.conn = conn

        async def publish(self, subject, _data, timeout=None):
            if subject == "dharma.a2a.codex":
                calls.append({"subject": subject, "data": json.loads(_data.decode("utf-8"))})
                return types.SimpleNamespace(stream="DHARMA_A2A", seq=1)
            if subject == "dharma.a2a.warp_oz":
                calls.append({"subject": subject, "data": json.loads(_data.decode("utf-8"))})
                raise RuntimeError("broker client error")
            calls.append({"subject": subject, "data": json.loads(_data.decode("utf-8"))})
            await self.conn.error_cb(
                Exception(f"nats: permissions violation for publish to {subject}")
            )
            raise TimeoutError("pub ack timed out")

    class FakeConnection:
        def __init__(self, error_cb):
            self.error_cb = error_cb
            self.closed = False

        async def subscribe(self, *_args, **_kwargs):
            return FakeSubscription()

        def jetstream(self):
            return FakeJetStream(self)

        async def close(self):
            self.closed = True

    async def fake_connect(**kwargs):
        conn = FakeConnection(kwargs["error_cb"])
        calls.append(kwargs)
        return conn

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace(connect=fake_connect))
    monkeypatch.setattr(a2a_doctor, "_creds", lambda: ("nats://127.0.0.1:4222", "devin", "secret"))
    monkeypatch.setattr(a2a_doctor, "_tls_context", lambda: None)

    rows = asyncio.run(
        a2a_doctor._probe_outbound_reachability(  # noqa: SLF001
            reg,
            ["dharma.a2a.codex", "dharma.a2a.perplexity", "dharma.a2a.warp_oz"],
        )
    )

    assert [row["status"] for row in rows] == [
        "ALLOWED",
        "DENIED(permissions)",
        "PUBLISH_FAILED",
        "NO_STREAM",
    ]
    assert "permissions violation for publish to dharma.a2a.perplexity" in rows[1]["detail"]
    assert rows[2]["detail"] == "broker client error"
    published_subjects = [entry["subject"] for entry in calls if "subject" in entry]
    assert published_subjects == [
        "dharma.a2a.codex",
        "dharma.a2a.perplexity",
        "dharma.a2a.warp_oz",
    ]
    first_publish = next(entry for entry in calls if "data" in entry)
    assert first_publish["data"]["kind"] == "reachability_probe"
    assert first_publish["data"]["from"] == "devin"
    assert first_publish["data"]["note"] == "a2a_doctor --probe-send authorization probe"
    assert first_publish["data"]["subject"] == "dharma.a2a.codex"


def test_main_json_includes_outbound_reachability(monkeypatch, capsys):
    async def fake_gather(scan):
        return {
            "hub": {"stream": "DHARMA_A2A", "messages": 1, "subjects": ["dharma.a2a.codex"]},
            "roster": {},
            "scanned": scan,
        }

    async def fake_probe(reg, live_subjects):
        assert live_subjects == ["dharma.a2a.codex"]
        return [{"lane": "codex", "subject": "dharma.a2a.codex", "status": "ALLOWED", "detail": ""}]

    monkeypatch.setitem(sys.modules, "nats", types.SimpleNamespace())
    monkeypatch.setattr(a2a_doctor, "_load_registration", lambda: {"metadata": {}})
    monkeypatch.setattr(a2a_doctor, "_gather", fake_gather)
    monkeypatch.setattr(a2a_doctor, "_probe_outbound_reachability", fake_probe)

    code = a2a_doctor.main(["--json", "--probe-send"])

    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["outbound_reachability"] == [
        {"lane": "codex", "subject": "dharma.a2a.codex", "status": "ALLOWED", "detail": ""}
    ]
