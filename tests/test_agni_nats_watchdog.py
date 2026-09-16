import contextlib
import datetime as dt
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
from unittest.mock import patch

SOURCE = pathlib.Path(__file__).resolve().parents[1] / 'scripts/ops/agni_nats_watchdog.py'
spec = importlib.util.spec_from_file_location('watchdog', SOURCE)
watchdog = importlib.util.module_from_spec(spec)
spec.loader.exec_module(watchdog)


class WatchdogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = pathlib.Path(self.tmp.name)
        self.env, self.hb, self.state = root/'bridge.env', root/'heartbeat.json', root/'state.json'
        self.env.write_text("NATS_URL='nats://127.0.0.1:4223'\nNATS_PASSWORD=do-not-emit\n")
        self.hb.write_text(json.dumps({'timestamp': dt.datetime.now(dt.timezone.utc).isoformat()}))

    def run_watchdog(self, probe=(True, 'INFO {"jetstream":true,"cluster":"fleet"}\r\n'), active=True):
        output = io.StringIO()
        with patch.object(watchdog,'BRIDGE_ENV',self.env), patch.object(watchdog,'HEARTBEAT',self.hb), patch.object(watchdog,'STATE',self.state), patch.object(watchdog,'tcp_probe',return_value=probe) as tcp, patch.object(watchdog,'service_active',return_value=active), patch.object(watchdog,'gateway_health',return_value=(True,'')), patch.object(watchdog,'recent_gateway_errors',return_value=[]), contextlib.redirect_stdout(output):
            code=watchdog.main()
        return code,json.loads(self.state.read_text()),output.getvalue(),tcp.call_args_list

    def test_current_transport_healthy_and_cluster_allowed(self):
        code,state,out,calls=self.run_watchdog()
        self.assertEqual(code,0)
        self.assertTrue(state['healthy'])
        self.assertEqual(out,'')
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0].args,('127.0.0.1',4223))

    def test_unavailable_transport_still_alerts(self):
        code,state,out,_=self.run_watchdog((False,'TimeoutError'))
        self.assertEqual(code,1)
        self.assertTrue(any(x.startswith('bridge_transport_down:127.0.0.1:4223') for x in state['problems']))
        self.assertNotIn('do-not-emit',out)

    def test_missing_config_fails_without_legacy_fallback(self):
        self.env.unlink()
        code,state,_,calls=self.run_watchdog()
        self.assertEqual(code,1)
        self.assertEqual(calls,[])
        self.assertIn('bridge_transport_configuration_invalid',state['problems'])

    def test_stale_heartbeat_still_alerts(self):
        self.hb.write_text(json.dumps({'timestamp':'2000-01-01T00:00:00Z'}))
        code,state,_,_=self.run_watchdog()
        self.assertEqual(code,1)
        self.assertTrue(any(x.startswith('bridge_heartbeat_stale:') for x in state['problems']))

    def test_missing_jetstream_or_service_still_alerts(self):
        code,state,_,_=self.run_watchdog((True,'INFO {"jetstream":false}\r\n'),False)
        self.assertEqual(code,1)
        self.assertIn('jetstream_not_advertised',state['problems'])
        self.assertIn('service_inactive:dharma-a2a-nats-tunnel',state['problems'])

    def test_bad_credential_bearing_url_is_not_emitted(self):
        self.env.write_text('NATS_URL=https://user:do-not-emit@example.test\n')
        code,state,out,calls=self.run_watchdog()
        self.assertEqual(code,1)
        self.assertEqual(calls,[])
        self.assertNotIn('do-not-emit',out+json.dumps(state))

    def test_probe_and_health_failures_emit_no_raw_detail(self):
        secret = 'do-not-emit-token'
        with patch.object(watchdog.socket, 'create_connection', side_effect=OSError(secret)):
            ok, detail = watchdog.tcp_probe('127.0.0.1', 4223)
        self.assertEqual((ok, detail), (False, 'OSError'))
        body = io.BytesIO(json.dumps({'ok': False, 'token': secret}).encode())
        body.status = 200
        with patch.object(watchdog.urllib.request, 'urlopen', return_value=body):
            self.assertEqual(watchdog.gateway_health(), (False, 'ok_not_true'))
        with patch.object(watchdog.urllib.request, 'urlopen', side_effect=OSError(secret)):
            self.assertEqual(watchdog.gateway_health(), (False, 'OSError'))
        output = io.StringIO()
        with patch.object(watchdog,'BRIDGE_ENV',self.env), patch.object(watchdog,'HEARTBEAT',self.hb), patch.object(watchdog,'STATE',self.state), patch.object(watchdog.socket,'create_connection',side_effect=OSError(secret)), patch.object(watchdog,'service_active',return_value=True), patch.object(watchdog.urllib.request,'urlopen',return_value=io.BytesIO(json.dumps({'ok': False, 'token': secret}).encode())), patch.object(watchdog,'recent_gateway_errors',return_value=[]), contextlib.redirect_stdout(output):
            self.assertEqual(watchdog.main(), 1)
        emitted = output.getvalue() + self.state.read_text()
        self.assertNotIn(secret, emitted)
        self.assertIn('gateway_unhealthy:', emitted)


if __name__ == '__main__':
    unittest.main()
