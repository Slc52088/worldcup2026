/**
 * charts.js — Chart.js / Plotly 封装，统一深色主题
 */
const CHART_THEME = {
  text: "#e8ecf4",
  muted: "#9aa3b8",
  grid: "rgba(255,255,255,0.06)",
  blue: "#3fa9ff",
  green: "#19e5b6",
  gold: "#f4d676",
  red: "#ff6b81",
  amber: "#ffb648",
  font: "Inter, system-ui, sans-serif",
};

// 注册的图表实例，便于路由切换时销毁
const _charts = {};

function destroyChart(id) {
  if (_charts[id]) {
    try { _charts[id].destroy(); } catch (e) {}
    delete _charts[id];
  }
}

if (window.Chart) {
  Chart.defaults.color = CHART_THEME.muted;
  Chart.defaults.font.family = CHART_THEME.font;
  Chart.defaults.borderColor = CHART_THEME.grid;
}

/** 胜平负甜甜圈图 */
function renderWinDrawLoss(canvasId, probs, labels) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  _charts[canvasId] = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: labels || ["主胜", "平局", "客胜"],
      datasets: [{
        data: [probs.p_home * 100, probs.p_draw * 100, probs.p_away * 100],
        backgroundColor: [CHART_THEME.green, CHART_THEME.amber, CHART_THEME.red],
        borderColor: "rgba(0,0,0,0.25)",
        borderWidth: 2,
        hoverOffset: 8,
      }],
    },
    options: {
      cutout: "62%",
      plugins: {
        legend: { position: "bottom", labels: { padding: 16, usePointStyle: true } },
        tooltip: { callbacks: { label: (c) => `${c.label}: ${c.parsed.toFixed(1)}%` } },
      },
      animation: { animateRotate: true, duration: 800 },
    },
  });
}

