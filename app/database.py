from __future__ import annotations

import json
import asyncio
from pathlib import Path
from collections.abc import Iterator, MutableMapping
from typing import TypeVar
from collections import defaultdict

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

#Concurrency locks
shift_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

def load_sample_data() -> None:
    """
    Loads sample caregiver and shift data from 'sample_data.json' into the in-memory databases.

    - Reads the JSON file located in the same directory as this file.
    - Populates the caregivers_db with caregiver records, keyed by caregiver ID.
    - Populates the shifts_db with shift records, keyed by shift ID.
      For each shift, ensures default fields:
        - 'status' (default: 'open')
        - 'assigned_caregiver' (default: None)
        - 'fanout_round' (default: 0)
        - 'contacted' (default: empty list)
    """
    sample_path = Path(__file__).parent.parent / "sample_data.json"
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


async def claim_shift(shift_id: str, caregiver_id: str) -> bool:
    """
    Attempts to claim a shift for a caregiver.

    - Locks the shift record using a per-shift lock to prevent concurrent claims.
    - Checks if the shift is open.
    - If valid, updates the shift status to 'claimed' and assigns the caregiver.
    - Returns True on success, False if the shift is not open.
    """
    async with shift_locks[shift_id]:  
        shift = shifts_db.get(shift_id)
        if shift and shift["status"] == "open":
            shift["status"] = "claimed"
            shift["assigned_caregiver"] = caregiver_id
            shifts_db.put(shift_id, shift)
            return True
        return False
