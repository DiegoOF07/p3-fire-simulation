from app.store import LRUStore


def test_evicts_least_recently_used():
    store = LRUStore[int](2)
    a = store.add(1)
    b = store.add(2)
    store.get(a)
    store.add(3)
    assert store.get(a) == 1
    assert store.get(b) is None
    assert len(store) == 2
