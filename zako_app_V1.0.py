import asyncio
import re
import requests
import threading
import sys
import customtkinter as ctk
from playwright.async_api import async_playwright
from datetime import datetime, timezone, timedelta

# ==============================================================================
# 🔴 绝对原封不动的后端代码 🔴
# 100% 还原 V3.0 的原始代码，没有任何阉割，速度拉满！
# ==============================================================================

BASE_URL = "https://lnt.xmu.edu.cn"

HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

def get_current_semester_info(cookie):
    headers = {**HEADERS_BASE, "cookie": cookie}
    try:
        resp = requests.get(f"{BASE_URL}/api/current-semester-info", headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            s_id = str(data['semester']['id'])
            y_id = str(data['academic_year']['id'])
            return s_id, y_id
    except Exception:
        pass
    print("⚠️ 动态获取学期失败，使用内置默认值...")
    return "29", "12"

async def login_and_get_cookie():
    print("❤正在打开浏览器喵❤，连接厦大CAS畅课登录系统喵❤")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        student_id = None

        def handle_request(request):
            nonlocal student_id
            if student_id is None:
                match = re.search(r'/student/(\d+)/rollcalls', request.url)
                if match:
                    student_id = int(match.group(1))
                    print(f"\n✅ 找到主人真实学生ID了喵❤：{student_id}")

        page.on("request", handle_request)
        await page.goto(BASE_URL)

        if "ids.xmu.edu.cn" in page.url:
            print("👉 请在浏览器中输入账号密码登录，登录成功后脚本才自动继续喵~❤")
            await page.wait_for_function(
                "() => !window.location.href.includes('ids.xmu.edu.cn')",
                timeout=120000
            )
            print("✅ 登录成功喵❤！等待页面跳转喵❤！")

        try:
            await page.wait_for_url("**/lnt.xmu.edu.cn/**", timeout=15000, wait_until="commit")
            print("⚡ 票据交接完成！不等主页加载，直接开始截胡喵！")
            await asyncio.sleep(1)
        except Exception:
            print("⚠️ zako网络稍慢喵，跳过等待直接进入提取流程喵...")

        if student_id is None:
            print("🚀 喵要空降连招❤：后台拉取课程并强制跳转...")
            try:
                cookies_tmp = await context.cookies()
                cookie_str_tmp = "; ".join([f"{c['name']}={c['value']}" for c in cookies_tmp if "xmu.edu.cn" in c.get("domain", "")])
                
                s_id, y_id = get_current_semester_info(cookie_str_tmp)

                payload_tmp = {
                    "conditions": {"semester_id": [s_id], "academic_year_id": [y_id], "keyword": "", "classify_type": "recently_started", "display_studio_list": False},
                    "fields": "id,name",
                    "page": 1,
                    "page_size": 1,
                    "showScorePassedStatus": False
                }
                resp_tmp = await context.request.post(f"{BASE_URL}/api/my-courses", data=payload_tmp)
                data_tmp = await resp_tmp.json()
                
                courses_tmp = data_tmp.get("courses", data_tmp.get("data", []))

                if courses_tmp:
                    first_course_id = courses_tmp[0]["id"]
                    print(f"👉 后台秒定课程ID {first_course_id}喵，正在控制浏览器直接跳走喵！")
                    await page.goto(f"{BASE_URL}/course/{first_course_id}/rollcall")
                    
                    for _ in range(15):
                        if student_id is not None:
                            break
                        await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️ 跳转触发失败，原因：{e}")

        cookies = await context.cookies()
        lnt_cookies = [c for c in cookies if "lnt.xmu.edu.cn" in c.get("domain", "")]
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in lnt_cookies])

        await browser.close()

        if not student_id:
            print("❌ 经过所有手段均未能获取学生ID。呜喵")
        return cookie_str, student_id

