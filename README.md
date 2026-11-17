# 全天候动态 ETF 组合 · 5.2 估值温度看板

基于 **5.2 估值温度策略**（10年滚动 PE/PB 分位 + 5年滚动 ERP 股债利差分位 + 中证500周期底部保护 + 20%~30% / 70%~80% 防闪烁迟滞缓冲状态机），利用 **GitHub Actions** 每个交易日自动计算，并通过 **GitHub Pages** 提供可视化看板。

---

## 📁 目录结构

```text
etf-temperature-monitor/
├── .github/
│   └── workflows/
│       └── daily_update.yml     # GitHub Actions 每日定时运行与自动提交配置
├── docs/
│   ├── index.html               # 基于 ECharts 的响应式可视化看板
│   ├── data.js                  # 每日生成的策略数据包 (支持本地双击打开与线上访问)
│   ├── data.json                # 每日生成的标准 JSON 数据
│   └── latest_report.md         # 每日生成的 Markdown 策略简报
├── run_daily_5_2.py             # 核心 5.2 温度与九宫格计算脚本 (独立于 RQAlpha)
├── requirements.txt             # Python 依赖清单 (akshare, pandas)
└── README.md
```

---

## 🚀 快速部署指南（仅需 3 步）

### 第一步：初始化 Git 并推送到 GitHub

1. 在 GitHub 上新建一个空仓库（例如命名为 `etf-temperature-monitor`，建议设为 **Public** 以免费使用 GitHub Pages）。
2. 在本文件夹（`d:\invest\chinaetf2\etf-temperature-monitor`）打开终端执行：

```bash
git init
git add .
git commit -m "feat: init 5.2 ETF temperature strategy dashboard"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/<你的仓库名>.git
git push -u origin main
```

> **提示**：推送完成后，GitHub Actions 会**自动触发首次运行**，拉取最新的沪深300、中证500估值与10年期国债收益率，并把完整历史数据更新到 `docs/` 目录下。

### 第二步：开启 GitHub Pages

1. 打开你的 GitHub 仓库页面，点击顶部菜单 **Settings** $\rightarrow$ 左侧栏 **Pages**。
2. 在 **Build and deployment** 下：
   - **Source** 选择 `Deploy from a branch`
   - **Branch** 选择 `main`，目录选择 `/docs`，点击 **Save**。
3. 等待约 1 分钟后，即可访问：
   `https://<你的GitHub用户名>.github.io/<你的仓库名>/`

### 第三步：确认 Actions 自动运行与手动触发

- **自动运行时间**：每个交易日（周一至周五）**北京时间 18:30**（`UTC 10:30`）自动拉取收盘估值并更新页面。
- **手动立即更新**：随时进入仓库顶部的 **Actions** $\rightarrow$ 选择左侧 `Daily 5.2 ETF Temperature Strategy Update` $\rightarrow$ 点击右侧 **Run workflow** 即可立即刷新。
