from __future__ import annotations

import asyncio

from textual.widgets import SelectionList, Static

from copout import picker
from copout.atuin import HistoryEntry


def test_picker_toggles_multiple_commands_and_confirms_oldest_first() -> None:
    async def exercise() -> None:
        app = picker.CommandPicker(
            [
                HistoryEntry("3", "newest", exit_status=0, duration=0.1),
                HistoryEntry("2", "middle", exit_status=1, duration=0.2),
                HistoryEntry("1", "oldest", exit_status=0, duration=0.3),
            ]
        )
        async with app.run_test(size=(100, 16)) as pilot:
            choices = app.query_one("#commands", SelectionList)
            assert choices.highlighted == 0

            await pilot.press("space")
            await pilot.press("down", "down")
            await pilot.press("space")
            assert choices.selected == [0, 2]

            await pilot.press("enter")

        assert app.return_value == [2, 0]

    asyncio.run(exercise())


def test_picker_preselects_records_by_id() -> None:
    async def exercise() -> None:
        app = picker.CommandPicker(
            [
                HistoryEntry("3", "newest"),
                HistoryEntry("2", "middle"),
                HistoryEntry("1", "oldest"),
            ],
            preselected_ids=["2", "1"],
        )
        async with app.run_test(size=(100, 16)) as pilot:
            choices = app.query_one("#commands", SelectionList)
            assert choices.selected == [1, 2]
            assert "2 selected" in str(app.query_one("#picker-help", Static).render())
            await pilot.press("enter")

        assert app.return_value == [2, 1]

    asyncio.run(exercise())


def test_picker_enter_requires_at_least_one_selection() -> None:
    async def exercise() -> None:
        app = picker.CommandPicker([HistoryEntry("1", "only command")])
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("enter")
            assert app.return_value is None
            await pilot.press("space", "enter")

        assert app.return_value == [0]

    asyncio.run(exercise())


def test_picker_escape_cancels() -> None:
    async def exercise() -> None:
        app = picker.CommandPicker([HistoryEntry("1", "only command")])
        async with app.run_test(size=(80, 12)) as pilot:
            await pilot.press("space", "escape")

        assert app.return_value is None

    asyncio.run(exercise())
