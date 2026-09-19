---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '7be2be4e-2dc4-4b63-9949-c58b41f0f5de'
  PropagateID: '7be2be4e-2dc4-4b63-9949-c58b41f0f5de'
  ReservedCode1: '6bea36bb-dca9-44df-a1ee-ffcd714249b9'
  ReservedCode2: '6bea36bb-dca9-44df-a1ee-ffcd714249b9'
---

# 重邮教务在线导航 · 实时更新版

一站式教务信息导航站：静态入口（链接/电话/办事流程）保持稳定，动态数据（当前学期周次、最新教务发文）由 GitHub Actions 每日自动抓取刷新。

## 一、文件结构

```
├── index.html                  # 静态页面结构 + JS 渲染动态数据区
├── data.json                   # 动态数据（由脚本每日写入，勿手工覆盖）
├── fetch.py                    # 抓取脚本：教务在线 → data.json
├── requirements.txt            # Python 依赖
├── .github/workflows/update.yml  # GitHub Actions 每日定时任务
└── README.md                   # 本说明
```

## 二、架构说明

```
GitHub Actions（每日北京时间 8:00）
    │
    ▼
fetch.py 用 requests 抓取教务在线（服务端执行，无 CORS 问题）
    │  ① 首页 → 学期/周次
    │  ② 教务发文列表 → 最新 15 条（标题/发文号/日期/链接）
    ▼
写入 data.json → git commit → push
    │
    ▼
GitHub Pages 发布 index.html
    │
    ▼
浏览器打开 → JS fetch('data.json') 渲染「学期徽章 + 最新发文」
```

- 前端**不直接**抓源站（避免 CORS 与反爬），数据全部来自仓库内 data.json。
- 抓取失败时 fetch.py 自动保留旧数据并在 `fetchStatus` 记录错误，**不会覆盖为空**。
- 静态数据（入口链接、电话）与动态数据（学期/发文）严格分离，后者只存在于 data.json。

## 三、从零到上线（部署步骤）

### 1. 注册 GitHub
访问 https://github.com 注册账号（免费）。

### 2. 创建 Public 仓库
登录后点右上角 **+ → New repository**：
- Repository name：如 `cqupt-jwzx-nav`
- 可见性：选 **Public**（Private 仓库使用 Pages 需付费版）
- **不要勾选** "Add a README file"、".gitignore"、"License"（本项目已自带 README.md；勾选会让仓库产生初始提交，上传时引发同名冲突）
- 保持三项全部不选，创建空仓库最干净
- 点 **Create repository**

### 3. 上传本项目全部文件
仓库页面点 **Add file → Upload files**，把本目录全部文件拖入（注意 `.github` 是隐藏文件夹，Windows 资源管理器需开启"显示隐藏项目"），或使用命令行：

```bash
git clone https://github.com/你的用户名/cqupt-jwzx-nav.git
# 把本项目文件复制进仓库目录
cd cqupt-jwzx-nav
git add .
git commit -m "init: 重邮教务导航实时版"
git push
```

### 4. 开启 GitHub Pages
仓库页 **Settings → Pages**：
- Build and deployment → Source 选 **Deploy from a branch**
- Branch 选 `main`，Folder 选 `/ (root)`
- 点 **Save**，等待 1-2 分钟
- 页面顶部出现访问地址：`https://你的用户名.github.io/cqupt-jwzx-nav/`

### 5. 配置 Actions 写权限（关键）
仓库页 **Settings → Actions → General**：
- Workflow permissions 选 **Read and write permissions**
- 点 **Save**
（update.yml 中已声明 `permissions: contents: write`，此项保证脚本可以提交 data.json）

### 6. 手动触发一次更新（验证流水线）
仓库页 **Actions** 标签 → 左侧选 **每日更新教务数据** → 右侧 **Run workflow** 按钮 → 分支选 `main` → 点 **Run workflow**。
等待约 1-2 分钟，绿色 ✓ 表示成功；点进运行记录可查看抓取日志（应显示 `semester` 与 `notices` 均 `[ok]`）。

### 7. 验证上线
打开 `https://你的用户名.github.io/cqupt-jwzx-nav/`：
- ✅ 右上角显示「2026-2027学年 秋季学期（1学期）· 第 X 周」及自动更新时间
- ✅ 首页「最新教务发文」显示 15 条真实发文，点击可跳原站
- ✅ 之后每天北京时间约 8:00（UTC 0:00）自动刷新；Actions 页可随时手动触发

> 注意：GitHub 的 cron 按队列调度，实际执行可能有几分钟到几十分钟延迟，属正常现象。

## 四、本地测试（可选）

```bash
cd 重邮教务导航-实时版
python -m venv venv
venv\Scripts\pip install -r requirements.txt
venv\Scripts\python fetch.py       # 手动抓一次，生成最新 data.json
python -m http.server 8000         # 本地起服务器
# 浏览器访问 http://localhost:8000
```

> 直接双击 index.html 也能打开，但浏览器安全策略会拦截 `fetch('data.json')`，
> 顶部会显示"实时学期数据未加载"，属正常现象；部署到 Pages 后自动恢复。

## 五、数据字段说明（data.json）

| 字段 | 说明 | 来源 |
|------|------|------|
| `lastUpdate` | 数据更新时间 | 脚本写入 |
| `fetchStatus` | success / partial: 错误信息 | 脚本写入 |
| `semester` | `text` 学期称谓、`weekText` 周次 | 每日抓取 |
| `notices[]` | `title`/`docNo`/`date`/`url` | 每日抓取（最新 15 条） |
| `deadlines[]` | `name`/`note`/`url` 报名截止提醒 | **人工维护** |

人工维护 deadlines 示例（编辑 data.json 后 push，注意每次脚本运行会保留该字段）：

```json
"deadlines": [
  {
    "name": "2026年大类招生专业分流报名",
    "note": "截止时间见教务发文〔2026〕8号",
    "url": "http://jwzx.cqupt.edu.cn/student/zyfl.php"
  }
]
```

## 六、维护提醒（重要）

本站依赖教务在线页面结构。**若教务在线改版**（首页学期文本格式变化、发文列表结构变化），fetch.py 的正则/选择器可能失效：

- 症状：`fetchStatus` 出现 `partial: ... 未能解析`，或 `notices` 长期不更新
- 自保机制：脚本会保留旧数据，页面不会空白
- 修复方法：打开 update.yml 手动 Run workflow 查看日志定位问题，然后修改 `fetch.py` 中 `fetch_semester`（正则）或 `fetch_notices`（选择器）后重新 push

建议每学期开学时（页面改版高发期）人工核对一次数据准确性。

> AI生成