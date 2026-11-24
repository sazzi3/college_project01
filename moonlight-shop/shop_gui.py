"""Windows desktop interface for 달빛 잡화점."""

import os
from pathlib import Path
import tkinter as tk
from tkinter import font, messagebox, ttk
from contextlib import suppress

from shop import ConfigError, DBError, ShopError, Store
from shop_dialogs import buy_dialog, help_dialog, price_dialog, reports_dialog, sales_dialog


ROOT = Path(__file__).resolve().parent
TITLE = "달빛 잡화점"
PARCHMENT = "#e8ddc7"
PAPER = "#f7efde"
WHITE = "#fff9ed"
INK = "#292a20"
MUTED = "#625b4d"
FOREST = "#343e2d"
DEEP_FOREST = "#242b21"
GOLD = "#875a22"
PALE_GOLD = "#efd29c"
LINE = "#cdbb9c"
ERROR = "#9a343c"
FONT = "Malgun Gothic"


def coins(amount):
    return f"{amount:,} G"


def label(parent, text="", *, size=10, weight="normal", fg=INK, bg=WHITE, **kwargs):
    return tk.Label(parent, text=text, font=(FONT, size, weight), fg=fg, bg=bg, **kwargs)


def frame(parent, bg=WHITE, *, border=False, **kwargs):
    return tk.Frame(parent, bg=bg, highlightthickness=int(border),
                    highlightbackground=LINE, **kwargs)


