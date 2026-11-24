"""달빛 잡화점의 터미널 게임 화면."""

from shop import ConfigError, DBError, ShopError, Store


def gold(amount):
    return f"{amount:,}G"


def read_number(prompt, minimum=1, maximum=None):
    while True:
        response = input(f"{prompt} (Enter로 취소) > ").strip()
        if not response:
            return None

        try:
            number = int(response)
        except ValueError:
            print("숫자를 입력하세요.")
            continue

        if number >= minimum and (maximum is None or number <= maximum):
            return number

        if maximum is None:
            print(f"{minimum:,} 이상의 숫자를 입력하세요.")
        else:
            print(f"{minimum:,}~{maximum:,} 사이의 숫자를 입력하세요.")


def show_help():
    print("\n[견습 상인 안내서]")
    print("1. 도매상에게 상품을 매입합니다. 도매 단가와 공급량은 날마다 달라집니다.")
    print("2. 권장 판매가를 참고해 가격을 정합니다. 가격이 높으면 손님이 구매를 망설입니다.")
    print("3. 영업을 시작하면 손님이 찾아옵니다. 결과를 정산하고 다음 날로 넘어갑니다.")
    print("4. 골드와 평판을 모아 상점을 확장하면 재고 한도가 커지고 상품이 열립니다.")
    print("목표는 3단계 상점을 만들고 1,200G를 보유하는 것입니다.")
    print("매입, 가격 변경, 영업 결과, 확장은 즉시 MySQL에 저장됩니다.")


def choose_shop(store):
    while True:
        shops = store.list_shops()
        print("\n=== 달빛 잡화점 ===")
        if shops:
            print("[저장된 상점]")
            for index, shop in enumerate(shops, start=1):
                print(f"  {index}. {shop['name']} · {shop['day']}일차 · {gold(shop['gold'])}")
        else:
            print("마을에 첫 상점을 열어 보세요.")
        print("  N. 새 상점 열기   H. 도움말   0. 게임 종료")
        choice = input("선택 > ").strip().lower()

        if choice == "0":
            return None
        if choice == "h":
            show_help()
            continue
        if choice == "n":
            name = input("상점 이름 (Enter로 취소) > ").strip()
            if name:
                try:
                    shop_id = store.create_shop(name)
                except ShopError as error:
                    print(f"\n{error}")
                else:
                    print(f"\n{name}의 문을 열었습니다!")
                    return shop_id
            continue

        try:
            index = int(choice)
        except ValueError:
            index = 0
        if 1 <= index <= len(shops):
            return shops[index - 1]["id"]
        print("메뉴에 표시된 항목을 선택하세요.")


def show_inventory(items, level):
    print("\n[상품 목록]")
    for item in items:
        name = f"{item['id']:>2}. {item['name']}"
        if item["required_level"] > level:
            print(f"  {name} · 상점 {item['required_level']}단계부터 매입 가능")
        else:
            print(
                f"  {name} · 보유 {item['quantity']}개 · 판매가 {gold(item['price'])}"
                f" · 권장 {gold(item['reference'])} · 도매가 {gold(item['cost'])} · 공급 {item['stock']}개"
            )
        if item["description"]:
            print(f"      {item['description']}")


def choose_item(store, status, prompt):
    items = store.inventory(status["id"])
    show_inventory(items, status["level"])
    item_id = read_number(prompt)
    if item_id is None:
        return None

    item = next((item for item in items if item["id"] == item_id), None)
    if item is None:
        print("목록에 있는 상품 번호를 선택하세요.")
        return None
    if item["required_level"] > status["level"]:
        print(f"상점을 {item['required_level']}단계로 확장하면 취급할 수 있습니다.")
        return None
    return item


def buy_stock(store, status):
    item = choose_item(store, status, "매입할 상품 번호")
    if item is None:
        return
    max_quantity = min(
        item["stock"],
        status["capacity"] - status["used"],
        status["gold"] // item["cost"],
    )
    if max_quantity <= 0:
        if item["stock"] <= 0:
            print("오늘은 도매상에 이 상품이 남아 있지 않습니다.")
        elif status["capacity"] == status["used"]:
            print("창고가 가득 찼습니다.")
        else:
            print("매입에 필요한 골드가 부족합니다.")
        return

    quantity = read_number(
        f"{item['name']} 매입 수량 · 개당 {gold(item['cost'])} · 최대 {max_quantity}개",
        maximum=max_quantity,
    )
    if quantity is not None:
        purchase = store.buy(status["id"], item["id"], quantity, expected_day=status["day"])
        print(f"{purchase['name']} {purchase['quantity']}개를 {gold(purchase['total'])}에 매입했습니다.")


