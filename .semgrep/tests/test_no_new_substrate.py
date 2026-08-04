"""Behavioral fixture for dharma.no-new-substrate (+ the collision companion).

Executed against the REAL rule file (.semgrep/dharma-anti-slop.yml) by
tests/test_semgrep_rule2_behavior.py, which asserts the exact set of finding
lines. Semgrep auto-ignores `tests/` directories, so this file's deliberate
violations never enter the strict repo scan.

Annotations follow semgrep's convention:
  # ruleid: <id>     -> the NEXT line must produce that finding
  # ok: <id>         -> the NEXT line must NOT produce that finding
  # todoruleid: <id> -> a KNOWN, NAMED gap: it should fire and does not
"""
import codecs
import io
import json
import sqlite3
from pathlib import Path
from typing import Protocol

import aiofiles
import aiosqlite


class GraphStore:
    pass


class CacheMixin:
    pass


# --- SQLite: the shapes the pre-2026-08-04 rule already caught -------------

# ruleid: dharma.no-new-substrate
class UndeclaredProjectionStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ruleid: dharma.no-new-substrate
class ClassBodySqliteStore:
    conn = sqlite3.connect("scratch.db")


# --- SQLite: shapes the pre-2026-08-04 rule MISSED -------------------------

# ruleid: dharma.no-new-substrate
class LocalVariableSqliteStore:
    def open_db(self, path: str):
        conn = sqlite3.connect(path)
        return conn


# ruleid: dharma.no-new-substrate
class ContextManagerSqliteStore:
    def query(self, path: str) -> None:
        with sqlite3.connect(path) as conn:
            conn.execute("SELECT 1")


# ruleid: dharma.no-new-substrate
class BareCallSqliteStore:
    def query(self, path: str) -> None:
        sqlite3.connect(path).execute("SELECT 1")


# ruleid: dharma.no-new-substrate
class NestedUnderIfSqliteStore:
    def connect(self, path: str) -> None:
        if not getattr(self, "_conn", None):
            try:
                self._conn = sqlite3.connect(path)
            except sqlite3.Error:
                self._conn = None


# ruleid: dharma.no-new-substrate
class AsyncAiosqliteStore:
    async def connect(self, path: str) -> None:
        self._conn = await aiosqlite.connect(path)


# --- JSONL / append substrates: promised since 2026-04-26, detected from
#     2026-08-04. These are the shapes forge_v1's Ledger and RunLedger use.

# ruleid: dharma.no-new-substrate
class PathOpenAppendLedger:
    """The exact shape of dharma_swarm/forge_v1/forge_v2/receipts.py::Ledger."""

    def append(self, record: dict) -> None:
        with self.path.open("a") as fh:
            fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class BuiltinOpenAppendLedger:
    def append(self, record: dict) -> None:
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class KeywordModeAppendLedger:
    def append(self, record: dict) -> None:
        fh = open(self.path, mode="a", encoding="utf-8")
        fh.write(json.dumps(record) + "\n")
        fh.close()


# ruleid: dharma.no-new-substrate
class PathOpenKeywordModeAppendLedger:
    def append(self, record: dict) -> None:
        with self.path.open(mode="at") as fh:
            json.dump(record, fh)


# ruleid: dharma.no-new-substrate
class ChainedPathOpenAppendRegistry:
    def append(self, record: dict) -> None:
        Path(self.path).open("a").write(json.dumps(record))


# ruleid: dharma.no-new-substrate
class BinaryAppendSubstrate:
    def append(self, blob: bytes) -> None:
        with open(self.path, "ab") as fh:
            fh.write(blob)


# ruleid: dharma.no-new-substrate
class NestedAppendLedger:
    def append(self, record: dict) -> None:
        if record:
            with open(self.path, "a") as fh:
                fh.write(json.dumps(record) + "\n")


# --- Append mode flags in a non-canonical ORDER. CPython treats the mode
#     string as a set (io.open: `modes = set(mode)`), so every one of these
#     appends exactly like "a". The pre-2026-08-04 regex anchored on a leading
#     "a" and missed all of them (codex review, PR #1220).

# ruleid: dharma.no-new-substrate
class PlusFirstAppendLedger:
    def append(self, record: dict) -> None:
        with open(self.path, "+a") as fh:
            fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class BinaryFirstAppendStore:
    def append(self, blob: bytes) -> None:
        with open(self.path, "ba") as fh:
            fh.write(blob)


