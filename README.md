# 全天候动态 ETF 组合 · 5.2 估值温度看板

基于 **5.2 估值温度策略**（10年滚动 PE/PB 分位 + 5年滚动 ERP 股债利差分位 + 中证500周期底部保护 + 20%~30% / 70%~80% 防闪烁迟滞缓冲状态机），利用 **GitHub Actions** 每个交易日自动计算，并通过专门的 **`gh-pages` 分支**发布 **GitHub Pages** 可视化看板。

---

## 🏗️ 分支隔离架构说明（`main` 与 `gh-pages` 分离）

* **`main` 分支（源码分支）**：仅存放 Python 计算脚本 `run_daily_5_2.py`、前端模板 `docs/index.html` 和 Action 配置文件，**永远不会被每日自动生成的提交记录污染**，本地修改代码后 `git push` 不会产生冲突。
* **`gh-pages` 分支（结果与发布分支）**：GitHub Actions 每次从 `main` 检出代码运行后，仅将生成的静态网页与最新数据（`index.html`、`data.js`、`data.json`、`latest_report.md`）提交到 `gh-pages` 分支根目录，供 GitHub Pages 直接发布。

---

## 📁 目录结构

```text
etf-temperature-monitor/
├── .github/
│   └── workflows/
│       └── daily_update.yml     # GitHub Actions：从 main 检出计算，仅提交结果到 gh-pages 分支
├── docs/
│   ├── index.html               # 基于 ECharts 的响应式可视化看板模板
│   └── data.js                  # 本地预览样本数据（线上由 Action 在内存中生成并推向 gh-pages）
├── run_daily_5_2.py             # 核心 5.2 温度与九宫格计算脚本 (独立于 RQAlpha)
├── requirements.txt             # Python 依赖清单 (akshare, pandas)
└── README.md
```

---

## 🚀 快速部署指南（仅需 2 步）

### 第一步：初始化 Git 并推送到 GitHub `main` 分支

1. 在 GitHub 上新建一个空仓库（建议设为 **Public** 以免费使用 GitHub Pages）。
2. 在本文件夹（`d:\invest\chinaetf2\etf-temperature-monitor`）打开终端执行：

```bash
cd d:\invest\chinaetf2\etf-temperature-monitor
git init
git add .
git commit -m "feat: init 5.2 ETF temperature strategy dashboard"
git branch -M main
git remote add origin https://github.com/<你的GitHub用户名>/<你的仓库名>.git
git push -u origin main
```

> **提示**：推送完成后，GitHub Actions 会立即自动触发首次运行，并**自动为你创建好 `gh-pages` 分支**，把最新计算结果提交进去。

### 第二步：将 GitHub Pages 绑定到 `gh-pages` 分支

1. 等待第一次 Action 运行成功（约 1 分钟）后，进入仓库顶部的 **Settings** $\rightarrow$ 左侧栏 **Pages**。
2. 在 **Build and deployment** 下：
   - **Source** 选择 `Deploy from a branch`
   - **Branch** 选择 **`gh-pages`**，目录选择 **`/ (root)`**，点击 **Save**。
3. 等待约 1 分钟后，即可访问：
   `https://<你的GitHub用户名>.github.io/<你的仓库名>/`
