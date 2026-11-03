import unittest
from datetime import datetime, timezone

from app.core.source_dates import source_date, clean_source_dates, merge_source_dates


NOW = datetime(2026, 11, 3, 21, 50, tzinfo=timezone.utc)


class SourceDateTests(unittest.TestCase):
    def parse(self, value, **kwargs):
        return source_date(value, field="test", semantics="published", reference=NOW, **kwargs)

    def test_epochs_and_explicit_offsets_represent_the_same_instant(self):
        instant = datetime(2026, 11, 1, 12, 9, tzinfo=timezone.utc)
        expected = instant.isoformat()
        for raw in [str(int(instant.timestamp())), str(int(instant.timestamp() * 1000)), "2026-11-01T13:09:00+01:00"]:
            self.assertEqual(self.parse(raw)["value"], expected)

    def test_relative_source_times_use_the_source_timezone(self):
        self.assertEqual(self.parse("Heute, 22:30", zone="Europe/Berlin")["value"], "2026-11-03T21:30:00+00:00")
        self.assertEqual(self.parse("Gestern, 22:30", zone="Europe/Berlin")["value"], "2026-11-02T21:30:00+00:00")
        self.assertEqual(self.parse("Heute, 22:30", zone="Europe/Berlin")["precision"], "minute")

    def test_date_only_values_do_not_invent_a_time(self):
        entry = self.parse("01.11.2026", zone="Europe/Berlin")
        self.assertEqual((entry["value"], entry["precision"]), ("2026-11-01", "date"))
        self.assertEqual(clean_source_dates({"published": entry}, NOW)["published"]["precision"], "date")

    def test_local_date_after_utc_midnight_boundary_survives_ingest(self):
        now = datetime(2026, 11, 3, 23, 30, tzinfo=timezone.utc)
        entry = source_date("04.11.2026", field="card_publication_date", semantics="published", zone="Europe/Berlin", reference=now)
        self.assertEqual(clean_source_dates({"published": entry}, now)["published"]["value"], "2026-11-04")

    def test_invalid_ambiguous_and_future_values_remain_unknown(self):
        for raw in [None, True, 0, "2014", "2026-02-30", "2026-11-03T12:00:00", "2099-01-01", "2099-01-01T12:00:00Z", "Heute, 99:99"]:
            with self.subTest(raw=raw):
                self.assertIsNone(self.parse(raw, zone="Europe/Berlin"))
        for day in [(2026, 10, 25), (2026, 3, 29)]:
            self.assertIsNone(source_date("Heute, 02:30", field="card_publication_date", semantics="published", zone="Europe/Berlin", reference=datetime(*day, 12, tzinfo=timezone.utc)))

    def test_bump_is_not_a_first_publication_or_modification(self):
        entry = source_date("2026-11-01T12:00:00Z", field="PUBLISHED", semantics="published_or_renewed", reference=NOW)
        dates = clean_source_dates({"published": entry}, NOW)
        self.assertEqual(dates["published"]["semantics"], "published_or_renewed")
        self.assertNotIn("modified", dates)

    def test_missing_and_invalid_new_dates_do_not_erase_known_source_evidence(self):
        published = self.parse("2026-11-01T12:00:00Z")
        previous = {"published": published}
        self.assertEqual(merge_source_dates(previous, clean_source_dates({"published": {"value": "invalid", "semantics": []}}, NOW)), previous)
        modified = source_date("2026-11-02T12:00:00Z", field="CHANGED", semantics="modified", reference=NOW)
        merged = merge_source_dates(previous, clean_source_dates({"modified": modified}, NOW))
        self.assertEqual(merged["published"], published)
        self.assertEqual(merged["modified"]["value"], modified["value"])
