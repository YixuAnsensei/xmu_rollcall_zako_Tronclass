# Zako 签到助手 · 开发说明与使用指导

> 适用版本:Expo SDK 57 / React Native 0.86.3 / React 19.2.3
> 项目位置:`D:\claude-code-haha\xmu_rollcall_mobile`

---

## 一、先搞清楚:你机器上这些命令到底是什么(环境层解释)

### bun 和 bunx 是什么

| 命令 | 是什么 | 装在哪 |
|---|---|---|
| `bun` | JS 运行时 + 包管理器(类似 node + npm 二合一) | `C:\Users\yi'xuan\.bun\bin\bun.exe`(已在 PATH) |
| `bunx` | bun 自带的"临时下载并运行一个命令行工具"的命令(等价 npx) | 同上 |
| `node` / `npm` | 传统 JS 运行时和包管理器 | 系统另装的 v24.18.0 |

关键理解:**`bunx expo` 不是"安装了 expo 这个软件"**。它的行为是:
1. 去 npm 仓库下载 expo 命令 → 存进全局缓存 `C:\Users\yi'xuan\.bun\install\cache`(不是当前目录)
2. 在当前目录寻找项目并运行

**当前目录没有 package.json 就会报 ConfigError 退出**——这就是你在 `C:\Users\yi'xuan` 下运行 `bunx expo start` 失败的原因。它没有"不小心安装"任何东西到你的用户目录,只是没找到项目。**正确做法永远是:先 `cd` 进项目目录再运行。**

```bash
cd /d/claude-code-haha/xmu_rollcall_mobile   # 先回到项目目录
bunx expo start --tunnel                     # 再运行
```

更省心的方式:项目 `package.json` 里已有 `scripts`,直接 `bun run web/start/android` 之类(见下文)。

### expo / eas / tsc 这些命令在项目里的位置

