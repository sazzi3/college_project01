"""Secondary windows for the Tkinter edition of 달빛 잡화점."""

import tkinter as tk
from tkinter import messagebox, ttk

from shop import DBError, GOAL_GOLD, ShopError


PAPER = "#f7efde"
CARDS = "#fff9ed"
INK = "#292a20"
FOREST = "#343e2d"
GOLD = "#875a22"
MUTED = "#625b4d"
FONT = "Malgun Gothic"


def _gold(amount):
    return f"{amount:,} G"


def _window(parent, title, heading, subtitle=None):
    owner = parent.winfo_toplevel()
    window = tk.Toplevel(owner, background=PAPER)
    window.withdraw()
    window.title(title)
    window.transient(owner)
    window.resizable(False, False)
    window.bind("<Escape>", lambda _event: window.destroy())

    style = ttk.Style(window)
    style.configure("ShopDialog.TFrame", background=PAPER)
    style.configure("ShopDialog.TLabel", background=PAPER, foreground=INK, font=(FONT, 10))
    style.configure("Muted.ShopDialog.TLabel", foreground=MUTED)
    style.configure("Heading.ShopDialog.TLabel", font=(FONT, 20, "bold"), foreground=FOREST)
    style.configure("Gold.ShopDialog.TLabel", font=(FONT, 11, "bold"), foreground=GOLD)
    style.configure("Error.ShopDialog.TLabel", foreground="#9a3436")
    style.configure("ShopDialog.TButton", padding=(12, 6), font=(FONT, 10, "bold"))
    style.configure("Primary.ShopDialog.TButton", foreground="#ffffff", background=FOREST)
    style.map("Primary.ShopDialog.TButton", background=[("active", "#4a563d")])
    style.configure("ShopDialog.Treeview", background=CARDS, fieldbackground=CARDS,
                    foreground=INK, borderwidth=0, rowheight=32, font=(FONT, 10))
    style.configure("ShopDialog.Treeview.Heading", background="#eee2c9", foreground=FOREST,
                    relief="flat", font=(FONT, 10, "bold"))

    body = ttk.Frame(window, style="ShopDialog.TFrame", padding=(25, 22, 25, 20))
    body.pack(fill="both", expand=True)
    _label(body, heading, "Heading").pack(anchor="w")
    if subtitle:
        _label(body, subtitle, "Muted").pack(anchor="w", pady=(6, 0))
    return window, body


def _label(parent, text, variant=None):
    style = f"{variant}.ShopDialog.TLabel" if variant else "ShopDialog.TLabel"
    return ttk.Label(parent, text=text, style=style, wraplength=560, justify="left")


