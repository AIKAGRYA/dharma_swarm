# cybernetics_codex Receipts

Repo receipts for this steward should live under:

```text
reports/loop_closure/cybernetics_codex/
```

Runtime registration receipts live outside the repo under the operator state root:

```text
~/.dharma/external_agents/cybernetics_codex/registration.json
~/.dharma/agents/cybernetics_codex/last_receipt.json
~/.dharma/onboarding/receipts/
```

Do not hand-write those runtime files. Use:

```bash
python3 scripts/governance/register_cybernetics_codex.py --write
```
