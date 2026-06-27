# Source Audit Required for fable_composer

Return one SemanticReceipt JSON object. This prompt includes real source excerpts from the current local checkout. You are auditing those excerpts, not merely the A2A packet.

Mandatory if you inspect the code below: include extra field "source_audit_claim": true and include this gate exactly: {"name":"source_audit_inspected_current_holon_source","condition":"auditor inspected current local holon source excerpts and source proof manifest","met":true}. If you do not inspect the code, set source_audit_claim=false.

Do not claim: multi-hour proof, clean immutable git, cloud source review, authenticated target runtime. Dirty git and multi_hour_proven=false are blockers for a Hermes-grade final pass.

A2A evidence: delivered packet_id=holon-source-audit-fable-20260626, target=fable_composer, envelope_sha256=5a81762b1e8fdc50f0760b3036214316c0db3157b956f6b28ca2ee076e271e55, source_subject=dharma.agent.fable_composer.inbox.

Verification evidence: 23/23 holon tests passed; 74/74 targeted tests passed; compileall passed; source-tree verify passed; isolated wheel verify passed; bounded burn-ins passed but multi_hour_proven=false.

Source proof: ```json
{"file_count": 24, "git_dirty": true, "git_head": "01d22b94fc05bf4bb248c2f51b09102377129d25", "git_status_short_digest": "sha256:49c4410178a0bcc22caac00e9f7e974493b9a368ae11048631cebd27850b6fca", "source_tree_digest": "sha256:a5d1cf467830ae6efe4ab989bd41a17e09bb35e90f497790d1d0e8af9956bffe"}
```

Audit questions: isolation from parent dharma_swarm in installed holon package; provider/tool/budget/artifact gates; service lock/heartbeat; parent truth projection honesty; remaining Hermes-grade blockers.

## holon/holon_runtime.py (sha256:bfe13b56848d2ccf9de51a92b377240c674f9c3274200f79332f06ad51ca836b)

```python
95:         request = self._request(prompt)
96:         try:
97:             response = await self.provider_router.complete(request)
98:             result = HolonCycleResult(
99:                 status="ran",
100:                 reply=response.content,
101:                 task=prompt,
102:                 cycle=cycle,
103:                 provider=response.provider,
104:                 model=response.model,
105:                 cost_usd=response.cost_usd,
106:                 finish_reason=response.finish_reason,
107:                 provider_attempts=response.attempts,
108:                 artifacts=list(response.artifacts or []),
109:                 tool_calls=list(response.tool_calls or []),
110:             )
111:             self._execute_tool_calls(result)
112:             if cap_usd > 0 and spent_usd + result.cost_usd > cap_usd:
113:                 result.status = "halted:budget"
114:                 result.reply = ""
115:                 result.metadata["cap_usd"] = cap_usd
116:                 result.metadata["spent_usd"] = spent_usd + result.cost_usd
117:         except Exception as exc:
118:             result = HolonCycleResult(
119:                 status="halted:error",
120:                 reply="",
121:                 task=prompt,
122:                 cycle=cycle,
123:                 error=f"{type(exc).__name__}: {exc}"[:300],
124:             )
125:         self._apply_artifact_gate(result)
126:         return self._record(
127:             result,
128:             side_effect_key=side_effect_key or _cycle_side_effect_key(self.holon.name, prompt, cycle),
129:         )
130: 
131:     def _request(self, prompt: str) -> LLMRequest:
132:         context = _memory_context(self.holon.name, self.memory_kernel)
133:         return build_request(
134:             self.holon,
135:             prompt,
136:             livingdock_context=context or None,
137:             request_model=self.holon.model,
138:             tools=self.tool_registry.list_specs(),
139:         )
140: 
141:     def _apply_artifact_gate(self, result: HolonCycleResult) -> None:
142:         if result.status != "ran":
143:             return
144:         if _OUTCOME_RE.search(result.reply or "") and not result.artifacts:
145:             result.status = "halted:unverified"
146:             result.metadata["outcome_claim_without_artifact"] = True
147: 
148:     def _execute_tool_calls(self, result: HolonCycleResult) -> None:
149:         envelope = _tool_call_envelope(result.reply)
150:         if envelope is None:
151:             return
152:         result.reply = envelope["content"]
153:         failed = False
154:         for call in envelope["tool_calls"]:
155:             tool_result = self.tool_registry.run(call.name, call.arguments)
156:             result.tool_calls.append(tool_result.record)
157:             if tool_result.artifact is not None:
158:                 result.artifacts.append(tool_result.artifact)
159:             if tool_result.record.status != "success":
160:                 failed = True
161:         if failed:
162:             result.status = "halted:tool"
163:             result.metadata["tool_call_failure"] = True
164: 
165:     def _record(self, result: HolonCycleResult, *, side_effect_key: str) -> HolonCycleResult:
166:         if result.status in {"ran", "halted:error", "halted:unverified", "halted:tool"}:
167:             try:
168:                 signal = compass.log_signal(
169:                     self.holon.name,
170:                     result.task,
171:                     result.reply,
172:                     agents_root=self.agents_root,
173:                 )
174:                 result.metadata["signal"] = signal
175:             except Exception:
176:                 logger.debug("[holon %s] compass signal skipped", self.holon.name, exc_info=True)
177:             event = persistence.save_cycle_record(
178:                 self.holon.name,
179:                 result.to_dict(),
180:                 agents_root=self.agents_root,
181:             )
182:             result.cycle = int(event["cycle"])
183:         receipt_ref = self.truth.record_cycle(result, side_effect_key=side_effect_key)
184:         result.receipt_refs.append(receipt_ref["path"])
185:         return result
186: 
187: 
188: def _persist(name: str, result: dict[str, Any], agents_root: Path | None) -> None:
189:     if agents_root is None:
190:         return
191:     try:
192:         persistence.save_cycle_record(name, result, agents_root=agents_root)
193:     except Exception:
194:         logger.debug("[holon %s] persist skipped", name, exc_info=True)
195: 
196: 
197: async def holon_wake_cycle(
198:     name: str,
199:     agent_runner: AgentRunner,
200:     *,
201:     spent_usd: float,
202:     cap_usd: float,
203:     agents_root: Path | None = None,
204:     persist: bool = True,
205:     memory_kernel: Any | None = None,
206: ) -> dict[str, Any]:
207:     root = agents_root or Path.home() / ".dharma" / "agents"
208:     if killswitch.is_kill_requested(name, agents_root=root):
209:         return {"status": "halted:kill"}
210:     try:
211:         budget_guard.check_cost_cap(name, spent_usd, cap_usd)
212:     except CostLimitExceeded as exc:
213:         return {"status": "halted:budget", "spent_usd": exc.spent, "cap_usd": exc.cap}
214: 
215:     task_for_runner = name
216:     summary_lines = _memory_summary_lines(memory_kernel)
217:     context_injected = bool(summary_lines)
218:     if summary_lines:
219:         task_for_runner = (
220:             f"{name}\n\n"
```

