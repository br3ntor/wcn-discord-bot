import unittest

from src.utils.helpers import format_staff_listing, group_staff_by_steamid

SID_A = "76561198007495099"
SID_B = "76561199218313417"


class TestGroupStaffBySteamid(unittest.TestCase):
    def test_groups_duplicate_accounts_under_one_steamid(self):
        rows = [
            ("br3ntor", "admin", SID_A),
            ("admin", "admin", SID_A),
            ("Hythos", "admin", SID_B),
        ]
        groups = group_staff_by_steamid(rows)
        self.assertEqual(
            groups,
            [
                (SID_A, [("admin", "admin"), ("br3ntor", "admin")]),
                (SID_B, [("Hythos", "admin")]),
            ],
        )

    def test_multi_account_groups_sorted_first(self):
        rows = [
            ("Solo", "admin", SID_B),
            ("Alpha", "admin", SID_A),
            ("Beta", "gm", SID_A),
        ]
        groups = group_staff_by_steamid(rows)
        self.assertEqual(groups[0][0], SID_A)
        self.assertEqual(len(groups[0][1]), 2)
        self.assertEqual(groups[1], (SID_B, [("Solo", "admin")]))

    def test_missing_steamid_kept_separate(self):
        rows = [
            ("Local1", "admin", None),
            ("Local2", "admin", None),
            ("Online", "admin", SID_A),
        ]
        groups = group_staff_by_steamid(rows)
        self.assertEqual(len(groups), 3)
        keys = [key for key, _ in groups]
        self.assertIn("nosteam:Local1", keys)
        self.assertIn("nosteam:Local2", keys)

    def test_names_sorted_case_insensitively_within_group(self):
        rows = [
            ("zeta", "admin", SID_A),
            ("Alpha", "admin", SID_A),
        ]
        groups = group_staff_by_steamid(rows)
        self.assertEqual(groups[0][1], [("Alpha", "admin"), ("zeta", "admin")])


class TestFormatStaffListing(unittest.TestCase):
    def test_empty_state(self):
        messages = format_staff_listing({"Server": []}, {})
        self.assertEqual(messages, ["No privileged users found on any server."])

    def test_counts_and_profile_link(self):
        rows = [
            ("br3ntor", "admin", SID_A),
            ("admin", "admin", SID_A),
            ("Hythos", "admin", SID_B),
        ]
        messages = format_staff_listing({"B42-vanilla": rows}, {})
        self.assertEqual(len(messages), 1)
        self.assertIn("**B42-vanilla** — 3 accounts across 2 SteamIDs", messages[0])
        self.assertIn(
            f"[{SID_A}](<https://steamcommunity.com/profiles/{SID_A}>) — "
            "admin, br3ntor (admin)",
            messages[0],
        )
        self.assertIn(
            f"[{SID_B}](<https://steamcommunity.com/profiles/{SID_B}>) — Hythos (admin)",
            messages[0],
        )

    def test_mixed_roles_shown_per_account(self):
        rows = [
            ("Bob", "gm", SID_A),
            ("Alice", "moderator", SID_A),
        ]
        messages = format_staff_listing({"S": rows}, {})
        self.assertIn(
            f"[{SID_A}](<https://steamcommunity.com/profiles/{SID_A}>) — "
            "Alice (moderator), Bob (gm)",
            messages[0],
        )

    def test_empty_server_and_error_lines(self):
        messages = format_staff_listing(
            {"Empty": [], "Full": [("Bob", "admin", SID_A)]},
            {"Broken": "Error accessing database for broken server"},
        )
        self.assertEqual(len(messages), 1)
        self.assertIn("**Empty** — no privileged users", messages[0])
        self.assertIn("⚠️ **Broken**: Error accessing database for broken", messages[0])

    def test_no_steamid_line(self):
        rows = [("Local", "admin", None)]
        messages = format_staff_listing({"S": rows}, {})
        self.assertIn("• Local (admin) — no SteamID", messages[0])

    def test_splits_into_multiple_messages_over_limit(self):
        rows = [(f"user{i:03d}", "admin", f"7656119800000{i:05d}") for i in range(100)]
        messages = format_staff_listing({"Big": rows}, {})
        self.assertGreater(len(messages), 1)
        for message in messages:
            self.assertLessEqual(len(message), 2000)
        combined = "\n".join(messages)
        for i in range(100):
            self.assertIn(f"7656119800000{i:05d}", combined)


if __name__ == "__main__":
    unittest.main()
