# Receipts

Lab-wide NAGA-IR-shaped receipt emissions live here.

## Partition Contract

Receipts are written under:

```text
dharma_lab/receipts/YYYY/MM/DD/<receipt_class>_<hash-prefix>.json
```

The local emitter in `dharma_lab/inference/receipts_hooks.py` creates missing
date partitions at runtime. Static seed partitions use `.gitkeep` only to make
the intended structure visible in git.

## Receipt Classes

All lab-owned classes use the `dharma_lab.*` prefix.

| Class | Producer | Default modality | Status |
|---|---|---|---|
| `dharma_lab.corpus_ingest.v1` | `dharma_lab/corpus/ingest.py` | `Attested_by` | implemented |
| `dharma_lab.inference.v1` | `dharma_lab/inference/router.py` | `Attested_by` for single-model output | implemented |
| `dharma_lab.model_registered.v1` | future model registry writer | `Attested_by` | reserved |
| `dharma_lab.shadow_lang_extension.v1` | future shadow language governance | `Attested_by` or `Tested_by` by consensus evidence | reserved |
| `dharma_lab.cross_fragment_coercion.v1` | governance promotion workflow | target-dependent | reserved |

## Canonicality Status

Receipts emitted by the seed helper follow `specs/naga_ir/receipt_wire.md`
field shape, but they are intentionally unsigned bootstrap records. They are
not canonical for cross-fragment transfer until a signer/verifier layer is
wired. Their epistemic origin records `noncanonical_unsigned_bootstrap` for
that reason.

