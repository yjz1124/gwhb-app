# -*- coding: utf-8 -*-
"""
港湾汉堡 · 手机打印 App（Kivy 瘦客户端）
=========================================
设计思路：App 只做「显示 + 转发打印」，真实数据与打印引擎都在电脑端
（mobile_server.py）。所以手机和电脑天然同步——电脑上有什么单，手机上就有什么单。

功能：
  · 一键自动搜索电脑（UDP 广播，免手工填 IP）；也可手动输入 电脑IP:端口
  · 今日/历史订单列表（预订单橙色标记、菜品/规格/备注/电话/取餐时间）
  · 勾选订单 → 完整小票（逐单）/ 仅菜品厨房联（合并一张）/ 原材料汇总（合并一张）
  · 20 秒自动刷新，勾选状态保留

打包 APK：见同目录《打包说明.md》   桌面调试：python main.py
"""
import json
import os
import socket
import threading
import time
import urllib.parse
import urllib.request

from kivy.app import App
from kivy.clock import Clock
from kivy.core.text import LabelBase
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.checkbox import CheckBox
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput

FONT = None
ORANGE = (1, 0.42, 0.21, 1)
DARKORANGE = (0.85, 0.35, 0.06, 1)
BLUE = (0.05, 0.65, 0.91, 1)
GREY = (0.42, 0.45, 0.50, 1)
RED = (0.86, 0.15, 0.15, 1)
WHITE = (1, 1, 1, 1)
FONT_CANDIDATES = [
    "/system/fonts/NotoSansCJK-Regular.ttc",
    "/system/fonts/DroidSansFallbackFull.ttf",
    "/system/fonts/DroidSansFallback.ttf",
    "/system/fonts/NotoSansSC-Regular.otf",
]


def register_font():
    """注册中文字体：优先用随包字体 font.ttf，其次安卓系统字体，最后 Windows 字体（桌面调试）"""
    global FONT
    here = os.path.dirname(os.path.abspath(__file__))
    cands = [os.path.join(here, "font.ttf")] + FONT_CANDIDATES + [
        r"C:\Windows\Fonts\simhei.ttf", r"C:\Windows\Fonts\Deng.ttf",
        r"C:\Windows\Fonts\msyh.ttc"]
    for p in cands:
        try:
            if p and os.path.exists(p):
                LabelBase.register(name="cn", fn_regular=p)
                FONT = "cn"
                return
        except Exception:
            continue


def L(text="", **kw):
    """统一使用中文字体的 Label"""
    kw.setdefault("font_size", "15sp")
    if FONT:
        kw["font_name"] = FONT
    return Label(text=text, **kw)


def B(text="", **kw):
    kw.setdefault("font_size", "15sp")
    if FONT:
        kw["font_name"] = FONT
    return Button(text=text, **kw)


class Api:
    """与电脑端 HTTP 接口通信（纯标准库 urllib，打包无额外依赖）"""

    def __init__(self):
        self.base = ""      # 形如 http://192.168.1.13:8779

    def set_base(self, addr):
        addr = (addr or "").strip().replace("http://", "").replace("https://", "").strip("/")
        if not addr:
            self.base = ""
            return
        if ":" not in addr:
            addr += ":8779"
        self.base = "http://" + addr

    def _get(self, path, timeout=8):
        req = urllib.request.Request(self.base + path)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def _post(self, path, payload, timeout=120):
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base + path, data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))

    def ping(self):
        return self._get("/api/ping", timeout=5)

    def orders(self, date8):
        return self._get("/api/orders?date=" + date8)

    def print_orders(self, mode, ids):
        return self._post("/api/print", {"mode": mode, "order_ids": ids})


def discover(timeout=2.5):
    """UDP 广播搜索电脑端服务，返回候选地址列表（可能多张网卡）
    例: ['192.168.1.13:8779', '172.17.112.1:8779']
    """
    sk = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sk.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sk.settimeout(timeout)
    hits = []
    try:
        targets = ["255.255.255.255"]
        try:
            host_ip = socket.gethostbyname(socket.gethostname())
            if host_ip.count(".") == 3:
                targets.append(host_ip.rsplit(".", 1)[0] + ".255")
        except Exception:
            pass
        for t in targets:
            try:
                sk.sendto(b"GWHB_DISCOVER", (t, 8778))
            except Exception:
                continue
        end = time.time() + timeout
        while time.time() < end:
            try:
                data, addr = sk.recvfrom(1024)
                info = json.loads(data.decode("utf-8"))
                if info.get("app") != "gwhb-burger":
                    continue
                port = info.get("port", 8779)
                for ip in [addr[0]] + list(info.get("ips") or []):
                    cand = f"{ip}:{port}"
                    if cand not in hits:
                        hits.append(cand)
            except socket.timeout:
                break
            except Exception:
                continue
    finally:
        sk.close()
    # 优先常见内网段（192.168 / 10. / 100. Tailscale），虚拟网卡段往后排
    def rank(a):
        ip = a.split(":")[0]
        if ip.startswith("192.168.") or ip.startswith("10."):
            return 0
        if ip.startswith("100."):
            return 1
        return 2
    return sorted(hits, key=rank)


