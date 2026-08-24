from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.personal_universe import WatchlistEntry, WatchlistPriority
from app.infrastructure.database.personal_universe_repository import PersonalUniverseRepository
from app.storage import PortfolioStore


def test_watchlist_entry_defaults_legacy_metadata() -> None:
    entry = WatchlistEntry.from_record(
        {
            "symbol": "01810",
            "name": "小米集团-W",
            "created_at": datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc).isoformat(),
            "updated_at": datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc).isoformat(),
        }
    )

    assert entry.symbol == "01810"
    assert entry.enabled is True
    assert entry.priority is WatchlistPriority.NORMAL
    assert entry.note == ""


def test_watchlist_entry_parses_persisted_attention_metadata() -> None:
    entry = WatchlistEntry.from_record(
        {
            "symbol": " 00700 ",
            "name": "腾讯控股",
            "enabled": 0,
            "priority": "CORE",
            "note": "等待财报后复核",
            "created_at": "2026-08-20T09:00:00+08:00",
            "updated_at": "2026-08-20T10:00:00+08:00",
        }
    )

    assert entry.symbol == "00700"
    assert entry.enabled is False
    assert entry.priority is WatchlistPriority.CORE
    assert entry.note == "等待财报后复核"


def test_watchlist_entry_rejects_naive_timestamps() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        WatchlistEntry.from_record(
            {
                "symbol": "01810",
                "name": "小米集团-W",
                "created_at": "2026-08-20T09:00:00",
                "updated_at": "2026-08-20T09:00:00",
            }
        )


def test_legacy_watchlist_save_is_compatible_with_pux1_metadata(tmp_path) -> None:
    store = PortfolioStore(tmp_path / "watchlist.db")
    repository = PersonalUniverseRepository(store)

    created = store.save_watchlist_item("01810", "小米集团-W")
    assert created["enabled"] == 1
    assert created["priority"] == "NORMAL"
    assert created["note"] == ""

    updated = repository.update_watchlist_item(
        "01810",
        enabled=False,
        priority=WatchlistPriority.CORE,
        note="等待财报后复核",
    )
    assert updated is not None
    assert repository.list_watchlist() == []
    assert repository.list_watchlist(include_disabled=True)[0].enabled is False

    # Existing POST-style clients still save name/symbol through PortfolioStore.
    # That compatibility path must not erase the newer attention metadata.
    legacy_saved_again = store.save_watchlist_item("01810", "小米集团-W")
    assert legacy_saved_again["enabled"] == 0
    assert legacy_saved_again["priority"] == "CORE"
    assert legacy_saved_again["note"] == "等待财报后复核"
