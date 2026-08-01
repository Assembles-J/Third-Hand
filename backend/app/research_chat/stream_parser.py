"""Defensive parser for OpenAI-compatible upstream SSE chunks."""
from __future__ import annotations
import json
from collections.abc import Iterable

def parse_sse_lines(lines: Iterable[str]):
    for line in lines:
        if not line.startswith("data:"): continue
        body=line[5:].strip()
        if not body or body=="[DONE]": continue
        try: yield json.loads(body)
        except json.JSONDecodeError: continue

def chunk_delta(chunk):
    choices=chunk.get("choices") or []
    return (choices[0].get("delta") or {}) if choices else {}