# ruleid: dharma.no-new-substrate
class TextFirstAppendRegistry:
    def append(self, record: dict) -> None:
        fh = open(self.path, "ta")
        fh.write(json.dumps(record) + "\n")
        fh.close()


# ruleid: dharma.no-new-substrate
class PlusBinaryPathOpenLedger:
    def append(self, blob: bytes) -> None:
        with self.path.open("+ab") as fh:
            fh.write(blob)


# ruleid: dharma.no-new-substrate
class KeywordReorderedModeLedger:
    def append(self, record: dict) -> None:
        with open(self.path, mode="b+a") as fh:
            fh.write(json.dumps(record).encode())


# --- Qualified `.open(path, mode)`: aiofiles (a core dependency) and the
#     aliased builtins io/codecs/gzip. Mode is the SECOND positional argument
#     here, unlike Path.open — the pre-2026-08-04 shapes bound it to the path
#     and rejected every one of these (codex review, PR #1220).

# ruleid: dharma.no-new-substrate
class AiofilesPositionalAppendLedger:
    async def append(self, record: dict) -> None:
        async with aiofiles.open(self.path, "a") as fh:
            await fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class AiofilesKeywordAppendLedger:
    async def append(self, record: dict) -> None:
        async with aiofiles.open(self.path, mode="a") as fh:
            await fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class AiofilesAwaitAssignStore:
    async def append(self, record: dict) -> None:
        fh = await aiofiles.open(self.path, "a")
        await fh.write(json.dumps(record) + "\n")


# ruleid: dharma.no-new-substrate
class IoOpenAppendStore:
    def append(self, record: dict) -> None:
        fh = io.open(self.path, "a")
        fh.write(json.dumps(record) + "\n")


# --- Ratified WP-0C1R exemptions: Rule 2 must stay silent ------------------
# Rule 2's exemptions are NAME-scoped, so these three are silent under it
# wherever they appear — that is what the `ok:` lines prove.
#
# The COLLISION rule is name+FILE scoped (from 2026-08-04): silence is granted
# to dharma_swarm/{bridge_registry,graph_store,knowledge_units}.py only. This
# fixture is none of those, so the same three spellings are collisions here —
# which is the point. Proof that the real ratified files stay silent under
# BOTH rules is
# tests/test_semgrep_rule2_behavior.py::test_ratified_exemptions_stay_silent_in_the_real_tree,
# which scans them in the tree.

# ok: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class BridgeRegistry:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ok: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class SQLiteGraphStore(GraphStore):
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ok: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class KnowledgeStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# --- Inheriting a ratified exemption is a new substrate --------------------


class registries:  # noqa: N801
    """Stands in for a module namespace so the qualified-base fixture below is
    real, importable Python rather than an unresolvable import."""

    BridgeRegistry = BridgeRegistry


# ruleid: dharma.no-new-substrate
class InheritedProjectionStore(BridgeRegistry):
    pass


# A base list matches like an argument list: before 2026-08-04 only the
# exempt-base-FIRST spelling was caught. These three evaded (codex, PR #1220).

# ruleid: dharma.no-new-substrate
class TrailingBaseProjectionStore(CacheMixin, BridgeRegistry):
    pass


# ruleid: dharma.no-new-substrate
class QualifiedBaseProjectionStore(registries.BridgeRegistry):
    pass


# ruleid: dharma.no-new-substrate
class ThirdPositionBaseLedger(CacheMixin, GraphStore, SQLiteGraphStore):
    pass


# ok: dharma.no-new-substrate
class UnrelatedBaseStore(GraphStore, CacheMixin):
    """A composite base list with no exempt substrate in it stays silent —
    the widened `(..., $BASE, ...)` shape must not flag every subclass."""


# --- Name collision with a ratified exemption ------------------------------
# Rule 2 itself is name-scoped and swallows every one of these (documented gap
# in its message); the companion rule catches them because the name is
# re-used OUTSIDE its canonical file AND the class opens a substrate. The base
# list is irrelevant — none, one, or several.

# --- one base (the shape the first version of the companion rule covered) ---

# todoruleid: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class KnowledgeStore(Protocol):  # noqa: F811
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# todoruleid: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class BridgeRegistry(GraphStore):  # noqa: F811
    def append(self, record: dict) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(record) + "\n")


