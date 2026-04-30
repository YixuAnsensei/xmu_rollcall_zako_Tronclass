"""
zako 签到助手 —— CustomTkinter 版
工作流：
 1. 主页点猫爪 -> 启动浏览器 / CAS 登录
 2. 拿到 cookie + student_id -> 拉取课程列表 -> 跳课程页
 3. 点课程 -> 查最新签到码 -> 跳结果页
 4. 结果页可返回课程页继续查；任何页面右上角日志按钮可展开日志
"""

import asyncio
import re
import threading
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
            return str(data["semester"]["id"]), str(data["academic_year"]["id"])
    except Exception:
        pass
    log("⚠️ 动态获取学期失败，使用内置默认值...")
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
        await page.goto(BASE_URL)

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
    resp = requests.post(f"{BASE_URL}/api/my-courses", headers=headers, json=payload)
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
    return unique


def get_latest_rollcall_id(course_id, cookie, student_id):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url  = (
        f"{BASE_URL}/api/course/{course_id}"
        f"/student/{student_id}/rollcalls?page=1&page_size=99"
    )
    resp = requests.get(url, headers=headers)
    data = resp.json()

    if isinstance(data, list):
        rollcalls = data
    elif "rollcalls" in data:
        rollcalls = data["rollcalls"]
    elif "data" in data:
        rollcalls = data["data"]
    else:
        rollcalls = []

    if not rollcalls:
        return None, None
    latest = rollcalls[-1]
    return (
        latest.get("id") or latest.get("rollcall_id"),
        latest.get("rollcall_time") or latest.get("created_at"),
    )


def get_number_code(rollcall_id, cookie):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url  = f"{BASE_URL}/api/rollcall/{rollcall_id}/student_rollcalls"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    return data.get("number_code"), data.get("status"), data.get("end_time")


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

        # ── 共享状态 ─────────────────────────────────
        self._cookie     = None
        self._student_id = None
        self._courses    = []
        self._busy       = False        # 防止重复点击

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
                self.after(0, self._show_courses)   # 切换到课程页（主线程）

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
    # 第 3 页：签到码结果
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

        # 后台拉取签到码
        def fetch():
            r_id, r_time = get_latest_rollcall_id(
                course_id, self._cookie, self._student_id
            )
            if not r_id:
                return None
            number_code, status, _ = get_number_code(r_id, self._cookie)
            try:
                dt = datetime.fromisoformat(r_time.replace("Z", "+00:00"))
                time_str = dt.astimezone(timezone(timedelta(hours=8))).strftime(
                    "%Y-%m-%d %H:%M"
                )
            except Exception:
                time_str = str(r_time)
            return {"code": number_code, "status": status, "time": time_str, "rid": r_id}

        def on_result(result, err):
            if err:
                self._log(f"❌ 查询出错: {err}")
                self.after(0, self._show_result_card, None, course_id, course_name)
                return
            self._log(
                f"✅ {course_name} | {result['time'] if result else '-'} "
                f"| 签到码: {result['code'] if result else '无'}"
            )
            self.after(0, self._show_result_card, result, course_id, course_name)

        run_sync_in_thread(fetch, on_result)

    def _show_loading_card(self):
        for w in self._code_card_frame.winfo_children():
            w.destroy()
        card = ctk.CTkFrame(self._code_card_frame, fg_color=SURFACE, corner_radius=20)
        card.pack(fill="both", expand=True)
        ctk.CTkLabel(
            card, text="🔍", font=("Segoe UI Emoji", 48)
        ).place(relx=0.5, rely=0.4, anchor="center")
        ctk.CTkLabel(
            card, text="正在查询签到码喵~",
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
        for w in self._code_card_frame.winfo_children():
            w.destroy()

        card = ctk.CTkFrame(self._code_card_frame, fg_color=SURFACE, corner_radius=20)
        card.pack(fill="both", expand=True)

        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        if result is None:
            # 无签到记录
            ctk.CTkLabel(inner, text="😿", font=("Segoe UI Emoji", 52)).pack()
            make_label(inner, "暂无签到记录", size=18, bold=True, anchor="center").pack(pady=(8,2))
            make_label(inner, "这门课还没有签到喵~", size=13, color=TEXT_SEC, anchor="center").pack()

        elif result["code"]:
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


# ==============================================================================
# 入口
# ==============================================================================
if __name__ == "__main__":
    app = ZakoApp()
    app.mainloop()