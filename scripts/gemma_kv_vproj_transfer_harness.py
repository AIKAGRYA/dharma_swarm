#!/usr/bin/env python3
"""
Gemma-2-9B KV-cache + persistent V-projection transfer harness.

This ports the older one-off Gemma behavioral-transfer script to current
Transformers DynamicCache and evaluates the method with the same output/state
metrics used by the Gemma Scope feature-install pilots.
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
from transformers import AutoModelForCausalLM, AutoTokenizer
from transformers.cache_utils import DynamicCache


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
    print(f"[gemma_kv_vproj_transfer] {message}", file=sys.stderr, flush=True)


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


def feature_ids_from_probe(probe_summary: Path, site_key: str, k: int) -> list[int]:
    data = gfi.load_json(probe_summary)
    if site_key not in data.get("sites", {}):
        raise KeyError(f"{site_key!r} not in probe summary. Available: {sorted(data.get('sites', {}))}")
    return [int(idx) for idx in data["sites"][site_key]["top_features"][:k]]


def cache_to_list(cache) -> list[tuple[torch.Tensor, torch.Tensor]]:
    return [(k.detach(), v.detach()) for k, v, *_ in cache]


def encode_cache_prefix(model, tokenizer, prompt: str, max_length: int):
    input_device = next(model.parameters()).device
    enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length)
    input_ids = enc["input_ids"].to(input_device)
    if input_ids.shape[1] < 2:
        raise ValueError("Prompt must tokenize to at least two tokens for prefix-cache generation")
    prefix_ids = input_ids[:, :-1]
    last_id = input_ids[:, -1:]
    with torch.no_grad():
        outputs = model(input_ids=prefix_ids, use_cache=True, return_dict=True)
    return cache_to_list(outputs.past_key_values), input_ids, last_id


def patch_cache_tail(
    *,
    model,
    base_cache: list[tuple[torch.Tensor, torch.Tensor]],
    donor_cache: list[tuple[torch.Tensor, torch.Tensor]],
    tail: int,
    layers: Sequence[int] | None = None,
    alpha: float = 1.0,
    component: str = "kv",
) -> DynamicCache:
    layer_set = set(layers) if layers is not None else None
    patched = DynamicCache(config=model.config)
    for layer_idx, (base_k, base_v) in enumerate(base_cache):
        donor_k, donor_v = donor_cache[layer_idx]
        out_k = base_k.clone()
        out_v = base_v.clone()
        if layer_set is None or layer_idx in layer_set:
            n = min(tail, out_k.shape[2], donor_k.shape[2])
            if n > 0:
                donor_k_tail = donor_k[:, :, -n:, :].to(out_k.device, dtype=out_k.dtype)
                donor_v_tail = donor_v[:, :, -n:, :].to(out_v.device, dtype=out_v.dtype)
                if alpha == 1.0:
                    if component in {"k", "kv"}:
                        out_k[:, :, -n:, :] = donor_k_tail
                    if component in {"v", "kv"}:
                        out_v[:, :, -n:, :] = donor_v_tail
                else:
                    if component in {"k", "kv"}:
                        out_k[:, :, -n:, :] = (1 - alpha) * out_k[:, :, -n:, :] + alpha * donor_k_tail
                    if component in {"v", "kv"}:
                        out_v[:, :, -n:, :] = (1 - alpha) * out_v[:, :, -n:, :] + alpha * donor_v_tail
        patched.update(out_k, out_v, layer_idx)
    return patched


def parse_layer_spec(raw: str, num_layers: int) -> list[int] | None:
    raw = raw.strip().lower()
    if raw in {"", "all", "*"}:
        return None
    layers: set[int] = set()
    for piece in raw.split(","):
        piece = piece.strip()
        if not piece:
            continue
        if "-" in piece:
            lo_raw, hi_raw = piece.split("-", 1)
            lo = int(lo_raw)
            hi = int(hi_raw)
            layers.update(range(lo, hi + 1))
        else:
            layers.add(int(piece))
    bad = [layer for layer in sorted(layers) if layer < 0 or layer >= num_layers]
    if bad:
        raise ValueError(f"Layer spec {raw!r} includes invalid layers for {num_layers} layers: {bad}")
    return sorted(layers)


def capture_vproj_activations(model, tokenizer, prompt: str, layers: Sequence[int], max_length: int) -> dict[int, torch.Tensor]:
    input_device = next(model.parameters()).device
    captures: dict[int, torch.Tensor] = {}
    handles = []

    def make_hook(layer: int):
        def hook(_module, _inputs, output):
            captures[layer] = output.detach().clone()
            return None

        return hook

    for layer in layers:
        handles.append(model.model.layers[layer].self_attn.v_proj.register_forward_hook(make_hook(layer)))
    try:
        enc = tokenizer(prompt, return_tensors="pt", truncation=True, max_length=max_length)
        enc = gfi.to_input_device(enc, input_device)
        with torch.no_grad():
            model(**enc, use_cache=True)
    finally:
        for handle in handles:
            handle.remove()
    return captures


class PersistentVProjPatcher:
    def __init__(self, donor_v: dict[int, torch.Tensor], tail: int):
        self.donor_v = donor_v
        self.tail = tail
        self.handles = []

    def make_hook(self, layer: int):
        def hook(_module, _inputs, output):
            patched = output.clone()
            donor = self.donor_v[layer].to(device=patched.device, dtype=patched.dtype)
            n = min(self.tail, patched.shape[1], donor.shape[1])
            if n > 0:
                patched[:, -n:, :] = donor[:, -n:, :]
            return patched

        return hook

    def register(self, model, layers: Sequence[int]) -> None:
        for layer in layers:
            self.handles.append(model.model.layers[layer].self_attn.v_proj.register_forward_hook(self.make_hook(layer)))

    def remove(self) -> None:
        for handle in self.handles:
            handle.remove()
        self.handles = []


def generate_from_patched_prefix(
    model,
    tokenizer,
    prompt: str,
    *,
    patched_cache: DynamicCache,
    initial_last_id: torch.Tensor,
    max_new_tokens: int,
    vpatcher: PersistentVProjPatcher | None = None,
    vproj_layers: Sequence[int] = (),
) -> tuple[str, str, bool]:
    generated_ids = tokenizer(prompt, return_tensors="pt")["input_ids"].to(next(model.parameters()).device)
    current_kv = patched_cache
    current_id = initial_last_id
    eos_reached = False

    if vpatcher is not None:
        vpatcher.register(model, vproj_layers)
    try:
        for _ in range(max_new_tokens):
            with torch.no_grad():
                outputs = model(input_ids=current_id, past_key_values=current_kv, use_cache=True, return_dict=True)
            next_token = outputs.logits[:, -1, :].argmax(dim=-1, keepdim=True)
            generated_ids = torch.cat([generated_ids, next_token], dim=-1)
            current_id = next_token
            current_kv = outputs.past_key_values
            if tokenizer.eos_token_id is not None and int(next_token.item()) == int(tokenizer.eos_token_id):
                eos_reached = True
                break
    finally:
        if vpatcher is not None:
            vpatcher.remove()

    full_text = tokenizer.decode(generated_ids[0], skip_special_tokens=True)
    continuation = full_text[len(prompt) :].strip()
    return full_text, continuation, eos_reached


def generate_with_vproj_only(
    model,
    tokenizer,
    prompt: str,
    *,
    max_new_tokens: int,
    vpatcher: PersistentVProjPatcher,
    vproj_layers: Sequence[int],
) -> tuple[str, str, bool]:
    vpatcher.register(model, vproj_layers)
    try:
        return gfi.generate_condition(model, tokenizer, prompt, max_new_tokens, None)
    finally:
        vpatcher.remove()


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


@dataclass
class DonorState:
    prompt_id: str
    text: str
    cache: list[tuple[torch.Tensor, torch.Tensor]]
    vproj: dict[int, torch.Tensor]


def compress_cache_v_tails_global(
    cache: list[tuple[torch.Tensor, torch.Tensor]],
    *,
    tail: int,
    layers: Sequence[int] | None,
    ranks: Sequence[int],
) -> tuple[dict[int, list[tuple[torch.Tensor, torch.Tensor]]], dict[str, object]]:
    """Low-rank SVD of donor V-cache tails across selected layers and tokens."""
    if not ranks:
        return {}, {}
    layer_set = set(layers) if layers is not None else set(range(len(cache)))
    rows = []
    specs = []
    for layer_idx, (_key, value) in enumerate(cache):
        if layer_idx not in layer_set:
            continue
        n = min(tail, value.shape[2])
        if n <= 0:
            continue
        value_tail = value[:, :, -n:, :].float().cpu()
        matrix = value_tail[0].permute(1, 0, 2).reshape(n, -1)
        rows.append(matrix)
        specs.append((layer_idx, n, value_tail.shape[1], value_tail.shape[3]))
    if not rows:
        return {}, {"error": "no selected V-cache tails to compress"}

    matrix = torch.cat(rows, dim=0)
    u, s, vh = torch.linalg.svd(matrix, full_matrices=False)
    total_energy = float(torch.sum(s * s).item())
    max_rank = int(s.shape[0])
    compressed: dict[int, list[tuple[torch.Tensor, torch.Tensor]]] = {}
    energy_by_rank: dict[str, float] = {}

    for raw_rank in ranks:
        rank = max(0, min(int(raw_rank), max_rank))
        if rank == 0:
            approx = torch.zeros_like(matrix)
        else:
            approx = (u[:, :rank] * s[:rank]) @ vh[:rank, :]
        energy_by_rank[str(raw_rank)] = (
            float(torch.sum(s[:rank] * s[:rank]).item() / total_energy) if total_energy > 1e-12 else float("nan")
        )

        cursor = 0
        rebuilt = [(key.clone(), value.clone()) for key, value in cache]
        for layer_idx, n, n_heads, head_dim in specs:
            chunk = approx[cursor : cursor + n]
            cursor += n
            value_tail = chunk.reshape(n, n_heads, head_dim).permute(1, 0, 2).unsqueeze(0)
            target = rebuilt[layer_idx][1]
            target[:, :, -n:, :] = value_tail.to(device=target.device, dtype=target.dtype)
        compressed[int(raw_rank)] = rebuilt

    diagnostics = {
        "scope": "global_layer_token_rows",
        "matrix_shape": list(matrix.shape),
        "selected_layers": sorted(layer_set),
        "max_rank": max_rank,
        "requested_ranks": [int(rank) for rank in ranks],
        "energy_retained": energy_by_rank,
        "top_singular_values": [float(x) for x in s[: min(12, len(s))].tolist()],
    }
    return compressed, diagnostics


def tail_pad_cache(cache: list[tuple[torch.Tensor, torch.Tensor]], tail: int) -> list[tuple[torch.Tensor, torch.Tensor]]:
    out = []
    for key, value in cache:
        n = min(tail, key.shape[2])
        key_tail = torch.zeros((*key.shape[:2], tail, key.shape[3]), dtype=torch.float32)
        value_tail = torch.zeros((*value.shape[:2], tail, value.shape[3]), dtype=torch.float32)
        key_tail[:, :, -n:, :] = key[:, :, -n:, :].float().cpu()
        value_tail[:, :, -n:, :] = value[:, :, -n:, :].float().cpu()
        out.append((key_tail, value_tail))
    return out


def tail_pad_vproj(vproj: dict[int, torch.Tensor], tail: int) -> dict[int, torch.Tensor]:
    out = {}
    for layer, value in vproj.items():
        n = min(tail, value.shape[1])
        tail_value = torch.zeros((value.shape[0], tail, value.shape[2]), dtype=torch.float32)
        tail_value[:, -n:, :] = value[:, -n:, :].float().cpu()
        out[layer] = tail_value
    return out


def mean_cache_tails(caches: list[list[tuple[torch.Tensor, torch.Tensor]]], tail: int) -> list[tuple[torch.Tensor, torch.Tensor]]:
    padded = [tail_pad_cache(cache, tail) for cache in caches]
    out = []
    for layer_idx in range(len(padded[0])):
        keys = torch.stack([cache[layer_idx][0] for cache in padded], dim=0).mean(dim=0)
        values = torch.stack([cache[layer_idx][1] for cache in padded], dim=0).mean(dim=0)
        out.append((keys, values))
    return out


def mean_vproj_tails(vprojs: list[dict[int, torch.Tensor]], tail: int) -> dict[int, torch.Tensor]:
    padded = [tail_pad_vproj(vproj, tail) for vproj in vprojs]
    return {
        layer: torch.stack([vproj[layer] for vproj in padded], dim=0).mean(dim=0)
        for layer in padded[0]
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
    parser.add_argument("--positive-prefix", default="recursive_self_reference_")
    parser.add_argument("--pseudo-prefix", default="same_vocab_different_semantics_")
    parser.add_argument("--baseline-prefixes", nargs="+", default=["baseline_factual_", "baseline_math_", "baseline_creative_"])
    parser.add_argument("--donor-offset", type=int, default=0)
    parser.add_argument("--sham-offset", type=int, default=0)
    parser.add_argument("--donor-mode", choices=["single", "mean"], default="single")
    parser.add_argument("--mean-donor-count", type=int, default=4)
    parser.add_argument("--mean-sham-count", type=int, default=4)
    parser.add_argument("--tail", type=int, default=16)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--max-new-tokens", type=int, default=64)
    parser.add_argument("--readout-layer", type=int, default=35)
    parser.add_argument("--readout-site-key", default="L35_resid_tail")
    parser.add_argument("--early-layer", type=int, default=6)
    parser.add_argument("--late-layer", type=int, default=38)
    parser.add_argument("--vproj-layers", default="35,38")
    parser.add_argument("--kv-layers", default="all", help="Comma/range spec, e.g. all, 0-17, 18-41, 35,38.")
    parser.add_argument("--kv-component", choices=["k", "v", "kv"], default="kv")
    parser.add_argument(
        "--kv-svd-ranks",
        nargs="*",
        type=int,
        default=[],
        help="Optional global low-rank SVD ranks for donor V-cache tails. Use conditions kv_vproj_svd_<rank>.",
    )
    parser.add_argument("--k-features", type=int, default=16)
    parser.add_argument("--kv-alpha", type=float, default=1.0)
    parser.add_argument(
        "--conditions",
        nargs="+",
        default=["kv_only", "vproj_only", "kv_vproj", "sham_kv_vproj"],
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
    vproj_layers = [int(piece.strip()) for piece in args.vproj_layers.split(",") if piece.strip()]
    kv_layers = parse_layer_spec(args.kv_layers, num_layers=42)

    bank = gfi.load_json(args.bank)
    natural_items = gfi.select_items(bank, args.positive_prefix, args.n_natural, "natural_reference")
    control_items = gfi.select_items(bank, args.pseudo_prefix, args.n_control, "pseudo_control")
    baseline_items: list[gfi.PromptItem] = []
    for prefix in args.baseline_prefixes:
        baseline_items.extend(gfi.select_items(bank, prefix, args.n_baseline_per_group, prefix.rstrip("_")))
    donor_item = natural_items[args.donor_offset % len(natural_items)]
    sham_item = control_items[args.sham_offset % len(control_items)]

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

    readout_features = feature_ids_from_probe(args.probe_summary, args.readout_site_key, args.k_features)
    log(f"loading readout SAE L{args.readout_layer}")
    readout_sae = gfi.load_sae(args.readout_layer, "resid", "16k", sae_device)

    def build_single_donor(item: gfi.PromptItem) -> DonorState:
        log(f"encoding donor state: {item.prompt_id}")
        cache, _, _ = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
        vproj = capture_vproj_activations(model, tokenizer, item.text, vproj_layers, args.max_length)
        return DonorState(prompt_id=item.prompt_id, text=item.text, cache=cache, vproj=vproj)

    def build_mean_donor(items: list[gfi.PromptItem], label: str, count: int, offset: int) -> DonorState:
        selected = [items[(offset + idx) % len(items)] for idx in range(count)]
        log(f"encoding mean {label} donor from {[item.prompt_id for item in selected]}")
        caches = []
        vprojs = []
        for item in selected:
            cache, _, _ = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            caches.append(cache)
            vprojs.append(capture_vproj_activations(model, tokenizer, item.text, vproj_layers, args.max_length))
        return DonorState(
            prompt_id="mean:" + ",".join(item.prompt_id for item in selected),
            text="",
            cache=mean_cache_tails(caches, args.tail),
            vproj=mean_vproj_tails(vprojs, args.tail),
        )

    if args.donor_mode == "mean":
        donor = build_mean_donor(natural_items, "recursive", args.mean_donor_count, args.donor_offset)
        sham = build_mean_donor(control_items, "sham", args.mean_sham_count, args.sham_offset)
    else:
        donor = build_single_donor(donor_item)
        sham = build_single_donor(sham_item)

    compressed_donor_caches, donor_svd_diagnostics = compress_cache_v_tails_global(
        donor.cache,
        tail=args.tail,
        layers=kv_layers,
        ranks=args.kv_svd_ranks,
    )
    compressed_sham_caches, sham_svd_diagnostics = compress_cache_v_tails_global(
        sham.cache,
        tail=args.tail,
        layers=kv_layers,
        ranks=args.kv_svd_ranks,
    )

    results: dict[str, list[dict]] = defaultdict(list)
    vectors: dict[str, list[np.ndarray]] = defaultdict(list)

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
        full_text, continuation, eos = gfi.generate_condition(model, tokenizer, item.text, args.max_new_tokens, None)
        record("natural_reference", item, full_text, continuation, eos, natural_centroid=None)

    natural_centroid = np.nanmean(np.stack(vectors["natural_reference"], axis=0), axis=0)

    def run_condition(condition: str, item: gfi.PromptItem):
        if condition.startswith("kv_vproj_svd_"):
            rank = int(condition.rsplit("_", 1)[-1])
            if rank not in compressed_donor_caches:
                raise ValueError(f"Rank {rank} was not built. Pass --kv-svd-ranks {rank}.")
            base_cache, _input_ids, last_id = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            patched = patch_cache_tail(
                model=model,
                base_cache=base_cache,
                donor_cache=compressed_donor_caches[rank],
                tail=args.tail,
                layers=kv_layers,
                alpha=args.kv_alpha,
                component=args.kv_component,
            )
            return generate_from_patched_prefix(
                model,
                tokenizer,
                item.text,
                patched_cache=patched,
                initial_last_id=last_id,
                max_new_tokens=args.max_new_tokens,
                vpatcher=PersistentVProjPatcher(donor.vproj, args.tail),
                vproj_layers=vproj_layers,
            )
        if condition.startswith("sham_kv_vproj_svd_"):
            rank = int(condition.rsplit("_", 1)[-1])
            if rank not in compressed_sham_caches:
                raise ValueError(f"Rank {rank} was not built. Pass --kv-svd-ranks {rank}.")
            base_cache, _input_ids, last_id = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            patched = patch_cache_tail(
                model=model,
                base_cache=base_cache,
                donor_cache=compressed_sham_caches[rank],
                tail=args.tail,
                layers=kv_layers,
                alpha=args.kv_alpha,
                component=args.kv_component,
            )
            return generate_from_patched_prefix(
                model,
                tokenizer,
                item.text,
                patched_cache=patched,
                initial_last_id=last_id,
                max_new_tokens=args.max_new_tokens,
                vpatcher=PersistentVProjPatcher(sham.vproj, args.tail),
                vproj_layers=vproj_layers,
            )
        if condition == "kv_only":
            base_cache, _input_ids, last_id = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            patched = patch_cache_tail(
                model=model,
                base_cache=base_cache,
                donor_cache=donor.cache,
                tail=args.tail,
                layers=kv_layers,
                alpha=args.kv_alpha,
                component=args.kv_component,
            )
            return generate_from_patched_prefix(
                model,
                tokenizer,
                item.text,
                patched_cache=patched,
                initial_last_id=last_id,
                max_new_tokens=args.max_new_tokens,
            )
        if condition == "vproj_only":
            return generate_with_vproj_only(
                model,
                tokenizer,
                item.text,
                max_new_tokens=args.max_new_tokens,
                vpatcher=PersistentVProjPatcher(donor.vproj, args.tail),
                vproj_layers=vproj_layers,
            )
        if condition == "kv_vproj":
            base_cache, _input_ids, last_id = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            patched = patch_cache_tail(
                model=model,
                base_cache=base_cache,
                donor_cache=donor.cache,
                tail=args.tail,
                layers=kv_layers,
                alpha=args.kv_alpha,
                component=args.kv_component,
            )
            return generate_from_patched_prefix(
                model,
                tokenizer,
                item.text,
                patched_cache=patched,
                initial_last_id=last_id,
                max_new_tokens=args.max_new_tokens,
                vpatcher=PersistentVProjPatcher(donor.vproj, args.tail),
                vproj_layers=vproj_layers,
            )
        if condition == "sham_kv_vproj":
            base_cache, _input_ids, last_id = encode_cache_prefix(model, tokenizer, item.text, args.max_length)
            patched = patch_cache_tail(
                model=model,
                base_cache=base_cache,
                donor_cache=sham.cache,
                tail=args.tail,
                layers=kv_layers,
                alpha=args.kv_alpha,
                component=args.kv_component,
            )
            return generate_from_patched_prefix(
                model,
                tokenizer,
                item.text,
                patched_cache=patched,
                initial_last_id=last_id,
                max_new_tokens=args.max_new_tokens,
                vpatcher=PersistentVProjPatcher(sham.vproj, args.tail),
                vproj_layers=vproj_layers,
            )
        raise ValueError(f"Unknown condition: {condition}")

    for item in baseline_items:
        log(f"baseline generate: {item.prompt_id}")
        full_text, continuation, eos = gfi.generate_condition(model, tokenizer, item.text, args.max_new_tokens, None)
        record("baseline", item, full_text, continuation, eos, natural_centroid=natural_centroid)
        for condition in args.conditions:
            log(f"{condition} generate: {item.prompt_id}")
            full_text, continuation, eos = run_condition(condition, item)
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
            "donor_prompt_id": donor.prompt_id,
            "sham_prompt_id": sham.prompt_id,
            "donor_mode": args.donor_mode,
            "tail": args.tail,
            "kv_alpha": args.kv_alpha,
            "kv_layers": "all" if kv_layers is None else kv_layers,
            "kv_component": args.kv_component,
            "kv_svd_ranks": args.kv_svd_ranks,
            "donor_svd_diagnostics": donor_svd_diagnostics,
            "sham_svd_diagnostics": sham_svd_diagnostics,
            "vproj_layers": vproj_layers,
            "readout_layer": args.readout_layer,
            "readout_features": readout_features,
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