def change_price(store, status):
    item = choose_item(store, status, "판매가를 바꿀 상품 번호")
    if item is None:
        return
    price = read_number(
        f"{item['name']}의 새 판매가 · 현재 {gold(item['price'])} · 권장 {gold(item['reference'])}"
        f" · 최저 {gold(item['min_price'])}",
        minimum=item["min_price"],
    )
    if price is not None:
        store.set_price(status["id"], item["id"], price)
        print(f"{item['name']}의 판매가를 {gold(price)}로 변경했습니다.")


def show_day_result(store, status):
    result = store.close_day(status["id"], expected_day=status["day"])
    print(f"\n[{result['day']}일차 영업 정산]")
    print(result["event"])
    print(f"방문 {result['customers']}명 · 구매 없이 돌아간 손님 {result['missed']}명")

    if result["sales"]:
        for sale in result["sales"]:
            print(f"  {sale['name']} {sale['quantity']}개 · {gold(sale['total'])}")
    else:
        print("오늘 판매된 상품이 없습니다.")

    print(
        f"매출 {gold(result['revenue'])} · 팔린 상품의 원가 {gold(result['cost'])}"
        f" · 매출총이익 {gold(result['profit'])}"
    )


def show_reports(store, status):
    reports = store.reports(status["id"])
    print("\n[최근 7일 영업 기록]")
    if not reports:
        print("첫 영업을 마치면 여기에 기록이 표시됩니다.")
        return

    for row in reports:
        print(
            f"  {row['day']}일차 · 매출 {gold(row['revenue'])} · 원가 {gold(row['cost'])}"
            f" · 매출총이익 {gold(row['profit'])} · 방문 {row['customers']}명 · 미구매 {row['missed']}명"
        )


def expand_shop(store, status):
    if status["upgrade_cost"] is None:
        print("상점이 최고 단계에 도달했습니다.")
        return

    cost = status["upgrade_cost"]
    required_reputation = status["upgrade_requirement"]
    print(f"\n[상점 확장] {status['level']}단계 → {status['level'] + 1}단계")
    reserve = status["reserve"]
    print(f"확장비 {gold(cost)} · 확장 후 남겨둘 운영 자금 {gold(reserve)} · 필요 평판 {required_reputation}")
    if status["gold"] < cost + reserve or status["reputation"] < required_reputation:
        print("영업으로 골드와 평판을 모아 확장 조건을 충족하세요.")
        return
    if input("확장하려면 Y를 입력하세요 > ").strip().lower() == "y":
        result = store.upgrade(status["id"], expected_level=status["level"])
        print(f"{gold(result['cost'])}를 사용해 {result['level']}단계로 확장했습니다.")
        print(f"창고 한도가 {result['capacity']}개로 늘었습니다.")


def play_shop(store, shop_id):
    actions = {
        "2": buy_stock,
        "3": change_price,
        "4": show_day_result,
        "5": show_reports,
        "6": expand_shop,
    }
    announced_goal = False
    while True:
        status = store.status(shop_id)
        print(f"\n=== {status['name']} · {status['day']}일차 ===")
        print(
            f"{gold(status['gold'])} · 상점 {status['level']}단계 · 평판 {status['reputation']}"
            f" · 창고 {status['used']}/{status['capacity']}"
        )
        print(f"오늘의 소식  {status['event']}")
        if status["goal_met"] and not announced_goal:
            print("축하합니다! 상점 3단계와 보유 골드 1,200G 목표를 달성했습니다. 계속 영업할 수 있습니다.")
            announced_goal = True
        print("1. 상품 목록   2. 상품 매입   3. 판매가 변경   4. 오늘 영업하기")
        print("5. 영업 기록   6. 상점 확장   H. 도움말       0. 상점 선택으로")
        choice = input("선택 > ").strip().lower()

        try:
            if choice == "0":
                return
            if choice == "h":
                show_help()
            elif choice == "1":
                show_inventory(store.inventory(shop_id), status["level"])
            elif choice in actions:
                actions[choice](store, status)
            else:
                print("메뉴에 표시된 항목을 선택하세요.")
        except ShopError as error:
            print(f"\n{error}")


def main():
    store = None
    try:
        store = Store()
        while (shop_id := choose_shop(store)) is not None:
            play_shop(store, shop_id)
    except (KeyboardInterrupt, EOFError):
        print()
    except ConfigError as error:
        print(f"\n설정을 확인해 주세요. {error}")
        return 1
    except DBError as error:
        print(f"\nMySQL 연결 또는 저장 작업에 실패했습니다. {error}")
        return 1
    except ShopError as error:
        print(f"\n{error}")
        return 1
    finally:
        if store is not None:
            store.close()

    print("달빛 잡화점의 영업을 마칩니다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
