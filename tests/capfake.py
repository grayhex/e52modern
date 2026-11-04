"""Fake transport rows with a proper capability matrix (flat lists are no longer trusted)."""
from symport.phone import capabilities


def row(base: dict, available=(), untested_writes=(), unsupported=()) -> dict:
    m = capabilities.Matrix()
    for op in available:
        m.available(op, "test-fixture", "fixture probe")
    for op in untested_writes:
        m.untested(op, "test-fixture", "fixture write, never probed")
    for op in unsupported:
        m.unsupported(op, "test-fixture", "fixture")
    return capabilities.apply(dict(base), m)
