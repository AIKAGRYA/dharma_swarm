# Holon Provider Secret Proxy Request

Packet role: operator-liaison request for the standalone Holon proof.

The Holon build cannot complete its live key-backed provider burn-in gate
because the local toolbelt reports no provider API keys. The build agent must
not ask the human directly. Please act as the operator-contact proxy and ask
for the narrowest missing item only.

Requested item:

- A safe secret-reference handle for one live provider route that Holon can use
  for a bounded burn-in smoke test, preferably OpenAI or OpenRouter.

Do not place raw API keys, passwords, or bearer tokens in A2A packets, logs,
receipts, prompts, commits, or broad broadcasts.

Acceptable proxy responses:

- `secret_reference_available=true` with the name/location of an approved
  local secret reference that the build runtime is authorized to read.
- `secret_reference_pending=true` if the operator request has been made but no
  approved reference is available yet.
- `secret_reference_unavailable=true` with a safe reason if no live provider
  credential can be provided.

The build will continue all non-secret work while this request is pending.