```python
285:             persist=persist,
286:             memory_kernel=memory_kernel,
287:         )
288:         if result.get("status") == "ran" and not result.get("outcome_claim_without_artifact"):
289:             clean_passk_streak += 1
290:         else:
291:             clean_passk_streak = 0
292:         result["passk_streak_after"] = clean_passk_streak
293:         results.append(result)
294:         if result["status"] != "ran":
295:             break
296:     return results
297: 
298: 
299: def runtime_from_identity(name: str, *, agents_root: Path | None = None) -> HolonRuntime:
300:     root = agents_root or Path.home() / ".dharma" / "agents"
301:     holon = load_holon(name, agents_root=root)
302:     return HolonRuntime(holon, agents_root=root)
303: 
304: 
305: def artifact_ref(path: Path, *, kind: str = "file") -> ArtifactRef:
306:     text = path.read_bytes()
307:     return ArtifactRef(
308:         kind=kind,
309:         path=str(path),
310:         digest="sha256:" + hashlib.sha256(text).hexdigest(),
311:     )
312: 
313: 
314: def _memory_context(name: str, memory_kernel: Any | None) -> str:
315:     del name
316:     return "\n".join(_memory_summary_lines(memory_kernel))
317: 
318: 
319: def _memory_summary_lines(memory_kernel: Any | None) -> list[str]:
320:     if memory_kernel is None:
321:         return []
322:     try:
323:         budget = MemoryContextBudget(
324:             max_candidate_atoms=30,
325:             max_admitted_atoms=6,
326:             max_total_chars=1800,
327:             include_content=True,
328:         )
329:         pack = memory_kernel.preview_memory_pack(
330:             surface_ids=None,
331:             atom_types=None,
332:             query=None,
333:             budget=budget,
334:         )
335:         lines = []
336:         for item in list(getattr(pack, "items", ()) or ())[:6]:
337:             src = getattr(item, "surface_id", "memory")
338:             txt = getattr(item, "content_snippet", None) or getattr(item, "content", None) or ""
339:             if txt:
340:                 lines.append(f"<source:memory:{src}> {str(txt)[:280]}")
341:         return lines
342:     except Exception:
343:         logger.debug("memory context pack injection skipped", exc_info=True)
344:         return []
345: 
346: 
347: def _cycle_side_effect_key(name: str, task: str, cycle: int | None) -> str:
348:     return stable_digest({"holon": name, "task": task, "cycle": cycle})
349: 
350: 
```