def _show(window, focus):
    owner = window.master
    window.update_idletasks()
    width = window.winfo_reqwidth()
    height = window.winfo_reqheight()
    center_x = owner.winfo_rootx() + owner.winfo_width() // 2
    center_y = owner.winfo_rooty() + owner.winfo_height() // 2
    x = max(0, min(center_x - width // 2, window.winfo_screenwidth() - width))
    y = max(0, min(center_y - height // 2, window.winfo_screenheight() - height))
    window.geometry(f"+{x}+{y}")
    window.deiconify()
    window.wait_visibility()
    window.grab_set()
    focus.focus_set()
    window.wait_window()


def _buttons(body):
    bar = ttk.Frame(body, style="ShopDialog.TFrame")
    bar.pack(fill="x", pady=(14, 0))
    return bar


def _close_button(window, body):
    close = ttk.Button(_buttons(body), text="확인", command=window.destroy,
                       style="Primary.ShopDialog.TButton")
    close.pack(side="right")
    window.bind("<Return>", lambda _event: window.destroy())
    return close


def _read_number(parent, *, title, item, details, field, initial, minimum, maximum,
                 submit_label, submit, preview=None):
    window, body = _window(parent, title, item["name"], item["description"])
    _label(body, details).pack(anchor="w", pady=(14, 15))
    _label(body, field).pack(anchor="w", pady=(0, 4))

    value = tk.StringVar(window, value=str(initial))
    entry = ttk.Entry(body, textvariable=value, width=18, font=(FONT, 12))
    entry.pack(anchor="w", ipady=4)
    entry.selection_range(0, "end")

    error_label = _label(body, "", "Error")
    error_label.pack(anchor="w", pady=(6, 0))

    if preview:
        preview_label = _label(body, "", "Gold")
        preview_label.pack(anchor="w", pady=(2, 0))

        def update_preview(*_args):
            try:
                number = int(value.get())
            except ValueError:
                number = 0
            preview_label.configure(text=preview(number) if minimum <= number <= maximum else " ")

        value.trace_add("write", update_preview)
        update_preview()

    result = None
    db_error = None

    def confirm(_event=None):
        nonlocal result, db_error
        try:
            number = int(value.get())
        except ValueError:
            error_label.configure(text="숫자를 입력하세요.")
            return

        if not minimum <= number <= maximum:
            error_label.configure(text=f"{minimum:,}~{maximum:,} 범위로 입력하세요.")
            return

        try:
            result = submit(number)
        except ShopError as error:
            error_label.configure(text=str(error))
            return
        except DBError as error:
            db_error = error
        window.destroy()

    bar = _buttons(body)
    ttk.Button(bar, text=submit_label, command=confirm, style="Primary.ShopDialog.TButton").pack(side="right")
    ttk.Button(bar, text="취소", command=window.destroy,
               style="ShopDialog.TButton").pack(side="right", padx=(0, 7))
    window.bind("<Return>", confirm)
    _show(window, entry)
    if db_error is not None:
        raise db_error
    return result


def buy_dialog(parent, store, status, item):
    """Return the successful purchase message, or None."""
    if item["required_level"] > status["level"]:
        messagebox.showwarning("상품 매입", f"상점 {item['required_level']}단계부터 매입할 수 있습니다.",
                               parent=parent)
        return None

    space = status["capacity"] - status["used"]
    cost = item["cost"]
    maximum = min(item["stock"], space, status["gold"] // cost)
    if maximum <= 0:
        if item["stock"] <= 0:
            reason = "오늘 도매상에 남은 수량을 모두 매입했습니다."
        elif space <= 0:
            reason = "창고가 가득 찼습니다. 영업으로 재고를 줄인 뒤 다시 매입하세요."
        else:
            reason = f"상품 한 개를 매입하려면 {_gold(cost)}가 필요합니다."
        messagebox.showwarning("상품 매입", reason, parent=parent)
        return None

    def submit(quantity):
        purchase = store.buy(status["id"], item["id"], quantity, expected_day=status["day"])
        return f"{purchase['name']} {purchase['quantity']}개를 {_gold(purchase['total'])}에 매입했습니다."

    return _read_number(
        parent, title="상품 매입", item=item,
        details=f"도매가 {_gold(cost)} · 현재 재고 {item['quantity']}개 · 남은 공급 {item['stock']}개",
        field=f"매입 수량 (최대 {maximum}개)", initial=1, minimum=1, maximum=maximum,
        submit_label="매입 확정", submit=submit,
        preview=lambda quantity: (
            f"매입 비용 {_gold(cost * quantity)} · 매입 후 {_gold(status['gold'] - cost * quantity)}"
        ),
    )


def price_dialog(parent, store, status, item):
    """Return the successful price change message, or None."""
    if item["required_level"] > status["level"]:
        messagebox.showwarning("판매가 변경", f"상점 {item['required_level']}단계부터 취급할 수 있습니다.",
                               parent=parent)
        return None

    minimum = item["min_price"]
    maximum = item["reference"] * 3

    def submit(price):
        store.set_price(status["id"], item["id"], price)
        return f"{item['name']}의 판매가를 {_gold(price)}로 변경했습니다."

    return _read_number(
        parent, title="판매가 변경", item=item,
        details=(f"현재 판매가 {_gold(item['price'])} · 기준가 {_gold(item['reference'])}\n"
                 "기준가를 넘길수록 구매를 포기하는 손님이 늘어날 수 있습니다."),
        field=f"새 판매가 ({minimum:,}~{maximum:,} G)", initial=item["price"],
        minimum=minimum, maximum=maximum, submit_label="판매가 저장", submit=submit,
    )


def _table(body, columns, rows):
    names = tuple(column[0] for column in columns)
    table = ttk.Treeview(body, columns=names, show="headings", height=len(rows),
                         selectmode="none", style="ShopDialog.Treeview", takefocus=False)
    for name, width, anchor in columns:
        table.heading(name, text=name, anchor=anchor)
        table.column(name, width=width, anchor=anchor, stretch=False)
    table.tag_configure("alternate", background="#f5ecda")
    for index, row in enumerate(rows):
        table.insert("", "end", values=row, tags=("alternate",) if index % 2 else ())
    table.pack(fill="x", pady=(14, 0))


def sales_dialog(parent, result):
    """Show the outcome of one completed day."""
    window, body = _window(parent, "영업 정산", f"{result['day']}일차 영업 정산", result["event"])
    _label(body, f"방문 {result['customers']}명 · 미구매 {result['missed']}명").pack(anchor="w", pady=(11, 0))

    if result["sales"]:
        rows = [(sale["name"], f"{sale['quantity']}개", _gold(sale["total"])) for sale in result["sales"]]
        _table(body, (("상품", 200, "w"), ("판매 수량", 104, "center"), ("매출", 116, "e")), rows)
    else:
        _label(body, "오늘 판매된 상품이 없습니다.", "Muted").pack(anchor="w", pady=(14, 0))

    _label(body, f"매출 {_gold(result['revenue'])} · 판매 원가 {_gold(result['cost'])}").pack(anchor="w", pady=(14, 3))
    _label(body, f"매출총이익 {_gold(result['profit'])}", "Gold").pack(anchor="w")
    _show(window, _close_button(window, body))


def reports_dialog(parent, reports):
    """Show the most recent seven completed days."""
    window, body = _window(parent, "영업 기록", "최근 7일 영업 기록")
    if reports:
        rows = [(f"{row['day']}일차", _gold(row["revenue"]), _gold(row["cost"]), _gold(row["profit"]),
                 f"{row['customers']}명", f"{row['missed']}명") for row in reports]
        _table(body, (("날짜", 78, "w"), ("매출", 94, "e"), ("판매 원가", 100, "e"),
                      ("매출총이익", 106, "e"), ("방문", 68, "center"), ("미구매", 68, "center")), rows)
    else:
        _label(body, "첫 영업을 마치면 정산 내역을 확인할 수 있습니다.", "Muted").pack(anchor="w", pady=(10, 0))
    _show(window, _close_button(window, body))


def help_dialog(parent, guest=False):
    """Explain the shop loop and winning conditions."""
    window, body = _window(parent, "도움말", "길드 보급 담당자 안내서")
    instructions = (
        ("시장 소식 확인", "도매가와 공급량, 인기 상품이 날마다 달라집니다."),
        ("상품 매입과 가격 설정", "도매상에서 상품을 사고 판매가를 정하세요. 기준가를 참고하면 적정 가격을 잡기 쉽습니다."),
        ("영업과 정산", "영업을 시작하면 손님이 찾아옵니다. 매출과 이익을 정산하고 다음 날로 넘어갑니다."),
        ("상점 확장", "영업으로 얻은 골드와 평판으로 상점을 확장하면 더 많은 상품을 보관하고 판매할 수 있습니다."),
    )
    for title, description in instructions:
        _label(body, title, "Gold").pack(anchor="w", pady=(12, 1))
        _label(body, description).pack(anchor="w")
    _label(body, f"목표는 상점 3단계와 보유 골드 {_gold(GOAL_GOLD)}입니다.\n"
                 + ("체험 모드에서는 실행 중에만 기록이 유지되며, 종료하면 삭제됩니다."
                    if guest else "매입, 가격 변경, 영업, 확장은 완료할 때마다 MySQL에 저장됩니다."),
                 "Muted").pack(anchor="w", pady=(13, 0))
    _show(window, _close_button(window, body))
