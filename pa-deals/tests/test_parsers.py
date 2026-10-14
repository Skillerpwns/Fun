import unittest

from padeals.parsers import count_products, extract_offers

from . import fakes


def capture(doc):
    return {"url": "https://example.test/api", "json": doc}


class DutchieTests(unittest.TestCase):
    def test_options_become_separate_offers(self):
        offers, platforms = extract_offers("s1", [capture(fakes.dutchie_response([fakes.dutchie_product(0)]))])
        self.assertEqual(platforms, ["dutchie"])
        self.assertEqual([o["size"] for o in offers], ["1/8 oz (3.5g)", "1/4 oz (7g)"])
        eighth = offers[0]
        self.assertEqual(eighth["price"], 32.0)          # 40 * 0.8 special price
        self.assertEqual(eighth["original_price"], 40)
        self.assertEqual(eighth["weight_g"], 3.5)
        self.assertEqual(eighth["price_per_g"], 9.14)
        self.assertEqual(eighth["deal"], "20% off Test Brand")
        self.assertEqual(eighth["strain_type"], "indica")
        self.assertEqual(eighth["thc"], 18)

    def test_duplicate_responses_are_merged(self):
        doc = fakes.dutchie_response(fakes.dutchie_catalog(10))
        offers, _ = extract_offers("s1", [capture(doc), capture(doc)])
        single, _ = extract_offers("s1", [capture(doc)])
        self.assertEqual(len(offers), len(single))


class JaneTests(unittest.TestCase):
    def test_algolia_hits(self):
        doc = {"results": [{"hits": fakes.jane_catalog(5), "page": 0, "nbPages": 1}]}
        offers, platforms = extract_offers("s2", [capture(doc)])
        self.assertEqual(platforms, ["jane"])
        flower = [o for o in offers if o["category"] == "flower"]
        self.assertEqual(sorted(o["weight_g"] for o in flower), [3.5, 7.0])
        eighth = next(o for o in flower if o["weight_g"] == 3.5)
        self.assertEqual((eighth["price"], eighth["original_price"], eighth["deal"]), (36, 45, "Flower Friday"))
        vape = next(o for o in offers if o["category"] == "vape")
        self.assertEqual((vape["price"], vape["weight_g"]), (50, 1.0))


class VariantsTests(unittest.TestCase):
    def test_dutchie_plus_shape(self):
        doc = {"data": {"menu": {"products": [fakes.variants_product(1)]}}}
        offers, platforms = extract_offers("s3", [capture(doc)])
        self.assertEqual(platforms, ["variants"])
        self.assertEqual([(o["size"], o["price"], o["original_price"]) for o in offers],
                         [("1/8 oz (3.5g)", 42, 50), ("1/4 oz (7g)", 90, None)])
        self.assertEqual(offers[0]["thc"], 21)
        self.assertEqual(offers[0]["brand"], "Plus Brand")

    def test_sweed_style_unit_size(self):
        doc = {"list": [{"id": 5, "name": "Sweed Strain", "brand": {"name": "B"}, "category": {"name": "Flower"},
                         "strain": {"name": "Sweed Strain", "prevalence": {"name": "Sativa"}},
                         "variants": [{"price": 60, "promoPrice": 48, "unitSize": {"value": 3.5, "unitAbbr": "g"},
                                       "labTests": {"thc": {"value": [26.1], "unitAbbr": "%"}}}]}]}
        offers, _ = extract_offers("s4", [capture(doc)])
        self.assertEqual(len(offers), 1)
        self.assertEqual((offers[0]["price"], offers[0]["weight_g"], offers[0]["strain_type"], offers[0]["thc"]),
                         (48, 3.5, "sativa", 26.1))


class GenericTests(unittest.TestCase):
    def test_unknown_platform_list(self):
        doc = {"items": [{"title": f"Mystery Flower {i} 3.5g", "price": 30 + i, "category": "Flower"}
                         for i in range(4)]}
        offers, platforms = extract_offers("s5", [capture(doc)])
        self.assertEqual(platforms, ["generic"])
        self.assertEqual(len(offers), 4)
        self.assertEqual(offers[0]["weight_g"], 3.5)

    def test_generic_not_used_when_a_platform_matched(self):
        known = fakes.dutchie_response([fakes.dutchie_product(1)])
        noise = {"items": [{"name": f"Gift card {i}", "price": 25} for i in range(5)]}
        offers, platforms = extract_offers("s1", [capture(known), capture(noise)])
        self.assertEqual(platforms, ["dutchie"])
        self.assertTrue(all(o["source"] == "dutchie" for o in offers))

    def test_unrelated_json_has_no_products(self):
        self.assertEqual(count_products({"data": {"dispensary": {"name": "X", "hours": []}}}), 0)


if __name__ == "__main__":
    unittest.main()
