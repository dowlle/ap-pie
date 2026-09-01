import unittest

from room_coordination import apply_host_mappings, build_roster_preview


class GeneratedRosterReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.yamls = [
            {"id": 10, "player_name": "Appletini", "game": "Super Metroid", "submitter_user_id": 4},
            {"id": 11, "player_name": "Berry", "game": "ANIMAL WELL", "submitter_user_id": 5},
        ]
        self.players = [
            {"slot": 2, "name": "Berry_2", "game": "ANIMAL WELL"},
            {"slot": 1, "name": "Appletini", "game": "Super Metroid"},
        ]

    def test_only_exact_name_matches_are_suggested(self):
        rows = build_roster_preview(self.players, self.yamls)
        self.assertEqual([row["slot"] for row in rows], [1, 2])
        self.assertEqual(rows[0]["match_status"], "exact")
        self.assertEqual(rows[0]["suggested_yaml_id"], 10)
        self.assertEqual(rows[1]["match_status"], "unmatched")
        self.assertIsNone(rows[1]["suggested_yaml_id"])

    def test_duplicate_exact_names_are_ambiguous(self):
        yamls = self.yamls + [
            {"id": 12, "player_name": "Appletini", "game": "SMZ3", "submitter_user_id": 7},
        ]
        rows = build_roster_preview(self.players, yamls)
        self.assertEqual(rows[0]["match_status"], "ambiguous")
        self.assertIsNone(rows[0]["suggested_yaml_id"])
        self.assertEqual(len(rows[0]["candidates"]), 2)

    def test_host_mapping_can_resolve_non_exact_name(self):
        preview = build_roster_preview(self.players, self.yamls)
        rows = apply_host_mappings(
            preview,
            self.yamls,
            [{"team": 0, "slot": 2, "yaml_id": 11}],
        )
        self.assertEqual(rows[0]["yaml_id"], 10)
        self.assertEqual(rows[0]["yaml_owner_user_id"], 4)
        self.assertEqual(rows[1]["yaml_id"], 11)
        self.assertEqual(rows[1]["yaml_owner_user_id"], 5)

    def test_one_yaml_cannot_own_two_generated_slots(self):
        preview = build_roster_preview(self.players, self.yamls)
        with self.assertRaisesRegex(ValueError, "more than one"):
            apply_host_mappings(
                preview,
                self.yamls,
                [
                    {"team": 0, "slot": 1, "yaml_id": 10},
                    {"team": 0, "slot": 2, "yaml_id": 10},
                ],
            )

    def test_foreign_yaml_id_is_rejected(self):
        preview = build_roster_preview(self.players, self.yamls)
        with self.assertRaisesRegex(ValueError, "not part of this room"):
            apply_host_mappings(preview, self.yamls, [{"team": 0, "slot": 2, "yaml_id": 999}])

    def test_mapping_for_stale_tracker_slot_is_rejected(self):
        preview = build_roster_preview(self.players, self.yamls)
        with self.assertRaisesRegex(ValueError, "not in the current tracker roster"):
            apply_host_mappings(preview, self.yamls, [{"team": 0, "slot": 99, "yaml_id": 11}])

    def test_duplicate_mapping_row_is_rejected(self):
        preview = build_roster_preview(self.players, self.yamls)
        with self.assertRaisesRegex(ValueError, "mapped more than once"):
            apply_host_mappings(
                preview,
                self.yamls,
                [
                    {"team": 0, "slot": 2, "yaml_id": 11},
                    {"team": 0, "slot": 2, "yaml_id": None},
                ],
            )


if __name__ == "__main__":
    unittest.main()
