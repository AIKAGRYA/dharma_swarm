#!/usr/bin/env python3
"""
Generation-time distributed Gemma intervention pilot.

This runner composes three mechanisms that previous sweeps treated separately:
early source SAE feature writing, L17 writer-head output writing, and late L35
readout SAE feature writing. It is intentionally small and diagnostic.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import torch
from scipy import stats
from transformers import AutoConfig, AutoModelForCausalLM, AutoTokenizer


PHASE1_SCRIPTS = Path("/Users/dhyana/ALL MECH INTERP/mech-interp-latent-lab-phase1/scripts")
if str(PHASE1_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PHASE1_SCRIPTS))

import gemma_scope_feature_install as gfi  # noqa: E402


DEFAULT_BANK = Path("/Users/dhyana/ALL MECH INTERP/mech-interp-latent-lab-phase1/prompts/bank.json")
DEFAULT_PROBE_SUMMARY = Path(
    "/Users/dhyana/ALL MECH INTERP/mech-interp-latent-lab-phase1/results/"
    "phase2_generalization/gemma_2_9b/sae_pilot_20260419/"
    "gemma_scope_probe_l3_resid_recursive_selfref_n10.json"
)


def log(message: str) -> None:
    print(f"[gemma_scope_bundle_install] {message}", file=sys.stderr, flush=True)


@dataclass
class SitePlan:
    name: str
    layer: int
    kind: str
    site_key: str
    mode: str
    feature_ids: list[int]
    random_ids: list[int]
    target_delta: np.ndarray
    target_positive: np.ndarray
    sae: object


class MultiHook:
    def __init__(self, hooks: Sequence[object]):
        self.hooks = list(hooks)

    def register(self, model) -> None:
        for hook in self.hooks:
            hook.register(model)

    def remove(self) -> None:
        for hook in reversed(self.hooks):
            hook.remove()


class HeadSteerer:
    def __init__(
        self,
        *,
        layer: int,
        head_ids: list[int],
        num_heads: int,
        head_dim: int,
        tail: int,
        mode: str,
        alpha: float,
        values: torch.Tensor,
    ):
        self.layer = layer
        self.head_ids = head_ids
        self.num_heads = num_heads
        self.head_dim = head_dim
        self.tail = tail
        self.mode = mode
        self.alpha = alpha
        self.values = values.detach().float().cpu()
        self.handle = None

    def hook(self, _module, inputs):
        if not self.head_ids:
            return None
        tensor = inputs[0].clone()
        batch, seq, width = tensor.shape
        if width != self.num_heads * self.head_dim:
            raise RuntimeError(f"Unexpected head width {width}, expected {self.num_heads * self.head_dim}")
        n = min(seq, self.tail, self.values.shape[0])
        reshaped = tensor.view(batch, seq, self.num_heads, self.head_dim)
        values = self.values[-n:].to(device=reshaped.device, dtype=reshaped.dtype)
        heads = torch.tensor(self.head_ids, dtype=torch.long, device=reshaped.device)
        if self.mode == "add":
            reshaped[:, -n:, heads, :] = reshaped[:, -n:, heads, :] + self.alpha * values.unsqueeze(0)
        elif self.mode == "set":
            reshaped[:, -n:, heads, :] = values.unsqueeze(0)
        else:
            raise ValueError(f"Unsupported head mode: {self.mode}")
        return (reshaped.view(batch, seq, width),)

    def register(self, model) -> None:
        self.handle = model.model.layers[self.layer].self_attn.o_proj.register_forward_pre_hook(self.hook)

    def remove(self) -> None:
        if self.handle is not None:
            self.handle.remove()
            self.handle = None


def paired_effect(a: Iterable[float], b: Iterable[float]) -> dict[str, float]:
    arr_a = np.array(list(a), dtype=float)
    arr_b = np.array(list(b), dtype=float)
    mask = np.isfinite(arr_a) & np.isfinite(arr_b)
    arr_a = arr_a[mask]
    arr_b = arr_b[mask]
    if len(arr_a) != len(arr_b) or len(arr_a) < 2:
        return {"mean_delta": float("nan"), "t_stat": float("nan"), "p_value": float("nan"), "dz": float("nan")}
    delta = arr_a - arr_b
    t_stat, p_value = stats.ttest_rel(arr_a, arr_b)
    std = np.std(delta, ddof=1)
    return {
        "mean_delta": float(np.mean(delta)),
        "t_stat": float(t_stat),
        "p_value": float(p_value),
        "dz": float(np.mean(delta) / std) if std > 1e-10 else float("nan"),
    }


def parse_int_csv(raw: str) -> list[int]:
    return [int(piece.strip()) for piece in raw.split(",") if piece.strip()]


def feature_ids_from_probe(probe_summary: Path, site_key: str, k: int) -> list[int]:
    data = gfi.load_json(probe_summary)
    if site_key not in data.get("sites", {}):
        raise KeyError(f"{site_key!r} not in probe summary. Available: {sorted(data.get('sites', {}))}")
    return [int(idx) for idx in data["sites"][site_key]["top_features"][:k]]


def random_feature_ids(target_ids: list[int], k: int, seed: int, width: int = 16384) -> list[int]:
    rng = random.Random(seed)
    target_set = set(target_ids)
    return rng.sample([idx for idx in range(width) if idx not in target_set], k)


def make_site_plan(
    *,
    model,
    tokenizer,
    natural_items: list[gfi.PromptItem],
    control_items: list[gfi.PromptItem],
    probe_summary: Path,
    name: str,
    layer: int,
    kind: str,
    site_key: str,
    mode: str,
    k_features: int,
    tail: int,
    max_length: int,
    sae_device: str,
    seed: int,
) -> SitePlan:
    feature_ids = feature_ids_from_probe(probe_summary, site_key, k_features)
    random_ids = random_feature_ids(feature_ids, k_features, seed)
    sae = gfi.load_sae(layer, kind, "16k", sae_device)
    log(f"collecting {name} deltas at L{layer} {kind} with features={feature_ids[:4]}...")
    positive = gfi.encode_site_features(model, tokenizer, sae, natural_items, layer, kind, tail, max_length)
    control = gfi.encode_site_features(model, tokenizer, sae, control_items, layer, kind, tail, max_length)
    positive_mean = positive.mean(axis=0)
    control_mean = control.mean(axis=0)
    return SitePlan(
        name=name,
        layer=layer,
        kind=kind,
        site_key=site_key,
        mode=mode,
        feature_ids=feature_ids,
        random_ids=random_ids,
        target_delta=positive_mean[feature_ids] - control_mean[feature_ids],
        target_positive=positive_mean[feature_ids],
        sae=sae,
    )


def capture_head_tail(
    model,
    tokenizer,
    text: str,
    *,
    layer: int,
    tail: int,
    num_heads: int,
    head_dim: int,
    max_length: int,
) -> torch.Tensor:
    input_device = next(model.parameters()).device
    capture: dict[str, torch.Tensor] = {}

    def hook(_module, inputs):
        capture["head"] = inputs[0].detach().clone()
        return None

    handle = model.model.layers[layer].self_attn.o_proj.register_forward_pre_hook(hook)
    try:
        enc = tokenizer(text, return_tensors="pt", truncation=True, max_length=max_length)
        enc = gfi.to_input_device(enc, input_device)
        with torch.no_grad():
            model(**enc, use_cache=False)
    finally:
        handle.remove()

    tensor = capture["head"]
    batch, seq, width = tensor.shape
    if batch != 1 or width != num_heads * head_dim:
        raise RuntimeError(f"Unexpected captured head tensor shape: {tuple(tensor.shape)}")
    reshaped = tensor.view(batch, seq, num_heads, head_dim)[0]
    n = min(seq, tail)
    out = torch.zeros((tail, num_heads, head_dim), dtype=torch.float32)
    out[-n:] = reshaped[-n:].float().cpu()
    return out


def mean_head_tail(
    model,
    tokenizer,
    items: list[gfi.PromptItem],
    *,
    layer: int,
    tail: int,
    num_heads: int,
    head_dim: int,
    max_length: int,
) -> torch.Tensor:
    tensors = []
    for item in items:
        tensors.append(
            capture_head_tail(
                model,
                tokenizer,
                item.text,
                layer=layer,
                tail=tail,
                num_heads=num_heads,
                head_dim=head_dim,
                max_length=max_length,
            )
        )
    return torch.stack(tensors, dim=0).mean(dim=0)


def feature_hook(plan: SitePlan, *, use_random: bool, alpha: float):
    feature_ids = plan.random_ids if use_random else plan.feature_ids
    values = plan.target_positive if plan.mode == "set" else plan.target_delta
    return gfi.FeatureSteerer(
        sae=plan.sae,
        feature_ids=feature_ids,
        layer=plan.layer,
        kind=plan.kind,
        mode=plan.mode,
        alpha=alpha,
        values=values,
        tail=16,
    )


def generate_with_hooks(model, tokenizer, prompt: str, max_new_tokens: int, hooks: Sequence[object]):
    steerer = MultiHook(hooks) if hooks else None
    return gfi.generate_condition(model, tokenizer, prompt, max_new_tokens, steerer)


def summarize(rows: list[dict]) -> dict[str, float]:
    def mean(key: str) -> float:
        return float(np.nanmean([row[key] for row in rows])) if rows else float("nan")

    return {
        "n": len(rows),
        "mean_self_ref_markers": mean("self_ref_markers"),
        "mean_rv_output": mean("rv_output"),
        "mean_readout_score": mean("readout_score"),
        "mean_word_count": mean("word_count"),
        "mean_max_trigram_rep": mean("max_trigram_rep"),
        "mean_distance_to_natural": mean("distance_to_natural"),
        "eos_rate": float(np.mean([1.0 if row["eos_reached"] else 0.0 for row in rows])) if rows else float("nan"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--bank", type=Path, default=DEFAULT_BANK)
    parser.add_argument("--probe-summary", type=Path, default=DEFAULT_PROBE_SUMMARY)
    parser.add_argument("--model", default="google/gemma-2-9b")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--sae-device", default="auto")
    parser.add_argument("--dtype", default="bfloat16")
    parser.add_argument("--n-natural", type=int, default=6)
    parser.add_argument("--n-control", type=int, default=6)
    parser.add_argument("--n-baseline-per-group", type=int, default=2)
    parser.add_argument("--baseline-prefixes", nargs="+", default=["baseline_factual_", "baseline_math_", "baseline_creative_"])
    parser.add_argument("--positive-prefix", default="recursive_self_reference_")
    parser.add_argument("--pseudo-prefix", default="same_vocab_different_semantics_")
    parser.add_argument("--source-layer", type=int, default=3)
    parser.add_argument("--source-kind", choices=["resid", "mlp"], default="resid")
    parser.add_argument("--source-site-key", default="L3_RESID_tail")
    parser.add_argument("--readout-layer", type=int, default=35)
    parser.add_argument("--readout-site-key", default="L35_resid_tail")
    parser.add_argument("--head-layer", type=int, default=17)
    parser.add_argument("--target-heads", default="15,12")
    parser.add_argument("--random-heads", default="8,13")
    parser.add_argument("--k-features", type=int, default=16)
    parser.add_argument("--tail", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=32)
    parser.add_argument("--source-alpha", type=float, default=3.0)
    parser.add_argument("--head-alpha", type=float, default=1.0)
    parser.add_argument("--early-layer", type=int, default=6)
    parser.add_argument("--late-layer", type=int, default=38)
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=[
            "source_add",
            "readout_set",
            "source_readout",
            "head_add",
            "bundle_all",
            "random_bundle",
        ],
    )
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)

    device = gfi.resolve_device(args.device)
    sae_device = gfi.resolve_device(args.sae_device)
    dtype = gfi.resolve_dtype(args.dtype)

    bank = gfi.load_json(args.bank)
    natural_items = gfi.select_items(bank, args.positive_prefix, args.n_natural, "natural_reference")
    control_items = gfi.select_items(bank, args.pseudo_prefix, args.n_control, "pseudo_control")
    baseline_items: list[gfi.PromptItem] = []
    for prefix in args.baseline_prefixes:
        baseline_items.extend(gfi.select_items(bank, prefix, args.n_baseline_per_group, prefix.rstrip("_")))

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACE_TOKEN") or os.getenv("HUGGINGFACE_HUB_TOKEN")
    log(f"loading tokenizer: {args.model}")
    tokenizer = AutoTokenizer.from_pretrained(args.model, token=token)
    log(f"loading model: {args.model} dtype={dtype} device_map=auto")
    model = AutoModelForCausalLM.from_pretrained(
        args.model,
        token=token,
        torch_dtype=dtype,
        device_map="auto",
        attn_implementation="eager",
    )
    model.eval()
    log("model loaded")

    config = AutoConfig.from_pretrained(args.model, token=token)
    num_heads = int(config.num_attention_heads)
    head_dim = int(config.head_dim)
    target_heads = parse_int_csv(args.target_heads)
    random_heads = parse_int_csv(args.random_heads)

    source_plan = make_site_plan(
        model=model,
        tokenizer=tokenizer,
        natural_items=natural_items,
        control_items=control_items,
        probe_summary=args.probe_summary,
        name="source",
        layer=args.source_layer,
        kind=args.source_kind,
        site_key=args.source_site_key,
        mode="add",
        k_features=args.k_features,
        tail=args.tail,
        max_length=args.max_length,
        sae_device=sae_device,
        seed=args.seed + 1,
    )
    readout_plan = make_site_plan(
        model=model,
        tokenizer=tokenizer,
        natural_items=natural_items,
        control_items=control_items,
        probe_summary=args.probe_summary,
        name="readout",
        layer=args.readout_layer,
        kind="resid",
        site_key=args.readout_site_key,
        mode="set",
        k_features=args.k_features,
        tail=args.tail,
        max_length=args.max_length,
        sae_device=sae_device,
        seed=args.seed + 2,
    )

    log(f"collecting L{args.head_layer} head deltas for heads={target_heads}")
    positive_head = mean_head_tail(
        model,
        tokenizer,
        natural_items,
        layer=args.head_layer,
        tail=args.tail,
        num_heads=num_heads,
        head_dim=head_dim,
        max_length=args.max_length,
    )
    control_head = mean_head_tail(
        model,
        tokenizer,
        control_items,
        layer=args.head_layer,
        tail=args.tail,
        num_heads=num_heads,
        head_dim=head_dim,
        max_length=args.max_length,
    )
    head_delta = positive_head[:, target_heads, :] - control_head[:, target_heads, :]

    log("loading readout SAE for generated-state scoring")
    readout_sae = readout_plan.sae
    readout_features = readout_plan.feature_ids

    results: dict[str, list[dict]] = defaultdict(list)
    vectors: dict[str, list[np.ndarray]] = defaultdict(list)

    def condition_hooks(name: str) -> list[object]:
        if name == "source_add":
            return [feature_hook(source_plan, use_random=False, alpha=args.source_alpha)]
        if name == "readout_set":
            return [feature_hook(readout_plan, use_random=False, alpha=1.0)]
        if name == "source_readout":
            return [
                feature_hook(source_plan, use_random=False, alpha=args.source_alpha),
                feature_hook(readout_plan, use_random=False, alpha=1.0),
            ]
        if name == "head_add":
            return [
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=target_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="add",
                    alpha=args.head_alpha,
                    values=head_delta,
                )
            ]
        if name == "head_set":
            return [
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=target_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="set",
                    alpha=1.0,
                    values=positive_head[:, target_heads, :],
                )
            ]
        if name == "source_head_add":
            return [
                feature_hook(source_plan, use_random=False, alpha=args.source_alpha),
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=target_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="add",
                    alpha=args.head_alpha,
                    values=head_delta,
                ),
            ]
        if name == "source_head_set":
            return [
                feature_hook(source_plan, use_random=False, alpha=args.source_alpha),
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=target_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="set",
                    alpha=1.0,
                    values=positive_head[:, target_heads, :],
                ),
            ]
        if name == "random_head_set":
            return [
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=random_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="set",
                    alpha=1.0,
                    values=positive_head[:, target_heads, :],
                )
            ]
        if name == "bundle_all":
            return [
                feature_hook(source_plan, use_random=False, alpha=args.source_alpha),
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=target_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="add",
                    alpha=args.head_alpha,
                    values=head_delta,
                ),
                feature_hook(readout_plan, use_random=False, alpha=1.0),
            ]
        if name == "random_bundle":
            return [
                feature_hook(source_plan, use_random=True, alpha=args.source_alpha),
                HeadSteerer(
                    layer=args.head_layer,
                    head_ids=random_heads,
                    num_heads=num_heads,
                    head_dim=head_dim,
                    tail=args.tail,
                    mode="add",
                    alpha=args.head_alpha,
                    values=head_delta,
                ),
                feature_hook(readout_plan, use_random=True, alpha=1.0),
            ]
        raise ValueError(f"Unknown condition: {name}")

    def record(condition: str, item: gfi.PromptItem, full_text: str, continuation: str, eos: bool, natural_centroid=None):
        state = gfi.capture_generated_state(
            model,
            tokenizer,
            readout_sae,
            full_text,
            args.readout_layer,
            readout_features,
            args.tail,
            args.early_layer,
            args.late_layer,
        )
        vec = state["readout_feature_vector"]
        vectors[condition].append(vec)
        distance = 0.0 if natural_centroid is None else float(np.linalg.norm(vec - natural_centroid))
        results[condition].append(
            {
                "prompt_id": item.prompt_id,
                "group": item.group,
                "continuation": continuation,
                "eos_reached": eos,
                "rv_output": state["rv_output"],
                "readout_score": state["readout_score"],
                "distance_to_natural": distance,
                **gfi.analyze_text(continuation),
            }
        )

    for item in natural_items:
        log(f"natural_reference generate: {item.prompt_id}")
        full_text, continuation, eos = generate_with_hooks(model, tokenizer, item.text, args.max_new_tokens, [])
        record("natural_reference", item, full_text, continuation, eos, natural_centroid=None)

    natural_centroid = np.nanmean(np.stack(vectors["natural_reference"], axis=0), axis=0)

    for item in baseline_items:
        log(f"baseline generate: {item.prompt_id}")
        full_text, continuation, eos = generate_with_hooks(model, tokenizer, item.text, args.max_new_tokens, [])
        record("baseline", item, full_text, continuation, eos, natural_centroid=natural_centroid)
        for condition in args.conditions:
            log(f"{condition} generate: {item.prompt_id}")
            hooks = condition_hooks(condition)
            full_text, continuation, eos = generate_with_hooks(model, tokenizer, item.text, args.max_new_tokens, hooks)
            record(condition, item, full_text, continuation, eos, natural_centroid=natural_centroid)

    summaries = {condition: summarize(rows) for condition, rows in results.items()}
    baseline_distance = summaries["baseline"]["mean_distance_to_natural"]
    for condition, summary in summaries.items():
        if condition == "natural_reference" or not np.isfinite(baseline_distance) or baseline_distance < 1e-10:
            summary["distance_ratio_vs_baseline"] = float("nan")
        else:
            summary["distance_ratio_vs_baseline"] = float(summary["mean_distance_to_natural"] / baseline_distance)

    paired = {}
    baseline_rows = results["baseline"]
    for condition, rows in results.items():
        if condition in {"baseline", "natural_reference"}:
            continue
        paired[condition] = {
            "self_ref_vs_baseline": paired_effect(
                [row["self_ref_markers"] for row in rows],
                [row["self_ref_markers"] for row in baseline_rows],
            ),
            "rv_vs_baseline": paired_effect([row["rv_output"] for row in rows], [row["rv_output"] for row in baseline_rows]),
            "readout_vs_baseline": paired_effect(
                [row["readout_score"] for row in rows],
                [row["readout_score"] for row in baseline_rows],
            ),
            "distance_vs_baseline": paired_effect(
                [row["distance_to_natural"] for row in rows],
                [row["distance_to_natural"] for row in baseline_rows],
            ),
        }

    payload = {
        "config": {
            "model": args.model,
            "probe_summary": str(args.probe_summary),
            "source_plan": {
                "layer": source_plan.layer,
                "kind": source_plan.kind,
                "site_key": source_plan.site_key,
                "features": source_plan.feature_ids,
                "random_features": source_plan.random_ids,
                "alpha": args.source_alpha,
            },
            "readout_plan": {
                "layer": readout_plan.layer,
                "site_key": readout_plan.site_key,
                "features": readout_plan.feature_ids,
                "random_features": readout_plan.random_ids,
                "mode": readout_plan.mode,
            },
            "head_plan": {
                "layer": args.head_layer,
                "target_heads": target_heads,
                "random_heads": random_heads,
                "alpha": args.head_alpha,
            },
            "tail": args.tail,
            "k_features": args.k_features,
            "max_new_tokens": args.max_new_tokens,
            "conditions": args.conditions,
            "seed": args.seed,
            "device": device,
            "sae_device": sae_device,
            "dtype": str(dtype),
        },
        "conditions": summaries,
        "paired_effects": paired,
        "outputs": dict(results),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n")
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
