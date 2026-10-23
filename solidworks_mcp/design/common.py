"""Canonical encoding and local immutable file helpers."""
import hashlib
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path


def now():
    return datetime.now(timezone.utc).isoformat()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def object_hash(value):
    return digest(encoded(value).encode("utf-8"))


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"invalid number: {x}")))


def write_new(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)
    return path


def finite(value, name="value", positive=False):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if positive and value <= 0:
        raise ValueError(f"{name} must be positive")
    return float(value)


def default_home():
    return Path(os.environ.get("SW_DESIGN_HOME", str(Path.home() / ".solidworks-design"))).expanduser().resolve()
