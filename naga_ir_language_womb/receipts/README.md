# Receipts

Womb-wide NAGA-IR-shaped receipt emissions live here.

## Partition Contract

Receipts are written under:

```text
naga_ir_language_womb/receipts/YYYY/MM/DD/<receipt_class>_<hash-prefix>.json
```

The local emitter in `naga_ir_language_womb/inference/receipts_hooks.py` creates missing
date partitions at runtime. Static seed partitions use `.gitkeep` only to make
the intended structure visible in git.

## Receipt Classes

All womb-owned classes use the `naga_ir_language_womb.*` prefix.

| Class | Producer | Default modality | Status |
|---|---|---|---|
| `naga_ir_language_womb.corpus_ingest.v1` | `naga_ir_language_womb/corpus/ingest.py` | `Attested_by` | implemented |
| `naga_ir_language_womb.inference.v1` | `naga_ir_language_womb/inference/router.py` | `Attested_by` for single-model output | implemented |
| `naga_ir_language_womb.model_registered.v1` | future model registry writer | `Attested_by` | reserved |
| `naga_ir_language_womb.prior_art_review.v1` | future prior-art gate writer | `Attested_by` or stronger if independently reviewed | reserved |
| `naga_ir_language_womb.language_extension.v1` | future NAGA-IR child language governance | `Attested_by` or `Tested_by` by consensus evidence | reserved |
| `naga_ir_language_womb.cross_fragment_coercion.v1` | governance promotion workflow | target-dependent | reserved |

## Canonicality Status

Receipts emitted by the seed helper follow `specs/naga_ir/receipt_wire.md`
field shape, but they are intentionally unsigned bootstrap records. They are
not canonical for cross-fragment transfer until a signer/verifier layer is
wired. Their epistemic origin records `noncanonical_unsigned_bootstrap` for
that reason.
