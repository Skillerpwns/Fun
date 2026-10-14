import unittest

from padeals.normalize import (category_of, make_offer, offer_key, parse_weight_g, strain_guess,
                               strain_type_of, thc_percent)


class WeightTests(unittest.TestCase):
    def test_common_labels(self):
        cases = {
            "1/8oz": 3.5, "1/8 oz": 3.5, "1/8th": 3.5, "1/4oz": 7.0, "1/2 oz": 14.0, "1oz": 28.0,
            "3.5g": 3.5, "3.5 g": 3.5, "1g": 1.0, "0.5g": 0.5, "28 grams": 28.0, "Eighth": 3.5,
            "Half Ounce": 14.0, "": None, "N/A": None,
        }
        for label, grams in cases.items():
            with self.subTest(label=label):
                self.assertEqual(parse_weight_g(label, "flower"), grams)

    def test_milligrams_are_weight_only_for_vapes_and_concentrates(self):
        self.assertEqual(parse_weight_g("500mg", "vape"), 0.5)
        self.assertIsNone(parse_weight_g("100mg", "edible"))
        self.assertIsNone(parse_weight_g("1000mg", "tincture"))

    def test_weight_inside_product_name(self):
        self.assertEqual(parse_weight_g("Gelato 41 [3.5g]", "flower"), 3.5)
        self.assertEqual(parse_weight_g("Gorilla Glue #4 1g", "concentrate"), 1.0)


class CategoryTests(unittest.TestCase):
    def test_platform_labels(self):
        cases = {"Flower": "flower", "Vaporizers": "vape", "Pre-Rolls": "preroll", "PRE_ROLLS": "preroll",
                 "Concentrate": "concentrate", "CONCENTRATES": "concentrate", "extract": "concentrate",
                 "Tincture": "tincture", "Topicals": "topical", "Capsules": "capsule", "Edible": "edible"}
        for label, expected in cases.items():
            with self.subTest(label=label):
                self.assertEqual(category_of(label), expected)

    def test_vape_beats_concentrate_words(self):
        self.assertEqual(category_of("Live Resin Cart"), "vape")

    def test_falls_back_to_later_hints(self):
        self.assertEqual(category_of("", None, "Blue Dream Pre-Roll 1g"), "preroll")
        self.assertEqual(category_of("Misc"), "other")


class FieldTests(unittest.TestCase):
    def test_strain_type(self):
        self.assertEqual(strain_type_of("Indica Hybrid"), "indica")
        self.assertEqual(strain_type_of("INDICA_HYBRID"), "indica")
        self.assertEqual(strain_type_of("High CBD"), "cbd")
        self.assertEqual(strain_type_of(None), "")

    def test_thc_shapes(self):
        self.assertEqual(thc_percent(22.456), 22.46)
        self.assertEqual(thc_percent("24.1%"), 24.1)
        self.assertEqual(thc_percent({"unit": "PERCENTAGE", "range": [20, 25.5]}), 25.5)
        self.assertIsNone(thc_percent({"unit": "MILLIGRAMS", "range": [100]}))
        self.assertIsNone(thc_percent("100mg"))
        self.assertIsNone(thc_percent(0))

    def test_strain_guess_strips_brand_and_size(self):
        self.assertEqual(strain_guess("Cresco - GMO Cookies Flower [3.5g]", "Cresco"), "GMO Cookies")
        self.assertEqual(strain_guess("Blue Dream Live Resin Cart 0.5g"), "Blue Dream")


class OfferTests(unittest.TestCase):
    def test_sale_and_price_per_gram(self):
        offer = make_offer(store_id="s1", source="t", name="GMO 3.5g", category_hints=("Flower",),
                           size_label="1/8oz", price=45, sale_price=36)
        self.assertEqual(offer["price"], 36)
        self.assertEqual(offer["original_price"], 45)
        self.assertEqual(offer["discount_pct"], 20)
        self.assertEqual(offer["price_per_g"], 10.29)

    def test_sale_price_not_lower_is_ignored(self):
        offer = make_offer(store_id="s1", source="t", name="X", price=40, sale_price=40)
        self.assertEqual(offer["price"], 40)
        self.assertIsNone(offer["original_price"])

    def test_no_price_per_gram_for_edibles(self):
        offer = make_offer(store_id="s1", source="t", name="Gummies 100mg", category_hints=("Edible",), price=20)
        self.assertIsNone(offer["price_per_g"])

    def test_unusable_rows_are_dropped(self):
        self.assertIsNone(make_offer(store_id="s1", source="t", name="", price=10))
        self.assertIsNone(make_offer(store_id="s1", source="t", name="X", price=None))
        self.assertIsNone(make_offer(store_id="s1", source="t", name="X", price=0))

    def test_offer_key_ignores_formatting(self):
        a = make_offer(store_id="s1", source="t", name="GMO  Cookies", brand="Cresco", size_label="1/8oz", price=40)
        b = make_offer(store_id="s1", source="t", name="gmo cookies", brand="CRESCO", size_label="3.5g", price=30)
        self.assertEqual(offer_key(a), offer_key(b))


if __name__ == "__main__":
    unittest.main()
