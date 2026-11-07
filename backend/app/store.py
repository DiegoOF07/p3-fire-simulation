from __future__ import annotations

import uuid
from collections import OrderedDict
from typing import Generic, TypeVar

from app.contracts import Scene

T = TypeVar("T")


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class LRUStore(Generic[T]):
    """In-memory store that drops the least recently used entry past capacity."""

    def __init__(self, capacity: int) -> None:
        self._items: OrderedDict[str, T] = OrderedDict()
        self._capacity = capacity

    def put(self, key: str, value: T) -> str:
        self._items[key] = value
        self._items.move_to_end(key)
        if len(self._items) > self._capacity:
            self._items.popitem(last=False)
        return key

    def add(self, value: T) -> str:
        return self.put(new_id(), value)

    def get(self, key: str) -> T | None:
        value = self._items.get(key)
        if value is not None:
            self._items.move_to_end(key)
        return value

    def __len__(self) -> int:
        return len(self._items)


scenes: LRUStore[Scene] = LRUStore(16)
