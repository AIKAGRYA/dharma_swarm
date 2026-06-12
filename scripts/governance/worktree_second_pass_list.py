"""List worktrees still needing inspection: everything minus gold/unsure/protected/active-stitch lanes."""
import json, os

m = json.load(open(os.path.expanduser('~/dharma_swarm/reports/worktree_triage_manifest_2026-06-10.json')))
GOLD = {
    '/Users/dhyana/dharma_swarm', '/Users/dhyana/dharma_swarm_live',
    '/Users/dhyana/cleanup_worktrees/dharma_swarm_memory_kernel_preflight_20260516',
    '/Users/dhyana/dharma_swarm_cashclaw', '/Users/dhyana/dharma_swarm_opus_identity',
    '/Users/dhyana/worktrees/dharma_swarm_runtime_truth_spine_v1',
    '/Users/dhyana/cleanup_worktrees/dharma_swarm_repair_pr323',
    '/Users/dhyana/dharma_capital_lab', '/Users/dhyana/.qwen/worktrees/holon-agent',
    '/Users/dhyana/dharma_swarm_governed_recursive_proof',
    '/Users/dhyana/worktrees/dharma_swarm_honest_spine_v2',
    '/Users/dhyana/cleanup_worktrees/dharma_swarm_recursive_evolution_20260516',
    '/Users/dhyana/dharma_swarm_substrate_spec',
}
UNSURE = {
    '/Users/dhyana/worktrees/dharma_swarm_spine_slice_b',
    '/Users/dhyana/dharma_swarm_main_cutover',
    '/Users/dhyana/dharma_swarm_pr_review_control',
}
KEEP = {
    '/Users/dhyana/ds_ws3', '/Users/dhyana/ds_ws4',
    '/Users/dhyana/ds_stitch_archive', '/Users/dhyana/ds_stitch_providers',
    '/Users/dhyana/ds_stitch_receipts',
}
rest = sorted(w['path'] for w in m if w.get('path') and w['path'] not in GOLD | UNSURE | KEEP)
print(len(rest), 'to inspect:')
for p in rest:
    print(' ', p)
