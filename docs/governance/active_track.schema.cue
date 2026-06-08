// active_track.schema.cue — OPTIONAL bleeding-edge validation layer for
// docs/governance/ACTIVE_TRACK.yaml (the v2 track-portfolio schema).
//
// This is NOT a hard CI dependency. The required gate is the stdlib-only
// Python checker (scripts/governance/check_track_status.py), which matches the
// repo's no-new-substrate discipline. CUE is offered for anyone who has it
// installed and wants structural + value validation with order-independent
// (concurrent-editor-safe) merge semantics:
//
//     cue vet docs/governance/ACTIVE_TRACK.yaml docs/governance/active_track.schema.cue
//
// CUE handles shape, types, bounds, enums, closed structs, and cross-field
// constraints. It does NOT cleanly express graph invariants (dependency-cycle
// detection, edge resolution, active-active conflict) — those live in the
// Python checker. Use both: CUE for shape, Python for the graph.

#Id: =~"^[a-z0-9][a-z0-9-]*$"

#Criterion: {
	id:   string & !=""
	kind: "file_exists" | "file_contains" | "pr_merged"
	if kind == "file_exists" {file: string & !=""}
	if kind == "file_contains" {
		file:    string & !=""
		pattern: string & !=""
	}
	if kind == "pr_merged" {pr: int}
	...
}

#NextItem: {
	id:      int | string
	what:    string & !=""
	kind:    "code" | "docs" | "test" | "data" | "runtime"
	blocker?: bool
	...
}

#SpineObjective: {
	id:       #Id
	name:     string & !=""
	ref?:     string
	measure?: string
	...
}

#Track: {
	id:          #Id
	name:        string & !=""
	status:      "ACTIVE" | "SHIPPABLE" | "PAUSED"
	opened_at?:  string
	verified_at: string & !=""
	ttl_days:    int & >0 & <=90
	owner:       string & !=""

	// How it ties to the spine — required; the Python checker verifies the
	// value resolves to a declared spine_objectives id.
	serves: #Id

	// Typed edges to sibling tracks (id references; graph validity in Python).
	complements?:    [...#Id]
	depends_on?:     [...#Id]
	conflicts_with?: [...#Id]

	// The no-global-mutex coordination plane: overlap among ACTIVE tracks warns.
	owned_surfaces?:    [...string]
	moves_vital_signs?: [...string]

	description?:        string
	prerequisites?:      [...#Criterion]
	completion_criteria?: [...#Criterion]
	non_goals?:          [...string]
	next_items?:         [...#NextItem]
	...
}

#TrackPolicy: {
	model?:                        string
	min_active:                    int & >=1            // floor; default 1 in checker
	max_active:                    int & >=1 & <=10     // ceiling — focus protection
	warn_active:                   int & >=1
	min_active_grace_days?:        int & >=0
	allow_active_active_conflict?: bool
	surface_overlap?:              "warn" | "error"
	if warn_active != _|_ && max_active != _|_ {
		warn_active: <=max_active
	}
	...
}

// Top-level document (v2).
schema_version: 1 | 2
spine_objectives: [...#SpineObjective]
track_policy?: #TrackPolicy
family?: {...}
vital_signs?: {
	source?:         string
	dashboard_route?: string
	dimensions?:     [...string]
	...
}
active_tracks: [...#Track] & [_, ...] | *[]   // v2: list of tracks
active_track?: #Track                          // v1 legacy singular (adapter)
closed_tracks?: [...{id: #Id, ...}]
living_axioms_ref?: string

// At least one track must be declared (v1 singular OR v2 list).
_hasTrack: len(active_tracks) > 0 | (active_track != _|_)
_hasTrack: true

// Keep the WIP ceiling honest: no more ACTIVE tracks than max_active.
if track_policy != _|_ {
	_activeCount: len([for t in active_tracks if t.status == "ACTIVE" {t}])
	_activeCount: <=track_policy.max_active
}
