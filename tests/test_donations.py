import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiosqlite

from src import config
from src.services import bot_db
from src.utils import helpers
from src.utils.helpers import (
    days_left_in_month,
    show_donation_progress,
    start_of_month_utc,
)

PDT = timezone(timedelta(hours=-7))
PST = timezone(timedelta(hours=-8))


class StartOfMonthTests(unittest.TestCase):
    def test_mid_month(self):
        now = datetime(2026, 9, 23, 15, 30, tzinfo=timezone.utc)
        # September 2026 is PDT (UTC-7)
        self.assertEqual(
            start_of_month_utc(now), datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc)
        )

    def test_utc_moment_before_pacific_month_start(self):
        # Sep 1 2026 02:00 UTC is still Aug 31 in Pacific
        now = datetime(2026, 9, 1, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(
            start_of_month_utc(now), datetime(2026, 8, 1, 7, 0, tzinfo=timezone.utc)
        )

    def test_year_boundary_january(self):
        # Jan 1 2026 02:00 UTC is Dec 31 2025 18:00 PST
        now = datetime(2026, 1, 1, 2, 0, tzinfo=timezone.utc)
        self.assertEqual(
            start_of_month_utc(now), datetime(2025, 12, 1, 8, 0, tzinfo=timezone.utc)
        )

    def test_winter_month_uses_pst(self):
        now = datetime(2026, 2, 10, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(
            start_of_month_utc(now), datetime(2026, 2, 1, 8, 0, tzinfo=timezone.utc)
        )


class DaysLeftInMonthTests(unittest.TestCase):
    def test_mid_month(self):
        now = datetime(2026, 9, 23, 12, 0, tzinfo=PDT)
        self.assertEqual(days_left_in_month(now), 7)

    def test_last_minute_of_month(self):
        now = datetime(2026, 9, 30, 23, 30, tzinfo=PDT)
        self.assertEqual(days_left_in_month(now), 0)

    def test_december_wraps_to_next_year(self):
        now = datetime(2026, 12, 15, 12, 0, tzinfo=PST)
        self.assertEqual(days_left_in_month(now), 16)

    def test_first_of_month(self):
        now = datetime(2026, 9, 1, 0, 0, tzinfo=PDT)
        self.assertEqual(days_left_in_month(now), 30)


class ShowDonationProgressTests(unittest.TestCase):
    def test_under_goal(self):
        message = show_donation_progress(100, 250)
        self.assertIn(f"[{'█' * 8}{'░' * 12}] 40.0%", message)
        self.assertIn("goal of $250", message)
        self.assertIn("by the end of the month", message)
        self.assertIn("Current amount raised: $100.00", message)
        self.assertNotIn("Congratulations", message)

    def test_exactly_at_goal(self):
        message = show_donation_progress(250, 250)
        self.assertIn("100.0%", message)
        self.assertIn("We've met our donation goal", message)
        self.assertNotIn("exceeded", message)

    def test_over_goal(self):
        message = show_donation_progress(275, 250)
        self.assertIn("110.0%", message)
        self.assertIn(f"[{'█' * 20}]", message)
        self.assertIn("met and exceeded", message)


class MonthlyDonationProgressTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        bot_db.db_path = Path(self.temp_dir.name) / "bot_database.db"
        await bot_db.init_db()
        self._orig_starting = getattr(config.Config, "KOFI_STARTING_AMOUNT", None)
        self._orig_goal = getattr(config.Config, "KOFI_DONATION_GOAL", None)
        config.Config.KOFI_STARTING_AMOUNT = 10.0
        config.Config.KOFI_DONATION_GOAL = 250.0

    async def asyncTearDown(self):
        if self._orig_starting is None:
            del config.Config.KOFI_STARTING_AMOUNT
        else:
            config.Config.KOFI_STARTING_AMOUNT = self._orig_starting
        if self._orig_goal is None:
            del config.Config.KOFI_DONATION_GOAL
        else:
            config.Config.KOFI_DONATION_GOAL = self._orig_goal
        self.temp_dir.cleanup()

    async def test_monthly_progress_counts_this_month_plus_starting(self):
        # Donation from long before the current month must be excluded
        async with aiosqlite.connect(bot_db.db_path) as db:
            await db.execute(
                "INSERT INTO donations (player_name, email, amount, donation_date)"
                " VALUES ('old', 'old@example.com', 100, '2020-01-01 00:00:00')"
            )
            await db.commit()

        self.assertTrue(await bot_db.add_donation("New", "new@example.com", 5.0))
        self.assertTrue(await bot_db.add_donation("New2", "new2@example.com", 7.5))

        current, goal = await helpers.get_monthly_donation_progress()
        self.assertEqual(current, 22.5)
        self.assertEqual(goal, 250.0)

    async def test_get_total_donations_since_window(self):
        old = datetime(2020, 1, 1, tzinfo=timezone.utc)
        recent = datetime.now(timezone.utc)

        async with aiosqlite.connect(bot_db.db_path) as db:
            await db.execute(
                "INSERT INTO donations (player_name, email, amount, donation_date)"
                " VALUES ('old', 'old@example.com', 100, '2020-01-01 00:00:00')"
            )
            await db.commit()

        self.assertTrue(await bot_db.add_donation("new", "new@example.com", 12.5))

        self.assertEqual(await bot_db.get_total_donations_since(old), 112.5)
        self.assertEqual(await bot_db.get_total_donations_since(recent), 12.5)
        # Window at/after the donation date includes it
        self.assertEqual(
            await bot_db.get_total_donations_since(recent - timedelta(seconds=1)),
            12.5,
        )


if __name__ == "__main__":
    unittest.main()
