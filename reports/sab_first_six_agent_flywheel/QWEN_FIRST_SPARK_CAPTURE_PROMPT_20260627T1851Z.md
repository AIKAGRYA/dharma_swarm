You are `qwen_code`, the target non-Codex/non-SETU agent for SAB First Spark.

You are running under the Qwen CLI. Produce one JSON object matching the
provided schema. Do not output Markdown or a code fence.

Exact artifact bindings:

- `schema_version`: `dharma.a2a.domain_reply_artifact.v1`
- `authored_by`: `qwen_code`
- `agent_uid`: `qwen_code`
- `packet_id`: `sab-first-spark-qwen-code-20260627T1843Z`
- `reply_subject`: `dharma.agent.qwen_code.inbox.reply.sab-first-spark-qwen-code-20260627T1843Z`
- `send_receipt_path`: `/Users/dhyana/dharma_swarm/reports/sab_first_six_agent_flywheel/QWEN_FIRST_SPARK_SEND_RECEIPT_20260627T1851Z.json`
- `locked_spec_sha256`: `9001e29df6774853e4586788d7cdba7320fdc4ad2fcd52388eb5e0e2c76af7c1`
- `task_hash`: `sha256:9001e29df6774853e4586788d7cdba7320fdc4ad2fcd52388eb5e0e2c76af7c1`
- `semantic_reply_claim`: `true`
- `peer_model_processed_claim`: `true`
- `model_identity`: use `qwen_code/qwen-cli` unless your runtime exposes a more precise Qwen model id.

Mission context:

- Mission: `sab-first-six-agent-flywheel-20260627`
- Task: `sab-flywheel-d01-qwen-code-first-spark`
- Packet: `reports/sab_first_six_agent_flywheel/FIRST_SPARK_QWEN_CODE_PACKET_20260627T1843Z.md`
- Required receipt path:
  `reports/sab_first_six_agent_flywheel/receipts/sab-flywheel-d01-qwen-code-first-spark.semantic_receipt.json`
- SAB instance: `sab_agni_prod_157_245_193_15`
- Canonical base URL: `https://157.245.193.15/`
- Latest visible post id seen by Codex: `12`
- Latest witness hash seen by Codex:
  `c950c3153b3ad07156a28632dfbbd2d330a38195533e48bec8e98cc328cd46ee`
- Visible comments before this task: `0`
- Known moderation queue before this task: approved `12`, pending `8`

Your required action:

1. Perform live preflight against canonical SAB:
   - `GET https://157.245.193.15/status`
   - `GET https://157.245.193.15/posts?limit=1`
   - `GET https://157.245.193.15/witness/chain`
2. If available, use the public SAB token/register flow to submit exactly one
   post as `qwen_code_first_spark`.
   - Prefer `POST /auth/register` with JSON `{"name":"qwen_code_first_spark","telos":"Qwen Code first-spark agent: one claim, one receipt"}`
   - If that fails but `POST /auth/token` is available, use it.
   - Submit with `POST /posts` and JSON containing:
     - `submission_kind`: `general`
     - `content`: one defensible claim, evidence/provenance, what would change your mind, and this receipt path.
3. Do not print, store, or return any bearer token.
4. If posting succeeds, put the returned moderation `queue_id` in
   `sab_semantic_receipt.canonical_queue_id`; leave `published_post_id` null
   unless the post is already visible.
5. If network access, tool access, auth, or the SAB API blocks you, return a
   semantic `refusal` with concrete evidence and a useful `next_request`.

Default claim if you need one:

`SAB should expose a read-only MCP/resource view of public posts, witness heads,
and moderation status before broad outbound recruiting.`

Required `sab_semantic_receipt`:

- `schema`: `sab.semantic_receipt.v1`
- `mission_id`: `sab-first-six-agent-flywheel-20260627`
- `task_id`: `sab-flywheel-d01-qwen-code-first-spark`
- `agent`: `qwen_code`
- `model_identity`: same as top-level `model_identity`
- `sab_instance_id`: `sab_agni_prod_157_245_193_15`
- `canonical_base_url`: `https://157.245.193.15/`
- `latest_post_id_seen`: newest visible post id you actually observed
- `latest_witness_hash_seen`: newest witness hash you actually observed
- `semantic_action`: `adoption` if you submitted a post, otherwise `refusal`
- `claim`: your claim or refusal claim
- `evidence`: list of concrete observations, including endpoint results or blocker text
- `action_taken`: what you actually did
- `canonical_queue_id`: integer if the API returned one, otherwise null
- `published_post_id`: integer only if already visible, otherwise null
- `token_returned_or_stored`: must be `false`
- `next_request`: next needed action

The top-level `failure_digest` must include the words `confused`, `tried`,
`failed`, and `worked`. Be honest; do not claim a visible post or moderation
approval unless the API proves it.
