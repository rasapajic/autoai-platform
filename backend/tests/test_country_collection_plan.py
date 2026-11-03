import unittest
from collections import Counter

from app.core.catalog_plan import COLLECTION_PLAN, collection_windows


class CountryCollectionPlanTests(unittest.TestCase):
    def test_growth_keeps_all_partitions_and_adds_seven_german_windows(self):
        windows = collection_windows("growth")
        expected = Counter(part.key for part in COLLECTION_PLAN)
        expected["autoscout24:D"] += 7
        self.assertEqual(Counter(part.key for part in windows), expected)
        self.assertEqual(len(windows), 23)
        self.assertEqual(windows[0].key, "autoscout24:D")
        self.assertTrue(all(part is windows[0] for part in windows if part.key == "autoscout24:D"))

    def test_head_visits_each_partition_only_once(self):
        self.assertIs(collection_windows("head"), COLLECTION_PLAN)
        self.assertEqual(len(COLLECTION_PLAN), 16)

    def test_unknown_modes_are_rejected(self):
        with self.assertRaises(ValueError):
            collection_windows("unbounded")
