import unittest
from collections import Counter

from app.core.catalog_plan import BASE_COLLECTION_PLAN, COLLECTION_PLAN, GERMAN_PRICE_BANDS, collection_windows


class CountryCollectionPlanTests(unittest.TestCase):
    def test_growth_keeps_other_partitions_and_uses_independent_german_price_bands(self):
        windows = collection_windows("growth")
        expected = Counter(part.key for part in COLLECTION_PLAN if part.key != "autoscout24:D")
        self.assertEqual(Counter(part.key for part in windows), expected)
        self.assertEqual(len(windows), 23)
        self.assertTrue(windows[0].key.startswith("autoscout24:D:price:"))
        self.assertEqual(len(set(part.key for part in windows)), 23)

    def test_head_visits_each_partition_only_once(self):
        self.assertIs(collection_windows("head"), BASE_COLLECTION_PLAN)
        self.assertEqual(len(BASE_COLLECTION_PLAN), 16)
        self.assertEqual(COLLECTION_PLAN[:16], BASE_COLLECTION_PLAN)

    def test_price_bands_cover_source_integer_euro_prices_without_gaps(self):
        self.assertEqual((GERMAN_PRICE_BANDS[0][0], GERMAN_PRICE_BANDS[-1][1]), (500, 2000000))
        for (_, previous_high), (next_low, _) in zip(GERMAN_PRICE_BANDS, GERMAN_PRICE_BANDS[1:]):
            self.assertEqual(previous_high + 1, next_low)
        for part in collection_windows("growth")[:8]:
            self.assertEqual(part.source, "autoscout24")
            self.assertEqual(part.filters["country"], "D")
            self.assertLessEqual(part.filters["min_price"], part.filters["max_price"])

    def test_unknown_modes_are_rejected(self):
        with self.assertRaises(ValueError):
            collection_windows("unbounded")
