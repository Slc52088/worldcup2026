/**
 * app.js — 路由 / 认证 / API 调用 / 页面渲染
 */
(function () {
  "use strict";
  const CFG = window.APP_CONFIG;
  const API = CFG.API_BASE.replace(/\/$/, "");
  const C = window.WCCharts;

  // ---------- 认证存储 ----------
  const TOKEN_KEY = "wc_token";
  const REMEMBER_KEY = "wc_remember";
  function getToken() {
    return localStorage.getItem(REMEMBER_KEY) === "1"
      ? localStorage.getItem(TOKEN_KEY)
      : sessionStorage.getItem(TOKEN_KEY);
  }
  function setToken(token, remember) {
    if (remember) {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(REMEMBER_KEY, "1");
    } else {
      sessionStorage.setItem(TOKEN_KEY, token);
      localStorage.removeItem(REMEMBER_KEY);
    }
  }
  function clearToken() {
    sessionStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REMEMBER_KEY);
  }

  // ---------- API 封装 ----------
  async function api(path, opts = {}) {
    const headers = Object.assign({ "Content-Type": "application/json" }, opts.headers || {});
    const token = getToken();
    if (token) headers["Authorization"] = "Bearer " + token;
    const res = await fetch(API + path, Object.assign({}, opts, { headers }));
    if (res.status === 401) {
      clearToken();
      showLock("会话已过期，请重新登录");
      throw new Error("unauthorized");
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(data.detail || "请求失败");
    return data;
  }

  // ---------- DOM 工具 ----------
  const $ = (sel) => document.querySelector(sel);
  const el = (id) => document.getElementById(id);
  function tpl(id) {
    return document.getElementById(id).content.cloneNode(true);
  }
  function fmtTime(iso) {
    if (!iso) return "";
    try { return new Date(iso).toLocaleString("zh-CN", { hour12: false }); }
    catch (e) { return iso; }
  }
  function pct(v) { return (v * 100).toFixed(1) + "%"; }

  // 概率三段条
  function probBar(p) {
    const h = (p.p_home * 100).toFixed(1), d = (p.p_draw * 100).toFixed(1), a = (p.p_away * 100).toFixed(1);
    return `
      <div class="prob-labels">
        <span class="text-dim">主胜 ${h}%</span>
        <span class="text-dim">平 ${d}%</span>
        <span class="text-dim">客胜 ${a}%</span>
      </div>
      <div class="prob-bar">
        <div class="prob-segment home" style="width:${h}%"></div>
        <div class="prob-segment draw" style="width:${d}%"></div>
        <div class="prob-segment away" style="width:${a}%"></div>
      </div>`;
  }

  function tip(text) {
    return `<span class="tooltip-trigger" data-tip="${text.replace(/"/g, "&quot;")}">?</span>`;
  }

  // ============ 密码锁 ============
  function showLock(errMsg) {
    el("boot-loading").style.display = "none";
    el("app").style.display = "none";
    const lock = el("lock-screen");
    lock.style.display = "flex";
    const errEl = el("lock-error");
    if (errMsg) {
      errEl.textContent = errMsg;
      const card = lock.querySelector(".lock-card");
      card.classList.remove("shake"); void card.offsetWidth; card.classList.add("shake");
    } else {
      errEl.textContent = "";
    }
  }

  async function doLogin() {
    const pw = el("lock-input").value;
    const remember = el("lock-remember").checked;
    if (!pw) { showLock("请输入密码"); return; }
    const btn = el("lock-btn");
    btn.disabled = true; btn.textContent = "验证中…";
    try {
      const res = await fetch(API + "/api/verify-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: pw, remember }),
      });
      const data = await res.json().catch(() => ({}));
      if (res.ok && data.success) {
        setToken(data.token, remember);
        el("lock-screen").style.display = "none";
        bootApp();
      } else {
        showLock(data.detail || "密码错误");
      }
    } catch (e) {
      showLock("无法连接服务器，请稍后再试");
    } finally {
      btn.disabled = false; btn.textContent = "进入系统";
    }
  }

  // ============ 路由 ============
  const routes = {
    home: renderHome,
    detail: renderDetail,
    champion: renderChampion,
    heat: renderHeat,
    dashboard: renderDashboard,
    about: renderAbout,
  };

  function go(route, param) {
    location.hash = param ? `#/${route}/${param}` : `#/${route}`;
  }

  function parseHash() {
    const h = location.hash.replace(/^#\//, "");
    const [route, param] = h.split("/");
    return { route: routes[route] ? route : "home", param };
  }

  async function router() {
    const { route, param } = parseHash();
    document.querySelectorAll(".nav-link").forEach((a) => {
      a.classList.toggle("active", a.dataset.route === route);
    });
    const view = el("view");
    view.style.opacity = "0";
    setTimeout(async () => {
      view.innerHTML = "";
      try {
        await routes[route](view, param);
      } catch (e) {
        if (e.message !== "unauthorized") {
          view.innerHTML = `<div class="glass alert-error">加载失败：${e.message}</div>`;
        }
      }
      view.style.opacity = "1";
    }, 150);
  }

  // ============ 骨架屏 ============
  function skeletonGrid(n = 6) {
    let s = "";
    for (let i = 0; i < n; i++) s += `<div class="skel-card skeleton"></div>`;
    return s;
  }

  // ============ 首页 ============
  let _allMatches = [];
  async function renderHome(view) {
    view.appendChild(tpl("tpl-home"));
    el("matches-grid").innerHTML = skeletonGrid();
    const data = await api("/api/matches");
    _allMatches = data.matches;
    el("home-updated").textContent = "更新于 " + fmtTime(data.last_updated);
    if (data.meta && data.meta.note) {
      el("home-updated").textContent += " · " + data.meta.note;
    }
    buildDateFilter(_allMatches);
    renderMatchCards(_allMatches);
  }

  function buildDateFilter(matches) {
    const dates = [...new Set(matches.map((m) => (m.kickoff || "").slice(0, 10)))].filter(Boolean).sort();
    const bar = el("date-filter");
    bar.innerHTML = `<button class="btn-ghost active" data-date="all">全部</button>` +
      dates.map((d) => `<button class="btn-ghost" data-date="${d}">${d.slice(5)}</button>`).join("");
    bar.querySelectorAll("button").forEach((b) => {
      b.onclick = () => {
        bar.querySelectorAll("button").forEach((x) => x.classList.remove("active"));
        b.classList.add("active");
        const d = b.dataset.date;
        renderMatchCards(d === "all" ? _allMatches : _allMatches.filter((m) => (m.kickoff || "").startsWith(d)));
      };
    });
  }

  function renderMatchCards(matches) {
    const grid = el("matches-grid");
    if (!matches.length) { grid.innerHTML = `<div class="empty">暂无比赛</div>`; return; }
    grid.innerHTML = matches.map((m) => {
      const heat = m.heat_index != null ? m.heat_index : 0;
      const hot = heat >= 60 ? `<span class="badge badge-hot">🔥 大热</span>` : "";
      const realBadge = m.is_real_odds
        ? `<span class="badge badge-real">真实赔率</span>`
        : `<span class="badge badge-sim">模拟赔率</span>`;
      return `
      <div class="match-card glass" data-id="${m.id}">
        <div class="match-card-band"></div>
        <div class="card-badges">${hot}${realBadge}</div>
        <div class="match-meta">${m.round || "小组赛"} · ${fmtTime(m.kickoff)}</div>
        <div class="match-teams">
          <div class="team">
            <div class="team-flag">${m.home_flag || "🏳️"}</div>
            <div class="team-name">${m.home}</div>
          </div>
          <div class="match-vs">VS</div>
          <div class="team">
            <div class="team-flag">${m.away_flag || "🏳️"}</div>
            <div class="team-name">${m.away}</div>
          </div>
        </div>
        ${m.preview ? probBar(m.preview) : ""}
      </div>`;
    }).join("");
    grid.querySelectorAll(".match-card").forEach((c) => {
      c.onclick = () => go("detail", c.dataset.id);
    });
  }

  // ============ 比赛详情 ============
  async function renderDetail(view, matchId) {
    view.appendChild(tpl("tpl-detail"));
    const root = el("detail-root");
    root.innerHTML = `<div class="full-loading" style="position:static;height:40vh;"><div class="spinner"></div></div>`;
    const d = await api("/api/matches/" + matchId);
    const m = d.match, pred = d.prediction, sent = d.sentiment, bet = d.betting;
    const realBadge = d.odds.is_real
      ? `<span class="badge badge-real">真实赔率</span>`
      : `<span class="badge badge-sim">模拟赔率</span>`;
    const alertBadge = (sent.alert && sent.alert.level !== "none")
      ? `<span class="badge badge-steam">⚡ 临场异动·${sent.alert.level === "high" ? "强" : sent.alert.level === "medium" ? "中" : "弱"}</span>` : "";
    const valueBadge = bet.verdict.has_value ? `<span class="badge badge-value">💎 价值投注</span>` : "";

    root.innerHTML = `
      <a class="btn-ghost" id="back-btn">← 返回</a>
      <div class="detail-header glass" style="margin-top:16px;padding:24px;">
        <div class="card-badges">${realBadge}${alertBadge}${valueBadge}</div>
        <div class="match-meta">${m.round || "小组赛"} · ${fmtTime(m.kickoff)}</div>
        <div class="match-teams" style="margin-top:8px;">
          <div class="team"><div class="team-flag">${m.home_flag}</div><div class="team-name">${m.home}</div></div>
          <div class="match-vs">VS</div>
          <div class="team"><div class="team-flag">${m.away_flag}</div><div class="team-name">${m.away}</div></div>
        </div>
      </div>

      <div class="detail-grid">
        <!-- 预测结果 -->
        <div class="detail-section glass">
          <h2>预测结果</h2>
          ${probBar(pred.final)}
          <canvas id="wdl-chart" height="200" style="margin-top:16px;"></canvas>
          <p class="rationale">${pred.summary}</p>
          <details class="weight-details">
            <summary>查看预测细节（各模型权重贡献）</summary>
            <div style="margin-top:12px;">
              ${pred.components.map((c) => `
                <div class="weight-row">
                  <span class="weight-name">${c.model === "poisson" ? "泊松统计" : c.model === "market" ? "市场共识" : c.model}</span>
                  <div class="weight-bar"><div style="width:${c.weight * 100}%"></div></div>
                  <span class="weight-pct">${(c.weight * 100).toFixed(0)}%</span>
                </div>
                <p class="rationale" style="font-size:.82rem;margin:4px 0 12px;">${c.rationale}</p>
              `).join("")}
              ${pred.adjustments.map((a) => `<p class="rationale" style="font-size:.82rem;"><b>${a.source}修正：</b>${a.text}</p>`).join("")}
            </div>
          </details>
        </div>

        <!-- 最可能比分 -->
        <div class="detail-section glass">
          <h2>最可能比分 Top 3</h2>
          ${pred.top_scores.map((s, i) => `
            <div class="scoreline-row">
              <span class="scoreline-score ${i === 0 ? "text-gold" : ""}">${s.score}</span>
              <div class="prob-bar" style="flex:1;margin:0 12px;">
                <div class="prob-segment home" style="width:${Math.min(100, s.prob * 100 * 3)}%"></div>
              </div>
              <span class="scoreline-prob">${pct(s.prob)}</span>
            </div>`).join("")}
        </div>

        <!-- 市场热度仪表盘 -->
        <div class="detail-section glass">
          <h2>市场热度仪表盘</h2>
          ${renderSentiment(sent)}
        </div>

        <!-- 赔率走势 -->
        <div class="detail-section glass">
          <h2>赔率走势（隐含概率）</h2>
          ${d.odds.history && d.odds.history.length
            ? `<canvas id="odds-chart" height="220"></canvas>`
            : `<p class="text-muted">本场暂无赔率历史数据。</p>`}
        </div>

        <!-- 历史相似比赛 -->
        <div class="detail-section glass">
          <h2>盘赔历史相似比赛</h2>
          <p class="rationale">${d.pattern_matches.rationale}</p>
          ${(d.pattern_matches.matches || []).map((p) => `
            <div class="pattern-item">
              <div>
                <div>${p.teams}</div>
                <div class="text-dim" style="font-size:.8rem;">${p.label}</div>
              </div>
              <span class="pattern-result ${p.result}">${p.result === "home" ? "主胜" : p.result === "draw" ? "平局" : "客胜"}</span>
              <span class="pattern-similarity">相似度 ${(p.similarity * 100).toFixed(0)}%</span>
            </div>`).join("")}
          ${d.pattern_matches.adjustment_hint ? `<p class="rationale"><b>方向提示：</b>${d.pattern_matches.adjustment_hint.text}</p>` : ""}
        </div>

        <!-- 双方近期对比 -->
        <div class="detail-section glass">
          <h2>双方近期数据对比</h2>
          <canvas id="radar-chart" height="240"></canvas>
          <div class="kpi-row" style="margin-top:12px;">
            ${formKpi(d.team_form.home)}
            ${formKpi(d.team_form.away)}
          </div>
        </div>

        <!-- 投注建议 -->
        <div class="detail-section glass" style="grid-column:1/-1;">
          <h2>价值投注建议</h2>
          <div class="value-bet-box ${bet.verdict.has_value ? "has-value" : ""}">
            <div class="value-bet-headline ${bet.verdict.has_value ? "text-gold" : ""}">${bet.verdict.headline}</div>
            <div class="value-bet-reason">${bet.verdict.reason}</div>
          </div>
          <div class="bet-outcome-list" style="margin-top:16px;">
            ${bet.all_outcomes.map((o) => `
              <div class="bet-outcome-row">
                <span class="bet-label">${o.label}</span>
                <span class="mono bet-probs">模型 ${o.model_prob}% / 隐含 ${o.implied_prob}%</span>
                <span class="mono bet-edge ${o.edge_pct > 0 ? "text-gold" : "text-dim"}">价值 ${o.edge_pct > 0 ? "+" : ""}${o.edge_pct}%</span>
                <span class="mono bet-ev">EV ${o.ev}</span>
              </div>`).join("")}
          </div>
          <p class="risk-note">${bet.verdict.risk_note}</p>
        </div>
      </div>
      <div class="last-updated">更新于 ${fmtTime(d.last_updated)} · 数据源：${d.odds.source}</div>
    `;

    el("back-btn").onclick = () => go("home");
    // 渲染图表
    C.renderWinDrawLoss("wdl-chart", pred.final);
    if (d.odds.history && d.odds.history.length) C.renderOddsHistory("odds-chart", d.odds.history);
    C.renderFormRadar("radar-chart", d.team_form.home, d.team_form.away);
    if (sent.money_distribution) C.renderMoneyDistribution("money-chart", sent.money_distribution);
    bindTooltips();
  }

  function renderSentiment(sent) {
    if (!sent.money_distribution) {
      return `<p class="text-muted">${sent.note || "热度数据暂不可用"}</p>`;
    }
    const ex = sent.explanations || {};
    const div = sent.divergence || {};
    return `
      <div class="kpi-row">
        <div class="kpi">
          <div class="kpi-label">冷热指数 ${tip(ex.heat_index || "")}</div>
          <div class="kpi-value text-gold">${sent.heat_index ?? "-"}</div>
          <div class="kpi-sub">盘面活跃度 0-100</div>
        </div>
        <div class="kpi">
          <div class="kpi-label">赔量背离 ${tip(ex.divergence || "")}</div>
          <div class="kpi-value">${div.value ?? "-"}</div>
          <div class="kpi-sub">方向：${div.direction || "-"}</div>
        </div>
      </div>
      <div class="kpi-label" style="margin-top:16px;">资金分布（反推）${tip(ex.money_distribution || "")}</div>
      <canvas id="money-chart" height="120" style="margin-top:8px;"></canvas>
      ${sent.alert && sent.alert.alerts && sent.alert.alerts.length
        ? `<div class="value-bet-box" style="margin-top:12px;"><div class="value-bet-reason">⚡ ${sent.alert.alerts[0].text}</div></div>`
        : ""}
    `;
  }

  function formKpi(f) {
    const last5 = (f.last5 || []).map((r) =>
      `<span class="form-dot form-${r}">${r}</span>`).join("");
    return `
      <div class="kpi">
        <div class="kpi-label">${f.team}</div>
        <div class="kpi-sub">场均进 ${f.avg_goals_for} / 失 ${f.avg_goals_against} · Elo ${f.elo}</div>
        <div style="margin-top:6px;">${last5}</div>
      </div>`;
  }

  // ============ 树节点点击：球队晋级路径弹层 ============
  async function showTeamPath(team) {
    const paths = window._bracketPaths || {};
    const info = paths[team];
    if (!info) return;
    // 关闭已有弹层
    document.querySelectorAll(".team-path-modal, .modal-backdrop").forEach((e) => e.remove());

    // 找该队的真实赛程（若尚未加载过比赛列表，则懒加载一次）
    if (!_allMatches || !_allMatches.length) {
      try {
        const data = await api("/api/matches");
        _allMatches = data.matches;
      } catch (e) { /* 忽略，按无赛程处理 */ }
    }
    const related = (_allMatches || []).filter(
      (m) => m.home === team || m.away === team
    );

    const stagesHtml = info.stages.map((s) => {
      const w = Math.min(100, s.prob);
      return `<div class="path-stage">
        <span class="path-round">${s.round}</span>
        <div class="prob-bar" style="flex:1;margin:0 10px;">
          <div class="prob-segment home" style="width:${w}%"></div>
        </div>
        <span class="path-prob mono">${s.prob}%</span>
      </div>`;
    }).join("");

    const relatedHtml = related.length
      ? `<div class="path-related">
          <div class="text-muted" style="font-size:.82rem;margin-bottom:8px;">该队的真实赛程：</div>
          ${related.map((m) => `
            <a class="path-match-link" data-id="${m.id}">
              ${m.home_flag} ${m.home} vs ${m.away} ${m.away_flag}
              <span class="text-dim">${fmtTime(m.kickoff)}</span>
            </a>`).join("")}
        </div>`
      : `<div class="path-related text-dim" style="font-size:.82rem;">当前赛程列表中暂无该队的具体场次。</div>`;

    const backdrop = document.createElement("div");
    backdrop.className = "modal-backdrop";
    const modal = document.createElement("div");
    modal.className = "team-path-modal glass";
    modal.innerHTML = `
      <div class="path-header">
        <span style="font-size:1.8rem;">${info.flag}</span>
        <div>
          <div class="path-team-name">${info.team}</div>
          <div class="text-dim" style="font-size:.8rem;">Elo ${info.elo} · 晋级各轮概率</div>
        </div>
        <button class="path-close btn-ghost">×</button>
      </div>
      <div class="path-stages">${stagesHtml}</div>
      ${relatedHtml}
      <p class="text-dim" style="font-size:.75rem;margin-top:12px;">
        说明：以上为基于实力的示意性淘汰赛模拟概率，非真实对阵。
      </p>`;

    document.body.appendChild(backdrop);
    document.body.appendChild(modal);
    const close = () => { backdrop.remove(); modal.remove(); };
    backdrop.onclick = close;
    modal.querySelector(".path-close").onclick = close;
    modal.querySelectorAll(".path-match-link").forEach((a) => {
      a.onclick = () => { close(); go("detail", a.dataset.id); };
    });
  }

  // ============ 冠军之路 ============
  async function renderChampion(view) {
    view.appendChild(tpl("tpl-champion"));
    el("podium").innerHTML = `<div class="spinner"></div>`;
    const d = await api("/api/champion");
    el("champion-note").textContent = d.confidence_note;
    el("champion-updated").textContent = "更新于 " + fmtTime(d.last_updated);
    const top3 = d.champion.slice(0, 3);
    const order = [1, 0, 2]; // 银-金-铜 视觉排列
    const tierMap = { 1: "gold", 2: "silver", 3: "bronze" };
    el("podium").innerHTML = order.map((idx) => {
      const t = top3[idx]; if (!t) return "";
      const rank = idx + 1;
      const tier = tierMap[rank];
      const medal = rank === 1 ? "🥇" : rank === 2 ? "🥈" : "🥉";
      return `<div class="podium-card ${tier} glass">
        <div class="crown">${medal}</div>
        <span class="flag">${t.flag}</span>
        <div class="name">${t.team}</div>
        <div class="prob">${t.prob}%</div>
        <div class="kpi-sub">${rank === 1 ? "夺冠" : rank === 2 ? "亚军" : "季军"}概率</div>
      </div>`;
    }).join("");
    C.renderChampionBar("champion-chart", d.champion);
    if (d.bracket) {
      el("bracket-note").textContent = d.bracket.note || "";
      C.renderBracket("bracket-tree", d.bracket, showTeamPath);
    }
    el("champion-ranking").innerHTML = d.semifinal.slice(0, 16).map((s, i) => {
      const champ = d.champion.find((c) => c.team === s.team) || { prob: 0 };
      return `<div class="champ-rank-row">
        <span class="heat-rank">${i + 1}</span>
        <span class="champ-team">${s.flag} ${s.team}</span>
        <span class="mono">进四强 ${s.prob}%</span>
        <span class="mono text-gold">夺冠 ${champ.prob}%</span>
      </div>`;
    }).join("");
  }

  // ============ 热度总览 ============
  async function renderHeat(view) {
    view.appendChild(tpl("tpl-heat"));
    el("heat-list").innerHTML = `<div class="spinner"></div>`;
    const d = await api("/api/market-overview");
    el("heat-updated").textContent = "更新于 " + fmtTime(d.last_updated);
    el("heat-list").innerHTML = d.rankings.map((r, i) => {
      const lvl = r.alert_level;
      const badge = lvl !== "none"
        ? `<span class="badge badge-steam">⚡ ${lvl === "high" ? "强异动" : lvl === "medium" ? "中异动" : "弱异动"}</span>` : "";
      return `<div class="heat-row glass" data-id="${r.id}">
        <span class="heat-rank">${i + 1}</span>
        <div class="heat-match-info">
          <div>${r.home_flag} ${r.home} <span class="text-dim">vs</span> ${r.away} ${r.away_flag}</div>
          <div class="text-dim" style="font-size:.8rem;">${fmtTime(r.kickoff)}</div>
        </div>
        <div class="heat-meter"><div style="width:${r.heat_index}%"></div></div>
        <span class="heat-value text-gold">${r.heat_index}</span>
        ${badge}
      </div>`;
    }).join("");
    el("heat-list").querySelectorAll(".heat-row").forEach((row) => {
      row.onclick = () => go("detail", row.dataset.id);
    });
  }

  // ============ 数据仪表盘 ============
  async function renderDashboard(view) {
    view.appendChild(tpl("tpl-dashboard"));
    const d = await api("/api/dashboard");
    el("dashboard-updated").textContent = "更新于 " + fmtTime(d.last_updated);
    const opt = d.optimizer || {};
    const perModel = opt.per_model || {};
    const weights = d.model_weights || {};
    el("dashboard-kpis").innerHTML = Object.keys(weights).length
      ? Object.entries(weights).map(([m, w]) => `
        <div class="kpi">
          <div class="kpi-label">${m === "poisson" ? "泊松统计" : m === "market" ? "市场共识" : m}</div>
          <div class="kpi-value text-gold">${(w * 100).toFixed(0)}%</div>
          <div class="kpi-sub">${perModel[m] ? `命中率 ${(perModel[m].hit_rate * 100).toFixed(0)}% · Brier ${perModel[m].brier}` : "权重"}</div>
        </div>`).join("")
      : `<div class="kpi"><div class="kpi-label">状态</div><div class="kpi-value">学习中</div><div class="kpi-sub">等待比赛结果累积</div></div>`;
    el("weight-list").innerHTML = Object.entries(weights).map(([m, w]) => `
      <div class="weight-row">
        <span class="weight-name">${m === "poisson" ? "泊松统计" : m === "market" ? "市场共识" : m}</span>
        <div class="weight-bar"><div style="width:${w * 100}%"></div></div>
        <span class="weight-pct">${(w * 100).toFixed(0)}%</span>
      </div>`).join("") || `<p class="text-muted">暂无权重数据</p>`;
    el("optimizer-note").textContent = opt.note || "系统将随比赛结果自动优化。";

    // 赛事数据源发现
    try {
      const ev = await api("/api/odds-events");
      const host = el("odds-events");
      const srcBadge = ev.is_real
        ? `<span class="badge badge-real">真实 · ${ev.source}</span>`
        : `<span class="badge badge-sim">模拟引擎</span>`;
      let html = `<div style="margin-bottom:12px;">${srcBadge}</div>`;
      if (ev.error) {
        html += `<p class="text-muted">⚠️ ${ev.error}</p>`;
      } else if (ev.events && ev.events.length) {
        html += `<p class="rationale">${ev.note || ""}</p><div class="ranking-list">` +
          ev.events.map((e) => `<div class="champ-rank-row">
            <span class="champ-team">${e.home_team} vs ${e.away_team}</span>
            <span class="mono text-dim">${fmtTime(e.commence_time)}</span>
            <span class="mono text-gold">${e.bookmaker_count} 家盘口</span>
          </div>`).join("") + `</div>`;
      } else {
        html += `<p class="text-muted">${ev.note || "暂无可用赛事。"}</p>`;
      }
      host.innerHTML = html;
    } catch (e) {
      el("odds-events").innerHTML = `<p class="text-muted">赛事发现数据加载失败。</p>`;
    }
  }

  // ============ 关于 ============
  async function renderAbout(view) {
    view.appendChild(tpl("tpl-about"));
    el("about-version").textContent = CFG.VERSION || "1.0";
  }

  // ============ 工具提示绑定 ============
  function bindTooltips() {
    document.querySelectorAll(".tooltip-trigger").forEach((t) => {
      t.onclick = (e) => {
        e.stopPropagation();
        document.querySelectorAll(".tooltip-pop").forEach((p) => p.remove());
        const pop = document.createElement("div");
        pop.className = "tooltip-pop glass";
        pop.textContent = t.dataset.tip;
        document.body.appendChild(pop);
        const r = t.getBoundingClientRect();
        pop.style.left = Math.min(window.innerWidth - 280, r.left) + "px";
        pop.style.top = (r.bottom + window.scrollY + 8) + "px";
        setTimeout(() => document.addEventListener("click", () => pop.remove(), { once: true }), 0);
      };
    });
  }

  // ============ 启动 ============
  function bootApp() {
    el("boot-loading").style.display = "none";
    el("lock-screen").style.display = "none";
    el("app").style.display = "block";
    window.addEventListener("hashchange", router);
    if (!location.hash) location.hash = "#/home";
    else router();
    // 导航绑定
    document.querySelectorAll("[data-route]").forEach((a) => {
      if (a.classList.contains("nav-brand")) a.onclick = () => go("home");
    });
    el("logout-btn").onclick = () => { clearToken(); location.hash = ""; showLock(); };
  }

  async function init() {
    // 锁屏交互
    el("lock-btn").onclick = doLogin;
    el("lock-input").addEventListener("keydown", (e) => { if (e.key === "Enter") doLogin(); });

    const token = getToken();
    if (!token) { showLock(); return; }
    // 已有令牌：唤醒后端并验证
    el("boot-loading").style.display = "flex";
    try {
      await api("/api/health");
      bootApp();
    } catch (e) {
      if (e.message === "unauthorized") return; // showLock 已触发
      showLock("无法连接服务器，请稍后再试");
    }
  }

  document.addEventListener("DOMContentLoaded", init);

  // PWA Service Worker 注册
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").catch(() => {});
    });
  }
})();