## holon/providers.py (sha256:e964acd2238579606c9ee94ceef55db83bfc04a11eb5e97dc752f4a1702ccb2e)

```python
128: class ProviderRouter:
129:     def __init__(self, providers: list[Provider], *, retries: int = 1, max_cost_usd: float = 0.0) -> None:
130:         self.providers = providers or [EchoProvider()]
131:         self.retries = max(1, int(retries))
132:         self.max_cost_usd = max_cost_usd
133: 
134:     async def complete(self, request: LLMRequest) -> ProviderResponse:
135:         attempts: list[ProviderAttempt] = []
136:         spent = 0.0
137:         for provider in self.providers:
138:             for _ in range(self.retries):
139:                 started = time.perf_counter()
140:                 try:
141:                     completion = await _complete_provider(provider, request)
142:                     latency_ms = int((time.perf_counter() - started) * 1000)
143:                     spent += float(completion.cost_usd or 0.0)
144:                     if self.max_cost_usd > 0 and spent > self.max_cost_usd:
145:                         raise RuntimeError(
146:                             f"provider cost cap exceeded: spent={spent:.6f} cap={self.max_cost_usd:.6f}"
147:                         )
148:                     attempt = ProviderAttempt(
149:                         provider=provider.name,
150:                         model=completion.model or request.model or provider.model,
151:                         status="success",
152:                         latency_ms=latency_ms,
153:                         cost_usd=float(completion.cost_usd or 0.0),
154:                         finish_reason=completion.finish_reason,
155:                     )
156:                     attempts.append(attempt)
157:                     return ProviderResponse(
158:                         content=completion.content,
159:                         provider=completion.provider or provider.name,
160:                         model=completion.model or request.model or provider.model,
161:                         finish_reason=completion.finish_reason,
162:                         cost_usd=spent,
163:                         attempts=attempts,
164:                         artifacts=completion.artifacts,
165:                         tool_calls=completion.tool_calls,
166:                         usage=completion.usage,
167:                     )
168:                 except Exception as exc:
169:                     latency_ms = int((time.perf_counter() - started) * 1000)
170:                     attempts.append(
171:                         ProviderAttempt(
172:                             provider=getattr(provider, "name", "unknown"),
173:                             model=request.model or getattr(provider, "model", ""),
174:                             status="failed",
175:                             latency_ms=latency_ms,
176:                             error=f"{type(exc).__name__}: {exc}"[:300],
177:                         )
178:                     )
179:                 if self.max_cost_usd > 0 and spent >= self.max_cost_usd:
180:                     break
181:         errors = "; ".join(attempt.error for attempt in attempts if attempt.error)
182:         raise RuntimeError(f"all providers failed: {errors}")
183: 
184:     async def stream(self, request: LLMRequest) -> AsyncIterator[str]:
185:         response = await self.complete(request)
186:         yield response.content
187: 
188: 
189: def build_provider_router(
190:     env: dict[str, str] | None = None,
191:     *,
192:     preferred_provider: str = "auto",
193:     model: str = "",
194: ) -> ProviderRouter:
195:     env_map = env if env is not None else os.environ
196:     preferred = (preferred_provider or "auto").strip().lower()
197:     providers: list[Provider] = []
198: 
199:     def add_openai() -> None:
200:         openai_key = env_map.get("OPENAI_API_KEY")
201:         if not openai_key:
202:             return
203:         providers.append(
204:             OpenAICompatibleProvider(
205:                 name="openai",
206:                 api_key=openai_key,
207:                 base_url=env_map.get("OPENAI_BASE_URL", "https://api.openai.com/v1"),
208:                 model=model or env_map.get("OPENAI_MODEL", "gpt-4.1-mini"),
209:             )
210:         )
211: 
212:     def add_openrouter() -> None:
213:         openrouter_key = env_map.get("OPENROUTER_API_KEY")
214:         if not openrouter_key:
215:             return
216:         providers.append(
217:             OpenAICompatibleProvider(
218:                 name="openrouter",
219:                 api_key=openrouter_key,
220:                 base_url=env_map.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
```

