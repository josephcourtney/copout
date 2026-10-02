from __future__ import annotations

from copout import cli
from copout.atuin import HistoryEntry


def test_explicit_selectors_expand_history_lookup_to_oldest_requested(monkeypatch) -> None:
    entries = [HistoryEntry(str(index), f"cmd {index}") for index in range(250, 0, -1)]
    observed_limits: list[int] = []

    def recent_history(limit: int, *, required_ids=()):
        del required_ids
        observed_limits.append(limit)
        return entries[:limit]

    monkeypatch.setattr(cli.atuin, "recent_history", recent_history)
    monkeypatch.setattr(cli.atuin, "hydrate_outputs", lambda selected: selected)
    monkeypatch.setattr(cli, "_write_record", lambda *args, **kwargs: 0)
    monkeypatch.setattr(cli, "_start_writer", lambda *, print_output: (None, None))

    result = cli.run_pick(
        selectors=["250"],
        preselect=[],
        preselect_records=[],
        limit=100,
        print_output=True,
        as_json=False,
        as_markdown=False,
        pretty_attributes=False,
    )

    assert result == 0
    assert observed_limits == [250]


def test_relative_preselection_extends_picker_window_and_resolves_record_ids(monkeypatch) -> None:
    entries = [HistoryEntry(str(index), f"cmd {index}") for index in range(150, 0, -1)]
    observed_limits: list[int] = []
    picked: list[list[str]] = []

    def recent_history(limit: int, *, required_ids=()):
        del required_ids
        observed_limits.append(limit)
        return entries[:limit]

    def pick(candidates, *, preselected_ids=None):
        del candidates
        picked.append(list(preselected_ids or []))
        return None

    monkeypatch.setattr(cli.atuin, "recent_history", recent_history)
    monkeypatch.setattr(cli, "_pick_entries", pick)

    result = cli.run_pick(
        selectors=[],
        preselect=["1", "150"],
        preselect_records=[],
        limit=100,
        print_output=True,
        as_json=False,
        as_markdown=False,
        pretty_attributes=False,
    )

    assert result == 0
    assert observed_limits == [150]
    assert picked == [["1", "150"]]


def test_relative_and_record_id_preselection_are_unioned(monkeypatch) -> None:
    entries = [
        HistoryEntry("new", "newest"),
        HistoryEntry("middle", "middle"),
        HistoryEntry("old", "oldest"),
    ]
    picked: list[list[str]] = []

    monkeypatch.setattr(cli.atuin, "recent_history", lambda limit, *, required_ids=(): entries)

    def pick(candidates, *, preselected_ids=None):
        del candidates
        picked.append(list(preselected_ids or []))
        return None

    monkeypatch.setattr(cli, "_pick_entries", pick)

    result = cli.run_pick(
        selectors=[],
        preselect=["1"],
        preselect_records=["old"],
        limit=100,
        print_output=True,
        as_json=False,
        as_markdown=False,
        pretty_attributes=False,
    )

    assert result == 0
    assert picked == [["old", "new"]]
