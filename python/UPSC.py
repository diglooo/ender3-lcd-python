import re
import subprocess
from typing import Any, Dict, List, Optional


_NUMBER_RE = re.compile(r"^[+-]?(?:\d+|\d+\.\d*|\.\d+)(?:[eE][+-]?\d+)?$")


def _parse_value(value: str) -> Any:
    normalized = value.strip()
    lower = normalized.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if normalized.isdigit() or (normalized.startswith(('+', '-')) and normalized[1:].isdigit()):
        try:
            return int(normalized)
        except ValueError:
            pass
    if _NUMBER_RE.match(normalized):
        try:
            return float(normalized)
        except ValueError:
            pass
    return normalized


def _normalize_key(key: str) -> str:
    return key.strip().replace('.', '_').replace(' ', '_')


def run_upsc(device: str = "apcups@localhost", timeout: int = 10) -> str:
    """Run `upsc <device>` and return its stdout output."""
    result = subprocess.run(
        ["upsc", device], capture_output=True, text=True, timeout=timeout
    )
    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(
            f"upsc failed for {device}: returncode={result.returncode}, stderr={stderr}"
        )
    return result.stdout


class UPSC:
    """Parser for `upsc` key/value output.

    The original key names are preserved in `raw`, while normalized attributes
    are available through attribute access and `data`.
    """

    def __init__(self, raw: Optional[Dict[str, Any]] = None, messages: Optional[List[str]] = None):
        self.raw: Dict[str, Any] = raw or {}
        self.data: Dict[str, Any] = {k: v for k, v in self.raw.items()}
        self.messages: List[str] = messages or []

        for key, value in self.raw.items():
            normalized = _normalize_key(key)
            if normalized and not hasattr(self, normalized):
                setattr(self, normalized, value)

    @classmethod
    def from_output(cls, output: str) -> "UPSC":
        raw: Dict[str, Any] = {}
        messages: List[str] = []

        for line in output.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if ':' not in stripped:
                messages.append(stripped)
                continue

            key, value = stripped.split(':', 1)
            raw[key.strip()] = _parse_value(value)

        return cls(raw=raw, messages=messages)

    @classmethod
    def from_system(cls, device: str = "apcups@localhost", timeout: int = 10) -> "UPSC":
        output = run_upsc(device, timeout)
        return cls.from_output(output)

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.raw.get(key, default)

    def __repr__(self) -> str:
        return f"<UPSC {len(self.raw)} fields>"