class ShopApp:
    def __init__(self, root, store=None):
        self.root = root
        self.store = store
        self.shop_id = None
        self.images = {}
        self.notice = tk.StringVar(master=root)
        self.connection_vars = {
            key: tk.StringVar(master=root, value=os.getenv(f"MYSQL_{key.upper()}", default))
            for key, default in {
                "host": "127.0.0.1", "port": "3306", "user": "root",
                "password": "", "database": "fantasy_shop",
            }.items()
        }

        root.title(TITLE)
        root.configure(bg=PARCHMENT)
        if os.name == "nt":
            with suppress(tk.TclError):
                root.iconbitmap(default=ROOT / "assets" / "guild.ico")
        width = min(1220, root.winfo_screenwidth() - 48)
        height = min(790, root.winfo_screenheight() - 90)
        root.geometry(f"{width}x{height}+{(root.winfo_screenwidth() - width) // 2}+32")
        root.minsize(min(1000, width), min(670, height))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.configure_theme()
        if store is None:
            self.show_login()
        else:
            self.show_saves()

    def configure_theme(self):
        default_font = font.nametofont("TkDefaultFont", root=self.root)
        default_font.configure(family=FONT, size=10)
        font.nametofont("TkTextFont", root=self.root).configure(family=FONT, size=10)
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Shop.TButton", font=(FONT, 10, "bold"), padding=(12, 7),
                        background=PAPER, foreground=FOREST, bordercolor=LINE)
        style.map("Shop.TButton", background=[("pressed", "#e3d4b5"), ("active", "#eee0c4")],
                  foreground=[("disabled", "#847969")])
        style.configure("Accent.TButton", font=(FONT, 10, "bold"), padding=(14, 8),
                        background=FOREST, foreground=WHITE, bordercolor=FOREST)
        style.map("Accent.TButton", background=[("disabled", "#e3dbc8"),
                                               ("pressed", "#283020"), ("active", "#4a563d")],
                  foreground=[("disabled", "#79736a")])
        style.configure("Header.TButton", font=(FONT, 9, "bold"), padding=(11, 6),
                        background=DEEP_FOREST, foreground="#fff2dc", bordercolor="#636b51")
        style.map("Header.TButton", background=[("active", FOREST), ("pressed", "#454e38")])
        style.configure("Shop.TEntry", padding=(8, 5), fieldbackground=WHITE, foreground=INK,
                        bordercolor=LINE)
        style.configure("Shop.Treeview", background=WHITE, fieldbackground=WHITE, foreground=INK,
                        borderwidth=0, font=(FONT, 10), rowheight=max(36, default_font.metrics("linespace") + 15))
        style.map("Shop.Treeview", background=[("selected", "#e4d2a8")],
                  foreground=[("selected", "#382a16")])
        style.configure("Shop.Treeview.Heading", background="#eee2c9", foreground=FOREST,
                        borderwidth=0, font=(FONT, 9, "bold"), padding=(6, 7))
        style.map("Shop.Treeview.Heading", background=[("active", "#eee2c9")])

    def reset_view(self):
        for widget in self.root.winfo_children():
            widget.destroy()
        self.notice.set("")

    def header(self, actions):
        bar = frame(self.root, DEEP_FOREST, padx=24, pady=9)
        bar.pack(fill="x")
        emblem = tk.Canvas(bar, width=25, height=24, highlightthickness=0, bg=DEEP_FOREST)
        emblem.create_oval(2, 3, 19, 20, outline="", fill=PALE_GOLD)
        emblem.create_oval(8, 0, 23, 15, outline="", fill=DEEP_FOREST)
        emblem.create_oval(20, 6, 23, 9, outline="", fill=PALE_GOLD)
        emblem.pack(side="left", padx=(0, 6))
        label(bar, TITLE, size=15, weight="bold", fg="#fff4e2", bg=DEEP_FOREST).pack(side="left")
        label(bar, "길드 보급소", size=9, fg=PALE_GOLD, bg=DEEP_FOREST).pack(side="left", padx=(12, 0))
        for title, callback in reversed(actions):
            ttk.Button(bar, text=title, command=callback, style="Header.TButton").pack(side="right", padx=(8, 0))

    def artwork(self, parent, kind):
        width, height, left, top = {
            "cover": (416, 328, 200, 0),
            "banner": (448, 136, 96, 490),
        }[kind]
        if kind not in self.images:
            try:
                if "original" not in self.images:
                    self.images["original"] = tk.PhotoImage(
                        master=self.root, file=ROOT / "assets" / "shop-illustration.png"
                    )
                crop = tk.PhotoImage(master=self.root, width=width, height=height)
                self.root.tk.call(crop, "copy", self.images["original"], "-from", left, top,
                                  left + width * 3, top + height * 3, "-subsample", 3, 3)
                self.images[kind] = crop
            except tk.TclError:
                self.images[kind] = None
        if self.images[kind] is not None:
            return label(parent, bg=FOREST, image=self.images[kind], borderwidth=0)

        canvas = tk.Canvas(parent, width=width, height=height, bg=FOREST, highlightthickness=0)
        x, y = width // 2, height // 2
        canvas.create_oval(x - 31, y - 31, x + 31, y + 31, outline="", fill=PALE_GOLD)
        canvas.create_oval(x - 12, y - 43, x + 42, y + 12, outline="", fill=FOREST)
        return canvas

    def start_panel(self, title, subtitle):
        outer = frame(self.root, PARCHMENT, padx=30, pady=24)
        outer.pack(fill="both", expand=True)
        panel = frame(outer, border=True, padx=27, pady=24)
        panel.pack(fill="x", expand=True, anchor="center")
        panel.grid_columnconfigure(0, weight=1)
        content = frame(panel)
        content.grid(row=0, column=0, sticky="nsew", padx=(0, 28))
        self.artwork(panel, "cover").grid(row=0, column=1, sticky="e")
        label(content, title, size=24, weight="bold", fg=FOREST).pack(anchor="w")
        label(content, subtitle, fg=MUTED, wraplength=480, justify="left").pack(anchor="w", pady=(2, 16))
        return content

    def show_login(self, error=""):
        self.reset_view()
        self.header([("도움말", lambda: help_dialog(self.root))])
        content = self.start_panel("MySQL 연결", "서버에 연결하면 상점을 새로 열거나 저장한 게임을 이어갈 수 있습니다.")
        settings = frame(content)
        settings.pack(fill="x")
        settings.grid_columnconfigure(0, weight=3, uniform="fields")
        settings.grid_columnconfigure(1, weight=2, uniform="fields")
        fields = (
            ("서버 주소", "host", 0, 0), ("포트", "port", 0, 1),
            ("사용자", "user", 1, 0), ("데이터베이스", "database", 1, 1),
            ("비밀번호", "password", 2, 0),
        )
        for title, key, row, column in fields:
            group = frame(settings)
            group.grid(row=row, column=column, columnspan=2 if key == "password" else 1,
                       sticky="ew", padx=(0, 12) if column == 0 and key != "password" else 0,
                       pady=(0, 8))
            label(group, title, size=9, weight="bold", fg=FOREST).pack(anchor="w")
            entry = ttk.Entry(group, textvariable=self.connection_vars[key], style="Shop.TEntry",
                              show="*" if key == "password" else "")
            entry.pack(fill="x", pady=(3, 0))
            entry.bind("<Return>", lambda _event: self.connect())
            if key == "password":
                entry.focus_set()

        self.error_text = tk.StringVar(master=self.root, value=error)
        label(content, textvariable=self.error_text, fg=ERROR, wraplength=470,
              justify="left", anchor="w").pack(fill="x", pady=(3, 3))
        actions = frame(content)
        actions.pack(fill="x")
        ttk.Button(actions, text="연결하기", command=self.connect, style="Accent.TButton").pack(side="left")
        self.init_button = ttk.Button(actions, text="데이터베이스 초기화", command=self.initialize_database,
                                      style="Shop.TButton")

    def settings(self):
        settings = {key: value.get() for key, value in self.connection_vars.items()}
        for key in ("host", "user", "database"):
            settings[key] = settings[key].strip()
            if not settings[key]:
                raise ConfigError("서버 주소, 사용자, 데이터베이스를 모두 입력하세요.")
        try:
            settings["port"] = int(settings["port"])
        except ValueError as exc:
            raise ConfigError("포트 번호를 숫자로 입력하세요.") from exc
        if not 1 <= settings["port"] <= 65535:
            raise ConfigError("포트 번호는 1부터 65535까지 입력할 수 있습니다.")
        return {**settings, "charset": "utf8mb4", "connection_timeout": 5}

    def connect(self):
        self.init_button.pack_forget()
        self.error_text.set("")
        opened = None
        try:
            settings = self.settings()
            self.root.configure(cursor="watch")
            self.root.update_idletasks()
            opened = Store(settings)
            shops = opened.list_shops()
        except ConfigError as exc:
            self.error_text.set(str(exc))
            return
        except DBError as exc:
            if opened is not None:
                opened.close()
            if exc.errno in (1049, 1146) and settings["database"] == "fantasy_shop":
                self.error_text.set("게임 테이블이 없습니다. MySQL 관리자 계정으로 초기화할 수 있습니다.")
                self.init_button.pack(side="left", padx=(8, 0))
            elif exc.errno in (1044, 1045):
                self.error_text.set("MySQL 사용자, 비밀번호 또는 데이터베이스 접근 권한을 확인하세요.")
            else:
                self.error_text.set(f"MySQL 연결에 실패했습니다. 서버가 실행 중인지 확인하세요. ({exc})")
            return
        finally:
            self.root.configure(cursor="")
        self.store = opened
        self.show_saves(shops)

    def initialize_database(self):
        if not messagebox.askyesno("데이터베이스 초기화", "MySQL에 게임용 테이블을 만들까요?",
                                   parent=self.root):
            return
        try:
            settings = self.settings()
            if settings["database"] != "fantasy_shop":
                raise ConfigError("초기화할 데이터베이스 이름을 fantasy_shop으로 입력하세요.")
            schema = (ROOT / "schema.sql").read_text(encoding="utf-8")
            self.root.configure(cursor="watch")
            self.root.update_idletasks()
            Store.initialize_database(settings, schema)
        except (ConfigError, DBError, OSError) as exc:
            self.error_text.set(f"초기화에 실패했습니다. MySQL 관리자 권한과 설정을 확인하세요. ({exc})")
            return
        finally:
            self.root.configure(cursor="")
        self.connect()

    def show_saves(self, shops=None):
        if shops is None:
            try:
                shops = self.store.list_shops()
            except DBError as exc:
                self.disconnect(f"MySQL에 다시 연결해 주세요. ({exc})")
                return
        self.reset_view()
        self.shop_id = None
        self.header([("도움말", lambda: help_dialog(self.root)), ("연결 설정", self.disconnect)])
        content = self.start_panel("보급 기록 선택", "기존 보급소 장부를 펼치거나 새 상점의 첫 장을 기록하세요.")
        table_frame = frame(content)
        table_frame.pack(fill="x")
        self.save_table = ttk.Treeview(table_frame, columns=("name", "day", "gold"), show="headings",
                                       height=5, selectmode="browse", style="Shop.Treeview")
        self.setup_columns(self.save_table, (
            ("name", "상점", 150, "w"), ("day", "영업일", 73, "center"), ("gold", "보유 골드", 92, "e"),
        ))
        for shop in shops:
            self.save_table.insert("", "end", iid=str(shop["id"]),
                                   values=(shop["name"], f"{shop['day']}일차", coins(shop["gold"])))
        self.add_scrollbar(self.save_table)
        open_button = ttk.Button(content, text="불러오기", command=self.open_saved, style="Shop.TButton")
        open_button.pack(anchor="e", pady=(7, 10))
        if shops:
            self.save_table.selection_set(str(shops[0]["id"]))
        else:
            open_button.state(["disabled"])
        self.save_table.bind("<Double-1>", lambda event: self.open_saved()
                             if self.save_table.identify_row(event.y) else None)
        self.save_table.bind("<Return>", lambda _event: self.open_saved())

        self.name_var = tk.StringVar(master=self.root)
        add = frame(content)
        add.pack(fill="x")
        label(add, "새 상점 이름", size=9, weight="bold", fg=FOREST).pack(anchor="w", pady=(0, 4))
        entry = ttk.Entry(add, textvariable=self.name_var, style="Shop.TEntry")
        entry.pack(side="left", fill="x", expand=True)
        entry.bind("<Return>", lambda _event: self.create_shop())
        ttk.Button(add, text="새 상점 열기", command=self.create_shop, style="Accent.TButton").pack(side="left", padx=(8, 0))
        label(content, textvariable=self.notice, fg=ERROR, anchor="w").pack(fill="x", pady=(6, 0))
        if not shops:
            entry.focus_set()

    def open_saved(self):
        selected = self.save_table.selection()
        if selected:
            self.try_action(lambda: self.show_shop(int(selected[0])))

    def create_shop(self):
        try:
            shop_id = self.store.create_shop(self.name_var.get())
        except (ShopError, DBError) as exc:
            self.notice.set(str(exc))
        else:
            self.try_action(lambda: self.show_shop(shop_id))

    def show_shop(self, shop_id):
        status = self.store.status(shop_id)
        products = self.store.inventory(shop_id)
        self.reset_view()
        self.shop_id = shop_id
        self.header([
            ("영업 기록", self.show_reports),
            ("도움말", lambda: help_dialog(self.root)),
            ("상점 선택", self.show_saves),
        ])
        page = frame(self.root, PARCHMENT, padx=24, pady=16)
        page.pack(fill="both", expand=True)
        hero = frame(page, FOREST)
        hero.pack(fill="x", pady=(0, 12))
        hero.grid_columnconfigure(0, weight=1)
        self.artwork(hero, "banner").grid(row=0, column=1, sticky="e")
        frame(hero, "#a98042", height=2).grid(row=1, column=0, columnspan=2, sticky="ew")
        hero_text = frame(hero, FOREST, padx=20, pady=12)
        hero_text.grid(row=0, column=0, sticky="w")
        self.day_text = tk.StringVar(master=self.root)
        self.shop_text = tk.StringVar(master=self.root)
        self.event_text = tk.StringVar(master=self.root)
        label(hero_text, textvariable=self.day_text, size=10, weight="bold",
              bg=FOREST, fg=PALE_GOLD).pack(anchor="w")
        label(hero_text, textvariable=self.shop_text, size=24, weight="bold",
              bg=FOREST, fg=WHITE).pack(anchor="w")
        event_label = label(hero_text, textvariable=self.event_text, size=9, bg=FOREST,
                            fg="#f3ebd6", justify="left")
        event_label.pack(anchor="w", pady=(4, 0))
        hero.bind("<Configure>", lambda event: event_label.configure(wraplength=max(250, event.width - 492)))

        metrics = frame(page, PARCHMENT)
        metrics.pack(fill="x", pady=(0, 12))
        self.metric_values = {}
        for index, (key, title) in enumerate((
            ("gold", "보유 골드"), ("level", "상점 단계"), ("reputation", "평판"), ("used", "창고"),
        )):
            metrics.grid_columnconfigure(index, weight=1, uniform="metrics")
            card = frame(metrics, border=True, padx=12, pady=7)
            card.grid(row=0, column=index, sticky="ew", padx=(0, 9 if index < 3 else 0))
            value = tk.StringVar(master=self.root)
            self.metric_values[key] = value
            label(card, title, size=9, fg=MUTED).pack(anchor="w")
            label(card, textvariable=value, size=16, weight="bold", fg=GOLD if key == "gold" else FOREST).pack(anchor="w")

        content = frame(page, PARCHMENT)
        content.pack(fill="both", expand=True)
        content.grid_columnconfigure(0, weight=1)
        content.grid_rowconfigure(0, weight=1)
        self.build_inventory(content)
        self.build_detail(content)
        footer = frame(page, PARCHMENT)
        footer.pack(fill="x", pady=(12, 0))
        label(footer, textvariable=self.notice, bg=PARCHMENT, fg=FOREST, size=9,
              wraplength=520, justify="left").pack(side="left")
        ttk.Button(footer, text="오늘 영업하기", command=self.run_day,
                   style="Accent.TButton").pack(side="right")
        self.upgrade_button = ttk.Button(footer, text="상점 확장", command=self.upgrade,
                                         style="Shop.TButton")
        self.upgrade_button.pack(side="right", padx=(0, 8))
        self.apply_shop_data(status, products)

    def build_inventory(self, parent):
        panel = frame(parent, border=True, padx=13, pady=9)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        label(panel, "보급품 장부", size=15, weight="bold", fg=FOREST).pack(anchor="w", pady=(0, 7))
        table_frame = frame(panel)
        table_frame.pack(fill="both", expand=True)
        self.table = ttk.Treeview(table_frame, columns=("name", "quantity", "cost", "price", "stock"),
                                  show="headings", height=7, selectmode="browse", style="Shop.Treeview")
        self.setup_columns(self.table, (
            ("name", "상품", 142, "w"), ("quantity", "보유", 52, "center"),
            ("cost", "도매가", 65, "e"), ("price", "판매가", 74, "e"),
            ("stock", "공급", 55, "center"),
        ), stretch_all=True)
        self.table.tag_configure("alternate", background="#f5ecda")
        self.table.tag_configure("locked", foreground="#776f62")
        self.add_scrollbar(self.table)
        self.table.bind("<<TreeviewSelect>>", lambda _event: self.update_detail())

    def build_detail(self, parent):
        detail = frame(parent, border=True, padx=14, pady=11, width=260)
        detail.grid(row=0, column=1, sticky="ns")
        detail.pack_propagate(False)
        label(detail, "보급 창구", size=9, weight="bold", fg=GOLD).pack(anchor="w")
        self.item_name = tk.StringVar(master=self.root)
        self.item_description = tk.StringVar(master=self.root)
        self.item_info = tk.StringVar(master=self.root)
        label(detail, textvariable=self.item_name, size=16, weight="bold", fg=FOREST).pack(anchor="w")
        label(detail, textvariable=self.item_description, fg=MUTED, wraplength=225,
              justify="left").pack(anchor="w", pady=(4, 8))
        label(detail, textvariable=self.item_info, wraplength=225, justify="left").pack(anchor="w", pady=(0, 8))
        self.price_button = ttk.Button(detail, text="판매가 변경", command=self.price_selected, style="Shop.TButton")
        self.price_button.pack(side="bottom", fill="x")
        self.buy_button = ttk.Button(detail, text="상품 매입", command=self.buy_selected, style="Accent.TButton")
        self.buy_button.pack(side="bottom", fill="x", pady=(0, 6))

    @staticmethod
    def setup_columns(table, columns, *, stretch_all=False):
        for position, (key, title, width, anchor) in enumerate(columns):
            table.heading(key, text=title, anchor=anchor)
            table.column(key, width=width, minwidth=width if position else 108,
                         stretch=stretch_all or position == 0, anchor=anchor)

    @staticmethod
    def add_scrollbar(table):
        scrollbar = ttk.Scrollbar(table.master, orient="vertical", command=table.yview)
        table.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        table.pack(side="left", fill="both", expand=True)

    def refresh(self, notice=""):
        self.apply_shop_data(self.store.status(self.shop_id), self.store.inventory(self.shop_id), notice)

    def apply_shop_data(self, status, products, notice=""):
        self.status = status
        self.items = {str(product["id"]): product for product in products}
        self.day_text.set(f"{status['day']}일차 · 길드 공지")
        self.shop_text.set(status["name"])
        self.event_text.set(status["event"])
        self.metric_values["gold"].set(coins(status["gold"]))
        self.metric_values["level"].set(f"{status['level']} / 3")
        self.metric_values["reputation"].set(str(status["reputation"]))
        self.metric_values["used"].set(f"{status['used']} / {status['capacity']}개")
        self.upgrade_button.state(["disabled" if status["upgrade_cost"] is None else "!disabled"])
        if status["goal_met"]:
            self.notice.set(f"목표 달성 · {notice or '계속 영업할 수 있습니다.'}")
        else:
            self.notice.set(notice or "운영 목표 · 상점 3단계 / 보유 1,200 G")

        selection = self.table.selection()
        self.table.delete(*self.table.get_children())
        for index, (key, item) in enumerate(self.items.items()):
            tags = ["alternate"] if index % 2 else []
            if item["required_level"] > status["level"]:
                tags.append("locked")
                values = (f"{item['name']} · {item['required_level']}단계", "—", "—", "—", "—")
            else:
                values = (item["name"], item["quantity"], coins(item["cost"]),
                          coins(item["price"]), item["stock"])
            self.table.insert("", "end", iid=key, values=values, tags=tags)
        selected = selection[0] if selection and selection[0] in self.items else next(iter(self.items), None)
        if selected is not None:
            self.table.selection_set(selected)
            self.table.focus(selected)
            self.table.see(selected)
        self.update_detail()

    def selected_item(self):
        selected = self.table.selection()
        return self.items.get(selected[0]) if selected else None

    def update_detail(self):
        item = self.selected_item()
        if item is None:
            self.item_name.set("상품을 선택하세요")
            self.item_description.set("")
            self.item_info.set("")
            self.price_button.state(["disabled"])
            self.buy_button.state(["disabled"])
            return
        self.item_name.set(item["name"])
        self.item_description.set(item["description"])
        if item["required_level"] > self.status["level"]:
            self.item_info.set(f"상점을 {item['required_level']}단계로 확장하면 취급할 수 있습니다.")
            self.price_button.state(["disabled"])
            self.buy_button.state(["disabled"])
            return
        self.price_button.state(["!disabled"])
        available = min(item["stock"], self.status["gold"] // item["cost"],
                        self.status["capacity"] - self.status["used"])
        self.item_info.set(
            f"기준 판매가  {coins(item['reference'])}\n"
            f"현재 매입 가능  {available}개"
        )
        self.buy_button.state(["!disabled" if available > 0 else "disabled"])
        if available == 0:
            reason = "오늘 공급량을 모두 매입했습니다." if item["stock"] == 0 else "골드 또는 창고 공간이 부족합니다."
            self.item_info.set(f"{self.item_info.get()}\n{reason}")

    def try_action(self, action):
        try:
            action()
        except (ConfigError, ShopError, DBError) as exc:
            messagebox.showerror(TITLE, str(exc), parent=self.root)

    def buy_selected(self):
        self.change_item(buy_dialog)

    def price_selected(self):
        self.change_item(price_dialog)

    def change_item(self, dialog):
        item = self.selected_item()
        if item is None:
            return

        def change():
            notice = dialog(self.root, self.store, self.status, item)
            if notice:
                self.refresh(notice)

        self.try_action(change)

    def run_day(self):
        def sell():
            result = self.store.close_day(self.shop_id, expected_day=self.status["day"])
            self.refresh(f"{result['day']}일차 매출 {coins(result['revenue'])} · 총이익 {coins(result['profit'])}")
            sales_dialog(self.root, result)

        self.try_action(sell)

    def show_reports(self):
        self.try_action(lambda: reports_dialog(self.root, self.store.reports(self.shop_id)))

    def upgrade(self):
        status = self.status
        cost = status["upgrade_cost"]
        reputation = status["upgrade_requirement"]
        if cost is None:
            return
        needed = cost + status["reserve"]
        details = f"확장비 {coins(cost)} · 필요 평판 {reputation}\n"
        details += f"운영 자금 {coins(status['reserve'])}를 남겨야 합니다. (필요 골드 {coins(needed)})"
        if status["gold"] < needed or status["reputation"] < reputation:
            messagebox.showinfo("상점 확장 조건", details, parent=self.root)
            return
        if messagebox.askyesno("상점 확장", f"{status['level'] + 1}단계로 확장할까요?\n\n{details}",
                               parent=self.root):
            def expand():
                result = self.store.upgrade(self.shop_id, expected_level=status["level"])
                self.refresh(f"상점 {result['level']}단계로 확장 · 창고 {result['capacity']}개")

            self.try_action(expand)

    def disconnect(self, error=""):
        if self.store is not None:
            self.store.close()
            self.store = None
        self.show_login(error)

    def close(self):
        if self.store is not None:
            self.store.close()
            self.store = None
        self.root.destroy()


def main():
    root = tk.Tk()
    ShopApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