```python
221:                 model=model or env_map.get("OPENROUTER_MODEL", "openai/gpt-4.1-mini"),
222:             )
223:         )
224: 
225:     if preferred == "echo":
226:         providers.append(EchoProvider(model=model or env_map.get("HOLON_ECHO_MODEL", "holon-echo-v1")))
227:     elif preferred == "openai":
228:         add_openai()
229:     elif preferred == "openrouter":
230:         add_openrouter()
231:     else:
232:         add_openai()
233:         add_openrouter()
234:     if not providers or preferred != "echo":
235:         providers.append(EchoProvider(model=model or env_map.get("HOLON_ECHO_MODEL", "holon-echo-v1")))
236:     return ProviderRouter(
237:         providers,
238:         retries=int(env_map.get("HOLON_PROVIDER_RETRIES", "1") or "1"),
239:         max_cost_usd=float(env_map.get("HOLON_MAX_COST_USD", "0") or "0"),
240:     )
241: 
242: 
243: async def _complete_provider(provider: Provider, request: LLMRequest) -> ProviderResponse:
244:     complete = getattr(provider, "complete", None)
245:     if callable(complete):
246:         return await complete(request)
247:     chunks = [chunk async for chunk in provider.stream(request)]
248:     return ProviderResponse(
249:         content="".join(chunks),
250:         provider=getattr(provider, "name", "unknown"),
251:         model=request.model or getattr(provider, "model", ""),
252:         finish_reason="stop",
253:         cost_usd=0.0,
254:         attempts=[],
255:     )
256: 
257: 
258: def _messages_with_system(request: LLMRequest) -> list[dict[str, str]]:
259:     messages: list[dict[str, str]] = []
260:     if request.system:
261:         messages.append({"role": "system", "content": request.system})
262:     for message in request.messages:
263:         messages.append(
264:             {
265:                 "role": str(message.get("role", "user")),
266:                 "content": str(message.get("content", "")),
267:             }
268:         )
269:     return messages
270: 
271: 
272: def _openai_tool_spec(tool: dict[str, Any]) -> dict[str, Any]:
273:     return {
274:         "type": "function",
275:         "function": {
276:             "name": str(tool.get("name") or ""),
277:             "description": str(tool.get("description") or ""),
278:             "parameters": _json_schema(tool.get("schema") or {}),
279:         },
280:     }
281: 
282: 
283: def _json_schema(schema: dict[str, Any]) -> dict[str, Any]:
284:     if schema.get("type"):
285:         return dict(schema)
286:     properties: dict[str, Any] = {}
287:     for key, value in schema.items():
288:         if isinstance(value, dict):
289:             properties[str(key)] = value
290:             continue
291:         raw = str(value or "string")
292:         if "object" in raw:
293:             properties[str(key)] = {"type": "object"}
294:         elif "number" in raw or "float" in raw:
295:             properties[str(key)] = {"type": "number"}
296:         elif "int" in raw:
297:             properties[str(key)] = {"type": "integer"}
298:         elif "bool" in raw:
299:             properties[str(key)] = {"type": "boolean"}
300:         else:
301:             properties[str(key)] = {"type": "string"}
302:     return {"type": "object", "properties": properties}
303: 
304: 
305: def _normalize_openai_tool_calls(raw_calls: list[Any]) -> list[dict[str, Any]]:
```

## holon/supervisor.py (sha256:10e4391c3ec7679f3650fb3facb23acb89729be94dbb6969991d415c284b4339)