def probe_first_ok(cands, timeout=3):
    """依次探测候选地址，返回第一个能连上的"""
    for c in cands:
        try:
            base = "http://" + c
            req = urllib.request.Request(base + "/api/ping")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                if json.loads(r.read().decode("utf-8")).get("app") == "gwhb-burger":
                    return c
        except Exception:
            continue
    return None


class OrderRow(BoxLayout):
    """一行订单：勾选框 + 订单信息"""

    def __init__(self, order, checked, on_toggle, **kw):
        super().__init__(orientation="horizontal", size_hint_y=None, **kw)
        self.order = order
        self.height = dp(96)
        self.padding = (dp(6), dp(6))
        self.spacing = dp(6)
        self.on_toggle = on_toggle

        self.cb = CheckBox(size_hint_x=None, width=dp(34), active=checked)
        self.cb.bind(active=self._toggled)
        self.add_widget(self.cb)

        right = BoxLayout(orientation="vertical", spacing=dp(2))
        top = BoxLayout(orientation="horizontal", size_hint_y=None, height=dp(26), spacing=dp(6))
        top.add_widget(L(text=str(order.get("order_no", "-")), bold=True, font_size="18sp",
                         size_hint_x=None, width=dp(64), color=(0.1, 0.1, 0.1, 1)))
        pre = order.get("type") == "预订单"
        top.add_widget(L(text=order.get("type", ""), font_size="12sp", size_hint_x=None,
                         width=dp(58), color=(ORANGE if pre else GREY)))
        top.add_widget(L(text="￥" + str(order.get("amount", "")), font_size="16sp", bold=True,
                         color=RED))
        right.add_widget(top)

        right.add_widget(L(text=f"🕒 {order.get('time','')}    📞 {order.get('phone','-')}",
                           font_size="12sp", color=GREY,
                           size_hint_y=None, height=dp(20)))
        if order.get("pickup_time"):
            right.add_widget(L(text="⏰ 取餐 " + str(order["pickup_time"]), font_size="12sp",
                               color=ORANGE, size_hint_y=None, height=dp(20)))
        items = []
        for it in order.get("items", []):
            s = f"{it.get('name','')} x{it.get('qty',1)}"
            if it.get("spec"):
                s += f" ｜{it['spec']}"
            if it.get("specs"):
                s += "  └ " + "、".join(it["specs"])
            items.append(s)
        right.add_widget(L(text="\n".join(items) or "（无明细）", font_size="12sp",
                           size_hint_y=None, height=dp(20) * max(1, len(items)),
                           color=(0.2, 0.2, 0.2, 1)))
        self.add_widget(right)

    def _toggled(self, _, val):
        self.on_toggle(self.order.get("id"), val)

    def set_checked(self, val):
        self.cb.active = val


