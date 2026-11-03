import unittest
from datetime import datetime, timedelta, timezone

from app.core.recommendation import recommend_offer, compare_offer, MIN_SAMPLE

NOW = datetime(2026, 11, 3, 22, tzinfo=timezone.utc)


def offer(**changes):
    values = dict(id="target", make="Volkswagen", model="Tiguan", year=2023, mileage=60000,
                fuel_type="petrol", transmission="automatic", body_type="suv", country="DE",
                engine_power_kw=110, variant="1.5 TSI", engine_cc=1498, condition="used",
                price=18000, currency="EUR", last_seen_at=NOW, is_active=True,
                source="willhaben", external_id="wh_target", url="https://example.test/target",
                accident_free=True, service_history=True)
    return {**values, **changes}


def cohort(count=10, **changes):
    return [offer(id=f"row-{i}", external_id=f"wh_{i}", url=f"https://example.test/{i}",
                  mileage=55001+i*200, price=20000, **changes) for i in range(count)]


class RecommendationTests(unittest.TestCase):
    def test_enough_similar_observations_give_a_reason_and_next_step_not_a_guarantee(self):
        result = recommend_offer(offer(), cohort(), NOW)
        self.assertEqual(result["status"], "consider")
        self.assertIn("10.0% ispod", result["reason"])
        self.assertIn("10 sličnih oglasa", result["reason"])
        self.assertIn("nezavisan pregled", result["next_step"])
        self.assertEqual(result["confidence"], "limited")
        self.assertIn("VIN", " ".join(result["cautions"]))

    def test_zero_delta_is_a_real_comparison_and_price_thresholds_are_consistent(self):
        for price, expected in [(20000,"consider"), (21000,"consider"), (21020,"negotiate"),
                                (24000,"negotiate"), (24020,"avoid"), (15000,"verify")]:
            with self.subTest(price=price):
                result = recommend_offer(offer(price=price), cohort(), NOW)
                self.assertEqual(result["status"], expected)
                self.assertTrue(result["comparison"]["available"])
        self.assertEqual(compare_offer(offer(price=20000), cohort(), NOW)["delta_pct"], 0)

    def test_nine_comparables_never_produce_a_buy_signal(self):
        result = recommend_offer(offer(), cohort(MIN_SAMPLE-1), NOW)
        self.assertEqual(result["status"], "verify")
        self.assertIn("najmanje 10", result["reason"])
        self.assertIsNone(result["comparison"]["reference_price"])

    def test_different_engines_fuel_body_trim_markets_and_stale_rows_are_excluded(self):
        for changes in ({"fuel_type":"diesel"}, {"body_type":"estate"}, {"engine_power_kw":150},
                        {"variant":"2.0 TSI"}, {"engine_cc":1998}, {"country":"AT"},
                        {"model":"Tiguan Allspace"}, {"transmission":"manual"}, {"condition":"new"},
                        {"accident_free":None}, {"year":2020}, {"mileage":95000},
                        {"last_seen_at":NOW-timedelta(days=8)}, {"is_active":False},
                        {"currency":"CHF"}, {"price":float("nan")}):
            with self.subTest(changes=changes):
                rows = [{**row, **changes} for row in cohort()]
                self.assertEqual(compare_offer(offer(), rows, NOW)["sample_size"], 0)

    def test_missing_data_stale_target_or_legacy_estimate_never_fabricate_a_comparison(self):
        for changes in ({"year":None}, {"year":2027}, {"mileage":None}, {"engine_power_kw":0},
                        {"country":"unknown"}, {"currency":"CHF"}, {"price":0},
                        {"last_seen_at":NOW-timedelta(days=8)}, {"last_seen_at":NOW.replace(tzinfo=None)},
                        {"last_seen_at":NOW+timedelta(hours=1)}):
            with self.subTest(changes=changes):
                result = recommend_offer(offer(**changes, price_estimated=30000, price_delta_pct=-40), cohort(), NOW)
                self.assertFalse(result["comparison"]["available"])
                self.assertEqual(result["status"], "verify")

    def test_zero_km_is_known_and_numeric_strings_do_not_become_missing(self):
        rows = [{**row, "mileage":i+1} for i,row in enumerate(cohort())]
        result = compare_offer(offer(mileage=0), rows, NOW)
        self.assertTrue(result["available"])
        self.assertTrue(compare_offer(offer(year="2023", mileage="60000"), cohort(), NOW)["available"])

    def test_duplicates_and_syndicated_target_do_not_fill_the_minimum_sample(self):
        rows = cohort(9)
        for i in range(20):
            rows.append({**rows[0], "id":f"copy-{i}", "source":"other", "external_id":f"copy-{i}", "url":f"https://other.test/{i}"})
        rows.append(offer(id="syndicated", source="other", external_id="syndicated", url="https://other.test/target"))
        self.assertEqual(compare_offer(offer(), rows, NOW)["sample_size"], 9)
        self.assertFalse(compare_offer(offer(), rows, NOW)["available"])

    def test_same_url_or_external_id_does_not_count_twice_even_with_a_different_price(self):
        rows = cohort(9)
        rows += [{**rows[0], "id":"same-url", "price":19000, "external_id":"new", "url":rows[0]["url"]+"?tracking=1"},
                 {**rows[1], "id":"same-id", "price":21000, "url":"https://new.test/unique"}]
        self.assertEqual(compare_offer(offer(), rows, NOW)["sample_size"], 9)

    def test_wide_price_range_is_insufficient_and_does_not_hide_dispersion(self):
        rows = [{**row,"price":10000+i*4000} for i,row in enumerate(cohort())]
        result = recommend_offer(offer(), rows, NOW)
        self.assertEqual(result["status"], "verify")
        self.assertIn("previše rasute", result["reason"])

    def test_damage_and_missing_service_records_override_an_attractive_price(self):
        for changes, expected in [({"accident_free":False}, "oštećenja"), ({"condition":"damaged"}, "oštećenja"), ({"service_history":False}, "održavanje")]:
            result = recommend_offer(offer(**changes), cohort(), NOW)
            self.assertEqual(result["status"], "verify")
            self.assertIn(expected, result["title"])

    def test_unknown_history_is_not_described_as_verified_and_query_failure_is_honest(self):
        result = recommend_offer(offer(accident_free=None, service_history=None), cohort(), NOW)
        self.assertIn("Istorija oštećenja nije potvrđena.", result["cautions"])
        self.assertIn("Nema potvrđene servisne dokumentacije.", result["cautions"])
        unavailable = recommend_offer(offer(), now=NOW, comparison_error=True)
        self.assertEqual(unavailable["status"], "verify")
        self.assertIn("trenutno nije dostupno", unavailable["reason"])


if __name__ == "__main__":
    unittest.main()
