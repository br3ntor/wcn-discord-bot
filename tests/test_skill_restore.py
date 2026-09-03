import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from src.features.skill_restore import (
    REASON_NO_DATA,
    REASON_NO_RECORD,
    REASON_NO_RELOGIN,
    REASON_OK,
    LevelRestore,
)

STEAM_ID = "76561198000000001"
PLAYER = "TestPlayer"
COORDS = "[1000,1000,0]"


def stamp(day: int, h: int, m: int, sec: str) -> str:
    return f"[{day:02d}-08-26 {h:02d}:{m:02d}:{sec}]"


def login_line(day: int, h: int, m: int, sec: str, hours: int) -> str:
    return (
        f"{stamp(day, h, m, sec)} [{STEAM_ID}][{PLAYER}][{COORDS}]"
        f"[Login][Hours Survived: {hours}]."
    )


def skill_line(
    day: int, h: int, m: int, sec: str, levels: dict[str, int], hours: int
) -> str:
    body = ", ".join(f"{skill}={level}" for skill, level in levels.items())
    return (
        f"{stamp(day, h, m, sec)} [{STEAM_ID}][{PLAYER}][{COORDS}]"
        f"[{body}][Hours Survived: {hours}]."
    )


def died_line(day: int, h: int, m: int, sec: str, hours: int) -> str:
    return (
        f"{stamp(day, h, m, sec)} [{STEAM_ID}][{PLAYER}][{COORDS}]"
        f"[Died][Hours Survived: {hours}]."
    )


def created_line(day: int, h: int, m: int, sec: str, slot: int = 1) -> str:
    return (
        f"{stamp(day, h, m, sec)} [{STEAM_ID}][{PLAYER}][{COORDS}]"
        f"[Created Player {slot}][Hours Survived: 0]."
    )


def level_changed_line(
    day: int, h: int, m: int, sec: str, skill: str, level: int
) -> str:
    return (
        f"{stamp(day, h, m, sec)} [{STEAM_ID}][{PLAYER}][{COORDS}]"
        f"[Level Changed][{skill}][{level}]."
    )