/** 赔率走势折线（隐含概率随时间） */
function renderOddsHistory(canvasId, history) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !history || !history.length) return;
  const labels = history.map((p) => `${p.t_minus_hours}h`);
  const toImplied = (p, key) => {
    const inv = 1 / p[key];
    const s = 1 / p.home + 1 / p.draw + 1 / p.away;
    return (inv / s) * 100;
  };
  _charts[canvasId] = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "主胜", data: history.map((p) => toImplied(p, "home")), borderColor: CHART_THEME.green, backgroundColor: "transparent", tension: 0.35, borderWidth: 2.5, pointRadius: 2 },
        { label: "平局", data: history.map((p) => toImplied(p, "draw")), borderColor: CHART_THEME.amber, backgroundColor: "transparent", tension: 0.35, borderWidth: 2, pointRadius: 2 },
        { label: "客胜", data: history.map((p) => toImplied(p, "away")), borderColor: CHART_THEME.red, backgroundColor: "transparent", tension: 0.35, borderWidth: 2, pointRadius: 2 },
      ],
    },
    options: {
      scales: {
        x: { grid: { color: CHART_THEME.grid }, reverse: true, title: { display: true, text: "距开赛", color: CHART_THEME.muted } },
        y: { grid: { color: CHART_THEME.grid }, ticks: { callback: (v) => v + "%" }, title: { display: true, text: "隐含概率", color: CHART_THEME.muted } },
      },
      plugins: {
        legend: { position: "top", labels: { usePointStyle: true } },
        tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.parsed.y.toFixed(1)}%` } },
      },
      interaction: { intersect: false, mode: "index" },
    },
  });
}

/** 资金分布水平条 */
function renderMoneyDistribution(canvasId, dist) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx || !dist) return;
  _charts[canvasId] = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["主胜", "平局", "客胜"],
      datasets: [{
        data: [dist.home, dist.draw, dist.away],
        backgroundColor: [CHART_THEME.green, CHART_THEME.amber, CHART_THEME.red],
        borderRadius: 6,
        barThickness: 28,
      }],
    },
    options: {
      indexAxis: "y",
      scales: {
        x: { grid: { color: CHART_THEME.grid }, ticks: { callback: (v) => v + "%" }, max: 100 },
        y: { grid: { display: false } },
      },
      plugins: {
        legend: { display: false },
        tooltip: { callbacks: { label: (c) => `${c.parsed.x.toFixed(1)}%` } },
      },
    },
  });
}

/** 球队近期攻防雷达对比 */
function renderFormRadar(canvasId, home, away) {
  destroyChart(canvasId);
  const ctx = document.getElementById(canvasId);
  if (!ctx) return;
  const norm = (v, max) => Math.min(100, (v / max) * 100);
  _charts[canvasId] = new Chart(ctx, {
    type: "radar",
    data: {
      labels: ["进攻", "防守", "Elo实力", "近期状态"],
      datasets: [
        {
          label: home.team,
          data: [norm(home.avg_goals_for, 3), norm(3 - home.avg_goals_against, 3), norm(home.elo - 1500, 700), norm(home.record.W, 5)],
          borderColor: CHART_THEME.blue, backgroundColor: "rgba(63,169,255,0.18)", borderWidth: 2,
        },
        {
          label: away.team,
          data: [norm(away.avg_goals_for, 3), norm(3 - away.avg_goals_against, 3), norm(away.elo - 1500, 700), norm(away.record.W, 5)],
          borderColor: CHART_THEME.gold, backgroundColor: "rgba(244,214,118,0.15)", borderWidth: 2,
        },
      ],
    },
    options: {
      scales: { r: { grid: { color: CHART_THEME.grid }, angleLines: { color: CHART_THEME.grid }, pointLabels: { color: CHART_THEME.text }, ticks: { display: false, backdropColor: "transparent" }, suggestedMin: 0, suggestedMax: 100 } },
      plugins: { legend: { position: "top", labels: { usePointStyle: true } } },
    },
  });
}

/** 夺冠概率横向柱（Plotly） */
function renderChampionBar(divId, champions) {
  const el = document.getElementById(divId);
  if (!el || !window.Plotly) return;
  const top = champions.slice(0, 12).reverse();
  Plotly.newPlot(el, [{
    type: "bar",
    orientation: "h",
    x: top.map((t) => t.prob),
    y: top.map((t) => `${t.flag} ${t.team}`),
    marker: {
      color: top.map((_, i) => i === top.length - 1 ? CHART_THEME.gold : CHART_THEME.blue),
      line: { width: 0 },
    },
    text: top.map((t) => t.prob + "%"),
    textposition: "auto",
    hovertemplate: "%{y}: %{x}%<extra></extra>",
  }], {
    paper_bgcolor: "transparent",
    plot_bgcolor: "transparent",
    font: { color: CHART_THEME.muted, family: CHART_THEME.font },
    margin: { l: 130, r: 20, t: 10, b: 30 },
    xaxis: { gridcolor: CHART_THEME.grid, ticksuffix: "%", zeroline: false },
    yaxis: { automargin: true },
  }, { responsive: true, displayModeBar: false });
}

window.WCCharts = {
  renderWinDrawLoss, renderOddsHistory, renderMoneyDistribution,
  renderFormRadar, renderChampionBar, renderBracket, destroyChart,
};

/** 交互式淘汰赛树状图（纯 SVG，颜色深浅表示晋级概率，节点可点击） */
function renderBracket(containerId, bracket, onNodeClick) {
  const host = document.getElementById(containerId);
  if (!host || !bracket || !bracket.rounds) return;
  // 暴露路径数据供点击使用
  window._bracketPaths = bracket.team_paths || {};
  window._bracketRoundNames = bracket.round_names || [];

  const rounds = bracket.rounds;
  const champ = bracket.champion_candidates || [];
  const nCols = rounds.length + 1; // +冠军列
  const colW = 190, rowH = 46, gapY = 14;
  const topPad = 24; // 顶部留白给列标题
  const r0 = rounds[0].matchups.length; // 首轮对阵位数 (8)
  const totalRows = r0 * 2;             // 16 队
  const height = totalRows * (rowH + gapY) + topPad;
  const width = nCols * colW;

  // 概率 → 颜色（蓝→金渐变深浅）
  const probColor = (p) => {
    const t = Math.min(1, p / 100);
    // 低概率偏暗蓝，高概率偏金
    const c1 = [40, 60, 110], c2 = [244, 214, 118];
    const mix = c1.map((v, i) => Math.round(v + (c2[i] - v) * t));
    return `rgb(${mix[0]},${mix[1]},${mix[2]})`;
  };
  const textColor = (p) => (p / 100 > 0.45 ? "#0b1020" : "#e8ecf4");

  // 计算每个节点的 y 坐标：首轮均匀分布，后续轮取相邻两节点中点
  const positions = []; // positions[col] = [{y, entry}...] (按队/对阵展开)
  // 首轮：每个对阵 2 个队
  let col0 = [];
  rounds[0].matchups.forEach((mu, mi) => {
    mu.forEach((e, ei) => {
      const idx = mi * 2 + ei;
      col0.push({ y: idx * (rowH + gapY) + rowH / 2 + topPad, entry: e });
    });
  });
  positions.push(col0);

  // 后续轮：每个对阵位 1 个"代表"节点（其实是两候选，画在该位中点，但我们逐队画概率块）
  // 为清晰起见：后续每轮我们画该轮每个对阵位的两个候选，纵向落在其来源两节点的中间区域
  for (let r = 1; r < rounds.length; r++) {
    const prev = positions[r - 1];
    const colNodes = [];
    rounds[r].matchups.forEach((mu, mi) => {
      // 该对阵位来自上一轮的 4 个源节点(2 对) -> 取其 y 跨度
      const srcStart = mi * 4;
      const ys = [];
      for (let k = 0; k < 4 && srcStart + k < prev.length; k++) ys.push(prev[srcStart + k].y);
      const center = ys.length ? ys.reduce((a, b) => a + b, 0) / ys.length : mi * (rowH + gapY);
      mu.forEach((e, ei) => {
        colNodes.push({ y: center + (ei === 0 ? -rowH * 0.7 : rowH * 0.7), entry: e, mi });
      });
    });
    positions.push(colNodes);
  }

  // 冠军列
  const lastPrev = positions[positions.length - 1];
  const champY = lastPrev.length ? lastPrev.reduce((a, b) => a + b.y, 0) / lastPrev.length : height / 2;

  // 绘制 SVG
  let svg = `<svg viewBox="0 0 ${width} ${height}" width="100%" preserveAspectRatio="xMidYMid meet" style="min-width:${width}px;">`;

  // 连接线
  for (let r = 1; r < positions.length; r++) {
    positions[r].forEach((node) => {
      // 连到上一列同对阵位的源（粗略：连到上一列纵向最近的节点）
      const prev = positions[r - 1];
      let nearest = prev[0], best = Infinity;
      prev.forEach((pn) => { const d = Math.abs(pn.y - node.y); if (d < best) { best = d; nearest = pn; } });
      const x1 = (r - 1) * colW + colW - 14;
      const x2 = r * colW + 14;
      const mx = (x1 + x2) / 2;
      svg += `<path d="M${x1} ${nearest.y} C ${mx} ${nearest.y}, ${mx} ${node.y}, ${x2} ${node.y}"
                fill="none" stroke="rgba(255,255,255,0.10)" stroke-width="1.5"/>`;
    });
  }
  // 连到冠军
  positions[positions.length - 1].forEach((node) => {
    const x1 = (positions.length - 1) * colW + colW - 14;
    const x2 = positions.length * colW + 14;
    const mx = (x1 + x2) / 2;
    svg += `<path d="M${x1} ${node.y} C ${mx} ${node.y}, ${mx} ${champY}, ${x2} ${champY}"
              fill="none" stroke="rgba(244,214,118,0.25)" stroke-width="1.5"/>`;
  });

  // 节点
  positions.forEach((col, ci) => {
    col.forEach((node) => {
      const e = node.entry;
      const x = ci * colW + 14;
      const p = e.reach_prob;
      svg += `<g class="bracket-node" data-team="${e.team}" data-prob="${p}">
        <rect x="${x}" y="${node.y - rowH / 2}" width="${colW - 28}" height="${rowH - 8}"
              rx="8" fill="${probColor(p)}" stroke="rgba(255,255,255,0.12)" stroke-width="1">
          <title>${e.team} · 到达${rounds[ci] ? rounds[ci].round : ""}概率 ${p}%</title>
        </rect>
        <text x="${x + 12}" y="${node.y - 2}" fill="${textColor(p)}" font-size="13" font-weight="600">${e.flag} ${e.team}</text>
        <text x="${x + 12}" y="${node.y + 13}" fill="${textColor(p)}" font-size="10" opacity="0.8">${p}%</text>
      </g>`;
    });
  });

  // 冠军框
  const champTop = champ[0];
  if (champTop) {
    const x = positions.length * colW + 14;
    svg += `<g class="bracket-node champion-node" data-team="${champTop.team}" data-prob="${champTop.reach_prob}">
      <rect x="${x}" y="${champY - rowH / 2}" width="${colW - 28}" height="${rowH - 8}" rx="8"
            fill="url(#goldGrad)" stroke="rgba(244,214,118,0.6)" stroke-width="1.5">
        <title>最可能夺冠：${champTop.team} ${champTop.reach_prob}%</title>
      </rect>
      <text x="${x + 12}" y="${champY - 2}" fill="#0b1020" font-size="13" font-weight="800">🏆 ${champTop.flag} ${champTop.team}</text>
      <text x="${x + 12}" y="${champY + 13}" fill="#0b1020" font-size="10" font-weight="700">夺冠 ${champTop.reach_prob}%</text>
    </g>`;
  }

  // 列标题
  svg += `<g>`;
  rounds.forEach((r, ci) => {
    svg += `<text x="${ci * colW + (colW - 28) / 2 + 14}" y="14" fill="#9aa3b8" font-size="11" text-anchor="middle">${r.round}</text>`;
  });
  svg += `<text x="${positions.length * colW + (colW - 28) / 2 + 14}" y="14" fill="#f4d676" font-size="11" text-anchor="middle">冠军</text>`;
  svg += `</g>`;

  svg += `<defs><linearGradient id="goldGrad" x1="0" y1="0" x2="1" y2="1">
    <stop offset="0%" stop-color="#f7e08a"/><stop offset="100%" stop-color="#c79a3a"/>
  </linearGradient></defs>`;
  svg += `</svg>`;

  host.innerHTML = `<div class="bracket-scroll">${svg}</div>`;

  // 绑定节点点击：弹出该队晋级路径
  host.querySelectorAll(".bracket-node[data-team]").forEach((node) => {
    node.style.cursor = "pointer";
    node.addEventListener("click", () => {
      const team = node.getAttribute("data-team");
      if (typeof onNodeClick === "function") onNodeClick(team);
    });
  });
}
