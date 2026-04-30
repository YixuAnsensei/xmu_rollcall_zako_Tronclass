import re
from playwright.sync_api import sync_playwright

# =============================
# 是否使用 Cookie 登录，是否要更新Cookie的标记
# =============================
USE_COOKIE = True
UPDATE_COOKIE = False


# =============================
# 输出课程名
# =============================
def format_course_output(text):
    lines = text.strip().splitlines()
    if not lines:  # 防御性编程
        return ""

    primary_line = lines[0].strip()

    if re.search(r'[周节]', primary_line):
        name_part = re.split(r'课程代码|代码:|202\d', text)[0].strip()
        match = re.search(r'周[一二三四五六日1-7]', name_part)
        if match:
            result = name_part[:match.start()]
        else:
            result = re.split(r'周', name_part)[0]
        return result.strip()
    else:
        return primary_line


# =============================
# 抓取
# =============================
def extract_rollcall_info():
    global USE_COOKIE
    global UPDATE_COOKIE  # 新增：声明为全局变量

    if not USE_COOKIE:
        USERNAME = input("请输入学号: ")
        PASSWORD = input("请输入密码: ")

    with sync_playwright() as p:

        browser = p.chromium.launch(headless=False)

        # ========= 登录 =========
        if USE_COOKIE:
            try:
                context = browser.new_context(storage_state="state.json")
            except:
                print("❌ 找不到Cookie文件，请重新登录")
                USERNAME = input("请输入学号: ")
                PASSWORD = input("请输入密码: ")
                context = browser.new_context()
                USE_COOKIE = False
        else:
            context = browser.new_context()

        page = context.new_page()

        if not USE_COOKIE:
            page.goto(
                "https://ids.xmu.edu.cn/authserver/login?type=userNameLogin&service=https%3A%2F%2Fc-identity.xmu.edu.cn%2Fauth%2Frealms%2Fxmu%2Fbroker%2Fcas-client%2Fendpoint%3Fstate%3D0nyJ678pdTmlBbN7wQseawI22TdXULx9Xarn2HmzTyM.WEHXCKqWJJw.Tronclass",
                wait_until="domcontentloaded"
            )

            page.fill("#username", USERNAME)
            page.fill("#password", PASSWORD)
            page.click(".login-btn")

            page.wait_for_load_state("networkidle")
            print("✅ 登录成功")

            # 修正：只有在UPDATE_COOKIE为True时才保存Cookie
            if UPDATE_COOKIE:
                try:
                    context.storage_state(path="state.json")
                    print("✅ Cookie已更新到state.json")
                except Exception as e:
                    print(f"⚠️ Cookie保存失败: {e}")
            else:
                print("⏭️ 未更新Cookie")

        # ========= 课程页面 =========
        page.goto("https://lnt.xmu.edu.cn/user/courses")

        page.wait_for_timeout(2000)

        course_selectors = [
            ".course-card",
            ".course-item",
            ".course",
            "[class*='course']",
            "div.course",
            "li.course"
        ]

        courses = None

        for selector in course_selectors:
            elements = page.locator(selector)
            if elements.count() > 0:
                courses = elements
                break

        if not courses or courses.count() == 0:
            print("❌ 未找到课程")
            return

        # ========= 输出课程 =========
        print("\n📚 课程列表：")

        for i in range(courses.count()):
            try:
                full_text = courses.nth(i).inner_text().strip()
                display_name = format_course_output(full_text)
                print(f"{i + 1}. {display_name}")
            except:
                print(f"{i + 1}. 课程{i + 1}")

        choice = input("\n选择课程编号: ")

        idx = int(choice) - 1
        courses.nth(idx).click()

        # ========= 进入点名 =========
        keywords = ["点名记录", "点名", "考勤", "签到"]

        for k in keywords:
            el = page.locator(f"text={k}")
            if el.count():
                el.first.click()
                break

        print("⏳ 获取最新点名...")

        rollcall_id = None

        # ========= 监听接口 =========
        def handle_response(response):
            nonlocal rollcall_id

            if "rollcalls" in response.url and response.request.method == "GET":
                try:
                    data = response.json()
                    rc = data["rollcalls"][-1]
                    rollcall_id = rc["rollcall_id"]
                except:
                    pass

        page.on("response", handle_response)

        page.reload()
        page.wait_for_timeout(3000)

        if not rollcall_id:
            print("❌ 未获取到点名记录")
            return

        # ========= 获取 number_code =========
        api = f"https://lnt.xmu.edu.cn/api/rollcall/{rollcall_id}/student_rollcalls"

        resp = page.request.get(api)

        data = resp.json()

        number_code = (
                data.get("number_code")
                or data.get("data", {}).get("number_code")
        )

        time_str = (
                data.get("end_time")
                or data.get("data", {}).get("end_time")
        )
        date_part = time_str.split('T')[0]

        print("\n✅ 获取成功")
        print("时间:", date_part)
        print("API网址:", api)
        print("rollcall_id:", rollcall_id)
        print("number_code:", number_code)

        input("\n回车关闭浏览器...")
        browser.close()


if __name__ == "__main__":
    print("说明:\n需要第三方库playwright,使用如下命令安装:\n  pip install playwright\n  playwright install chromium\n")
    # 是否使用Cookie的选择
    use_cookie_input = input("是否使用Cookie登录?(y/n): ").strip().lower()

    if use_cookie_input == "n" or use_cookie_input == "no":
        USE_COOKIE = False
        UPDATE_COOKIE = False  # 用户选择不使用Cookie登录，不更新Cookie
    else:
        USE_COOKIE = True
        # 询问是否需要更新Cookie
        update_cookie_input = input("是否需要更新Cookie?(y/n): ").strip().lower()
        if update_cookie_input == "y" or update_cookie_input == "yes":
            # 用户选择使用Cookie登录并要求更新Cookie
            USE_COOKIE = False
            UPDATE_COOKIE = True
        else:
            # 用户选择使用Cookie登录但不需要更新Cookie
            UPDATE_COOKIE = False

    # 调用提取点名信息的函数
    extract_rollcall_info()