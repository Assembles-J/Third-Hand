"""Candidate-management domain.

Owns candidate source, lifecycle, cooldown and deterministic reactivation rules.
It must not own FastAPI transport or grant trading authority to AI research.
"""
