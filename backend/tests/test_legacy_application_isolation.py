from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_public_application_module_is_only_a_compatibility_alias() -> None:
    source = (ROOT / "app" / "application.py").read_text(encoding="utf-8")
    assert len(source.splitlines()) <= 30
    assert "app.legacy" in source
    assert "@app." not in source


def test_legacy_monolith_is_quarantined_and_not_silently_rewritten() -> None:
    legacy = ROOT / "app" / "legacy" / "application_legacy.py"
    source = legacy.read_text(encoding="utf-8")
    assert len(source.splitlines()) > 2500
    assert 'app = FastAPI(title="Third-Hand API", version="0.2.0")' in source
    assert '@app.post("/v1/decisions/generate")' in source
    assert '@app.post("/v1/paper-trading/run")' in source


def test_runtime_and_compat_import_share_the_same_application_state() -> None:
    import app.application as compatibility
    import app.main as runtime

    assert compatibility.app is runtime.app
    assert compatibility.store is runtime.store
    assert compatibility.generate_decisions is runtime.generate_decisions
    assert runtime.__name__ == "app.legacy.application_legacy"
