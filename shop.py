"""Game rules and MySQL persistence for the fantasy shop."""

from contextlib import contextmanager, suppress
from dataclasses import dataclass
from getpass import getpass
import os
import random

try:
    import mysql.connector as connector
    from mysql.connector import Error as DBError
except ModuleNotFoundError:
    connector = None

    class DBError(Exception):
        pass


class ConfigError(Exception):
    """The game cannot load its database settings."""


class ShopError(Exception):
    """The requested action is unavailable in the current game state."""


@dataclass(frozen=True)
class Market:
    message: str
    wholesale_percent: int = 100
    supply_bonus: int = 0
    popular_products: tuple[int, ...] = ()
    demand_bonus: int = 0


MARKETS = (
    Market("접수대에 평시 보급 요청이 들어왔습니다. 장부의 상품 기준가를 확인하세요."),
    Market("북문 원정대 출정일. 회복 물약과 무기, 방어구를 찾는 모험가가 늘어납니다.",
           110, 0, (1, 3, 5, 7), 3),
    Market("산길이 열려 대상단이 도착했습니다. 도매가가 내려가고 매입 한도가 늘어납니다.",
           90, 4),
    Market("마법탑의 야간 실습일. 마나 약초와 은빛 부적, 별빛 지팡이가 인기입니다.",
           100, 0, (2, 4, 6), 4),
    Market("성문 앞 교역 축제. 모든 상품에 평소보다 많은 손님이 찾아옵니다.",
           105, 2, (1, 2, 3, 4, 5, 6, 7), 2),
)
CAPACITIES = {1: 36, 2: 64, 3: 96}
UPGRADES = {1: (400, 6), 2: (780, 16)}
RESERVE = 90
GOAL_GOLD = 1200
MAX_WHOLESALE_PERCENT = max(market.wholesale_percent for market in MARKETS)


def db_settings():
    try:
        port = int(os.getenv("MYSQL_PORT", "3306"))
    except ValueError as exc:
        raise ConfigError("MYSQL_PORT에 포트 번호를 입력하세요.") from exc
    if not 1 <= port <= 65535:
        raise ConfigError("MYSQL_PORT의 범위는 1~65535입니다.")

    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD")
    if password is None:
        password = getpass(f"MySQL 비밀번호 ({user}, 설정하지 않았다면 Enter) > ")
    return {
        "host": os.getenv("MYSQL_HOST", "127.0.0.1"),
        "port": port,
        "user": user,
        "password": password,
        "database": os.getenv("MYSQL_DATABASE", "fantasy_shop"),
        "charset": "utf8mb4",
        "connection_timeout": 5,
    }


def market_for(day):
    return MARKETS[(day - 1) % len(MARKETS)]


