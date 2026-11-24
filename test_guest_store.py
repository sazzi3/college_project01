"""Repository root: py -m unittest test_guest_store.py -v"""
import unittest

from guest_store import GuestStore
from shop import ShopError


class GuestStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = GuestStore()
        self.id = self.store.create_shop("연습 상점")

    def test_starts_with_same_default_state_as_mysql(self):
        status = self.store.status(self.id)
        self.assertEqual((status["day"], status["gold"], status["level"], status["used"]), (1, 220, 1, 14))
        self.assertEqual(len(self.store.inventory(self.id)), 7)
        self.assertEqual(len(self.store.list_shops()), 1)

    def test_buy_and_price(self):
        before = self.store.status(self.id)
        item = self.store.inventory(self.id)[0]
        self.store.buy(self.id, item["id"], 2, expected_day=before["day"])
        self.assertEqual(self.store.status(self.id)["gold"], before["gold"] - item["cost"] * 2)
        self.assertEqual(self.store.inventory(self.id)[0]["quantity"], 8)
        self.store.set_price(self.id, item["id"], item["reference"] + 2)
        self.assertEqual(self.store.inventory(self.id)[0]["price"], item["reference"] + 2)
        with self.assertRaises(ShopError):
            self.store.set_price(self.id, item["id"], -5)
        with self.assertRaises(ShopError):
            self.store.buy(self.id, item["id"], 1000)

    def test_sell_and_reports_and_new_day_supply(self):
        self.store.buy(self.id, 1, 1)
        result = self.store.close_day(self.id, expected_day=1)
        self.assertEqual(self.store.status(self.id)["day"], 2)
        self.assertEqual(result["profit"], result["revenue"] - result["cost"])
        self.assertEqual(self.store.reports(self.id)[0]["day"], 1)
        with self.assertRaises(ShopError):
            self.store.close_day(self.id, expected_day=1)
        self.assertEqual(self.store.inventory(self.id)[0]["bought"], 0)

    def test_upgrade_rules_and_ephemeral_data(self):
        status = self.store.status(self.id)
        with self.assertRaises(ShopError):
            self.store.upgrade(self.id)
        self.assertEqual(status["level"], 1)
        self.store.close()
        self.assertEqual(self.store.list_shops(), [])

    def test_long_game_to_level_three(self):
        for _ in range(100):
            status = self.store.status(self.id)
            if status["level"] == 3:
                break
            if (status["upgrade_cost"] is not None
                    and status["gold"] >= status["upgrade_cost"] + status["reserve"]
                    and status["reputation"] >= status["upgrade_requirement"]):
                self.store.upgrade(self.id, expected_level=status["level"])
                continue
            for item in self.store.inventory(self.id):
                if item["required_level"] > status["level"]:
                    continue
                current = self.store.status(self.id)
                maximum = min(item["stock"], current["capacity"] - current["used"], current["gold"] // item["cost"])
                if maximum > 0:
                    self.store.buy(self.id, item["id"], min(maximum, 4), expected_day=current["day"])
            self.store.close_day(self.id, expected_day=status["day"])
        self.assertEqual(self.store.status(self.id)["level"], 3)


if __name__ == "__main__":
    unittest.main()
