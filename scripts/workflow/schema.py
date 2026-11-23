"""A generic recursive shape check of a value against a schema of types, lists and dicts."""

from __future__ import annotations


def check(schema: object, value: object, path: str = "") -> list[str]:
    """Return one error per mismatch of value against schema, each naming its path.

    A type matches only that exact type (bool is not int); [T] matches a list of T
    (paths path[i]); {K: T} with K a type is a map (paths path.key); any other dict
    is a fixed-key object (missing keys error, extra keys allowed). [] when valid;
    never raises, never mutates value.
    """
    where = path or "result"
    if isinstance(schema, type):
        ok = type(value) is schema
        return [] if ok else [f"{where}: expected {schema.__name__}, got {type(value).__name__}"]
    kind = list if isinstance(schema, list) else dict
    if not isinstance(value, kind):
        return [f"{where}: expected {kind.__name__}, got {type(value).__name__}"]
    if isinstance(schema, list):
        return [e for i, v in enumerate(value) for e in check(schema[0], v, f"{path}[{i}]")]

    def join(k: object) -> str:
        return f"{path}.{k}" if path else str(k)

    if len(schema) == 1 and isinstance(next(iter(schema)), type):  # {K: T}: check every key and value
        ((key_type, item),) = schema.items()
        bad_keys = [f"{join(k)}: key expected {key_type.__name__}" for k in value if not isinstance(k, key_type)]
        return bad_keys + [e for k, v in value.items() if isinstance(k, key_type) for e in check(item, v, join(k))]
    errors = [f"{join(k)}: missing" for k in schema if k not in value]
    return errors + [e for k, sub in schema.items() if k in value for e in check(sub, value[k], join(k))]