class Store:
    def __init__(self, settings=None):
        if connector is None:
            raise ConfigError("드라이버가 필요합니다. python -m pip install -r requirements.txt")
        self.connection = connector.connect(**(db_settings() if settings is None else settings))

    @staticmethod
    def initialize_database(settings, schema):
        if connector is None:
            raise ConfigError("MySQL 드라이버가 필요합니다.")
        connection_settings = {**settings, "database": None}
        connection = connector.connect(**connection_settings)
        try:
            with connection.cursor() as cursor:
                for statement in schema.split(";"):
                    if statement.strip():
                        cursor.execute(statement)
            connection.commit()
        finally:
            with suppress(DBError):
                connection.close()

    def close(self):
        with suppress(DBError):
            self.connection.close()

    @contextmanager
    def _transaction(self):
        cursor = self.connection.cursor(dictionary=True, buffered=True)
        try:
            self.connection.start_transaction()
            yield cursor
            self.connection.commit()
        except BaseException:
            with suppress(DBError):
                self.connection.rollback()
            raise
        finally:
            with suppress(DBError):
                cursor.close()

    @staticmethod
    def _shop(cursor, shop_id, *, lock=False, expected_day=None):
        query = "SELECT id, name, day, gold, level, reputation, goal_reached FROM shops WHERE id = %s"
        if lock:
            query += " FOR UPDATE"
        cursor.execute(query, (shop_id,))
        shop = cursor.fetchone()
        if shop is None:
            raise ShopError("저장된 상점을 찾을 수 없습니다.")
        if expected_day is not None and shop["day"] != expected_day:
            raise ShopError("다른 창에서 다음 날로 넘어갔습니다. 메뉴를 다시 선택하세요.")
        return shop

    @staticmethod
    def _inventory(cursor, shop):
        cursor.execute(
            """
            SELECT p.id, p.name, p.description, p.base_cost, p.reference_price AS reference,
                   p.supply, p.demand, p.required_level, i.quantity, i.stock_cost, i.price,
                   COALESCE(bought.quantity, 0) AS bought
            FROM inventory AS i
            JOIN products AS p ON p.id = i.product_id
            LEFT JOIN (
                SELECT product_id, SUM(quantity) AS quantity
                FROM trades
                WHERE shop_id = %s AND day = %s AND kind = 'buy'
                GROUP BY product_id
            ) AS bought ON bought.product_id = p.id
            WHERE i.shop_id = %s
            ORDER BY p.id
            """,
            (shop["id"], shop["day"], shop["id"]),
        )
        market = market_for(shop["day"])
        products = cursor.fetchall()
        for product in products:
            product["cost"] = product["base_cost"] * market.wholesale_percent // 100
            product["min_price"] = product["base_cost"] * MAX_WHOLESALE_PERCENT // 100
            product["stock"] = product["supply"] + market.supply_bonus - int(product["bought"])
        return products

    @staticmethod
    def _available_product(products, shop, item_id):
        product = next((product for product in products if product["id"] == item_id), None)
        if product is None:
            raise ShopError("상품 번호를 확인하세요.")
        if product["required_level"] > shop["level"]:
            raise ShopError(f"이 상품은 상점 {product['required_level']}레벨에 해금됩니다.")
        return product

    def list_shops(self):
        with self._transaction() as cursor:
            cursor.execute("SELECT id, name, day, gold FROM shops ORDER BY id")
            return cursor.fetchall()

    def create_shop(self, name):
        name = name.strip()
        if not 1 <= len(name) <= 24 or not name.isprintable():
            raise ShopError("상점 이름을 1~24자로 입력하세요.")
        with self._transaction() as cursor:
            try:
                cursor.execute("INSERT INTO shops (name) VALUES (%s)", (name,))
            except DBError as exc:
                if exc.errno == 1062:
                    raise ShopError("이미 같은 이름의 상점이 있습니다.") from exc
                raise
            shop_id = cursor.lastrowid
            cursor.execute(
                """
                INSERT INTO inventory (shop_id, product_id, quantity, price)
                SELECT %s, id, starter_quantity, reference_price FROM products
                """,
                (shop_id,),
            )
            return shop_id

    def status(self, shop_id):
        with self._transaction() as cursor:
            shop = self._shop(cursor, shop_id)
            cursor.execute(
                "SELECT COALESCE(SUM(quantity), 0) AS used FROM inventory WHERE shop_id = %s",
                (shop_id,),
            )
            cost, requirement = UPGRADES.get(shop["level"], (None, None))
            return {
                **shop,
                "capacity": CAPACITIES[shop["level"]],
                "used": int(cursor.fetchone()["used"]),
                "event": market_for(shop["day"]).message,
                "upgrade_cost": cost,
                "upgrade_requirement": requirement,
                "reserve": RESERVE,
                "goal_met": bool(shop["goal_reached"]),
            }

    def inventory(self, shop_id):
        with self._transaction() as cursor:
            return self._inventory(cursor, self._shop(cursor, shop_id))

    def buy(self, shop_id, item_id, quantity, *, expected_day=None):
        if not isinstance(quantity, int) or quantity < 1:
            raise ShopError("매입 수량을 1 이상으로 입력하세요.")
        with self._transaction() as cursor:
            shop = self._shop(cursor, shop_id, lock=True, expected_day=expected_day)
            products = self._inventory(cursor, shop)
            product = self._available_product(products, shop, item_id)
            if quantity > product["stock"]:
                raise ShopError(f"오늘 남은 매입 한도는 {product['stock']}개입니다.")
            space = CAPACITIES[shop["level"]] - sum(row["quantity"] for row in products)
            if quantity > space:
                raise ShopError(f"창고에 {space}개를 더 보관할 수 있습니다.")
            total = quantity * product["cost"]
            if total > shop["gold"]:
                raise ShopError(f"매입에 {total:,} G가 필요합니다.")

            cursor.execute("UPDATE shops SET gold = %s WHERE id = %s",
                           (shop["gold"] - total, shop_id))
            cursor.execute(
                """
                UPDATE inventory SET quantity = quantity + %s, stock_cost = stock_cost + %s
                WHERE shop_id = %s AND product_id = %s
                """,
                (quantity, total, shop_id, item_id),
            )
            cursor.execute(
                """
                INSERT INTO trades (shop_id, day, product_id, kind, quantity, unit_price, cost)
                VALUES (%s, %s, %s, 'buy', %s, %s, %s)
                """,
                (shop_id, shop["day"], item_id, quantity, product["cost"], total),
            )
            return {"name": product["name"], "quantity": quantity, "total": total}

    def set_price(self, shop_id, item_id, price):
        with self._transaction() as cursor:
            shop = self._shop(cursor, shop_id, lock=True)
            product = self._available_product(self._inventory(cursor, shop), shop, item_id)
            minimum = product["min_price"]
            maximum = product["reference"] * 3
            if not isinstance(price, int) or not minimum <= price <= maximum:
                raise ShopError(f"판매가는 {minimum:,}~{maximum:,} G로 정할 수 있습니다.")
            cursor.execute(
                "UPDATE inventory SET price = %s WHERE shop_id = %s AND product_id = %s",
                (price, shop_id, item_id),
            )

    def close_day(self, shop_id, *, expected_day=None):
        with self._transaction() as cursor:
            shop = self._shop(cursor, shop_id, lock=True, expected_day=expected_day)
            day = shop["day"]
            market = market_for(day)
            rng = random.Random(f"{shop_id}:{day}")
            sales = []
            revenue = sold_cost = units_sold = customers = missed = 0
            for product in self._inventory(cursor, shop):
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
                # The last sale absorbs the rounding remainder of the inventory cost.
                cost = product["stock_cost"] * sold // product["quantity"]
                cursor.execute(
                    """
                    UPDATE inventory SET quantity = %s, stock_cost = %s
                    WHERE shop_id = %s AND product_id = %s
                    """,
                    (product["quantity"] - sold, product["stock_cost"] - cost,
                     shop_id, product["id"]),
                )
                cursor.execute(
                    """
                    INSERT INTO trades (shop_id, day, product_id, kind, quantity, unit_price, cost)
                    VALUES (%s, %s, %s, 'sale', %s, %s, %s)
                    """,
                    (shop_id, day, product["id"], sold, product["price"], cost),
                )
                sales.append({"name": product["name"], "quantity": sold, "total": total})
                revenue += total
                sold_cost += cost
                units_sold += sold

            gain = min(7, 1 + units_sold // 2) if units_sold else 0
            gold = shop["gold"] + revenue
            goal_reached = shop["goal_reached"] or (shop["level"] == 3 and gold >= GOAL_GOLD)
            cursor.execute(
                """
                UPDATE shops SET day = %s, gold = %s, reputation = %s, goal_reached = %s
                WHERE id = %s
                """,
                (day + 1, gold, min(100, shop["reputation"] + gain), int(goal_reached), shop_id),
            )
            cursor.execute(
                """
                INSERT INTO daily_reports (shop_id, day, revenue, cost, customers, missed)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (shop_id, day, revenue, sold_cost, customers, missed),
            )
            return {
                "day": day, "sales": sales, "revenue": revenue, "cost": sold_cost,
                "profit": revenue - sold_cost, "customers": customers, "missed": missed,
                "event": market.message,
            }

    def reports(self, shop_id):
        with self._transaction() as cursor:
            cursor.execute(
                """
                SELECT day, revenue, cost, CAST(revenue AS SIGNED) - CAST(cost AS SIGNED) AS profit,
                       customers, missed
                FROM daily_reports WHERE shop_id = %s ORDER BY day DESC LIMIT 7
                """,
                (shop_id,),
            )
            return cursor.fetchall()

    def upgrade(self, shop_id, *, expected_level=None):
        with self._transaction() as cursor:
            shop = self._shop(cursor, shop_id, lock=True)
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
            gold = shop["gold"] - cost
            goal_reached = level == 3 and gold >= GOAL_GOLD
            cursor.execute("UPDATE shops SET gold = %s, level = %s, goal_reached = %s WHERE id = %s",
                           (gold, level, int(goal_reached), shop_id))
            return {"cost": cost, "level": level, "capacity": CAPACITIES[level]}