```python
28: async def run_supervisor(config: SupervisorConfig, *, runtime: HolonRuntime | None = None) -> dict[str, object]:
29:     results = []
30:     start_cycle = persistence.resume_point(config.name, agents_root=config.agents_root)["next_cycle"]
31:     lock = service.acquire_service_lock(
32:         config.name,
33:         agents_root=config.agents_root,
34:         holder=config.service_id,
35:         lease_seconds=config.lease_seconds,
36:         lock_path=config.lock_path,
37:     )
38:     if not lock.acquired:
39:         heartbeat = service.record_service_heartbeat(
40:             config.name,
41:             agents_root=config.agents_root,
42:             session_id=f"supervisor:{config.name}:{start_cycle}",
43:             service_id=config.service_id,
44:             status="paused",
45:             runtime_ref={"start_cycle": start_cycle, "lock": lock.to_dict()},
46:             claim_scope={"lock_held": True, "supervisor_started": False},
47:         )
48:         liveness = service.assess_service_liveness(
49:             config.name,
50:             agents_root=config.agents_root,
51:             service_id=config.service_id,
52:             fresh_after_seconds=config.heartbeat_fresh_seconds,
53:         )
54:         status = health.holon_status(config.name, agents_root=config.agents_root)
55:         receipt = build_receipt(
56:             kind="holon_supervisor_run",
57:             subject=config.name,
58:             status="warn",
59:             side_effect_key=f"supervisor-lock-held:{config.name}:{start_cycle}:{config.prompt}",
60:             payload={
61:                 "status": "lock_held",
62:                 "results": results,
63:                 "health": status,
64:                 "lock": lock.to_dict(),
65:                 "service_heartbeat": heartbeat,
66:                 "service_liveness": liveness,
67:             },
68:         )
69:         ref = write_receipt(receipt, agents_root=config.agents_root, holon_name=config.name)
70:         return {
71:             "status": "lock_held",
72:             "results": results,
73:             "health": status,
74:             "lock": lock.to_dict(),
75:             "service_heartbeat": heartbeat,
76:             "service_liveness": liveness,
77:             "receipt": ref,
78:         }
79: 
80:     final_heartbeat: dict[str, object] = {}
81:     lock_released = False
82:     try:
83:         active_runtime = runtime or runtime_from_identity(config.name, agents_root=config.agents_root)
84:         running_heartbeat = service.record_service_heartbeat(
85:             config.name,
86:             agents_root=config.agents_root,
87:             session_id=f"supervisor:{config.name}:{start_cycle}",
88:             service_id=config.service_id,
89:             status="running",
90:             runtime_ref={"start_cycle": start_cycle, "max_cycles": config.max_cycles},
91:             claim_scope={"lock_acquired": True, "supervisor_started": True},
92:         )
93:         final_heartbeat = running_heartbeat
94:         for offset in range(max(0, config.max_cycles)):
95:             cycle = start_cycle + offset
96:             result = await active_runtime.run_provider_cycle(
97:                 config.prompt,
98:                 cycle=cycle,
99:                 cap_usd=config.cap_usd,
100:                 side_effect_key=f"supervisor:{config.name}:{cycle}:{config.prompt}",
101:             )
102:             results.append(result.to_dict())
103:             if result.status != "ran":
104:                 break
105:             if config.sleep_seconds > 0:
106:                 await asyncio.sleep(config.sleep_seconds)
107:         final_status = _heartbeat_status(results)
108:         final_heartbeat = service.record_service_heartbeat(
109:             config.name,
110:             agents_root=config.agents_root,
111:             session_id=f"supervisor:{config.name}:{start_cycle}",
112:             service_id=config.service_id,
113:             status=final_status,
114:             runtime_ref={
115:                 "start_cycle": start_cycle,
116:                 "cycles_attempted": len(results),
117:                 "last_status": results[-1]["status"] if results else "none",
118:             },
119:             claim_scope={
120:                 "lock_acquired": True,
```

## holon/organs/service.py (sha256:fd0201ff419e8a400a0d75ef695b05181b542dfe0e5deebcb1837bd4285ebc3d)

```python
41: def acquire_service_lock(
42:     name: str,
43:     *,
44:     agents_root: Path,
45:     holder: str,
46:     lease_seconds: int = 300,
47:     lock_path: Path | None = None,
48: ) -> ServiceLock:
49:     path = lock_path or supervisor_lock_path(name, agents_root=agents_root)
50:     path.parent.mkdir(parents=True, exist_ok=True)
51:     now = _utc_now()
52:     lease = max(1, int(lease_seconds))
53:     _remove_expired_lock(path, now=now)
54:     expires_at = _format_utc(now + timedelta(seconds=lease))
55:     lock_id = stable_digest(
56:         {
57:             "holon": name,
58:             "holder": holder,
59:             "path": str(path),
60:             "observed_at": _format_utc(now),
61:             "expires_at": expires_at,
62:         }
63:     )
64:     payload = {
65:         "schema_version": LOCK_SCHEMA_VERSION,
66:         "holon": name,
67:         "holder": holder,
68:         "lock_id": lock_id,
69:         "acquired_at": _format_utc(now),
70:         "expires_at": expires_at,
71:     }
72:     try:
73:         fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
74:     except FileExistsError:
75:         return ServiceLock(
76:             acquired=False,
77:             path=str(path),
78:             holder=holder,
79:             reason="lock_held",
80:         )
81:     with os.fdopen(fd, "w", encoding="utf-8") as handle:
82:         handle.write(json.dumps(payload, sort_keys=True) + "\n")
83:     return ServiceLock(
84:         acquired=True,
85:         path=str(path),
86:         lock_id=lock_id,
87:         holder=holder,
88:         expires_at=expires_at,
89:     )
90: 
91: 
92: def release_service_lock(lock: ServiceLock) -> bool:
93:     if not lock.acquired:
94:         return False
95:     path = Path(lock.path)
96:     if not path.exists():
97:         return False
98:     try:
99:         payload = json.loads(path.read_text(encoding="utf-8"))
100:     except json.JSONDecodeError:
101:         return False
102:     if str(payload.get("lock_id") or "") != lock.lock_id:
103:         return False
104:     path.unlink()
105:     return True
106: 
107: 
108: def record_service_heartbeat(
109:     name: str,
110:     *,
111:     agents_root: Path,
112:     session_id: str = "",
113:     service_id: str = "holon-supervisor",
114:     status: str = "running",
115:     runtime_ref: dict[str, Any] | None = None,
116:     proof_ref: dict[str, Any] | None = None,
117:     claim_scope: dict[str, Any] | None = None,
118:     observed_at: datetime | None = None,
119: ) -> dict[str, Any]:
120:     path = service_heartbeat_path(name, agents_root=agents_root)
121:     rows, _errors = _read_rows(path)
122:     previous_hash = str(rows[-1].get("record_hash") or "") if rows else ""
123:     row = {
124:         "schema_version": HEARTBEAT_SCHEMA_VERSION,
125:         "holon": name,
```