class Root(BoxLayout):
    def __init__(self, **kw):
        super().__init__(orientation="vertical", **kw)
        self.api = Api()
        self.checked = []           # 勾选先后顺序
        self.rows = {}
        self.orders = []
        self.date8 = time.strftime("%Y%m%d")
        self.cfg_path = os.path.join(App.get_running_app().user_data_dir, "config.json")

        # ---------- 顶栏 ----------
        bar = BoxLayout(size_hint_y=None, height=dp(46), padding=(dp(8), dp(4)), spacing=dp(6))
        with bar.canvas.before:
            Color(*ORANGE)
            self._bar_rect = Rectangle(pos=bar.pos, size=bar.size)
        bar.bind(pos=self._sync_rect, size=self._sync_rect)
        self.status = L(text="正在查找电脑…", color=WHITE, bold=True)
        bar.add_widget(self.status)
        bar.add_widget(B(text="⚙", size_hint_x=None, width=dp(44),
                         background_color=DARKORANGE, on_release=lambda *_: self.open_settings()))
        self.add_widget(bar)

        # ---------- 日期 + 刷新 ----------
        datebar = BoxLayout(size_hint_y=None, height=dp(40), padding=(dp(8), dp(2)), spacing=dp(6))
        datebar.add_widget(B(text="‹ 前一天", size_hint_x=None, width=dp(84),
                             background_color=GREY, on_release=lambda *_: self.shift_day(-1)))
        self.date_lb = L(text="", bold=True)
        datebar.add_widget(self.date_lb)
        datebar.add_widget(B(text="后一天 ›", size_hint_x=None, width=dp(84),
                             background_color=GREY, on_release=lambda *_: self.shift_day(1)))
        datebar.add_widget(B(text="⟳", size_hint_x=None, width=dp(46),
                             background_color=BLUE, on_release=lambda *_: self.reload()))
        self.add_widget(datebar)

        self.summary = L(text="", size_hint_y=None, height=dp(24), font_size="13sp", color=GREY)
        self.add_widget(self.summary)

        # ---------- 订单列表 ----------
        self.sv = ScrollView()
        self.list_box = GridLayout(cols=1, spacing=dp(4), size_hint_y=None, padding=(dp(6), dp(2)))
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        self.sv.add_widget(self.list_box)
        self.add_widget(self.sv)

        # ---------- 底部打印栏 ----------
        bottom = BoxLayout(orientation="vertical", size_hint_y=None, height=dp(76),
                           padding=(dp(8), dp(4)), spacing=dp(2))
        self.cnt = L(text="未勾选订单", size_hint_y=None, height=dp(20),
                     font_size="12sp", color=GREY)
        bottom.add_widget(self.cnt)
        btns = BoxLayout(spacing=dp(6))
        self.b_full = B(text="🖨 完整", background_color=ORANGE, on_release=lambda *_: self.do_print("full"))
        self.b_kit = B(text="🍳 仅菜品", background_color=DARKORANGE, on_release=lambda *_: self.do_print("kitchen"))
        self.b_mat = B(text="📦 原材料", background_color=BLUE, on_release=lambda *_: self.do_print("materials"))
        for b in (self.b_full, self.b_kit, self.b_mat):
            b.disabled = True
            btns.add_widget(b)
        bottom.add_widget(btns)
        self.add_widget(bottom)

        self.load_config()
        Clock.schedule_once(lambda *_: self.auto_setup(), 0.3)
        Clock.schedule_interval(lambda *_: self.reload(silent=True), 20)

    def _sync_rect(self, inst, val):
        self._bar_rect.pos = inst.pos
        self._bar_rect.size = inst.size

    # ---------- 配置 ----------
    def load_config(self):
        try:
            cfg = json.load(open(self.cfg_path, encoding="utf-8"))
            self.api.set_base(cfg.get("server", ""))
        except Exception:
            pass

    def save_config(self):
        try:
            json.dump({"server": self.api.base.replace("http://", "")},
                      open(self.cfg_path, "w", encoding="utf-8"), ensure_ascii=False)
        except Exception as e:
            print("保存配置失败:", e)

    def auto_setup(self):
        """有保存过的地址就直接用；没有就自动搜索（也支持电脑是 Tailscale 地址）"""
        if self.api.base:
            self.status.text = "连接 " + self.api.base.replace("http://", "")
            self.reload()
        else:
            self.do_discover(first=True)

    def do_discover(self, first=False):
        self.status.text = "正在搜索电脑…"

        def work():
            cands = discover()
            hit = probe_first_ok(cands) if cands else None
            if hit is None and cands:
                hit = cands[0]      # 都探测不通也先用第一个（可能是电脑没开机以外的原因）
            Clock.schedule_once(lambda *_: self._discovered(hit, first), 0)
        threading.Thread(target=work, daemon=True).start()

    def _discovered(self, hit, first):
        if hit:
            self.api.set_base(hit)
            self.save_config()
            self.status.text = "已连接 " + hit
            self.reload()
        else:
            self.status.text = "未找到电脑，请点 ⚙ 手动填地址"
            if first:
                self.open_settings()

    # ---------- 设置弹窗 ----------
    def open_settings(self):
        box = BoxLayout(orientation="vertical", padding=dp(12), spacing=dp(8))
        box.add_widget(L(text="电脑端地址（IP:端口）\n填自动搜索到的那个，或 Tailscale 的 100.x 地址",
                         size_hint_y=None, height=dp(52), font_size="13sp"))
        ti = TextInput(text=self.api.base.replace("http://", ""), multiline=False,
                       size_hint_y=None, height=dp(42), font_size="16sp")
        if FONT:
            ti.font_name = FONT
        box.add_widget(ti)
        row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(6))
        pop = Popup(title="设置", content=box, size_hint=(0.92, None), height=dp(330))

        def _search(*_):
            pop.dismiss()
            self.do_discover()

        def _save(*_):
            self.api.set_base(ti.text)
            self.save_config()
            pop.dismiss()
            self.status.text = "连接 " + self.api.base.replace("http://", "")
            self.reload()

        row.add_widget(B(text="🔍 自动搜索", background_color=BLUE, on_release=_search))
        row.add_widget(B(text="测试并保存", background_color=ORANGE, on_release=_save))
        box.add_widget(row)
        box.add_widget(L(text="提示：手机和电脑在同一 WiFi 时用局域网地址；\n"
                              "在外面时用电脑的 Tailscale 地址（100.x.x.x）",
                         font_size="12sp", color=GREY))
        pop.open()

    # ---------- 日期 ----------
    def shift_day(self, delta):
        try:
            t = time.strptime(self.date8, "%Y%m%d")
            self.date8 = time.strftime("%Y%m%d", time.localtime(time.mktime(t) + delta * 86400))
        except Exception:
            self.date8 = time.strftime("%Y%m%d")
        self.checked = []
        self.reload()

    # ---------- 数据 ----------
    def reload(self, silent=False):
        if not self.api.base:
            return
        if not silent:
            self.status.text = "读取订单…"

        def work():
            try:
                data = self.api.orders(self.date8)
                Clock.schedule_once(lambda *_: self.render(data), 0)
            except Exception as e:
                def _fail(*_):
                    if silent:
                        self.status.text = "连接失败，点 ⚙ 检查地址"
                    else:
                        self.toast("连接失败: %s" % e)
                Clock.schedule_once(_fail, 0)
        threading.Thread(target=work, daemon=True).start()

    def render(self, data):
        self.orders = data.get("orders", [])
        ids = [o["id"] for o in self.orders]
        self.checked = [i for i in self.checked if i in ids]
        self.list_box.clear_widgets()
        self.rows = {}
        for o in self.orders:
            row = OrderRow(o, o["id"] in self.checked, self.on_toggle)
            self.rows[o["id"]] = row
            self.list_box.add_widget(row)
        d = data.get("date", self.date8)
        self.date_lb.text = f"{d[4:6]}月{d[6:8]}日"
        self.summary.text = f"共 {data.get('count', 0)} 单，合计 ￥{data.get('total', 0):.2f}"
        self.status.text = "已连接 " + self.api.base.replace("http://", "")
        self.update_bar()

    def on_toggle(self, oid, val):
        if val:
            if oid not in self.checked:
                self.checked.append(oid)
        else:
            self.checked = [i for i in self.checked if i != oid]
        self.update_bar()

    def update_bar(self):
        n = len(self.checked)
        self.cnt.text = f"已勾选 {n} 单（按勾选先后打印）" if n else "未勾选订单"
        for b in (self.b_full, self.b_kit, self.b_mat):
            b.disabled = (n == 0)

    # ---------- 打印 ----------
    def do_print(self, mode):
        if not self.checked:
            return
        names = {"full": "完整小票", "kitchen": "厨房联", "materials": "原材料汇总"}
        self.toast(f"正在打印{names[mode]}…")
        ids = list(self.checked)

        def work():
            try:
                res = self.api.print_orders(mode, ids)
                ok = res.get("ok")
                errs = [f"{r.get('order_id')}: {r.get('msg')}" for r in res.get("results", [])
                        if not r.get("ok")]
                msg = ("✅ " + names[mode] + "已打印") if ok else ("❌ " + (res.get("error") or "；".join(errs)))
            except Exception as e:
                msg = "❌ 打印失败: %s" % e
            Clock.schedule_once(lambda *_: self._after_print(msg), 0)
        threading.Thread(target=work, daemon=True).start()

    def _after_print(self, msg):
        self.toast(msg, 3)
        self.checked = []
        for r in self.rows.values():
            r.set_checked(False)
        self.update_bar()

    # ---------- 提示 ----------
    def toast(self, text, seconds=2):
        pop = Popup(title="", content=L(text=text, halign="center"),
                    size_hint=(0.72, None), height=dp(110), separator_height=0)
        pop.open()
        Clock.schedule_once(lambda *_: pop.dismiss(), seconds)


class GwhbApp(App):
    title = "港湾汉堡"

    def build(self):
        register_font()
        return Root()


if __name__ == "__main__":
    GwhbApp().run()
