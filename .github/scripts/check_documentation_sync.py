from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


LEDGER = "docs/ThirdHand_v3_Roadmap_and_Ledger.md"
ARCH = "docs/ThirdHand_Architecture_v3_consolidated.md"

PRODUCT_PREFIXES = (
    "backend/app/",
    "android/app/src/main/",
)
PRODUCT_EXACT = {"android/app/build.gradle.kts"}

AUTHORITY_PREFIXES = (
    "backend/app/domain/strategy/",
    "backend/app/application_services/strategy/",
)
AUTHORITY_EXACT = {
    "backend/app/action_policy.py",
    "backend/app/timeframe_authority.py",
    "backend/app/research_assessment.py",
    "backend/app/execution_precheck.py",
    "backend/app/position_sizing.py",
    "backend/app/risk.py",
    "backend/app/paper_execution_contract.py",
}
AUTHORITY_GLOBS = (
    "backend/app/decision_",
    "backend/app/paper_runtime",
)


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], text=True).strip()


def changed_files(commit: str) -> set[str]:
    out = git("diff-tree", "--no-commit-id", "--name-only", "-r", commit)
    return {line for line in out.splitlines() if line}


def is_merge(commit: str) -> bool:
    parents = git("rev-list", "--parents", "-n", "1", commit).split()
    return len(parents) > 2


def is_product(path: str) -> bool:
    return path in PRODUCT_EXACT or path.startswith(PRODUCT_PREFIXES)


def is_authority(path: str) -> bool:
    return (
        path in AUTHORITY_EXACT
        or path.startswith(AUTHORITY_PREFIXES)
        or any(path.startswith(prefix) for prefix in AUTHORITY_GLOBS)
    )


def fail(message: str) -> None:
    print(f"documentation-governance: {message}", file=sys.stderr)


def main() -> int:
    base = os.environ.get("GOV_BASE_SHA", "").strip()
    head = os.environ.get("GOV_HEAD_SHA", "").strip() or git("rev-parse", "HEAD")
    body_path = os.environ.get("GOV_PR_BODY_FILE", "").strip()

    if not base:
        fail("GOV_BASE_SHA is required")
        return 2

    commits = [c for c in git("rev-list", "--reverse", f"{base}..{head}").splitlines() if c]
    aggregate_product = False
    aggregate_authority = False
    errors: list[str] = []

    for commit in commits:
        if is_merge(commit):
            continue
        files = changed_files(commit)
        product = any(is_product(path) for path in files)
        authority = any(is_authority(path) for path in files)
        aggregate_product = aggregate_product or product
        aggregate_authority = aggregate_authority or authority

        short = commit[:12]
        if product and LEDGER not in files:
            errors.append(
                f"commit {short} changes product implementation but does not update {LEDGER} in the same commit"
            )
        if authority and ARCH not in files:
            errors.append(
                f"commit {short} changes authority-sensitive code but does not update {ARCH} in the same commit"
            )

    aggregate_files = set(
        line for line in git("diff", "--name-only", f"{base}...{head}").splitlines() if line
    )
    if aggregate_product and LEDGER not in aggregate_files:
        errors.append(f"PR changes product implementation but does not include {LEDGER}")
    if aggregate_authority and ARCH not in aggregate_files:
        errors.append(f"PR changes authority-sensitive implementation but does not include {ARCH}")

    if aggregate_product:
        if not body_path:
            errors.append("product PR must provide GOV_PR_BODY_FILE for PR-body governance checks")
        else:
            body = Path(body_path).read_text(encoding="utf-8") if Path(body_path).exists() else ""
            normalized = body.lower()
            required_markers = (
                "delivery status",
                "documentation sync",
                "backend",
                "android",
                "accepted",
            )
            for marker in required_markers:
                if marker not in normalized:
                    errors.append(f"PR body is missing required governance marker: {marker}")

    if errors:
        for item in errors:
            fail(item)
        return 1

    print("documentation-governance: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