```python
171: 
172: def assess_service_liveness(
173:     name: str,
174:     *,
175:     agents_root: Path,
176:     service_id: str | None = None,
177:     now: datetime | None = None,
178:     fresh_after_seconds: int = 300,
179: ) -> dict[str, Any]:
180:     path = service_heartbeat_path(name, agents_root=agents_root)
181:     ledger_ok, ledger_errors = verify_service_heartbeat_ledger(path)
182:     latest = latest_service_heartbeat(name, agents_root=agents_root, service_id=service_id)
183:     observed = _parse_utc(str((latest or {}).get("observed_at") or ""))
184:     current = now or _utc_now()
185:     age_seconds = None
186:     if observed is not None:
187:         age_seconds = max(0.0, round((current - observed).total_seconds(), 3))
188:     fresh_limit = max(1, int(fresh_after_seconds))
189:     status = str((latest or {}).get("status") or "unknown")
190:     fresh = age_seconds is not None and age_seconds <= fresh_limit
191:     return {
192:         "schema_version": "holon.service_liveness.v1",
193:         "holon": name,
194:         "heartbeat_seen": latest is not None,
195:         "service_alive": bool(latest and fresh and ledger_ok and status in LIVE_STATUSES),
196:         "fresh": fresh,
197:         "status": status,
198:         "age_seconds": age_seconds,
199:         "fresh_after_seconds": fresh_limit,
200:         "ledger_ok": ledger_ok,
201:         "ledger_errors": ledger_errors,
202:         "heartbeat_path": str(path),
203:         "latest_record_hash": str((latest or {}).get("record_hash") or ""),
204:         "latest_observed_at": str((latest or {}).get("observed_at") or ""),
205:         "latest_service_id": str((latest or {}).get("service_id") or ""),
206:     }
207: 
208: 
209: def _remove_expired_lock(path: Path, *, now: datetime) -> None:
210:     if not path.exists():
211:         return
212:     try:
213:         payload = json.loads(path.read_text(encoding="utf-8"))
214:     except json.JSONDecodeError:
215:         return
216:     expires_at = _parse_utc(str(payload.get("expires_at") or ""))
217:     if expires_at is not None and expires_at <= now:
218:         path.unlink()
219: 
220: 
221: def _read_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
222:     if not path.exists():
223:         return [], [f"{path.name} missing"]
224:     rows: list[dict[str, Any]] = []
225:     errors: list[str] = []
```

## holon/burn_in.py (sha256:8618bf579aef487179e8772d68cfe53b60dc329073c540f4798de43176392349)