class LevelRestoreTests(unittest.TestCase):
    def make_restore(self, files: list[tuple[str, list[str]]]) -> LevelRestore:
        """Write PerkLog fixtures into a temp dir, oldest file first."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        base_time = datetime.now().timestamp() - 3600
        for offset, (name, lines) in enumerate(files):
            path = base / name
            path.write_text("\n".join(lines) + "\n", encoding="utf-8")
            mtime = base_time + offset * 60
            os.utime(path, (mtime, mtime))
        return LevelRestore("TestServer", PLAYER, perk_log_path=str(base))

    def test_death_and_relogin_in_same_file(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-30_04-05_PerkLog.txt",
                    [
                        login_line(30, 6, 50, "11.175", 100),
                        skill_line(
                            30, 6, 50, "11.175", {"Axe": 5, "Woodwork": 10}, 100
                        ),
                        level_changed_line(30, 10, 0, "00.000", "Axe", 6),
                        died_line(30, 14, 36, "13.105", 150),
                        login_line(30, 20, 0, "00.000", 2),
                        skill_line(30, 20, 0, "00.000", {"Axe": 0, "Woodwork": 0}, 2),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 6, "Woodwork": 10})
        self.assertEqual(current, {"Axe": 0, "Woodwork": 0})
        self.assertEqual(
            lr.compute_xp_commands(pre, current),
            [("Axe", lr.get_xp_for_level("Axe", 6)), ("Woodwork", 32775)],
        )

    def test_death_and_relogin_in_rotated_file(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-30_04-05_PerkLog.txt",
                    [
                        login_line(30, 6, 50, "11.175", 100),
                        skill_line(30, 6, 50, "11.175", {"Axe": 5}, 100),
                        died_line(30, 14, 36, "13.105", 150),
                    ],
                ),
                (
                    "2026-08-31_00-37_PerkLog.txt",
                    [
                        login_line(31, 0, 42, "02.585", 41),
                        skill_line(31, 0, 42, "02.585", {"Axe": 6}, 41),
                    ],
                ),
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 5})
        self.assertEqual(current, {"Axe": 6})
        self.assertEqual(lr.compute_xp_commands(pre, current), [])

    def test_death_without_relogin(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-30_04-05_PerkLog.txt",
                    [
                        login_line(30, 6, 50, "11.175", 100),
                        skill_line(30, 6, 50, "11.175", {"Axe": 5}, 100),
                        died_line(30, 14, 36, "13.105", 150),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_NO_RELOGIN)
        self.assertEqual(pre, {})
        self.assertEqual(current, {})

    def test_wipe_detected_from_hours_regression(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-20_16-04_PerkLog.txt",
                    [
                        login_line(20, 20, 0, "00.000", 90),
                        skill_line(20, 20, 0, "00.000", {"Axe": 5, "Sprinting": 3}, 90),
                        level_changed_line(22, 10, 0, "00.000", "Axe", 6),
                        login_line(27, 19, 0, "00.000", 98),
                        skill_line(27, 19, 0, "00.000", {"Axe": 6, "Sprinting": 3}, 98),
                    ],
                ),
                (
                    "2026-08-27_18-05_PerkLog.txt",
                    [
                        login_line(27, 19, 32, "11.989", 0),
                        skill_line(27, 19, 32, "11.989", {"Axe": 0, "Sprinting": 0}, 0),
                        login_line(28, 12, 0, "00.000", 5),
                        skill_line(28, 12, 0, "00.000", {"Axe": 0, "Sprinting": 0}, 5),
                    ],
                ),
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 6, "Sprinting": 3})
        self.assertEqual(current, {"Axe": 0, "Sprinting": 0})

    def test_wipe_detected_from_created_player(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-16_02-52_PerkLog.txt",
                    [
                        login_line(16, 1, 0, "00.000", 558),
                        skill_line(16, 1, 0, "00.000", {"Axe": 5}, 558),
                        created_line(16, 2, 0, "00.000"),
                        skill_line(16, 2, 0, "00.000", {"Axe": 0}, 0),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 5})
        self.assertEqual(current, {"Axe": 0})

    def test_created_player_slot_2_after_death(self):
        lr = self.make_restore(
            [
                (
                    "2026-09-01_04-05_PerkLog.txt",
                    [
                        login_line(1, 15, 7, "02.284", 284),
                        skill_line(1, 15, 7, "02.284", {"Axe": 5}, 284),
                        died_line(1, 15, 50, "00.000", 300),
                        created_line(1, 15, 57, "13.649", slot=2),
                        skill_line(1, 15, 57, "13.653", {"Axe": 0}, 0),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 5})
        self.assertEqual(current, {"Axe": 0})

    def test_current_skills_include_late_level_changes(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-30_04-05_PerkLog.txt",
                    [
                        login_line(30, 6, 50, "11.175", 100),
                        skill_line(30, 6, 50, "11.175", {"Axe": 5}, 100),
                        died_line(30, 14, 36, "13.105", 150),
                        login_line(30, 20, 0, "00.000", 0),
                        skill_line(30, 20, 0, "00.000", {"Axe": 0}, 0),
                        level_changed_line(30, 22, 0, "00.000", "Axe", 2),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 5})
        self.assertEqual(current, {"Axe": 2})
        self.assertEqual(
            lr.compute_xp_commands(pre, current),
            [("Axe", lr.get_xp_for_level("Axe", 5) - lr.get_xp_for_level("Axe", 2))],
        )

    def test_wipe_outranks_smaller_later_death(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-30_12-50_PerkLog.txt",
                    [
                        login_line(30, 6, 0, "00.000", 150),
                        skill_line(30, 6, 0, "00.000", {"Axe": 6}, 150),
                        login_line(30, 12, 0, "00.000", 173),
                        skill_line(30, 12, 0, "00.000", {"Axe": 7}, 173),
                        login_line(30, 13, 0, "00.000", 0),
                        skill_line(30, 13, 0, "00.000", {"Axe": 0}, 0),
                        login_line(30, 20, 0, "00.000", 5),
                        skill_line(30, 20, 0, "00.000", {"Axe": 0}, 5),
                        died_line(31, 10, 0, "00.000", 98),
                        login_line(31, 11, 0, "00.000", 0),
                        skill_line(31, 11, 0, "00.000", {"Axe": 0}, 0),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_OK)
        self.assertEqual(pre, {"Axe": 7})
        self.assertEqual(current, {"Axe": 0})

    def test_no_death_and_no_wipe(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-25_16-04_PerkLog.txt",
                    [
                        login_line(25, 10, 0, "00.000", 25),
                        skill_line(25, 10, 0, "00.000", {"Axe": 2}, 25),
                        login_line(26, 10, 0, "00.000", 30),
                        skill_line(26, 10, 0, "00.000", {"Axe": 2}, 30),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_NO_RECORD)
        self.assertEqual(pre, {})
        self.assertEqual(current, {})

    def test_early_game_regression_is_not_a_wipe(self):
        lr = self.make_restore(
            [
                (
                    "2026-08-25_16-04_PerkLog.txt",
                    [
                        login_line(25, 10, 0, "00.000", 10),
                        skill_line(25, 10, 0, "00.000", {"Axe": 1}, 10),
                        login_line(25, 14, 0, "00.000", 15),
                        skill_line(25, 14, 0, "00.000", {"Axe": 1}, 15),
                        login_line(25, 16, 0, "00.000", 0),
                        skill_line(25, 16, 0, "00.000", {"Axe": 0}, 0),
                    ],
                )
            ]
        )

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_NO_RECORD)

    def test_no_records_at_all(self):
        lr = self.make_restore([])

        pre, current, reason = lr.analyze_player_history()

        self.assertEqual(reason, REASON_NO_DATA)
        self.assertEqual(pre, {})
        self.assertEqual(current, {})

    def test_compute_xp_commands_passive_skills(self):
        lr = self.make_restore([])

        commands = lr.compute_xp_commands(
            {"Fitness": 6, "Axe": 3}, {"Fitness": 5, "Axe": 3}
        )

        self.assertEqual(commands, [("Fitness", 30000)])


if __name__ == "__main__":
    unittest.main()