项目安装依赖(`bun install`)后,命令实体在:
- `D:\claude-code-haha\xmu_rollcall_mobile\node_modules\.bin\` 里(expo.exe、tsc.exe 等)
- `bunx` 会优先用这里的本地版本——**所以项目内运行和全局版本互不干扰,这是规范做法**

### 这些开发会在 C 盘留下哪些"合法"缓存(别误删,删了也能再生)

| 目录 | 作用 | 大小(本次实测) | 可否删 |
|---|---|---|---|
| `C:\Users\...\.bun\install\cache` | bun 全局包缓存 | ~1.9 GB | 可删,下次装包重新下载 |
| `C:\Users\...\.gradle` | Android 构建缓存(装 Android 依赖) | 清理后 ~2.3 GB | 可删,下次构建重新下载(很慢) |
| `C:\Users\...\.expo` | expo 登录凭证 + 遥测 | ~0.2 MB | **不要删**(里面是 EAS 登录状态) |
| `%TEMP%\bunx-*` | bunx 临时解包目录 | ~0.4 GB/个 | 可删,本次已清 |
| 项目 `node_modules` | 项目依赖 | 384 MB(D 盘) | 可删,`bun install` 重装 |

> 本次已自动清理:7 个旧版 Gradle 缓存+发行包(6.2 GB)、Temp 里的 bunx 残留和 cc-haha 解包残留(约 1.6 GB)、过期 qr_connect.png。

---

## 二、项目结构(现在是什么样)

```
xmu_rollcall_mobile/
├── app/                  # 界面( expo-router 文件路由 )
│   ├── _layout.tsx       #   根布局
│   ├── index.tsx         #   入口(判断登录态跳转)
│   └── screens/
│       ├── LoginScreen.tsx    # 登录页(现:手动粘贴 Cookie;将改:WebView 自动登录)
│       ├── HomeScreen.tsx     # 课程/主页
│       └── RollcallScreen.tsx # 签到页(号码签到 + 雷达签到)
├── lib/
│   ├── api.ts            # 对接 lnt.xmu.edu.cn 的全部接口 + 雷达三角定位算法
│   └── auth.ts           # 登录态内存存储(将升级为可持久化)
├── modules/
│   └── xmu-cookie/       # 本地 Expo 原生模块(Android Kotlin,读 WebView 的 HttpOnly Cookie)
├── android/              # expo prebuild 生成的原生工程(已在 .gitignore,不入库)
├── app.json              # Expo 配置 + EAS projectId
├── eas.json              # EAS 构建配置
├── CONNECT.txt           # APK 下载链接与调试说明
└── package.json
```

## 三、技术栈对照(用你熟悉的东西理解它)

你有 flutter/kotlin/swift/uniapp/vue 的底子,对应关系:

| 你熟悉的 | 这里对应的 | 一句话说明 |
|---|---|---|
| Vue 组件(.vue 单文件) | React 组件(.tsx) | 同样是"组件+状态驱动 UI",React 用 JSX(在 TS 里写 HTML 标签) |
| uni-app 一套代码多端 | Expo/React Native | RN 是"JS 写逻辑,渲染原生控件"(比 uniapp 的 webview 套壳更接近原生) |
| Flutter 的 widget 树 | React 元素树 | 声明式 UI 思想完全一样 |
| Kotlin 的 Activity/View | RN 的 Screen/NativeView | RN 页面最终也是原生 View,由 JS 驱动 |
| Gradle 构建 Android | 同样 Gradle(android/ 目录) | EAS 云端帮你跑 Gradle,本机可不装 Android Studio |

## 四、日常开发流程(规范版)

### 1. 日常改代码 → 手机即时预览(Expo Go)

```bash
cd /d/claude-code-haha/xmu_rollcall_mobile
bun run start -- --tunnel
```
- `--tunnel` 走 Cloudflare 隧道,免配防火墙,手机 Expo Go 扫终端二维码即可
- 改代码手机即时热更新(JS 层)
- 注意:**原生模块代码(modules/ 和 android/)改动不会热更**,需要重新 prebuild/构建

### 2. 出正式安装包(APK)

```bash
cd /d/claude-code-haha/xmu_rollcall_mobile
bunx eas build --platform android --profile preview
```
- 云端构建,构建完给出 expo.dev 下载链接(链接约 14 天过期)
- 首次构建时如果 `bunx` 提示要装 eas-cli,同意即可(装进全局缓存,正常行为)

### 3. 改了原生代码后

```bash
bunx expo prebuild --clean    # 重新生成 android/ 工程(会自动链接 modules/ 下的本地模块)
```
本机调试则 `bunx expo run:android`(需要 JDK;正式发版走 EAS 就不必本机装 Android Studio)

### 4. 提交前检查(必须全绿再提交)

```bash
bunx tsc --noEmit             # 类型检查
bunx expo-doctor              # 环境与依赖健康检查
```

## 五、当前开发进度与下一步

**已完成:**
- ✅ SDK 57 干净重建(CNG:原生工程不入库,由 prebuild 生成)
- ✅ 官方 EAS 构建出可用 APK(链接在 CONNECT.txt)
- ✅ 接口层 lib/api.ts:成绩/课程/号码签到/雷达签到三角定位全部移植自桌面版
- ✅ 手动粘贴 Cookie 登录 + /api/profile 验证
- ✅ react-native-webview 13.16.1 已安装(与 SDK 57 匹配,经 expo install 通道确认)
- ✅ 本地原生模块 modules/xmu-cookie 已用官方脚手架 `create-expo-module` 生成(用于读取 WebView 的 HttpOnly Cookie——普通 JS 拿不到它,这是 CAS 自动登录的钥匙)

**下一步(按你的要求:先对齐环境、明确需求,再动代码):**
1. 补全 modules/xmu-cookie 的 Kotlin 实现(`getCookieForUrlAsync` / `clearCookiesAsync`)
2. 重写 LoginScreen:WebView 打开 `lnt.xmu.edu.cn` 走学校 CAS 统一认证 → 回跳成功判定(复刻桌面版/Android 参考源:URL 含 lnt 且不含 ids 且 Cookie 含 session/token)→ 原生模块取 Cookie → 验证 → 自动登录;保留手动粘贴作兜底
3. lib/auth.ts 增加持久化(ex AsyncStorage / SecureStore,重启免登录)
4. 类型检查 + expo-doctor 全绿 → 提交 → EAS 新构建 → 更新 CONNECT.txt 链接

## 六、常见问题

- **浏览器打开 expo.dev 提示"unusual traffic"**:是你本机出口 IP 被 Cloudflare 标记(换手机流量/换代理节点即可访问;APK 直链本身用其他网络下载正常)。
- **npm 装包报 `Cannot convert object to primitive value`**:npm 12 的已知 bug,本项目一律用 `bun` / `bunx`,不要用裸 `npm install`。
- **在 C:\Users\yi'xuan 里跑命令报 ConfigError**:没在项目目录,先 `cd` 回来。
