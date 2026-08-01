import sqlite3
from typing import Protocol


class GraphStore:
    pass


# ruleid: dharma.no-new-substrate
class UndeclaredProjectionStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ok: dharma.no-new-substrate
class BridgeRegistry:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ok: dharma.no-new-substrate
class SQLiteGraphStore(GraphStore):
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ok: dharma.no-new-substrate
class KnowledgeStore:
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ruleid: dharma.no-new-substrate
class KnowledgeStore(Protocol):  # noqa: F811
    def __init__(self, path: str) -> None:
        self.conn = sqlite3.connect(path)


# ruleid: dharma.no-new-substrate
class InheritedProjectionStore(BridgeRegistry):
    pass
