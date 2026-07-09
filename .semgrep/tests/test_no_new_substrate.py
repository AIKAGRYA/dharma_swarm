import sqlite3


# ruleid: dharma.no-new-substrate
class WidgetStore:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)


# ruleid: dharma.no-new-substrate
class RunLedger:
    def open(self, db_path):
        self._conn = sqlite3.connect(db_path)


# ruleid: dharma.no-new-substrate
class ThingRegistry:
    _conn = sqlite3.connect("things.db")


# A class whose name does NOT end in Store/Ledger/Registry/Substrate is not
# caught: opening its own SQLite is not what this rule polices.
# ok: dharma.no-new-substrate
class PlainEngine:
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path)
