# Zako 签到助手 移动端 (Expo + React Native)

基于 [xmu_rollcall_zako_Tronclass](https://github.com/YixuAnsensei/xmu_rollcall_zako_Tronclass)（V4 桌面版）的 React Native 移动端实现，功能面与桌面 exe 对齐。

## 功能

- **CAS 自动登录**：App 内嵌 WebView 走学校统一认证，登录成功经本地原生模块（Android `CookieManager`）读取 HttpOnly Cookie，`/api/profile` 验证身份
- **不持久化登录**：学校 Cookie 时效极短，每次启动都需重新登录（与桌面版行为一致）
- **数字签到码查询**：获取最新签到码、状态（进行中/已结束）
- **一键数字签到**：自动取码并提交（V4 同款）
- **雷达签到**：四校区探针锁定校区 + 三边定位反解教师坐标自动提交

## 技术栈

- Expo SDK 57（React Native 0.86.3 / React 19.2.3）+ CNG 连续原生生成
- TypeScript + expo-router（文件路由）
- react-native-webview（CAS 登录页面）
- 本地 Expo 模块 `modules/xmu-cookie`（Kotlin，读 HttpOnly Cookie）
- EAS Build 云端构建 APK

## 运行方式

```bash
cd D:\claude-code-haha\xmu_rollcall_mobile
bun install                 # 安装依赖（npm 12 有 bug，统一用 bun）
bunx expo start --tunnel    # 开发调试（注意：Expo Go 无法测试原生模块）
bunx eas build --platform android --profile preview   # 构建正式 APK
```

详细开发流程、环境说明、常见问题见 [DEV_GUIDE.md](DEV_GUIDE.md)。

## 与桌面版的差异

| 功能 | 桌面版 (Python V4) | 移动版 (React Native) |
|------|-------------------|----------------------|
| CAS 登录 | Playwright 开本地浏览器 | WebView 内嵌登录 |
| Cookie 获取 | `context.cookies()` | 原生模块 `CookieManager.getCookie()` |
| 网络请求 | requests 库 | fetch API |
| 持久化 | 无（每次重新登录） | 无（每次重新登录） |
| 界面框架 | CustomTkinter | React Native StyleSheet |
| 打包 | PyInstaller .exe | EAS Build APK |

## 项目结构

```
xmu_rollcall_mobile/
├── app/
│   ├── _layout.tsx          # 根布局（路由导航）
│   ├── index.tsx            # 重定向到首页
│   └── screens/
│       ├── HomeScreen.tsx   # 主页
│       ├── LoginScreen.tsx  # CAS WebView 登录
│       ├── CoursesScreen.tsx # 课程列表
│       └── RollcallScreen.tsx # 签到结果页
├── lib/
│   ├── api.ts               # 后端 API + 雷达定位算法（从 Python 移植）
│   └── auth.ts              # 登录态（内存，不持久化）
├── modules/
│   └── xmu-cookie/          # 本地 Expo 原生模块（Kotlin CookieManager）
├── android/                 # expo prebuild 生成，不入库
├── app.json / eas.json      # Expo / EAS 配置
├── CONNECT.txt              # APK 下载链接
└── DEV_GUIDE.md             # 开发说明与使用指导
```

## 注意事项

- CAS 登录需真机 APK 测试：Expo Go 里没有自定义原生模块
- 原生代码（modules/、LoginScreen WebView 配置）改动必须重新构建 APK，不会热更新
- 雷达签到依赖网络往返时延，建议在校园网/热点环境下使用
