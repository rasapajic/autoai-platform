import unittest

from app.core.listing_normalization import normalize_vehicle_fields, evidenced_jaguar_model


class VehicleNormalizationTests(unittest.TestCase):
    def test_jaguar_families_need_full_named_evidence(self):
        for raw, headline, expected in [
            ("F", "Jaguar F-Type 3.0 Coupe", "F-Type"),
            ("F", "Jaguar F-Pace 2.0 AWD", "F-Pace"),
            ("E", "Jaguar E-Pace D180", "E-Pace"),
            ("E", "Jaguar E-Type Cabrio", "E-Type"),
            ("I", "Jaguar I-Pace HSE", "I-Pace"),
            ("S", "Jaguar S-Type Sedan", "S-Type"),
            ("C", "Jaguar C-Type", "C-Type"),
            ("10004", "Jaguar F-Type", "F-Type"),
        ]:
            with self.subTest(headline=headline):
                self.assertEqual(normalize_vehicle_fields({"make": "Jaguar", "model": raw,
                                                          "description": headline})["model"], expected)

    def test_jaguar_known_raw_aliases_are_consistent(self):
        for raw, expected in [("F Pace", "F-Pace"), ("F Type", "F-Type"),
                              ("I Pace Hse", "I-Pace"), ("Xf Sportbrake", "XF"),
                              ("Xe", "XE"), ("Xj6", "XJ6")]:
            with self.subTest(raw=raw):
                data = {"make": "Jaguar", "model": raw}
                normalized = normalize_vehicle_fields(data)
                self.assertEqual(normalized["model"], expected)
                self.assertEqual(normalize_vehicle_fields(normalized), normalized)

    def test_jaguar_ambiguous_and_conflicting_evidence_is_not_repaired(self):
        for data in [
            {"make": "Jaguar", "model": "F"},
            {"make": "Jaguar", "model": "E"},
            {"make": "Jaguar", "model": "S", "description": "Mercedes-Benz S-Class"},
            {"make": "Jaguar", "model": "F", "description": "Jaguar F-Type",
             "url": "https://example.test/jaguar-f-pace-123/"},
            {"make": "Jaguar", "model": "F-Type", "description": "Jaguar F-Pace"},
            {"make": "Jaguar", "model": "420", "description": "Jaguar F-Type"},
            {"make": "Ford", "model": "F", "description": "Jaguar F-Type"},
        ]:
            with self.subTest(data=data):
                self.assertIsNone(evidenced_jaguar_model(data))
        self.assertIsNone(normalize_vehicle_fields({"make": "Jaguar", "description": "Jaguar F-Type",
                          "url": "https://example.test/jaguar-f-pace-123/"})["model"])

    def test_jaguar_slug_and_unknown_make_can_supply_full_model(self):
        self.assertEqual(normalize_vehicle_fields({"make": "10004", "model": "50042",
            "url": "https://example.test/auto/jaguar-s-type-sedan-123456/"}),
            {"make": "Jaguar", "model": "S-Type"})

    def test_readable_manufacturers_from_primary_catalog_do_not_need_id_guesses(self):
        cases = [("Omoda 5 HEV Comfort Line", "Omoda", "5"),
                 ("Omoda 9 PHEV Premium Line", "Omoda", "9"),
                 ("Jaecoo 7 PHEV", "Jaecoo", "7"),
                 ("KGM Torres 1.5", "KGM", "Torres"),
                 ("Lynk & Co 01 PHEV", "Lynk & Co", "01"),
                 ("Donkervoort D8 GTO", "Donkervoort", "D8")]
        for title, make, model in cases:
            with self.subTest(title=title):
                self.assertEqual(normalize_vehicle_fields({"make": "10053", "description": title}), {"make": make, "model": model})
        self.assertEqual(normalize_vehicle_fields({"make": "10053"}), {"make": None, "model": None})

    def test_named_numeric_models_are_kept_without_a_title(self):
        for make, model in [("Omoda", "5"), ("Omoda", "7"), ("Omoda", "9"), ("Jaecoo", "5"), ("Jaecoo", "7"), ("Jaecoo", "8"), ("Lynk & Co", "02"), ("Lynk & Co", "08")]:
            with self.subTest(make=make, model=model):
                self.assertEqual(normalize_vehicle_fields({"make": make, "model": model}), {"make": make, "model": model})

    def test_observed_chery_taxonomy_code_requires_named_evidence(self):
        for model in ("4", "7", "8", "9"):
            with self.subTest(model=model):
                self.assertEqual(normalize_vehicle_fields({
                    "make": "10057", "description": f"Chery Tiggo {model} PHEV Unique AWD",
                }), {"make": "Chery", "model": f"Tiggo {model}"})
        self.assertEqual(normalize_vehicle_fields({"make": "10057"}), {"make": None, "model": None})

    def test_make_aliases_and_decorations(self):
        for raw, expected in [("VW", "Volkswagen"), ("‼ TOYOTA", "Toyota"), ("⭐VW", "Volkswagen"), ("SKODA", "Škoda"), ("Mercedes Benz", "Mercedes-Benz"), ("DS", "DS Automobiles")]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_vehicle_fields({"make": raw})["make"], expected)

    def test_numeric_codes_are_resolved_only_from_readable_evidence(self):
        self.assertEqual(normalize_vehicle_fields({
            "make": "1036", "model": "10004", "description": "Volkswagen Golf 1.6 TDI Comfortline",
        }), {"make": "Volkswagen", "model": "Golf"})
        self.assertEqual(normalize_vehicle_fields({"make": "1036", "model": "10004"}), {"make": None, "model": None})

    def test_source_url_can_supply_the_readable_vehicle_name(self):
        self.assertEqual(normalize_vehicle_fields({
            "make": "1003", "model": "50042", "url": "https://example.test/auto/land-rover-range-rover-sport-123456/",
        }), {"make": "Land Rover", "model": "Range Rover Sport"})

    def test_numeric_models_are_not_all_taxonomy_codes(self):
        for make, model in [("Peugeot", "208"), ("Peugeot", "2008"), ("Porsche", "911"), ("Fiat", "500"), ("Toyota", "86"), ("Audi", "80")]:
            with self.subTest(make=make, model=model):
                self.assertEqual(normalize_vehicle_fields({"make": make, "model": model}), {"make": make, "model": model})

    def test_numeric_model_in_title_is_preserved(self):
        self.assertEqual(normalize_vehicle_fields({"description": "Peugeot 2008 1.2 PureTech"}), {"make": "Peugeot", "model": "2008"})

    def test_conflicting_description_cannot_override_a_named_make(self):
        self.assertEqual(normalize_vehicle_fields({"make": "BMW", "model": "10004", "description": "Toyota Corolla"}), {"make": "BMW", "model": None})

    def test_year_or_sales_text_is_not_a_model(self):
        for title in ["BMW 2018", "Volkswagen zu verkaufen"]:
            with self.subTest(title=title):
                self.assertIsNone(normalize_vehicle_fields({"description": title})["model"])

    def test_engine_suffixes_do_not_split_a_model(self):
        for raw in ["Golf 1.6 TDI", "Golf TDI", " golf "]:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_vehicle_fields({"make": "VW", "model": raw}), {"make": "Volkswagen", "model": "Golf"})

    def test_legitimate_make_with_digits_and_hyphenated_model(self):
        self.assertEqual(normalize_vehicle_fields({"make": "Mazda", "model": "CX-5"}), {"make": "Mazda", "model": "CX-5"})


if __name__ == "__main__":
    unittest.main()
