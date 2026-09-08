"""
zako 签到助手 —— CustomTkinter 版
工作流：
 1. 主页点猫爪 -> 启动浏览器 / CAS 登录
 2. 拿到 cookie + student_id -> 拉取课程列表 -> 跳课程页
 3. 点课程 -> 查最新签到码 -> 跳结果页
 4. 结果页可返回课程页继续查；任何页面右上角日志按钮可展开日志
"""

import asyncio
import math
import os
import re
import sys
import threading
import uuid
import requests
import customtkinter as ctk
from playwright.async_api import async_playwright
from datetime import datetime, timezone, timedelta

# ── 颜色 / 字体常量 ────────────────────────────────────────
BG        = "#0F0E17"
SURFACE   = "#1A1828"
SURFACE2  = "#221F33"
ACCENT    = "#FF6B9D"
ACCENT_DK = "#CC4477"
TEXT_PRI  = "#FFFFFE"
TEXT_SEC  = "#A7A9BE"
SUCCESS   = "#06D6A0"
WARN      = "#FFD166"
DANGER    = "#EF476F"

BASE_URL = "https://lnt.xmu.edu.cn"
HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/147.0.0.0 Safari/537.36"
    ),
}

# ==============================================================================
# 后端逻辑（完美继承原有机制，仅增加 log 参数用于重定向输出到 UI）
# ==============================================================================

