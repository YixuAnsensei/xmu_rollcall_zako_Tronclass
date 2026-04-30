import asyncio
import re
import requests
from playwright.async_api import async_playwright

BASE_URL = "https://lnt.xmu.edu.cn"

HEADERS_BASE = {
    "accept": "application/json, text/plain, */*",
    "accept-language": "zh-CN,zh;q=0.9",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36",
}

# ==========================================
# 动态获取学期和学年 ID
# ==========================================
def get_current_semester_info(cookie):
    """访问系统接口，动态抓取最新的学年(12)和学期(29)"""
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

# ==========================================

async def login_and_get_cookie():
    print("❤正在打开浏览器喵❤，连接厦大CAS畅课登录系统喵❤")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        student_id = None

        # 1. 灵魂拦截器（收紧的正则，只抓真实的签到请求）
        def handle_request(request):
            nonlocal student_id
            if student_id is None:
                match = re.search(r'/student/(\d+)/rollcalls', request.url)
                if match:
                    student_id = int(match.group(1))
                    print(f"\n✅ 找到主人真实学生ID了喵❤：{student_id}")

        page.on("request", handle_request)

        # 2. 直接访问主页
        await page.goto(BASE_URL)

        if "ids.xmu.edu.cn" in page.url:
            print("👉 请在浏览器中输入账号密码登录，登录成功后脚本才自动继续喵~❤")
            await page.wait_for_function(
                "() => !window.location.href.includes('ids.xmu.edu.cn')",
                timeout=120000
            )
            print("✅ 登录成功喵❤！等待页面跳转喵❤！")

        # 3. 【核心提速】：wait_until="commit" 
        try:
            await page.wait_for_url("**/lnt.xmu.edu.cn/**", timeout=15000, wait_until="commit")
            print("⚡ 票据交接完成！不等主页加载，直接开始截胡喵！")
            await asyncio.sleep(1)
        except Exception:
            print("⚠️ zako网络稍慢喵，跳过等待直接进入提取流程喵...")

        # 4. 稳健跳转方案
        if student_id is None:
            print("🚀 喵要空降连招❤：后台拉取课程并强制跳转...")
            try:
                cookies_tmp = await context.cookies()
                cookie_str_tmp = "; ".join([f"{c['name']}={c['value']}" for c in cookies_tmp if "xmu.edu.cn" in c.get("domain", "")])
                
                # 【动态补丁】：跳跃前先查清当前是哪个学期
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
                    
                    # 轮询等待拦截器捕获 ID
                    for _ in range(15):
                        if student_id is not None:
                            break
                        await asyncio.sleep(1)
            except Exception as e:
                print(f"⚠️ 跳转触发失败，原因：{e}")

        # 5. 提 Cookie 走人
        cookies = await context.cookies()
        lnt_cookies = [c for c in cookies if "lnt.xmu.edu.cn" in c.get("domain", "")]
        cookie_str = "; ".join([f"{c['name']}={c['value']}" for c in lnt_cookies])

        await browser.close()

        if not student_id:
            print("❌ 经过所有手段均未能获取学生ID。呜喵")
        return cookie_str, student_id


# ----------------- 下方代码与之前保持完全一致 -----------------

def get_courses(cookie, s_id, y_id):
    print("\n❤正在获取课程列表喵~❤...")
    headers = {**HEADERS_BASE, "cookie": cookie, "content-type": "application/json",
               "referer": "https://lnt.xmu.edu.cn/user/index"}
    # 【动态补丁】：替换写死的 29 和 12
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


async def main():
    print("=" * 50)
    print("   ❤ zako又要用的厦大签到码查询工具喵~ (无限连发版) ❤")
    print("=" * 50)

    cookie, student_id = await login_and_get_cookie()
    if not cookie or not student_id:
        print("❌ 流程终止：未能拿到必要的凭证或真实学生ID嗷喵。")
        return

    # 【动态补丁】：获取完 Cookie 后，再查一次学期参数供下方拉取课程使用
    s_id, y_id = get_current_semester_info(cookie)

    # 传入动态获取到的学期和学年
    courses = get_courses(cookie, s_id, y_id)
    if not courses:
        print("❌ 获取课程列表失败，请检查上面是否有报错信息。")
        return

    print(f"\n❤你的课程列表喵：")
    for i, course in enumerate(courses):
        name = course.get("display_name") or course.get("name") or "未知课程"
        cid = course.get("id")
        print(f"  {i+1}. {name}  (ID: {cid})")

    # ==========================================
    # 核心修改区：开启无限循环模式喵！
    # ==========================================
    while True:
        print("\n" + "-" * 40)
        user_input = input("👉 请输入课程编号喵❤ (直接按 Enter 回车键退出程序)：")
        
        # 如果用户什么都没输直接按了回车，就跳出循环，结束程序
        if user_input.strip() == "":
            print("👋 拜拜喵~ 辛苦啦❤")
            break

        try:
            choice = int(user_input) - 1
            if choice < 0 or choice >= len(courses):
                print("❌ 编号无效，请看看上面的列表重新输入喵~")
                continue  # 编号不对，跳过本次循环，重新要求输入
        except ValueError:
            print("❌ 必须输入数字喵！")
            continue # 输入的不是数字，跳过本次循环，重新要求输入

        selected = courses[choice]
        course_id = selected.get("id")
        course_name = selected.get("display_name") or selected.get("name")
        print(f"\n已选择：{course_name}")

        print("❤正在获取最新zako签到记录...")
        rollcall_id, rollcall_time = get_latest_rollcall_id(course_id, cookie, student_id)
        if not rollcall_id:
            print("❌ 这门课暂无签到记录喵哦！换一门试试吧~")
            continue # 查不到这门课的，直接进入下一轮循环让你重新选

        from datetime import datetime, timezone, timedelta
        try:
            dt = datetime.fromisoformat(rollcall_time.replace("Z", "+00:00"))
            dt_local = dt.astimezone(timezone(timedelta(hours=8)))
            time_str = dt_local.strftime("%Y-%m-%d %H:%M")
        except:
            time_str = str(rollcall_time)

        print(f"❤找到最新签到~：{time_str}（ID: {rollcall_id}）")

        number_code, status, end_time = get_number_code(rollcall_id, cookie)

        print()
        print("=" * 40)
        if number_code:
            print(f"  zako的签到码是：【 {number_code} 】")
            status_map = {"active": "进行中", "finished": "已结束"}
            print(f"  状态：{status_map.get(status, status)}")
            print(f"  签到时间：{time_str}")
        else:
            print("  zako这次签到没有数字签到码喵~（搞不好是其他签到方式喵！如GPS定位/扫码等）")
        print("=" * 40)

if __name__ == "__main__":
    asyncio.run(main())