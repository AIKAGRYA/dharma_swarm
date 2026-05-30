"""Unit tests for dharma_swarm.storage_schema_registry.

Proves the contract for the eventual storage unification:
  - register_schema decorator semantics (dataclass-required, validation)
  - SCHEMA_REGISTRY isolation between tests
  - write_jsonl_versioned embeds reserved keys, rejects unknown schemas
  - read_jsonl_versioned strips reserved keys, validates schema_id, version
  - Migration chain composes correctly when auto_migrate=True
  - Version mismatch raises SchemaVersionMismatchError when auto_migrate=False
  - Unknown schema_id raises UnknownSchemaError unless strict=False
  - Round-trip preserves data
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from dharma_swarm.storage_schema_registry import (
    SCHEMA_REGISTRY,
    SchemaAlreadyRegisteredError,
    SchemaDescriptor,
    SchemaVersionMismatchError,
    UnknownSchemaError,
    clear_registry_for_tests,
    get_schema,
    read_jsonl_versioned,
    register_schema,
    registered_schema_ids,
    render_registry_summary,
    write_jsonl_versioned,
)


@pytest.fixture(autouse=True)
def _isolate_registry():
    snapshot = dict(SCHEMA_REGISTRY)
    clear_registry_for_tests()
    try:
        yield
    finally:
        clear_registry_for_tests()
        SCHEMA_REGISTRY.update(snapshot)


# ─── Decorator semantics ─────────────────────────────────────────────────────


def test_register_schema_returns_class_unchanged() -> None:
    @register_schema("test.Foo", version=1)
    @dataclass(frozen=True)
    class Foo:
        a: int
        b: str

    assert "test.Foo" in SCHEMA_REGISTRY
    f = SCHEMA_REGISTRY["test.Foo"]
    assert isinstance(f, SchemaDescriptor)
    assert f.cls is Foo
    assert f.version == 1
    assert Foo(a=1, b="x").a == 1


def test_register_schema_requires_dataclass() -> None:
    with pytest.raises(ValueError):
        @register_schema("test.NotDC", version=1)
        class NotDC:
            pass


def test_register_schema_duplicate_raises() -> None:
    @register_schema("test.Dup", version=1)
    @dataclass(frozen=True)
    class First:
        x: int

    with pytest.raises(SchemaAlreadyRegisteredError):
        @register_schema("test.Dup", version=1)
        @dataclass(frozen=True)
        class Second:
            x: int


def test_register_schema_rejects_empty_id() -> None:
    with pytest.raises(ValueError):
        @register_schema("", version=1)
        @dataclass(frozen=True)
        class Bad:
            pass


def test_register_schema_rejects_zero_version() -> None:
    with pytest.raises(ValueError):
        @register_schema("test.Bad", version=0)
        @dataclass(frozen=True)
        class Bad:
            pass


def test_get_schema_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_schema("nonexistent.thing")


def test_registered_schema_ids_sorted() -> None:
    @register_schema("z.Z", version=1)
    @dataclass(frozen=True)
    class Z:
        pass

    @register_schema("a.A", version=1)
    @dataclass(frozen=True)
    class A:
        pass

    @register_schema("m.M", version=1)
    @dataclass(frozen=True)
    class M:
        pass

    assert registered_schema_ids() == ["a.A", "m.M", "z.Z"]


# ─── JSONL write semantics ───────────────────────────────────────────────────


def test_write_jsonl_versioned_embeds_markers(tmp_path: Path) -> None:
    @register_schema("test.Rec", version=2)
    @dataclass(frozen=True)
    class Rec:
        x: int
        y: str

    p = tmp_path / "out.jsonl"
    n = write_jsonl_versioned(p, [Rec(x=1, y="a"), Rec(x=2, y="b")], schema_id="test.Rec")
    assert n == 2

    lines = p.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    import json
    obj = json.loads(lines[0])
    assert obj["__schema_id__"] == "test.Rec"
    assert obj["__schema_version__"] == 2
    assert obj["x"] == 1
    assert obj["y"] == "a"


def test_write_jsonl_versioned_unknown_schema_raises(tmp_path: Path) -> None:
    with pytest.raises(UnknownSchemaError):
        write_jsonl_versioned(tmp_path / "x.jsonl", [{"x": 1}], schema_id="unregistered.thing")


def test_write_jsonl_versioned_reserved_key_collision_raises(tmp_path: Path) -> None:
    @register_schema("test.Bad", version=1)
    @dataclass(frozen=True)
    class Bad:
        __schema_id__: str = "spoofed"  # type: ignore[misc]

    with pytest.raises(ValueError):
        write_jsonl_versioned(tmp_path / "x.jsonl", [Bad()], schema_id="test.Bad")


# ─── JSONL read semantics ────────────────────────────────────────────────────


def test_read_jsonl_versioned_round_trip(tmp_path: Path) -> None:
    @register_schema("test.RT", version=1)
    @dataclass(frozen=True)
    class RT:
        a: int
        b: str

    p = tmp_path / "rt.jsonl"
    write_jsonl_versioned(p, [RT(a=1, b="x"), RT(a=2, b="y")], schema_id="test.RT")
    out = read_jsonl_versioned(p, expected_schema_id="test.RT")
    assert out == [{"a": 1, "b": "x"}, {"a": 2, "b": "y"}]


def test_read_jsonl_versioned_strips_reserved_keys(tmp_path: Path) -> None:
    @register_schema("test.Strip", version=1)
    @dataclass(frozen=True)
    class S:
        v: int

    p = tmp_path / "s.jsonl"
    write_jsonl_versioned(p, [S(v=42)], schema_id="test.Strip")
    out = read_jsonl_versioned(p, expected_schema_id="test.Strip")
    assert out == [{"v": 42}]
    assert "__schema_id__" not in out[0]
    assert "__schema_version__" not in out[0]


def test_read_jsonl_versioned_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_jsonl_versioned(tmp_path / "absent.jsonl") == []


def test_read_jsonl_versioned_unknown_schema_strict_raises(tmp_path: Path) -> None:
    p = tmp_path / "alien.jsonl"
    p.write_text(
        '{"__schema_id__": "alien.Thing", "__schema_version__": 1, "x": 1}\n',
        encoding="utf-8",
    )
    with pytest.raises(UnknownSchemaError):
        read_jsonl_versioned(p)


def test_read_jsonl_versioned_unknown_schema_non_strict_passes(tmp_path: Path) -> None:
    p = tmp_path / "alien.jsonl"
    p.write_text(
        '{"__schema_id__": "alien.Thing", "__schema_version__": 1, "x": 1}\n',
        encoding="utf-8",
    )
    out = read_jsonl_versioned(p, strict=False)
    assert out == [{"x": 1}]


def test_read_jsonl_versioned_expected_id_mismatch_raises(tmp_path: Path) -> None:
    @register_schema("test.A", version=1)
    @dataclass(frozen=True)
    class A:
        v: int

    p = tmp_path / "a.jsonl"
    write_jsonl_versioned(p, [A(v=1)], schema_id="test.A")
    with pytest.raises(UnknownSchemaError):
        read_jsonl_versioned(p, expected_schema_id="test.NotA")


def test_read_jsonl_versioned_version_mismatch_raises(tmp_path: Path) -> None:
    @register_schema("test.Ver", version=2)
    @dataclass(frozen=True)
    class V:
        v: int

    # Manually write a v1 record
    p = tmp_path / "v.jsonl"
    p.write_text(
        '{"__schema_id__": "test.Ver", "__schema_version__": 1, "v": 99}\n',
        encoding="utf-8",
    )
    with pytest.raises(SchemaVersionMismatchError):
        read_jsonl_versioned(p, expected_schema_id="test.Ver")


def test_read_jsonl_versioned_auto_migrate(tmp_path: Path) -> None:
    def v1_to_v2(rec):
        rec["doubled"] = rec.pop("v") * 2
        return rec

    @register_schema("test.Mig", version=2, migrations={1: v1_to_v2})
    @dataclass(frozen=True)
    class Mig:
        doubled: int

    p = tmp_path / "m.jsonl"
    p.write_text(
        '{"__schema_id__": "test.Mig", "__schema_version__": 1, "v": 5}\n',
        encoding="utf-8",
    )
    out = read_jsonl_versioned(p, expected_schema_id="test.Mig", auto_migrate=True)
    assert out == [{"doubled": 10}]


def test_read_jsonl_versioned_auto_migrate_missing_step_raises(tmp_path: Path) -> None:
    @register_schema("test.Skip", version=3)  # current version 3, only have v1->v2 migration
    @dataclass(frozen=True)
    class Skip:
        v: int

    p = tmp_path / "skip.jsonl"
    p.write_text(
        '{"__schema_id__": "test.Skip", "__schema_version__": 1, "v": 1}\n',
        encoding="utf-8",
    )
    with pytest.raises(SchemaVersionMismatchError):
        read_jsonl_versioned(p, auto_migrate=True)


# ─── Round-trip with append ──────────────────────────────────────────────────


def test_write_jsonl_versioned_append(tmp_path: Path) -> None:
    @register_schema("test.App", version=1)
    @dataclass(frozen=True)
    class A:
        n: int

    p = tmp_path / "a.jsonl"
    write_jsonl_versioned(p, [A(n=1)], schema_id="test.App")
    write_jsonl_versioned(p, [A(n=2), A(n=3)], schema_id="test.App", append=True)
    out = read_jsonl_versioned(p, expected_schema_id="test.App")
    assert out == [{"n": 1}, {"n": 2}, {"n": 3}]


# ─── Inspector ───────────────────────────────────────────────────────────────


def test_render_registry_summary_empty() -> None:
    assert "empty" in render_registry_summary()


def test_render_registry_summary_populated() -> None:
    @register_schema("test.Sum", version=2, migrations={1: lambda r: r})
    @dataclass(frozen=True)
    class S:
        x: int

    s = render_registry_summary()
    assert "test.Sum" in s
    assert "v2" in s
    assert "migrations_from=1" in s
