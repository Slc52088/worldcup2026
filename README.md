# ⚽ 2026 世界杯 · 智能预测系统 (WorldCup 2026 Intelligent Prediction System)

> 一个面向 2026 美加墨世界杯的全栈预测 Web App。深色高端 UI、密码门禁、泊松+贝叶斯+蒙特卡洛预测引擎、盘赔相似度匹配、市场热度仪表盘、PWA 可安装。**完全使用免费资源构建与部署。**

---

## ⚠️ 重要声明 (请先读)

1. **仅供娱乐与技术学习，不构成任何博彩、投资或财务建议。** 概率与"价值投注"输出均为统计模型产物，不保证准确，请勿据此进行任何形式的真实下注。
2. **关于数据源的诚实说明：** 本项目设计了一个**可插拔数据适配层 (`OddsProvider`)**。
   - **赛程 / 历史结果** 来自真实开源数据 `openfootball/worldcup.json`（经 jsDelivr CDN 获取，无需密钥）。
   - **实时赔率** 默认由一个**确定性模拟引擎 (`SimulatedOddsProvider`)** 驱动，原因是：市面上声称"完全免费、无需密钥、提供多家博彩公司实时赔率"的 API 实际并不可靠存在。模拟引擎让 App 在部署当天**永远可用**，且界面会**明确标注数据为模拟**。
   - 当你拥有真实赔率源（例如 [The Odds API](https://the-odds-api.com/) 的免费档，约 500 次/月）时，仅需设置环境变量 `ODDS_API_KEY`，系统会自动切换到真实数据，界面标注随之变为真实来源。
3. **"资金流向 / Steam Move" 的方法学诚实标注：** 通过赔率变动反推市场资金倾向是业界使用的**启发式方法 (heuristic)**，它**反映的是赔率隐含概率的变化，并非真实可见的下注金额**。界面对此有明确说明，不夸大为"被广泛验证的精确事实"。

---

## ✨ 功能特性

| 模块 | 说明 |
|------|------|
| 🔒 全局密码门禁 | 单一访问密码，后端中间件校验 + 防暴力破解（失败计数+冷却），前端 `sessionStorage` 维持会话，支持"记住我"30天 |
| 📊 胜平负概率 | 泊松分布 + 贝叶斯融合市场共识，附自然语言依据 |
| 🎯 三个最可能比分 | 基于泊松比分矩阵，按概率排序，每个比分附概率 |
| 🔍 盘赔历史相似度 | DTW (动态时间规整) 匹配历史赔率走势，返回最相似场次与结果 |
| 🌡️ 市场热度仪表盘 | 资金分布(反推)、冷热指数、赔量背离、异动预警，每项含名词解释 |
| 💎 价值投注建议 | 融合所有信号，给出 EV(期望值) 与 Kelly 建议比例，附风险说明 |
| 🏆 冠军之路 | 蒙特卡洛模拟 10,000 次，输出冠/亚/季军概率 + 交互式淘汰赛树 |
| 🧠 自进化权重 | 依据历史命中率评估各模型贡献，自动再平衡集成权重 |
| 📱 PWA | manifest + Service Worker，可加入主屏，离线缓存基础框架 |

---

## 🗂️ 项目文件结构树

```
worldcup2026/
├── README.md                      # 本文件
├── .gitignore
│
├── backend/                       # FastAPI 后端 (部署到 Render)
│   ├── requirements.txt
│   ├── main.py                    # FastAPI app、路由、密码中间件、调度器启动
│   ├── config.py                  # 环境变量与全局配置
│   ├── auth.py                    # 密码校验 + 防暴力破解逻辑
│   │
│   ├── data/                      # 数据获取与存储
│   │   ├── data_fetcher.py        # 赛程/球队/近况获取 (openfootball)
│   │   ├── odds_provider.py       # 可插拔赔率适配层 (模拟 + The Odds API)
│   │   ├── store.py               # SQLite + JSON 缓存读写
│   │   └── cache/                 # 运行时生成的 JSON 缓存 (gitignored)
│   │
│   ├── models/                    # 预测模型核心
│   │   ├── statistical_model.py   # 泊松分布模型
│   │   ├── market_model.py        # 市场赔率 → 隐含概率 + 去抽水
│   │   ├── odds_pattern_matcher.py# DTW 盘赔相似度
│   │   ├── market_sentiment.py    # 资金分布/冷热指数
│   │   ├── sentiment_alert.py     # 异动预警 (steam move 检测)
│   │   ├── tournament_simulator.py# 蒙特卡洛赛事模拟
│   │   ├── ultimate_ensemble.py   # 三层集成、动态权重
│   │   ├── betting_strategy.py    # EV / Kelly 价值投注
│   │   └── optimizer.py           # 自进化权重优化器
│   │
│   └── tests/
│       └── test_models.py         # 模型基本单元测试
│
└── frontend/                      # 纯静态 SPA + PWA (部署到 GitHub Pages / Netlify)
    ├── index.html                 # 单页应用入口 (所有页面模板)
    ├── style.css                  # 惊艳深色主题、玻璃拟态、响应式
    ├── app.js                     # 路由、认证、API 调用、页面渲染
    ├── charts.js                  # Chart.js / Plotly 封装
    ├── config.js                  # 前端配置 (API base URL)
    ├── manifest.json              # PWA 清单
    ├── sw.js                      # Service Worker (离线缓存)
    └── assets/
        └── icons/                 # PWA 图标 (192/512)
```

---

## 🧰 免费资源清单

| 用途 | 资源 | 是否需密钥 | 备注 |
|------|------|-----------|------|
| 赛程 & 历史结果 | [openfootball/worldcup.json](https://github.com/openfootball/worldcup.json) via [jsDelivr](https://www.jsdelivr.com/) | 否 | 真实开源数据 |
| 实时赔率(可选) | [The Odds API](https://the-odds-api.com/) | 是(免费档) | ~500 请求/月；不配置则用模拟 |
| 后端托管 | [Render.com](https://render.com/) Free Web Service | — | 免费档闲置会休眠，见"唤醒策略" |
| 前端托管 | [GitHub Pages](https://pages.github.com/) 或 [Netlify](https://www.netlify.com/) | — | 免费静态托管 |
| 定时任务 | APScheduler (进程内) 或 Render Cron | — | 免费档建议用进程内调度 |
| 图表库 | [Chart.js](https://www.chartjs.org/), [Plotly.js](https://plotly.com/javascript/) | 否 | CDN 引入 |
| UI 框架 | [Bootstrap 5](https://getbootstrap.com/) | 否 | CDN 引入 |
| 字体 | [Inter](https://fonts.google.com/specimen/Inter) via Google Fonts | 否 | — |

---

## 🚀 部署指南

### A. 后端 → Render.com

1. 把本仓库推到你的 GitHub。
2. Render Dashboard → **New +** → **Web Service** → 连接该仓库。
3. 配置：
   - **Root Directory:** `backend`
   - **Runtime:** Python 3
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
4. **Environment** 标签页添加环境变量：

   | Key | Value | 说明 |
   |-----|-------|------|
   | `ACCESS_PASSWORD` | `你的访问密码` | **必填**，App 门禁密码 |
   | `ODDS_API_KEY` | `你的key` | 可选，不填则用模拟赔率 |
   | `ALLOWED_ORIGINS` | `https://你的前端域名` | CORS 白名单 (逗号分隔) |
   | `SECRET_KEY` | `随机长字符串` | 用于会话令牌签名 |

5. 部署完成后记下后端 URL，例如 `https://worldcup2026-api.onrender.com`。

### B. 前端 → GitHub Pages

1. 编辑 `frontend/config.js`，把 `API_BASE` 改成你的 Render 后端 URL。
2. 仓库 **Settings → Pages → Source** 选择 `main` 分支的 `/frontend` 目录（或将 `frontend/` 内容放到单独仓库根目录）。
3. 访问 GitHub 给出的 Pages 网址即可。

> Netlify 替代方案：拖拽 `frontend/` 文件夹到 Netlify Drop，或连接仓库设 publish 目录为 `frontend`。

### C. 唤醒策略 (Render 免费档休眠问题)

Render 免费 Web Service 闲置 ~15 分钟会休眠，首个请求需 ~30-50 秒冷启动。应对：
- 前端登录页内置"正在唤醒后端服务…"友好加载态（已实现）。
- 可选：用免费的 [cron-job.org](https://cron-job.org/) 每 10 分钟 ping 一次 `/api/health` 保活。

> 📖 **遇到部署问题？** 请查阅 [`DEPLOYMENT.md`](./DEPLOYMENT.md)，内含 CORS、冷启动、API 配额、登录、缓存等常见问题的排错清单与自检命令。

---

## 🔧 本地开发

```bash
# 后端
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ACCESS_PASSWORD=test123                       # Windows: set ACCESS_PASSWORD=test123
uvicorn main:app --reload --port 8000

# 前端 (另开终端)
cd frontend
# 把 config.js 的 API_BASE 设为 http://localhost:8000
python -m http.server 5500
# 浏览器打开 http://localhost:5500
```

---

## 🧪 方法学透明度

- **泊松模型**：以两队进攻/防守强度估计期望进球，构建比分概率矩阵。
- **市场模型**：将多家赔率取中位数 → 去除抽水(overround) → 得到市场共识隐含概率。
- **贝叶斯融合**：以市场共识为先验，统计模型为似然，加权得到后验概率。
- **DTW 相似度**：对赔率时间序列做动态时间规整，距离越小越相似。
- **蒙特卡洛**：按单场胜平负概率反复抽样推演整个淘汰赛，统计夺冠频率。
- **自进化权重**：用历史 Brier Score / 命中率反向调整各模型在集成中的权重。

所有概率均为**估计值**，存在模型误差与数据局限。详见 App 内"关于"页。

---

## 📄 License

MIT — 仅供学习与娱乐使用。
