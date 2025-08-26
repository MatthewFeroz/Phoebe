from __future__ import annotations

import json
import asyncio
from pathlib import Path
from collections.abc import Iterator, MutableMapping
from typing import TypeVar
from collections import defaultdict
from app.database import shifts_db, shift_locks

K = TypeVar("K")
V = TypeVar("V")

class InMemoryKeyValueDatabase[K, V]:
    """
    Simple in-memory key/value database.
    """

    def __init__(self) -> None:
        self._store: MutableMapping[K, V] = {}

    def put(self, key: K, value: V) -> None:
        self._store[key] = value

    def get(self, key: K) -> V | None:
        return self._store.get(key)

    def delete(self, key: K) -> None:
        self._store.pop(key, None)

    def all(self) -> list[V]:
        return list(self._store.values())

    def clear(self) -> None:
        self._store.clear()

    def __iter__(self) -> Iterator[V]:
        return iter(self._store.values())

    def __len__(self) -> int:
        return len(self._store)

#Create global databases
caregivers_db: InMemoryKeyValueDatabase[str, dict] = InMemoryKeyValueDatabase()
shifts_db: InMemoryKeyValueDatabase[str, dict] = InMemoryKeyValueDatabase()

def load_sample_data() -> None:
    # This line gets the directory path where the current file (database.py) is located.
    sample_path = Path(__file__).parent / "sample_data.json"
    with open(sample_path) as f:
        data = json.load(f)
    
    for caregiver in data.get("caregivers", []):
        caregivers_db.put(caregiver["id"], caregiver)
    
    for shift in data.get("shifts", []):
        shift.setdefault("status", "open")
        shift.setdefault("assigned_caregiver", None)
        shift.setdefault("fanout_round", 0)
        shift.setdefault("contacted", [])
        shifts_db.put(shift["id"], shift)