```python
52:                 agents_root=config.agents_root,
53:                 lease_seconds=config.lease_seconds,
54:                 service_id=config.service_id,
55:             )
56:         )
57:         sample = {
58:             "sample_index": len(samples) + 1,
59:             "started_at": sample_started,
60:             "completed_at": utc_now(),
61:             "supervisor_status": result.get("status"),
62:             "last_cycle_status": _last_cycle_status(result),
63:             "receipt": result.get("receipt") or {},
64:             "service_liveness": result.get("service_liveness") or {},
65:             "lock": result.get("lock") or {},
66:         }
67:         samples.append(sample)
68:         failed = sample["supervisor_status"] not in {"completed"} or sample["last_cycle_status"] != "ran"
69:         if failed and config.stop_on_failure:
70:             break
71:         if time.monotonic() >= deadline and len(samples) >= min_cycles:
72:             break
73:         if config.interval_seconds > 0:
74:             await asyncio.sleep(config.interval_seconds)
75:     completed_at = utc_now()
76:     elapsed_seconds = round(time.monotonic() - started_monotonic, 3)
77:     failed_samples = [
78:         sample
79:         for sample in samples
80:         if sample["supervisor_status"] != "completed" or sample["last_cycle_status"] != "ran"
81:     ]
82:     sample_count_met = len(samples) >= min_cycles
83:     multi_hour_proven = (
84:         elapsed_seconds >= max(1.0, float(config.multi_hour_threshold_seconds))
85:         and sample_count_met
86:         and not failed_samples
87:     )
88:     status = "pass" if sample_count_met and not failed_samples else "fail"
89:     payload = {
90:         "schema_version": "holon.burn_in.v1",
91:         "status": status,
92:         "passed": status == "pass",
93:         "multi_hour_proven": multi_hour_proven,
94:         "started_at": started_at,
95:         "completed_at": completed_at,
96:         "elapsed_seconds": elapsed_seconds,
97:         "config": config.to_dict(),
98:         "sample_count": len(samples),
99:         "sample_count_met": sample_count_met,
100:         "failed_sample_count": len(failed_samples),
101:         "samples": samples,
102:         "source_proof": package_source_proof(),
103:     }
104:     receipt = build_receipt(
105:         kind="holon_burn_in_run",
106:         subject=config.name,
107:         status=status,
108:         side_effect_key=(
109:             f"burn-in:{config.name}:{started_at}:"
110:             f"{config.duration_seconds}:{config.min_cycles}:{config.prompt}"
111:         ),
112:         payload=payload,
113:         verifier_refs=[
114:             str((sample.get("receipt") or {}).get("path") or "")
115:             for sample in samples
116:             if (sample.get("receipt") or {}).get("path")
```

## holon/source_proof.py (sha256:18c30f4574b3707d602eebb711068d98168cf54e2d2073710e4716a34a220d26)

```python
11: 
12: 
13: def package_source_proof(package_root: Path | None = None) -> dict[str, Any]:
14:     """Return a deterministic digest for the installed Holon package files.
15: 
16:     When the package is running from a git checkout, include the current HEAD
17:     and dirty state as additional context. The file digest remains the portable
18:     proof for installed wheels where ``.git`` is absent.
19:     """
20: 
21:     root = package_root or Path(__file__).resolve().parent
22:     files: list[dict[str, Any]] = []
23:     for path in sorted(root.rglob("*.py")):
24:         rel = path.relative_to(root).as_posix()
25:         if "__pycache__" in path.parts:
26:             continue
27:         data = path.read_bytes()
28:         files.append(
29:             {
30:                 "path": rel,
31:                 "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
32:                 "bytes": len(data),
33:             }
34:         )
35:     proof = {
36:         "schema_version": "holon.source_proof.v1",
37:         "package_root": str(root),
38:         "file_count": len(files),
39:         "files": files,
40:     }
41:     proof["source_tree_digest"] = stable_digest(
42:         {
43:             "schema_version": proof["schema_version"],
44:             "files": files,
45:         }
46:     )
47:     proof.update(_git_context(root))
48:     return proof
49: 
50: 
51: def _git_context(root: Path) -> dict[str, Any]:
52:     repo = _find_git_root(root)
53:     if repo is None:
54:         return {
55:             "git_available": False,
56:             "git_head": "",
57:             "git_dirty": None,
58:             "git_root": "",
```

## dharma_swarm/holon_truth_projection.py (sha256:00e3e166ff23e137ea35e3ca100586585d304ed56f4c7586a85b82e7392566f9)

