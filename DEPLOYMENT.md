# 🛠️ 部署排错清单 (Troubleshooting Guide)

本文件汇总部署本项目时最常见的问题及解决方案。按"症状 → 原因 → 解决"组织,遇到问题时按 Ctrl+F 搜索关键词。

---

## 目录
1. [CORS 跨域错误](#1-cors-跨域错误)
2. [Render 免费档冷启动 / 休眠](#2-render-免费档冷启动--休眠)
3. [The Odds API 配额 / 401 / 429](#3-the-odds-api-配额--401--429)
4. [登录 / 密码相关](#4-登录--密码相关)
5. [前端连不上后端](#5-前端连不上后端)
6. [赛程为空 / 显示"模拟"数据](#6-赛程为空--显示模拟数据)
7. [PWA 安装 / Service Worker](#7-pwa-安装--service-worker)
8. [数据不更新 / 缓存问题](#8-数据不更新--缓存问题)
9. [快速自检命令](#9-快速自检命令)

---

## 1. CORS 跨域错误

**症状**:浏览器控制台报 `Access to fetch ... has been blocked by CORS policy`,前端登录卡住或所有 API 请求失败。

**原因**:后端 `ALLOWED_ORIGINS` 环境变量未包含前端的真实域名。

**解决**:
1. 在 Render 后端的 **Environment** 里设置 `ALLOWED_ORIGINS` 为你的前端完整地址,例如:
   ```
   ALLOWED_ORIGINS=https://你的用户名.github.io
   ```
   - 多个域名用逗号分隔:`https://a.github.io,https://b.netlify.app`
   - **不要带末尾斜杠**(`https://x.github.io/` ❌ → `https://x.github.io` ✓)
   - GitHub Pages 项目页地址通常是 `https://用户名.github.io`(根),而非含仓库名的子路径——CORS 只看协议+域名+端口,**不看路径**,所以填到域名即可。
2. 改完环境变量后,Render 会自动重新部署。等部署完成再测试。
3. **临时排查**:把 `ALLOWED_ORIGINS` 设为 `*` 看是否恢复。若恢复,说明就是域名没配对。**生产环境请勿长期用 `*`**。

> 注意:本项目用的是无 Cookie 的 Bearer Token 认证,所以 `allow_credentials` 不是必须;但代码默认开启了它,使用 `*` 时部分浏览器会拒绝 `credentials + *` 组合。若坚持用 `*`,可在 `main.py` 把 `allow_credentials` 改为 `False`。

---

## 2. Render 免费档冷启动 / 休眠

**症状**:很久没访问后,第一次打开页面要等 30–50 秒;前端停在"正在唤醒预测引擎…"。

**原因**:Render 免费 Web Service 闲置约 15 分钟后会休眠,下次请求需冷启动。这是免费档的正常行为,**不是 bug**。

**解决 / 缓解**:
1. 前端已内置友好的"唤醒中"加载态,耐心等待即可。
2. **保活(可选)**:用免费的 [cron-job.org](https://cron-job.org/) 创建一个定时任务,每 10 分钟 GET 一次:
   ```
   https://你的后端.onrender.com/api/health
   ```
   这样服务基本不休眠。注意:这会消耗免费实例的月度运行时长,Render 免费档每月有 750 小时额度,单实例常驻够用。
3. 冷启动时后端还会跑一次 10000 次蒙特卡洛模拟(约 1–2 秒),属正常。

---

## 3. The Odds API 配额 / 401 / 429

**症状**:仪表盘"赔率数据源"显示 `API Key 无效或额度耗尽` 或 `请求过于频繁`;比赛详情里赔率徽章变成 `模拟赔率 (fallback)`。

**原因与解决**:

| 错误 | 含义 | 解决 |
|------|------|------|
| **401** | API Key 无效,或当月免费额度(约 500 次)已用完 | 检查 `ODDS_API_KEY` 是否填对;或等下月额度重置;或先不配 Key 用模拟引擎 |
| **429** | 短时间请求过多 | 本项目已内置 **10 分钟整轮缓存**,正常使用不会触发;若触发,降低 `UPDATE_INTERVAL_MINUTES` 的频率(调大数值) |
| 详情页总是 fallback | 该场比赛 The Odds API 暂未开盘 | 世界杯赛前较早时很多场次还没有盘口,属正常;临近开赛会出现 |

**省额度技巧**:
- 本项目对整轮赔率做了缓存,**所有比赛共享一次 API 请求**,不是每场各请求一次。
- `UPDATE_INTERVAL_MINUTES` 默认 30,即每 30 分钟刷新一次赔率 → 每天约 48 次 → 每月约 1440 次。**这会超出免费 500 次/月额度**。
  - 建议:把 `UPDATE_INTERVAL_MINUTES` 设为 **90 或 120**(每月约 360–480 次),留出手动访问余量。
- 不配 `ODDS_API_KEY` 时完全使用模拟引擎,**零外部请求**,适合演示。

---

## 4. 登录 / 密码相关

**症状 A**:输入正确密码仍提示"密码错误"。
- 检查 Render 后端 `ACCESS_PASSWORD` 是否设置且无多余空格。
- 注意大小写敏感。

**症状 B**:提示"尝试次数过多,请 N 秒后再试"。
- 这是防暴力破解锁定(默认 5 次失败锁 5 分钟)。等待提示的秒数,或重启后端清除内存计数。
- 可调 `MAX_FAILED_ATTEMPTS` 和 `LOCKOUT_SECONDS` 环境变量。

**症状 C**:刷新后又要重新登录。
- 没勾"记住我"时令牌存在 `sessionStorage`,关标签页即失效(设计如此)。勾选"记住我"可保持 30 天(存 `localStorage`)。
- 若勾了仍失效:检查浏览器是否禁用了本地存储 / 隐私模式。

**症状 D**:`401 未授权或会话已过期`。
- 令牌过期(默认非记住 12h / 记住 30 天),重新登录即可。
- 若 `SECRET_KEY` 在后端重启间变化(例如没设固定值),旧令牌会全部失效——**务必在 Render 设固定的 `SECRET_KEY`**。

---

## 5. 前端连不上后端

**症状**:登录按钮转圈后提示"无法连接服务器"。

**排查顺序**:
1. **`config.js` 的 `API_BASE` 是否改对**?这是最常见原因。必须是你的 Render 后端完整地址,如 `https://worldcup2026-api.onrender.com`(**无末尾斜杠**)。
2. 直接在浏览器打开 `https://你的后端/api/health`,应返回 `{"status":"ok",...}`。
   - 打不开 → 后端没部署成功或在冷启动,看 Render 日志。
3. 前端是 `https`、后端是 `http` → **混合内容**被浏览器拦截。Render 默认给 https,确保 `API_BASE` 用 `https://`。
4. 看浏览器控制台具体报错:CORS → 见第 1 节;`net::ERR` → 后端地址错或宕机。

---

## 6. 赛程为空 / 显示"模拟"数据

**症状**:首页比赛卡的来源标注是 `fallback`,或赛程看起来像示例对阵。

**原因**:`openfootball/worldcup.json` 的 2026 目录在赛前可能尚未就绪,或网络拉取失败,系统**优雅降级**到内置 32 强生成示例赛程(这是设计的容错行为,保证 App 永远可用)。

**解决**:
1. 这不影响功能演示。临近赛事、数据源就绪后会自动切换。
2. 想换数据源:改后端 `FIXTURES_URL` 环境变量指向可用的 openfootball 年份目录。
3. 想强制刷新:重启后端,或等 `UPDATE_INTERVAL_MINUTES` 周期到。

---

## 7. PWA 安装 / Service Worker

**症状 A**:没有"添加到主屏"提示。
- PWA 安装要求 **HTTPS**(GitHub Pages / Netlify 默认满足;`http://localhost` 也允许)。
- 需要有效的 `manifest.json` 和已注册的 `sw.js`(本项目已配置)。
- iOS Safari 不弹自动提示,需手动"分享 → 添加到主屏幕"。

**症状 B**:改了代码但页面还是旧的。
- Service Worker 缓存了旧资源。解决:
  1. 浏览器开发者工具 → Application → Service Workers → **Unregister**,然后硬刷新。
  2. 或在 `sw.js` 里把 `CACHE = "wc2026-v1"` 的版本号改成 `v2`,触发缓存更新。

**症状 C**:离线打不开。
- 首次访问需联网,SW 才能缓存外壳。之后离线可打开框架,但实时数据(API)离线不可用(设计如此,API 走网络优先)。

---

## 8. 数据不更新 / 缓存问题

**症状**:改了模型代码,但 `/api/champion` 等返回的还是旧结构(例如新加的字段不出现)。

**原因**:后端启动时会读取 `backend/data/cache/` 下的 JSON 缓存(为加速冷启动)。旧缓存可能缺少新字段。

**解决**:
```bash
# 本地:删缓存和数据库后重启
rm -f backend/data/cache/*.json backend/worldcup.db
# Render:缓存在容器内,重新部署(Manual Deploy → Clear build cache & deploy)即可重置
```
- 或等定时任务(`UPDATE_INTERVAL_MINUTES`)下一次刷新覆盖缓存。

> 💡 这是开发时最容易踩的坑:本项目作者在加淘汰赛树字段时,就因旧缓存导致字段不出现,删 `data/cache/` 后才正常。

---

## 9. 快速自检命令

部署后在本地终端逐条验证(把 URL 换成你的后端地址):

```bash
# 1. 后端是否存活
curl https://你的后端.onrender.com/api/health
# 期望: {"status":"ok","time":"..."}

# 2. 密码验证 (换成你的密码)
curl -X POST https://你的后端.onrender.com/api/verify-password \
  -H "Content-Type: application/json" \
  -d '{"password":"你的密码"}'
# 期望: {"success":true,"token":"..."}

# 3. 用拿到的 token 取比赛列表
TOKEN="上一步返回的token"
curl https://你的后端.onrender.com/api/matches \
  -H "Authorization: Bearer $TOKEN"
# 期望: {"matches":[...],...}

# 4. 检查当前赔率数据源
curl https://你的后端.onrender.com/api/odds-events \
  -H "Authorization: Bearer $TOKEN"
# 期望: 模拟引擎说明 或 真实赛事列表
```

---

## 还是不行?

1. **先看 Render 日志**:Dashboard → 你的服务 → Logs。Python 报错堆栈会直接显示。
2. **看浏览器控制台**(F12 → Console / Network),CORS、404、混合内容等问题一目了然。
3. 90% 的部署问题是这三类:`API_BASE` 没改对、`ALLOWED_ORIGINS` 没配、`SECRET_KEY`/`ACCESS_PASSWORD` 没设。先查这三个。