def get_courses(cookie, s_id, y_id):
    print("\n❤正在获取课程列表喵~❤...")
    headers = {**HEADERS_BASE, "cookie": cookie, "content-type": "application/json",
               "referer": "https://lnt.xmu.edu.cn/user/index"}
    payload = {
        "conditions": {
            "semester_id": [s_id],
            "academic_year_id": [y_id],
            "keyword": "",
            "classify_type": "recently_started",
            "display_studio_list": False
        },
        "fields": "id,name,display_name",
        "page": 1,
        "page_size": 30,
        "showScorePassedStatus": False
    }
    resp = requests.post(f"{BASE_URL}/api/my-courses", headers=headers, json=payload)
    
    try:
        data = resp.json()
    except Exception as e:
        print(f"⚠️ 返回数据解析失败: {resp.text}")
        return []

    courses = []
    if isinstance(data, list):
        courses = data
    elif "courses" in data:
        courses = data["courses"]
    elif "data" in data:
        courses = data["data"]
    else:
        print("⚠️ 无法解析课程列表喵呜~")
        return []

    seen = set()
    unique_courses = []
    for c in courses:
        cid = c.get("id")
        if cid not in seen:
            seen.add(cid)
            unique_courses.append(c)
    return unique_courses

def get_latest_rollcall_id(course_id, cookie, student_id):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url = f"{BASE_URL}/api/course/{course_id}/student/{student_id}/rollcalls?page=1&page_size=99"
    resp = requests.get(url, headers=headers)
    data = resp.json()

    rollcalls = []
    if isinstance(data, list):
        rollcalls = data
    elif "rollcalls" in data:
        rollcalls = data["rollcalls"]
    elif "data" in data:
        rollcalls = data["data"]

    if not rollcalls:
        return None, None

    latest = rollcalls[-1]
    rid = latest.get("id") or latest.get("rollcall_id")
    rtime = latest.get("rollcall_time") or latest.get("created_at")
    return rid, rtime

def get_number_code(rollcall_id, cookie):
    headers = {**HEADERS_BASE, "cookie": cookie}
    url = f"{BASE_URL}/api/rollcall/{rollcall_id}/student_rollcalls"
    resp = requests.get(url, headers=headers)
    data = resp.json()
    return data.get("number_code"), data.get("status"), data.get("end_time")


# ==============================================================================
# 🎨 严格遵循工程设计逻辑的 GUI 架构
# ==============================================================================

class StdoutRedirector:
    """极其轻量的底层劫持，0 延迟同步原始 print 输出到下拉终端"""
    def __init__(self, text_widget):
        self.text_widget = text_widget
        self.terminal = sys.__stdout__

    def write(self, message):
        self.terminal.write(message) 
        if message.strip() or message == '\n':
            # 采用 GUI 安全调度，绝对不干扰后台 Playwright 的执行效率
            self.text_widget.after(0, self._insert, message)

    def _insert(self, message):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", message)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def flush(self):
        self.terminal.flush()

class ZakoApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("❤ Zako 专属签到神器 ❤")
        self.geometry("450x800")
        ctk.set_appearance_mode("Light")
        ctk.set_default_color_theme("blue")

        self.user_data = {"cookie": None, "student_id": None, "courses_list": []}

        # 1. 核心视图区：上面一大块专门用来放 主页/课程页
        self.page_container = ctk.CTkFrame(self, fg_color="transparent")
        self.page_container.pack(fill="both", expand=True, padx=10, pady=(10, 0))

        # 2. 交互底座：【全局终端抽屉按键】
        self.toggle_btn = ctk.CTkButton(
            self, text="💻 展开/收起终端喵", command=self.toggle_terminal, fg_color="gray"
        )
        self.toggle_btn.pack(fill="x", side="bottom", padx=10, pady=(5, 10))

        # 3. 下拉栏终端 (默认隐藏！)
        self.log_frame = ctk.CTkFrame(self, height=250, corner_radius=5)
        self.log_frame.pack_propagate(False)
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, wrap="word", state="disabled", fg_color="#1E1E1E", text_color="white")
        self.log_textbox.pack(fill="both", expand=True, padx=5, pady=5)
        self.terminal_visible = False
        
        # 将原始 python 输出劫持到黑框框里
        sys.stdout = StdoutRedirector(self.log_textbox)

        # 4. 初始化两大主页面
        self.init_home_page()
        self.init_courses_page()
        self.show_page(self.home_frame)

    def toggle_terminal(self):
        """完全兑现你的设计：始终可以点击的下拉栏切换逻辑"""
        if self.terminal_visible:
            # 收起抽屉
            self.log_frame.pack_forget()
            self.terminal_visible = False
        else:
            # 展开抽屉 (保证它插入在按钮的上方)
            self.toggle_btn.pack_forget() # 先拿掉按钮
            self.log_frame.pack(fill="x", side="bottom", padx=10, pady=0) # 塞入终端
            self.toggle_btn.pack(fill="x", side="bottom", padx=10, pady=(5, 10)) # 把按钮放回最底
            self.terminal_visible = True

    def show_popup(self, title, message):
        popup = ctk.CTkToplevel(self)
        popup.title(title)
        popup.geometry("350x200")
        popup.transient(self) 
        popup.grab_set() 

        label = ctk.CTkLabel(popup, text=message, font=("Arial", 14), justify="center", wraplength=300)
        label.pack(fill="both", expand=True, padx=20, pady=20)

        btn = ctk.CTkButton(popup, text="好滴喵", command=popup.destroy, fg_color="#FF69B4", hover_color="#FF1493")
        btn.pack(pady=10)

    def show_page(self, page_frame):
        self.home_frame.pack_forget()
        self.courses_frame.pack_forget()
        page_frame.pack(fill="both", expand=True)

    # ---------------- 页面 1：极简主页 ----------------
    def init_home_page(self):
        self.home_frame = ctk.CTkFrame(self.page_container, fg_color="transparent")
        
        title = ctk.CTkLabel(self.home_frame, text="❤ Zako 签到神器 ❤", font=("Arial", 28, "bold"), text_color="#FF69B4")
        title.pack(pady=(50, 20))

        # 满足你的要求：只有一个可爱的猫爪按钮
        self.paw_button = ctk.CTkButton(
            self.home_frame, text="🐾", font=("Arial", 100), width=200, height=200, 
            corner_radius=100, fg_color="#FFE4E1", hover_color="#FFB6C1", text_color="#FF69B4",
            command=self.start_login_thread
        )
        self.paw_button.pack(pady=20)

        # 这个状态栏非常重要，它弥补了 UI 上“看起来慢”的错觉
        self.status_label = ctk.CTkLabel(self.home_frame, text="点击猫爪启动系统喵！", font=("Arial", 16), text_color="gray")
        self.status_label.pack(pady=10)

    # ---------------- 页面 2：课程列表页 ----------------
    def init_courses_page(self):
        self.courses_frame = ctk.CTkFrame(self.page_container, fg_color="transparent")
        
        title = ctk.CTkLabel(self.courses_frame, text="你的课程列表喵 👇", font=("Arial", 20, "bold"))
        title.pack(pady=(10, 10))

        self.course_scroll_view = ctk.CTkScrollableFrame(self.courses_frame)
        self.course_scroll_view.pack(fill="both", expand=True, padx=10, pady=10)

    # ---------------- UI 与 核心业务逻辑调度 ----------------
    def start_login_thread(self):
        # 瞬间给出反馈，防止用户觉得“卡死”或“变慢”
        self.paw_button.configure(text="⏳", state="disabled")
        self.status_label.configure(text="🚀 正在启动浏览器拦截，请留意弹出的窗口...", text_color="blue")
        
        # 完美还原最初始的欢迎词
        print("=" * 50)
        print("   ❤ zako又要用的厦大签到码查询工具喵~ (无限连发版) ❤")
        print("=" * 50)

        def run_async():
            asyncio.run(self.async_login_process())
            
        threading.Thread(target=run_async, daemon=True).start()

    async def async_login_process(self):
        # 调用 100% 原始方法
        cookie, student_id = await login_and_get_cookie()
        
        if not cookie or not student_id:
            print("❌ 流程终止：未能拿到必要的凭证或真实学生ID嗷喵。")
            self.after(0, lambda: self.status_label.configure(text="❌ 登录失败！请重试喵", text_color="red"))
            self.after(0, lambda: self.paw_button.configure(text="🐾", state="normal"))
            return
            
        self.user_data["cookie"] = cookie
        self.user_data["student_id"] = student_id
        
        self.after(0, lambda: self.status_label.configure(text="✅ 获取凭证成功！正在拉取课程表..."))
        
        s_id, y_id = get_current_semester_info(cookie)
        courses = get_courses(cookie, s_id, y_id)
        
        if not courses:
            print("❌ 获取课程列表失败，请检查上面是否有报错信息。")
            self.after(0, lambda: self.status_label.configure(text="❌ 课程拉取失败！", text_color="red"))
            self.after(0, lambda: self.paw_button.configure(text="🐾", state="normal"))
            return
            
        self.user_data["courses_list"] = courses
        
        # 完美还原课程打印逻辑
        print(f"\n❤你的课程列表喵：")
        for i, course in enumerate(courses):
            name = course.get("display_name") or course.get("name") or "未知课程"
            cid = course.get("id")
            print(f"  {i+1}. {name}  (ID: {cid})")
        
        self.after(0, self.build_and_show_courses)

    def build_and_show_courses(self):
        for widget in self.course_scroll_view.winfo_children():
            widget.destroy()

        for i, c in enumerate(self.user_data["courses_list"]):
            course_name = c.get('display_name') or c.get('name')
            course_id = str(c['id'])
            
            btn = ctk.CTkButton(
                self.course_scroll_view,
                text=f"{i+1}. {course_name}", font=("Arial", 14), height=40, anchor="w", 
                fg_color="transparent", text_color="black", border_width=1, border_color="gray", hover_color="#f0f0f0"
            )
            # 记录初始文字，便于状态恢复
            btn.original_text = f"{i+1}. {course_name}"
            # 绑定点击事件，将按钮本身传过去以改变状态
            btn.configure(command=lambda cid=course_id, cname=course_name, b=btn: self.start_check_thread(cid, cname, b))
            btn.pack(fill="x", padx=5, pady=5)

        # 重置主页状态，并（页面刷新）进入新的一页
        self.paw_button.configure(text="🐾", state="normal")
        self.status_label.configure(text="点击猫爪启动系统喵！", text_color="gray")
        self.show_page(self.courses_frame)

    def start_check_thread(self, course_id, course_name, btn_widget):
        # 瞬间修改按钮外观，让体验不卡顿！
        btn_widget.configure(text="⏳ 正在全速查询中...", text_color="blue")
        
        print(f"\n已选择：{course_name}")
        print("❤正在获取最新zako签到记录...")
        
        def run_check():
            r_id, r_time = get_latest_rollcall_id(course_id, self.user_data["cookie"], self.user_data["student_id"])
            
            if not r_id:
                print("❌ 这门课暂无签到记录喵哦！")
                self.after(0, lambda: btn_widget.configure(text=btn_widget.original_text, text_color="black"))
                self.after(0, lambda: self.show_popup("无记录", f"【{course_name}】\n\n这门课暂无签到记录喵哦！换一门试试吧~"))
                return
                
            try:
                dt = datetime.fromisoformat(r_time.replace("Z", "+00:00")).astimezone(timezone(timedelta(hours=8)))
                time_str = dt.strftime("%Y-%m-%d %H:%M")
            except: time_str = str(r_time)

            print(f"❤找到最新签到~：{time_str}（ID: {r_id}）")
            number_code, status, _ = get_number_code(r_id, self.user_data["cookie"])

            print()
            print("=" * 40)
            if number_code:
                status_map = {"active": "进行中", "finished": "已结束"}
                print(f"  zako的签到码是：【 {number_code} 】")
                print(f"  状态：{status_map.get(status, status)}")
                print(f"  签到时间：{time_str}")
                
                msg = f"🔑 签到码：{number_code}\n🕒 状态：{status_map.get(status, status)}\n📅 时间：{time_str}"
            else:
                print("  zako这次签到没有数字签到码喵~（搞不好是其他签到方式喵！如GPS定位/扫码等）")
                msg = f"🤔 这次没有数字密码喵！\n可能是GPS或扫码。\n📅 时间：{time_str}"
            print("=" * 40)

            # 恢复按钮外观，并弹出结果
            self.after(0, lambda: btn_widget.configure(text=btn_widget.original_text, text_color="black"))
            self.after(0, lambda: self.show_popup(course_name, msg))

        threading.Thread(target=run_check, daemon=True).start()

if __name__ == "__main__":
    app = ZakoApp()
    app.mainloop()