```python
54: def project_holon_receipt(
55:     receipt_path: Path | str,
56:     *,
57:     runtime_state: RuntimeStateStore | None = None,
58:     runtime_db_path: Path | str | None = None,
59:     agents_root: Path | str | None = None,
60:     dharma_home: Path | str | None = None,
61:     session_id: str = "",
62:     mission_id: str = "",
63:     parent_run_id: str = "",
64:     require_living_dock: bool = False,
65: ) -> HolonReceiptProjection:
66:     """Project a standalone receipt into the parent runtime truth spine."""
67: 
68:     path = Path(receipt_path).expanduser().resolve()
69:     source = _read_receipt(path)
70:     source_receipt_id = _required_text(source, "receipt_id")
71:     holon_name = _required_text(source, "subject")
72:     source_status = str(source.get("status") or "")
73:     created_at = _parse_utc(str(source.get("created_at") or ""))
74:     lifecycle_status = _lifecycle_status(source_status)
75:     root = Path(agents_root).expanduser().resolve() if agents_root else path.parents[1]
76: 
77:     living_report = verify_living_dock(
78:         holon_name,
79:         dharma_home=dharma_home,
80:         agents_root=root,
81:         require_dialogue=False,
82:         require_sanctum=False,
83:     )
84:     projection_block_reason = ""
85:     if require_living_dock and living_report.status == "fail":
86:         lifecycle_status = "blocked"
87:         projection_block_reason = "living_dock_verifier_failed"
88: 
89:     identity = _identity_for_receipt(
90:         source,
91:         holon_name=holon_name,
92:         session_id=session_id,
93:         mission_id=mission_id,
94:         parent_run_id=parent_run_id,
95:     )
96:     parent_receipt_id = f"rr_{_safe_id(identity.run_id)}_holon_projection"
97:     store = runtime_state or RuntimeStateStore(runtime_db_path)
98:     artifact_items = _artifact_items(source)
99:     artifact_ids = [
100:         _artifact_id(source_receipt_id, index, item)
101:         for index, item in enumerate(artifact_items, start=1)
102:     ]
103: 
104:     if _runtime_receipt_exists(store, parent_receipt_id):
105:         return HolonReceiptProjection(
106:             source_receipt_id=source_receipt_id,
107:             parent_receipt_id=parent_receipt_id,
108:             run_id=identity.run_id,
109:             task_id=identity.task_id,
110:             correlation_id=identity.correlation_id,
111:             status=lifecycle_status,
112:             artifact_ids=artifact_ids,
113:             source_digest_verified=_source_digest_verified(source),
114:             living_dock_status=living_report.status,
115:             already_projected=True,
116:         )
117: 
118:     source_digest_verified = _source_digest_verified(source)
119:     provider_context = _provider_context(source)
120:     artifact_refs = [f"artifact_records:{artifact_id}" for artifact_id in artifact_ids]
121:     projection_payload = {
122:         "schema_version": PROJECTION_SCHEMA_VERSION,
123:         "source_receipt_ref": str(path),
124:         "source_receipt_id": source_receipt_id,
125:         "source_receipt_kind": str(source.get("kind") or ""),
126:         "source_receipt_status": source_status,
127:         "source_receipt_digest": str(source.get("digest") or ""),
128:         "source_digest_verified": source_digest_verified,
129:         "holon_name": holon_name,
130:         "standalone_side_effect_key": str(source.get("side_effect_key") or ""),
131:         "lifecycle_status": lifecycle_status,
132:         "projection_block_reason": projection_block_reason,
```

```python
260: def _read_receipt(path: Path) -> dict[str, Any]:
261:     data = json.loads(path.read_text(encoding="utf-8"))
262:     if not isinstance(data, dict):
263:         raise ValueError(f"Holon receipt is not a JSON object: {path}")
264:     if data.get("schema_version") != SOURCE_RECEIPT_SCHEMA_VERSION:
265:         raise ValueError(f"unsupported Holon receipt schema: {data.get('schema_version')!r}")
266:     return data
267: 
268: 
269: def _required_text(data: dict[str, Any], key: str) -> str:
270:     value = str(data.get(key) or "").strip()
271:     if not value:
272:         raise ValueError(f"Holon receipt missing {key}")
273:     return value
274: 
275: 
276: def _safe_id(value: str) -> str:
277:     cleaned = _SAFE_ID_RE.sub("_", str(value or "").strip()).strip("_")
278:     return cleaned or "unknown"
279: 
280: 
281: def _parse_utc(raw: str) -> datetime:
282:     value = str(raw or "").strip()
283:     if value.endswith("Z"):
284:         value = value[:-1] + "+00:00"
285:     if not value:
286:         return datetime.now(UTC)
287:     parsed = datetime.fromisoformat(value)
288:     if parsed.tzinfo is None:
289:         return parsed.replace(tzinfo=UTC)
290:     return parsed.astimezone(UTC)
291: 
292: 
293: def _identity_for_receipt(
294:     source: dict[str, Any],
295:     *,
296:     holon_name: str,
297:     session_id: str,
298:     mission_id: str,
299:     parent_run_id: str,
300: ) -> ExecutionIdentity:
301:     receipt_id = _safe_id(_required_text(source, "receipt_id"))
302:     metadata = dict((source.get("payload") or {}).get("metadata") or {})
303:     existing = ExecutionIdentity.from_metadata(metadata, require=False)
304:     if existing is not None:
305:         return existing.with_updates(
306:             agent_id=existing.agent_id or holon_name,
```

Your verdict should usually be revise unless you believe the above evidence is enough for pass despite dirty git and missing multi-hour proof. Include remaining blockers in summary/recommendations.