# --- ZERO bases: codex's and devin's shared finding. `class $NAME($BASE):`
#     binds exactly one base expression, so these matched nothing at all and
#     Rule 2's name-scoped pattern-not swallowed them: zero findings for the
#     exact collision the companion rule exists to prevent. ---

# todoruleid: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class BridgeRegistry:  # noqa: F811
    """A base-less copycat appending its own JSONL."""

    def append(self, record: dict) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(record) + "\n")


# todoruleid: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class KnowledgeStore:  # noqa: F811
    """A base-less copycat opening its own SQLite."""

    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# --- MULTIPLE bases: devin's second shape. Measured against semgrep 1.168.0
#     this one ALREADY matched `class $NAME($BASE):` before the fix — the
#     claim that it evaded is refuted. Kept as a fixture so the behavior is
#     locked in rather than re-argued. ---

# todoruleid: dharma.no-new-substrate
# ruleid: dharma.no-new-substrate-exempt-name-collision
class SQLiteGraphStore(GraphStore, CacheMixin):  # noqa: F811
    def append(self, record: dict) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(record) + "\n")


# ok: dharma.no-new-substrate-exempt-name-collision
class KnowledgeStoreProtocolNoSubstrate(Protocol):
    """Mirrors dharma_swarm/engine/knowledge_store.py: a colliding name with
    no substrate is inert and must stay silent."""

    def get(self, key: str) -> str: ...


# --- Negative controls: must produce NO finding ----------------------------

# ok: dharma.no-new-substrate
class ReadOnlyStore:
    def read(self) -> str:
        with open(self.path) as fh:
            return fh.read()


# ok: dharma.no-new-substrate
class TruncatingWriteStore:
    def write(self, payload: str) -> None:
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write(payload)


# ok: dharma.no-new-substrate
class ExclusiveCreateStore:
    def create(self, payload: str) -> None:
        with open(self.path, "x") as fh:
            fh.write(payload)


# ok: dharma.no-new-substrate
class ReadWriteTruncateStore:
    """`"w+"` and `"rb"` share flag characters with the append modes — the
    order-independent mode regex must still reject them."""

    def rewrite(self, payload: str) -> None:
        with open(self.path, "w+") as fh:
            fh.write(payload)


# ok: dharma.no-new-substrate
class BinaryReadStore:
    def load(self) -> bytes:
        with open(self.path, "rb") as fh:
            return fh.read()


# ok: dharma.no-new-substrate
class AppendishFilenameStore:
    """`open("audit.log")` must not be read as mode="a..." — the reason the
    positional shape requires a preceding path argument."""

    def read_audit(self) -> str:
        with open("audit.log") as fh:
            return fh.read()


# ok: dharma.no-new-substrate
class NotASubstrateClassName:
    def append(self, record: dict) -> None:
        with open(self.path, "a") as fh:
            fh.write(json.dumps(record) + "\n")


# ok: dharma.no-new-substrate
def module_level_append_ledger(path: Path, record: dict) -> None:
    with path.open("a") as fh:
        fh.write(json.dumps(record) + "\n")


# --- Named, NOT-silent gaps: these SHOULD fire and do not ------------------

# todoruleid: dharma.no-new-substrate
class WrapperFunctionSqliteStore:
    """Substrate opened through a helper — needs interprocedural taint."""

    def __init__(self, path: str) -> None:
        self.conn = _open_connection(path)


# Was a `todoruleid` gap ("aliased builtins") until 2026-08-04; the qualified
# path-first `.open` shape added for aiofiles closes it for free.
# ruleid: dharma.no-new-substrate
class AliasedOpenLedger:
    def append(self, record: dict) -> None:
        with codecs.open(self.path, "a", "utf-8") as fh:
            fh.write(json.dumps(record) + "\n")


# todoruleid: dharma.no-new-substrate
class VariableModeLedger:
    def append(self, record: dict, mode: str = "a") -> None:
        with open(self.path, mode) as fh:
            fh.write(json.dumps(record) + "\n")


# todoruleid: dharma.no-new-substrate
class ClassBodyAppendLedger:
    # /dev/null, not a real ledger path: a class body executes on import and
    # a fixture must not write into the tree.
    handle = open("/dev/null", "a")


def _open_connection(path: str):
    return sqlite3.connect(path)
