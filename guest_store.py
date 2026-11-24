"""MySQL이 없어도 달빛 잡화점을 체험할 수 있는 메모리 저장소.

shop.Store와 동일한 공개 메서드를 제공하며 프로그램을 종료하면 데이터가 사라집니다.
"""

from copy import deepcopy
import random

from shop import (
    CAPACITIES, GOAL_GOLD, MAX_WHOLESALE_PERCENT,
    RESERVE, UPGRADES, ShopError, market_for,
)


# schema.sql의 최초 상품 데이터를 그대로 사용합니다.
_PRODUCT_ROWS = (
    (1, "회복 물약", "모험가가 들고 다니는 기본 비상약", 12, 23, 16, 5, 1, 6),
    (2, "마나 약초", "마법 물약의 재료로 쓰는 푸른 약초", 7, 15, 20, 5, 1, 6),
    (3, "철제 단검", "여행길을 지키는 튼튼한 단검", 24, 45, 9, 3, 1, 2),
    (4, "은빛 부적", "위험을 피하고 싶은 이들이 찾는 부적", 33, 62, 10, 4, 2, 0),
    (5, "기사 방패", "경비대와 모험가가 쓰는 방패", 47, 85, 7, 3, 2, 0),
    (6, "별빛 지팡이", "숙련된 마법사가 사용하는 지팡이", 71, 125, 7, 3, 3, 0),
    (7, "용비늘 갑옷", "용비늘을 덧댄 희귀한 갑옷", 108, 190, 5, 2, 3, 0),
)