def get_current_semester_info(cookie, log=print):
    headers = {**HEADERS_BASE, "cookie": cookie}
    try:
        resp = requests.get(
            f"{BASE_URL}/api/current-semester-info", headers=headers, timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            sem_id = str(data["semester"]["id"])
            year_id = str(data["academic_year"]["id"])
            log(f"✅ 成功获取当前学期信息喵~❤ (学期:{sem_id}, 学年:{year_id})")
            return sem_id, year_id
        else:
            log(f"⚠️ 动态获取学期接口响应异常 [{resp.status_code}]，使用内置默认值...")
    except Exception as e:
        log(f"⚠️ 动态获取学期请求失败: {e}，使用内置默认值...")
    return "29", "12"


async def login_and_get_cookie(log=print):
    log("❤ 正在打开浏览器喵 ❤，连接厦大CAS畅课登录系统喵❤")
    async with async_playwright() as p:
        browser = None
        context = None
        page = None

        # 🌟 核心升级：本地浏览器自动轮询策略
        # 按照 Edge -> Chrome 的顺序尝试本地浏览器
        local_channels = ["msedge", "chrome"]

        for channel in local_channels:
            try:
                log(f"🔄 正在尝试唤醒本地 [{channel}] 浏览器喵...")
                browser = await p.chromium.launch(headless=False, channel=channel)
                log(f"✅ 成功连接到本地 [{channel}] 喵！")
                break  # 一旦成功启动，立刻跳出循环！
            except Exception as e:
                log(f"⚠️ [{channel}] 启动失败喵，准备尝试下一个...")

        # 终极兜底方案：如果用户电脑连 Edge 和 Chrome 都没有
        if browser is None:
            log("🔄 没找到合适的本地浏览器，尝试启用 Playwright 备用内核喵...")
            try:
                browser = await p.chromium.launch(headless=False)
            except Exception as e:
                log("❌ 彻底失败了呜呜呜... 找不到任何可用浏览器。")
                return None, None # 直接终结流程

        context = await browser.new_context()
        page    = await context.new_page()
        student_id = None

        def handle_request(request):
            nonlocal student_id
            if student_id is None:
                m = re.search(r"/student/(\d+)/rollcalls", request.url)
                if m:
                    student_id = int(m.group(1))
                    log(f"✅ 找到主人真实学生ID了喵❤：{student_id}")

        page.on("request", handle_request)
        for attempt in range(1, 4):
            try:
                await page.goto(BASE_URL, timeout=20000, wait_until="commit")
                break
            except Exception as e:
                if attempt < 3:
                    log(f"⚠️ 畅课系统连接抖动 ({e})，正在自动重试第 {attempt}/3 次喵...")
                    await asyncio.sleep(1.5)
                else:
                    raise

        if "ids.xmu.edu.cn" in page.url:
            log("👉 请在浏览器中输入账号密码登录，登录成功后脚本才自动继续喵~❤")
            await page.wait_for_function(
                "() => !window.location.href.includes('ids.xmu.edu.cn')",
                timeout=120000,
            )
            log("✅ 登录成功喵❤！等待页面跳转喵❤！")

        try:
            await page.wait_for_url(
                "**/lnt.xmu.edu.cn/**", timeout=15000, wait_until="commit"
            )
            log("⚡ 票据交接完成！不等主页加载，直接开始截胡喵！")
            await asyncio.sleep(1)
        except Exception:
            log("⚠️ zako网络稍慢喵，跳过等待直接进入提取流程喵...")

        if student_id is None:
            log("🚀 喵要空降连招❤：后台拉取课程并强制跳转...")
            try:
                cookies_tmp = await context.cookies()
                cookie_str_tmp = "; ".join(
                    f"{c['name']}={c['value']}"
                    for c in cookies_tmp
                    if "xmu.edu.cn" in c.get("domain", "")
                )
                s_id, y_id = get_current_semester_info(cookie_str_tmp, log)
                payload_tmp = {
                    "conditions": {
                        "semester_id": [s_id],
                        "academic_year_id": [y_id],
                        "keyword": "",
                        "classify_type": "recently_started",
                        "display_studio_list": False,
                    },
                    "fields": "id,name",
                    "page": 1,
                    "page_size": 1,
                    "showScorePassedStatus": False,
                }
                resp_tmp  = await context.request.post(
                    f"{BASE_URL}/api/my-courses", data=payload_tmp
                )
                data_tmp  = await resp_tmp.json()
                courses_tmp = data_tmp.get("courses", data_tmp.get("data", []))
                if courses_tmp:
                    first_id = courses_tmp[0]["id"]
                    log(f"👉 后台秒定课程ID {first_id}喵，正在控制浏览器直接跳走喵！")
                    await page.goto(f"{BASE_URL}/course/{first_id}/rollcall")
                    for _ in range(15):
                        if student_id is not None:
                            break
                        await asyncio.sleep(1)
            except Exception as e:
                log(f"⚠️ 跳转触发失败，原因：{e}")

        cookies = await context.cookies()
        lnt_cookies = [c for c in cookies if "lnt.xmu.edu.cn" in c.get("domain", "")]
        cookie_str  = "; ".join(f"{c['name']}={c['value']}" for c in lnt_cookies)
        await browser.close()

        if not student_id:
            log("❌ 经过所有手段均未能获取学生ID。呜喵")
        return cookie_str, student_id


def get_courses(cookie, s_id, y_id, log=print):
    log("❤ 正在获取课程列表喵~❤...")
    headers = {
        **HEADERS_BASE,
        "cookie": cookie,
        "content-type": "application/json",
        "referer": "https://lnt.xmu.edu.cn/user/index",
    }
    payload = {
        "conditions": {
            "semester_id": [s_id],
            "academic_year_id": [y_id],
            "keyword": "",
            "classify_type": "recently_started",
            "display_studio_list": False,
        },
        "fields": "id,name,display_name",
        "page": 1,
        "page_size": 30,
        "showScorePassedStatus": False,
    }
    resp = requests.post(f"{BASE_URL}/api/my-courses", headers=headers, json=payload, timeout=15)
    try:
        data = resp.json()
    except Exception:
        log(f"⚠️ 返回数据解析失败: {resp.text}")
        return []

    if isinstance(data, list):
        courses = data
    elif "courses" in data:
        courses = data["courses"]
    elif "data" in data:
        courses = data["data"]
    else:
        log("⚠️ 无法解析课程列表喵呜~")
        return []

    seen, unique = set(), []
    for c in courses:
        cid = c.get("id")
        if cid not in seen:
            seen.add(cid)
            unique.append(c)
    log(f"✅ 成功获取课程列表喵~❤ 共 {len(unique)} 门课！")
    return unique


def get_latest_rollcall(course_id, cookie, student_id):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url  = (
        f"{BASE_URL}/api/course/{course_id}"
        f"/student/{student_id}/rollcalls?page=1&page_size=99"
    )
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
    except Exception:
        return None

    if isinstance(data, list):
        rollcalls = data
    elif "rollcalls" in data:
        rollcalls = data["rollcalls"]
    elif "data" in data:
        rollcalls = data["data"]
    else:
        rollcalls = []

    if not rollcalls:
        return None
    return rollcalls[-1]


def get_number_code(rollcall_id, cookie):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url  = f"{BASE_URL}/api/rollcall/{rollcall_id}/student_rollcalls"
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        data = resp.json()
        return data.get("number_code"), data.get("status"), data.get("end_time")
    except Exception:
        return None, None, None


# ==============================================================================
# 雷达签到引擎（四校区两阶段定位，移植自 zako_radar.py）
# ==============================================================================

RADAR_URL = f"{BASE_URL}/api/radar/rollcalls"

CAMPUSES = [
    {"name": "翔安校区", "lat": 24.6060, "lng": 118.3100},
    {"name": "思明校区", "lat": 24.4383, "lng": 118.0932},
    {"name": "马来西亚校区", "lat": 2.8327, "lng": 101.7028},
    {"name": "漳州校区", "lat": 24.3400, "lng": 117.9300},
]

EARTH_R = 6371000.0
PROBE_ACCURACY = 35

_radar_context = threading.local()


def find_active_radar_record(cookie, rollcall_id, log=None):
    try:
        resp = requests.get(
            RADAR_URL, headers={**HEADERS_BASE, "cookie": cookie}, timeout=15
        )
        data = resp.json()
    except Exception as e:
        if log:
            log(f"⚠️ 获取活动雷达列表失败: {e}")
        return None
    if isinstance(data, dict):
        rollcalls = data.get("rollcalls", [])
    elif isinstance(data, list):
        rollcalls = data
    else:
        rollcalls = []
    target = str(rollcall_id)
    for rc in rollcalls:
        if not isinstance(rc, dict):
            continue
        rid = str(rc.get("rollcall_id") or rc.get("id") or "")
        if rid == target:
            return rc
    return None


def radar_put(cookie, rollcall_id, lat, lng, timeout=15, session=None, device_id=None):
    if session is None:
        session = getattr(_radar_context, "session", None)
    if device_id is None:
        device_id = getattr(_radar_context, "device_id", None) or str(uuid.uuid4())
    payload = {
        "accuracy": PROBE_ACCURACY,
        "altitude": 0,
        "altitudeAccuracy": None,
        "deviceId": device_id,
        "heading": None,
        "latitude": lat,
        "longitude": lng,
        "speed": None,
    }
    client = session if session is not None else requests
    try:
        resp = client.put(
            f"{BASE_URL}/api/rollcall/{rollcall_id}/answer",
            json=payload,
            headers={**HEADERS_BASE, "cookie": cookie},
            timeout=timeout,
        )
        try:
            data = resp.json()
        except ValueError:
            data = {}
        return resp.status_code, data
    except Exception as e:
        return 0, {"error": str(e)}


def radar_distance(data):
    if not isinstance(data, dict):
        return None
    for key in ("distance", "dist", "distance_m", "distanceMeters"):
        val = data.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def latlon_to_xy(lat, lng, lat0, lng0):
    x = math.radians(lng - lng0) * EARTH_R * math.cos(math.radians(lat0))
    y = math.radians(lat - lat0) * EARTH_R
    return x, y


def xy_to_latlon(x, y, lat0, lng0):
    lat = lat0 + math.degrees(y / EARTH_R)
    lng = lng0 + math.degrees(x / (EARTH_R * math.cos(math.radians(lat0))))
    return lat, lng


def circle_intersections(x1, y1, d1, x2, y2, d2):
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist == 0:
        return None
    if dist > d1 + d2:
        if dist - (d1 + d2) <= 50.0:
            r = d1 / (d1 + d2)
            p = (x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
            return p, p
        return None
    if dist < abs(d1 - d2):
        if abs(d1 - d2) - dist <= 50.0:
            if d1 > d2:
                r = d1 / dist
                p = (x1 + (x2 - x1) * r, y1 + (y2 - y1) * r)
            else:
                r = d2 / dist
                p = (x2 + (x1 - x2) * r, y2 + (y1 - y2) * r)
            return p, p
        return None

    along = (d1 * d1 - d2 * d2 + dist * dist) / (2 * dist)
    h_sq = d1 * d1 - along * along
    if h_sq < 0:
        h_sq = 0.0
    height = math.sqrt(h_sq)
    mx = x1 + along * (x2 - x1) / dist
    my = y1 + along * (y2 - y1) / dist
    ox = -(y2 - y1) * height / dist
    oy = (x2 - x1) * height / dist
    return (mx + ox, my + oy), (mx - ox, my - oy)


def solve_two_points(lat1, lng1, lat2, lng2, d1, d2):
    lat0 = (lat1 + lat2) / 2
    lng0 = (lng1 + lng2) / 2
    x1, y1 = latlon_to_xy(lat1, lng1, lat0, lng0)
    x2, y2 = latlon_to_xy(lat2, lng2, lat0, lng0)
    sols = circle_intersections(x1, y1, d1, x2, y2, d2)
    if not sols:
        return None
    return (
        xy_to_latlon(sols[0][0], sols[0][1], lat0, lng0),
        xy_to_latlon(sols[1][0], sols[1][1], lat0, lng0),
    )


def radar_lock_campus(cookie, rollcall_id, log):
    best = None
    for c in CAMPUSES:
        status, data = radar_put(cookie, rollcall_id, c["lat"], c["lng"])
        if status == 200:
            log(f"🎯 校区探针直接命中：{c['name']}")
            return c, 0.0
        d = radar_distance(data)
        log(f"📡 {c['name']} 探针 distance={d}")
        if d is not None and (best is None or d < best[1]):
            best = (c, d)
    if best is None:
        return None, None
    return best


def radar_triangulate(cookie, rollcall_id, center, log):
    lat0, lng0 = center["lat"], center["lng"]
    dlat, dlng = 0.004, 0.004

    s1, d1 = radar_put(cookie, rollcall_id, lat0 + dlat, lng0)
    dist1 = radar_distance(d1)
    if s1 == 200:
        return True, (lat0 + dlat, lng0)

    s2, d2 = radar_put(cookie, rollcall_id, lat0, lng0 + dlng)
    dist2 = radar_distance(d2)
    if s2 == 200:
        return True, (lat0, lng0 + dlng)

    if dist1 is None or dist2 is None:
        log("⚠️ 探针未回传 distance，无法三边定位")
        return False, None

    sols = solve_two_points(lat0 + dlat, lng0, lat0, lng0 + dlng, dist1, dist2)
    if not sols:
        log("⚠️ 两圆不相交，定位失败")
        return False, None

    for (plat, plng) in sols:
        log(f"🧮 候选教师坐标 ({plat:.6f}, {plng:.6f})")
        s3, _ = radar_put(cookie, rollcall_id, plat, plng)
        if s3 == 200:
            return True, (plat, plng)
    return False, None


def send_radar(cookie, rollcall_id, log=print):
    log(f"🛰 开始雷达签到 rollcall_id={rollcall_id}")
    session = requests.Session()
    device_id = str(uuid.uuid4())
    _radar_context.session = session
    _radar_context.device_id = device_id
    try:
        center, hit = radar_lock_campus(cookie, rollcall_id, log)
        if center is None:
            log("❌ 四校区探针均未回传距离，雷达签到失败")
            return False, {"campus": None, "position": None}
        if hit == 0.0:
            log(f"✅ 雷达签到成功（校区中心直接命中：{center['name']}）")
            return True, {"campus": center["name"], "position": (center["lat"], center["lng"])}
        log(f"📍 锁定校区：{center['name']}")
        ok, pos = radar_triangulate(cookie, rollcall_id, center, log)
        if ok:
            log(f"✅ 雷达签到成功，教师位置≈({pos[0]:.6f}, {pos[1]:.6f})")
        else:
            log("❌ 校区内精确定位失败")
        return ok, {"campus": center["name"], "position": pos}
    finally:
        session.close()
        _radar_context.session = None
        _radar_context.device_id = None


# ==============================================================================
# 工具：在后台线程里跑 asyncio 事件循环
# ==============================================================================

def run_async(coro, callback):
    """在独立线程里运行 async 协程，完成后把结果用 callback 送回主线程。"""
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(coro)
            callback(result, None)
        except Exception as e:
            callback(None, e)
        finally:
            loop.close()
    threading.Thread(target=_run, daemon=True).start()


def run_sync_in_thread(fn, callback, *args, **kwargs):
    """在独立线程里运行普通同步函数，完成后 callback 送回结果。"""
    def _run():
        try:
            result = fn(*args, **kwargs)
            callback(result, None)
        except Exception as e:
            callback(None, e)
    threading.Thread(target=_run, daemon=True).start()


# ==============================================================================
# UI 辅助组件
# ==============================================================================

def make_label(parent, text, size=13, color=TEXT_PRI, bold=False, anchor="w", wraplength=0):
    weight = "bold" if bold else "normal"
    return ctk.CTkLabel(
        parent, text=text, font=("Microsoft YaHei", size, weight),
        text_color=color, anchor=anchor, wraplength=wraplength
    )


def make_button(parent, text, command, fg=ACCENT, hover=ACCENT_DK, width=200, height=40, size=13):
    return ctk.CTkButton(
        parent, text=text, command=command,
        fg_color=fg, hover_color=hover, text_color=BG,
        font=("Microsoft YaHei", size, "bold"),
        width=width, height=height, corner_radius=12,
    )


def separator(parent):
    return ctk.CTkFrame(parent, height=1, fg_color=SURFACE2)


def fmt_time(value):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(value)


# ==============================================================================
# 主应用
# ==============================================================================

class ZakoApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # ── 窗口基础设置 ─────────────────────────────
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.title("Zako 签到助手 ❤")
        self.geometry("500x700")
        self.resizable(False, False)
        self.configure(fg_color=BG)

        png_candidates = [
            os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "nekonn.png"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "nekonn.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "nekonn.png"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "nekonn.png"),
        ]
        ico_candidates = [
            os.path.join(getattr(sys, "_MEIPASS", ""), "assets", "nekonn.ico"),
            os.path.join(getattr(sys, "_MEIPASS", ""), "nekonn.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "nekonn.ico"),
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "nekonn.ico"),
        ]
        def _apply_icon():
            for p in png_candidates:
                if os.path.exists(p):
                    try:
                        self._icon_photo = tk.PhotoImage(file=p)
                        self.iconphoto(True, self._icon_photo)
                        break
                    except Exception:
                        pass
            for p in ico_candidates:
                if os.path.exists(p):
                    try:
                        self.iconbitmap(p)
                        break
                    except Exception:
                        pass
        _apply_icon()
        self.after(200, _apply_icon)

        # ── 共享状态 ─────────────────────────────────
        self._cookie     = None
        self._student_id = None
        self._courses    = []
        self._busy       = False        # 防止重复点击
        self._radar_running = False

        # ── 日志缓冲 ─────────────────────────────────
        self._log_lines  = []

        # ── 根布局：顶栏 + 内容区 ─────────────────────
        self._build_topbar()
        self._content = ctk.CTkFrame(self, fg_color=BG)
        self._content.pack(fill="both", expand=True, padx=0, pady=0)

        # ── 日志抽屉（隐藏态，覆盖在内容区上方）────────
        self._log_drawer_visible = False
        self._build_log_drawer()

        # ── 初始页面 ──────────────────────────────────
        self._show_home()

    # ─────────────────────────────────────────────────────
    # 顶栏
    # ─────────────────────────────────────────────────────
    def _build_topbar(self):
        bar = ctk.CTkFrame(self, fg_color=SURFACE, height=48, corner_radius=0)
        bar.pack(fill="x", side="top")
        bar.pack_propagate(False)

        make_label(bar, "❤ zako", size=15, color=ACCENT, bold=True).pack(
            side="left", padx=16
        )
        ctk.CTkButton(
            bar, text="📋 日志", width=72, height=30,
            fg_color=SURFACE2, hover_color="#2E2C3F", text_color=TEXT_SEC,
            font=("Microsoft YaHei", 12), corner_radius=8,
            command=self._toggle_log_drawer,
        ).pack(side="right", padx=12, pady=9)

    # ─────────────────────────────────────────────────────
    # 日志抽屉
    # ─────────────────────────────────────────────────────
    def _build_log_drawer(self):
        self._drawer = ctk.CTkFrame(self, fg_color=SURFACE, corner_radius=0)
        # 不 pack，靠 place 覆盖
        self._log_text = ctk.CTkTextbox(
            self._drawer,
            fg_color="#0A0912", text_color=TEXT_SEC,
            font=("Courier New", 11),
            wrap="word", state="disabled",
            corner_radius=8,
        )
        self._log_text.pack(fill="both", expand=True, padx=12, pady=(8, 12))

        ctk.CTkButton(
            self._drawer, text="✕ 关闭日志", width=120, height=28,
            fg_color=SURFACE2, hover_color=ACCENT_DK, text_color=TEXT_SEC,
            font=("Microsoft YaHei", 12), corner_radius=8,
            command=self._toggle_log_drawer,
        ).pack(pady=(0, 8))

    def _toggle_log_drawer(self):
        if self._log_drawer_visible:
            self._drawer.place_forget()
            self._log_drawer_visible = False
        else:
            self._drawer.place(relx=0, rely=0.08, relwidth=1, relheight=0.92)
            self._log_drawer_visible = True

    def _log(self, msg: str):
        """线程安全的日志写入（可从任意线程调用）。"""
        self._log_lines.append(msg)
        print(msg)
        self.after(0, self._flush_log, msg)

    def _flush_log(self, msg: str):
        self._log_text.configure(state="normal")
        self._log_text.insert("end", msg + "\n")
        self._log_text.see("end")
        self._log_text.configure(state="disabled")

    # ─────────────────────────────────────────────────────
    # 内容区切换（清空再重建）
    # ─────────────────────────────────────────────────────
    def _clear_content(self):
        for w in self._content.winfo_children():
            w.destroy()

    # =======================================================
    # 第 1 页：主页  ——  猫爪按钮
    # =======================================================
    def _show_home(self):
        self._clear_content()
        f = self._content

        ctk.CTkFrame(f, fg_color=BG, height=60).pack()

        make_label(f, "zako 签到助手", size=26, bold=True, anchor="center").pack()
        make_label(f, "点击猫爪，开始喵~", size=13, color=TEXT_SEC, anchor="center").pack(pady=(4, 0))

        ctk.CTkFrame(f, fg_color=BG, height=44).pack()

        # 猫爪按钮主体
        paw_frame = ctk.CTkFrame(
            f, fg_color=SURFACE, width=180, height=180, corner_radius=90
        )
        paw_frame.pack()
        paw_frame.pack_propagate(False)

        paw_lbl = ctk.CTkLabel(
            paw_frame, text="🐾", font=("Segoe UI Emoji", 80), fg_color="transparent"
        )
        paw_lbl.place(relx=0.5, rely=0.5, anchor="center")

        # 点击 / 悬停效果
        def on_enter(e):
            if not self._busy:
                paw_frame.configure(fg_color="#2A1F35")
        def on_leave(e):
            paw_frame.configure(fg_color=SURFACE)
        def on_click(e):
            if not self._busy:
                self._start_login()

        for w in (paw_frame, paw_lbl):
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)
            w.bind("<Button-1>", on_click)

        ctk.CTkFrame(f, fg_color=BG, height=24).pack()

        # 状态文字（动态更新）
        self._home_status = make_label(
            f, "", size=12, color=TEXT_SEC, anchor="center"
        )
        self._home_status.pack()

        ctk.CTkFrame(f, fg_color=BG, height=20).pack()

        make_label(
            f, "厦大 CAS 畅课签到码查询工具 ❤",
            size=11, color=TEXT_SEC, anchor="center"
        ).pack(side="bottom", pady=16)

    def _set_home_status(self, msg, color=TEXT_SEC):
        self.after(0, lambda: self._home_status.configure(text=msg, text_color=color))

    # ── 第1步：启动登录流程 ──────────────────────────────
    def _start_login(self):
        self._busy = True
        self._set_home_status("正在启动浏览器，请稍候喵~❤")

        def on_done(result, err):
            if err or result is None:
                self._log(f"❌ 登录异常: {err}")
                self._busy = False
                self._set_home_status("❌ 出错了，再试一次喵~", DANGER)
                return

            cookie, student_id = result
            if not cookie or not student_id:
                self._log("❌ 未能获取凭证或学生ID")
                self._busy = False
                self._set_home_status("❌ 未能获取凭证，再试一次喵~", DANGER)
                return

            self._cookie     = cookie
            self._student_id = student_id
            self._set_home_status("✅ 凭证就绪！正在拉取课程喵~", SUCCESS)
            self._log("✅ 凭证获取成功，开始拉取课程列表...")

            # 第2步：拉取学期信息 + 课程列表（同步，放子线程）
            def fetch_courses():
                s_id, y_id = get_current_semester_info(cookie, self._log)
                return get_courses(cookie, s_id, y_id, self._log)

            def on_courses(courses, err2):
                self._busy = False
                if err2 or not courses:
                    self._log(f"❌ 课程拉取失败: {err2}")
                    self._set_home_status("❌ 课程列表拉取失败喵哦~", DANGER)
                    return
                self._courses = courses
                self._log(f"🎉 成功拉取到 {len(courses)} 门课程喵！即将载入课程列表喵~❤")
                self._set_home_status(f"🎉 成功获取 {len(courses)} 门课程喵~❤", SUCCESS)
                self.after(500, self._show_courses)

            run_sync_in_thread(fetch_courses, on_courses)

        run_async(login_and_get_cookie(log=self._log), on_done)

    # =======================================================
    # 第 2 页：课程列表
    # =======================================================
    def _show_courses(self):
        self._clear_content()
        f = self._content

        # 标题区
        hdr = ctk.CTkFrame(f, fg_color=BG)
        hdr.pack(fill="x", padx=20, pady=(16, 8))

        # ↓↓↓ 绝对原位插入：仅在此处新增一个返回按钮，其他排版代码1个字都不变 ↓↓↓
        back_btn = ctk.CTkButton(
            hdr, text="← 返回主页", width=80, height=28,
            fg_color=SURFACE2, hover_color=SURFACE, text_color=TEXT_SEC,
            font=("Microsoft YaHei", 12), corner_radius=8,
            command=self._show_home,
        )
        back_btn.pack(anchor="w", pady=(0, 10))
        # ↑↑↑ 插入结束 ↑↑↑

        make_label(hdr, "选择课程", size=24, bold=True).pack(anchor="w")
        make_label(
            hdr, f"共 {len(self._courses)} 门课，点击查看最新签到码",
            size=12, color=TEXT_SEC
        ).pack(anchor="w", pady=(2, 0))

        separator(f).pack(fill="x", padx=20, pady=4)

        # 可滚动课程列表
        scroll = ctk.CTkScrollableFrame(f, fg_color=BG, scrollbar_button_color=SURFACE2)
        scroll.pack(fill="both", expand=True, padx=12, pady=4)

        for course in self._courses:
            self._make_course_row(scroll, course)

    def _make_course_row(self, parent, course):
        name = course.get("display_name") or course.get("name") or "未知课程"
        cid  = course.get("id")

        row = ctk.CTkFrame(parent, fg_color=SURFACE, corner_radius=12)
        row.pack(fill="x", pady=5, padx=4)

        icon = ctk.CTkLabel(
            row, text="📚", font=("Segoe UI Emoji", 22),
            width=44, height=44, fg_color=SURFACE2, corner_radius=10
        )
        icon.pack(side="left", padx=(10, 8), pady=10)

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True, pady=10)
        ctk.CTkLabel(
            info, text=name,
            font=("Microsoft YaHei", 13, "bold"),
            text_color=TEXT_PRI, anchor="w"
        ).pack(anchor="w")
        ctk.CTkLabel(
            info, text=f"ID: {cid}",
            font=("Courier New", 11),
            text_color=TEXT_SEC, anchor="w"
        ).pack(anchor="w")

        arrow = ctk.CTkLabel(row, text="›", font=("Arial", 22), text_color=TEXT_SEC)
        arrow.pack(side="right", padx=12)

        # 点击整行进入结果页
        def on_click(e, _cid=cid, _name=name):
            self._show_code(_cid, _name)

        def on_enter(e):
            row.configure(fg_color=SURFACE2)
        def on_leave(e):
            row.configure(fg_color=SURFACE)

        for w in (row, icon, info, arrow):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>",    on_enter)
            w.bind("<Leave>",    on_leave)

    # =======================================================
    # 第 3 页：签到结果（数字 / 雷达统一判定）
    # =======================================================
    def _show_code(self, course_id, course_name):
        self._clear_content()
        f = self._content

        # 顶部：返回按钮 + 课程名
        hdr = ctk.CTkFrame(f, fg_color=BG)
        hdr.pack(fill="x", padx=12, pady=(14, 4))

        back_btn = ctk.CTkButton(
            hdr, text="← 返回", width=72, height=32,
            fg_color=SURFACE2, hover_color=SURFACE, text_color=TEXT_SEC,
            font=("Microsoft YaHei", 12), corner_radius=8,
            command=self._show_courses,
        )
        back_btn.pack(side="left")

        make_label(
            hdr, text=course_name, size=14, bold=True,
            color=TEXT_PRI, anchor="w", wraplength=330
        ).pack(side="left", padx=10)

        separator(f).pack(fill="x", padx=20, pady=6)

        # 结果卡片容器（先放 loading）
        self._code_card_frame = ctk.CTkFrame(f, fg_color=BG)
        self._code_card_frame.pack(fill="both", expand=True, padx=20, pady=10)

        self._show_loading_card()

        # 后台拉取最新签到记录，并统一判定类型
        def fetch():
            latest = get_latest_rollcall(
                course_id, self._cookie, self._student_id
            )
            if latest is None:
                return None
            rid = str(latest.get("id") or latest.get("rollcall_id") or "")
            t = fmt_time(latest.get("rollcall_time") or latest.get("created_at"))
            type_text = str(
                latest.get("rollcall_type") or latest.get("type") or latest.get("kind") or ""
            ).lower()
            is_radar = (
                bool(latest.get("is_radar"))
                or bool(latest.get("isRadar"))
                or "radar" in type_text
            )
            if is_radar:
                active = find_active_radar_record(self._cookie, rid, self._log)
                if active is not None or str(latest.get("status") or "") == "active":
                    return {"type": "radar_active", "rid": rid, "time": t}
                return {"type": "radar_past", "time": t}
            number_code, status, _ = get_number_code(rid, self._cookie)
            if number_code:
                return {
                    "type": "digital",
                    "code": number_code,
                    "status": status,
                    "time": t,
                    "rid": rid,
                }
            active = find_active_radar_record(self._cookie, rid, self._log)
            if active is not None and (
                active.get("is_radar")
                or active.get("isRadar")
                or "radar" in str(active.get("rollcall_type") or active.get("type") or "").lower()
                or (not active.get("is_number") and not active.get("is_qrcode") and not active.get("is_qr"))
            ):
                return {"type": "radar_active", "rid": rid, "time": t}
            return {"type": "other", "time": t}

        def on_result(result, err):
            if err:
                self._log(f"❌ 查询出错: {err}")
                self.after(0, self._show_result_card, None, course_id, course_name)
                return
            self._log(
                f"✅ {course_name} | {result['time'] if result else '-'} "
                f"| 类型: {result['type'] if result else '无'}"
            )
            self.after(0, self._show_result_card, result, course_id, course_name)

        run_sync_in_thread(fetch, on_result)

    def _clear_card_frame(self):
        def _stop_bars(parent):
            for child in parent.winfo_children():
                if isinstance(child, ctk.CTkProgressBar):
                    try:
                        child.stop()
                    except Exception:
                        pass
                _stop_bars(child)
        _stop_bars(self._code_card_frame)
        for w in self._code_card_frame.winfo_children():
            w.destroy()

    def _show_loading_card(self):
        self._clear_card_frame()
        card = ctk.CTkFrame(self._code_card_frame, fg_color=SURFACE, corner_radius=20)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(
            card, text="🔍", font=("Segoe UI Emoji", 48)
        ).place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(
            card, text="正在查询签到喵~",
            font=("Microsoft YaHei", 14), text_color=TEXT_SEC
        ).place(relx=0.5, rely=0.56, anchor="center")
        ctk.CTkProgressBar(
            card, width=200, mode="indeterminate",
            progress_color=ACCENT, fg_color=SURFACE2
        ).place(relx=0.5, rely=0.68, anchor="center")
        # 启动动画
        for w in card.winfo_children():
            if isinstance(w, ctk.CTkProgressBar):
                w.start()

    def _show_result_card(self, result, course_id, course_name):
        self._clear_card_frame()

        card = ctk.CTkFrame(self._code_card_frame, fg_color=SURFACE, corner_radius=20)
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        if result is None:
            # 无签到记录
            ctk.CTkLabel(inner, text="😿", font=("Segoe UI Emoji", 52)).pack()
            make_label(inner, "暂无签到记录", size=18, bold=True, anchor="center").pack(pady=(8,2))
            make_label(inner, "这门课还没有签到喵~", size=13, color=TEXT_SEC, anchor="center").pack()

        elif result["type"] == "digital":
            # 有数字签到码
            status_map   = {"active": ("✅ 进行中", SUCCESS), "finished": ("🔒 已结束", TEXT_SEC)}
            status_txt, status_clr = status_map.get(result["status"], (result["status"], TEXT_SEC))

            ctk.CTkLabel(inner, text="🐾", font=("Segoe UI Emoji", 46)).pack()
            make_label(inner, "签到码", size=13, color=TEXT_SEC, anchor="center").pack(pady=(4,0))

            # 大号签到码（可选中复制）
            code_entry = ctk.CTkEntry(
                inner, width=240, height=80,
                font=("Arial Black", 48),
                text_color=ACCENT, fg_color="transparent",
                border_width=0, justify="center",
            )
            code_entry.insert(0, str(result["code"]))
            code_entry.configure(state="readonly")
            code_entry.pack(pady=4)

            # 状态标签
            status_frame = ctk.CTkFrame(inner, fg_color=SURFACE2, corner_radius=20)
            status_frame.pack(pady=4)
            ctk.CTkLabel(
                status_frame, text=status_txt,
                font=("Microsoft YaHei", 12, "bold"),
                text_color=status_clr
            ).pack(padx=16, pady=5)

            make_label(
                inner, f"签到时间：{result['time']}",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack(pady=(6, 0))

        elif result["type"] == "radar_active":
            # 雷达签到正在进行
            ctk.CTkLabel(inner, text="📡", font=("Segoe UI Emoji", 52)).pack()
            make_label(inner, "雷达签到进行中喵❤", size=18, bold=True, anchor="center").pack(pady=(8,2))
            make_label(
                inner, "教师在实时广播位置，点击按钮自动定位签到喵~",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack()
            make_label(
                inner, f"签到时间：{result['time']}",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack(pady=(6, 0))
            make_button(
                inner, "🛰 一键雷达签到",
                command=lambda: self._start_radar(result["rid"], course_name),
                width=240, height=46, size=14
            ).pack(pady=(14, 0))

        elif result["type"] == "radar_past":
            # 只有历史雷达签到记录
            ctk.CTkLabel(inner, text="📡", font=("Segoe UI Emoji", 52)).pack()
            make_label(inner, "上一次是雷达签到喵❤", size=18, bold=True, anchor="center").pack(pady=(8,2))
            make_label(
                inner, "当前没有进行中的雷达签到喵~",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack()
            make_label(
                inner, f"签到时间：{result['time']}",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack(pady=(6, 0))

        else:
            # 无数字签到码（GPS/扫码等）
            ctk.CTkLabel(inner, text="📍", font=("Segoe UI Emoji", 52)).pack()
            make_label(inner, "无数字签到码", size=18, bold=True, anchor="center").pack(pady=(8,2))
            make_label(
                inner, "可能是 GPS / 扫码等其他签到方式喵~",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack()
            make_label(
                inner, f"签到时间：{result['time']}",
                size=12, color=TEXT_SEC, anchor="center"
            ).pack(pady=(6, 0))

        # 再查一次按钮
        make_button(
            self._code_card_frame, "🔄 再查一次",
            command=lambda: self._show_code(course_id, course_name),
            width=300, height=42
        ).pack(pady=(12, 4))

    # =======================================================
    # 第 4 页：雷达签到执行视图
    # =======================================================
    def _start_radar(self, rollcall_id, course_name):
        if self._radar_running:
            return
        self._radar_running = True
        self._log(f"🛰 主人点击了雷达签到喵❤ rollcall_id={rollcall_id}")

        self._clear_card_frame()

        card = ctk.CTkFrame(self._code_card_frame, fg_color=SURFACE, corner_radius=20)
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(inner, text="🛰", font=("Segoe UI Emoji", 46)).pack()
        self._radar_status = make_label(
            inner, "正在四校区定位教师位置喵~请稍候...",
            size=13, color=TEXT_SEC, anchor="center"
        )
        self._radar_status.pack(pady=(6, 8))

        self._radar_bar = ctk.CTkProgressBar(
            inner, width=220, mode="indeterminate",
            progress_color=ACCENT, fg_color=SURFACE2
        )
        self._radar_bar.pack(pady=(0, 10))
        self._radar_bar.start()

        self._radar_log_box = ctk.CTkTextbox(
            inner, width=380, height=150,
            fg_color="#0A0912", text_color=TEXT_SEC,
            font=("Courier New", 11), wrap="word", state="disabled",
            corner_radius=8,
        )
        self._radar_log_box.pack()

        def work():
            return send_radar(self._cookie, rollcall_id, log=self._radar_log)

        def on_done(result, err):
            if err:
                self.after(0, self._finish_radar, False, {"error": str(err)}, rollcall_id, course_name)
                return
            ok, info = result
            self.after(0, self._finish_radar, ok, info, rollcall_id, course_name)

        run_sync_in_thread(work, on_done)

    def _radar_log(self, msg):
        self._log(msg)
        self.after(0, self._append_radar_log, msg)

    def _append_radar_log(self, msg):
        box = getattr(self, "_radar_log_box", None)
        if box is None:
            return
        try:
            if not box.winfo_exists():
                return
        except Exception:
            return
        box.configure(state="normal")
        box.insert("end", msg + "\n")
        box.see("end")
        box.configure(state="disabled")

    def _finish_radar(self, ok, info, rollcall_id, course_name):
        self._radar_running = False

        status = getattr(self, "_radar_status", None)
        bar = getattr(self, "_radar_bar", None)
        if status is None or bar is None:
            return
        try:
            if not status.winfo_exists():
                return
        except Exception:
            return
        try:
            bar.stop()
        except Exception:
            pass

        if ok:
            campus = info.get("campus") or ""
            detail = f"（{campus}）" if campus else ""
            pos = info.get("position")
            if pos:
                detail += f" 位置≈({pos[0]:.5f}, {pos[1]:.5f})"
            status.configure(text=f"✅ 雷达签到成功喵❤ {detail}", text_color=SUCCESS)
        else:
            status.configure(text="❌ 雷达签到失败喵，请重试~", text_color=DANGER)
            make_button(
                self._code_card_frame, "🔄 再试一次",
                command=lambda: self._start_radar(rollcall_id, course_name),
                width=300, height=42
            ).pack(pady=(12, 4))


# ==============================================================================
# 入口
# ==============================================================================
if __name__ == "__main__":
    app = ZakoApp()
    app.mainloop()