class GuestStore:
    """오직 메모리에만 저장하는 데모용 Store 호환 클래스."""

    is_guest = True

    def __init__(self):
        self._shops = {}
        self._next_id = 1

    def close(self):
        """데모 데이터는 프로세스가 끝나거나 인스턴스가 사라지면 소멸한다."""
        self._shops.clear()

    def list_shops(self):
        return [
            {key: shop[key] for key in ("id", "name", "day", "gold")}
            for shop in self._shops.values()
        ]

    def create_shop(self, name):
        name = name.strip()
        if not 1 <= len(name) <= 24 or not name.isprintable():
            raise ShopError("상점 이름을 1~24자로 입력하세요.")
        if any(shop["name"] == name for shop in self._shops.values()):
            raise ShopError("이미 같은 이름의 상점이 있습니다.")
        shop_id = self._next_id
        self._next_id += 1
        products = {}
        for (item_id, item_name, description, base_cost, reference, supply,
             demand, required_level, starter_quantity) in _PRODUCT_ROWS:
            products[item_id] = {
                "id": item_id, "name": item_name, "description": description,
                "base_cost": base_cost, "reference": reference,
                "supply": supply, "demand": demand,
                "required_level": required_level, "quantity": starter_quantity,
                "stock_cost": 0, "price": reference, "bought": 0,
            }
        self._shops[shop_id] = {
            "id": shop_id, "name": name, "day": 1, "gold": 220,
            "level": 1, "reputation": 0, "goal_reached": False,
            "products": products, "reports": [],
        }
        return shop_id

    def _get_shop(self, shop_id, *, expected_day=None):
        shop = self._shops.get(shop_id)
        if shop is None:
            raise ShopError("저장된 상점을 찾을 수 없습니다.")
        if expected_day is not None and shop["day"] != expected_day:
            raise ShopError("이미 다음 날로 넘어갔습니다. 메뉴를 다시 선택하세요.")
        return shop

    def _get_product(self, shop, item_id):
        product = shop["products"].get(item_id)
        if product is None:
            raise ShopError("상품 번호를 확인하세요.")
        if product["required_level"] > shop["level"]:
            raise ShopError(f"이 상품은 상점 {product['required_level']}레벨에 해금됩니다.")
        return product

    def status(self, shop_id):
        shop = self._get_shop(shop_id)
        upgrade_cost, required_reputation = UPGRADES.get(shop["level"], (None, None))
        return {
            "id": shop["id"], "name": shop["name"], "day": shop["day"],
            "gold": shop["gold"], "level": shop["level"],
            "reputation": shop["reputation"], "goal_reached": shop["goal_reached"],
            "capacity": CAPACITIES[shop["level"]],
            "used": sum(item["quantity"] for item in shop["products"].values()),
            "event": market_for(shop["day"]).message,
            "upgrade_cost": upgrade_cost,
            "upgrade_requirement": required_reputation,
            "reserve": RESERVE, "goal_met": bool(shop["goal_reached"]),
        }

    def inventory(self, shop_id):
        shop = self._get_shop(shop_id)
        market = market_for(shop["day"])
        result = []
        for original in shop["products"].values():
            product = original.copy()
            product["cost"] = product["base_cost"] * market.wholesale_percent // 100
            product["min_price"] = product["base_cost"] * MAX_WHOLESALE_PERCENT // 100
            product["stock"] = product["supply"] + market.supply_bonus - product["bought"]
            result.append(product)
        return result

    def buy(self, shop_id, item_id, quantity, *, expected_day=None):
        if not isinstance(quantity, int) or isinstance(quantity, bool) or quantity < 1:
            raise ShopError("매입 수량을 1 이상으로 입력하세요.")
        shop = self._get_shop(shop_id, expected_day=expected_day)
        product = self._get_product(shop, item_id)
        market = market_for(shop["day"])
        remaining = product["supply"] + market.supply_bonus - product["bought"]
        if quantity > remaining:
            raise ShopError(f"오늘 남은 매입 한도는 {remaining}개입니다.")
        used = sum(item["quantity"] for item in shop["products"].values())
        space = CAPACITIES[shop["level"]] - used
        if quantity > space:
            raise ShopError(f"창고에 {space}개를 더 보관할 수 있습니다.")
        cost = product["base_cost"] * market.wholesale_percent // 100
        total = quantity * cost
        if total > shop["gold"]:
            raise ShopError(f"매입에 {total:,} G가 필요합니다.")
        shop["gold"] -= total
        product["quantity"] += quantity
        product["stock_cost"] += total
        product["bought"] += quantity
        return {"name": product["name"], "quantity": quantity, "total": total}

    def set_price(self, shop_id, item_id, price):
        shop = self._get_shop(shop_id)
        product = self._get_product(shop, item_id)
        minimum = product["base_cost"] * MAX_WHOLESALE_PERCENT // 100
        maximum = product["reference"] * 3
        if not isinstance(price, int) or isinstance(price, bool) or not minimum <= price <= maximum:
            raise ShopError(f"판매가는 {minimum:,}~{maximum:,} G로 정할 수 있습니다.")
        product["price"] = price

    def close_day(self, shop_id, *, expected_day=None):
        shop = self._get_shop(shop_id, expected_day=expected_day)
        day = shop["day"]
        market = market_for(day)
        rng = random.Random(f"{shop_id}:{day}")
        sales = []
        revenue = sold_cost = units_sold = customers = missed = 0
        for product in shop["products"].values():
            if product["required_level"] > shop["level"]:
                continue
            interest = product["demand"] + rng.randint(-1, 1) + shop["reputation"] // 18
            if product["id"] in market.popular_products:
                interest += market.demand_bonus
            willing = sum(
                product["price"] <= product["reference"] * rng.randint(85, 140) // 100
                for _ in range(interest)
            )
            sold = min(willing, product["quantity"])
            customers += interest
            missed += interest - sold
            if sold == 0:
                continue
            total = sold * product["price"]
            cost = product["stock_cost"] * sold // product["quantity"]
            product["quantity"] -= sold
            product["stock_cost"] -= cost
            sales.append({"name": product["name"], "quantity": sold, "total": total})
            revenue += total
            sold_cost += cost
            units_sold += sold

        gain = min(7, 1 + units_sold // 2) if units_sold else 0
        shop["gold"] += revenue
        shop["reputation"] = min(100, shop["reputation"] + gain)
        shop["goal_reached"] = shop["goal_reached"] or (
            shop["level"] == 3 and shop["gold"] >= GOAL_GOLD
        )
        shop["reports"].append({
            "day": day, "revenue": revenue, "cost": sold_cost,
            "profit": revenue - sold_cost, "customers": customers, "missed": missed,
        })
        shop["day"] += 1
        for product in shop["products"].values():
            product["bought"] = 0
        return {
            "day": day, "sales": sales, "revenue": revenue,
            "cost": sold_cost, "profit": revenue - sold_cost,
            "customers": customers, "missed": missed, "event": market.message,
        }

    def reports(self, shop_id):
        shop = self._get_shop(shop_id)
        return deepcopy(list(reversed(shop["reports"][-7:])))

    def upgrade(self, shop_id, *, expected_level=None):
        shop = self._get_shop(shop_id)
        if expected_level is not None and shop["level"] != expected_level:
            raise ShopError("다른 창에서 상점을 확장했습니다. 메뉴를 다시 선택하세요.")
        if shop["level"] not in UPGRADES:
            raise ShopError("이미 최고 레벨의 상점입니다.")
        cost, requirement = UPGRADES[shop["level"]]
        if shop["reputation"] < requirement:
            raise ShopError(f"확장하려면 평판이 {requirement} 이상이어야 합니다.")
        if shop["gold"] < cost + RESERVE:
            raise ShopError(f"확장 비용과 운영 자금을 합쳐 {cost + RESERVE:,} G가 필요합니다.")
        level = shop["level"] + 1
        shop["gold"] -= cost
        shop["level"] = level
        shop["goal_reached"] = level == 3 and shop["gold"] >= GOAL_GOLD
        return {"cost": cost, "level": level, "capacity": CAPACITIES[level]}
