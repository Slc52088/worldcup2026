"""
ultimate_ensemble.py
最终决策融合：三层集成。

Layer 1 (基础概率): 泊松统计模型 + 市场共识模型 → 贝叶斯式加权融合。
Layer 2 (信号修正): 盘赔相似度方向提示 + 异动预警 对 L1 概率做小幅修正。
Layer 3 (动态权重): 从优化器读取各模型历史表现权重，决定 L1 中两源的混合比例。

输出：最终胜平负概率、三个最可能比分(含概率)、各组件权重贡献、整体依据。
"""
from __future__ import annotations
from models import statistical_model, market_model, odds_pattern_matcher, sentiment_alert
from data import store


DEFAULT_WEIGHTS = {"poisson": 0.45, "market": 0.55}


def _get_weights() -> dict:
    saved = store.get_model_weights()
    if saved and "poisson" in saved and "market" in saved:
        w_p = saved["poisson"]["weight"]
        w_m = saved["market"]["weight"]
        s = w_p + w_m
        if s > 0:
            return {"poisson": w_p / s, "market": w_m / s}
    return DEFAULT_WEIGHTS.copy()


def _normalize(ph, pd, pa):
    s = ph + pd + pa
    if s <= 0:
        return 1 / 3, 1 / 3, 1 / 3
    return ph / s, pd / s, pa / s


def predict(home: str, away: str, odds: dict) -> dict:
    # ---- Layer 1: 基础模型 ----
    poisson = statistical_model.predict(home, away)
    market = market_model.predict(odds)
    weights = _get_weights()

    components = [{"model": "poisson", "weight": weights["poisson"],
                   "p": (poisson["p_home"], poisson["p_draw"], poisson["p_away"]),
                   "rationale": poisson["rationale"]}]

    if market["p_home"] is not None:
        components.append({"model": "market", "weight": weights["market"],
                           "p": (market["p_home"], market["p_draw"], market["p_away"]),
                           "rationale": market["rationale"]})
    else:
        # 市场不可用时全权重给泊松
        components[0]["weight"] = 1.0

    # 加权融合
    total_w = sum(c["weight"] for c in components)
    ph = sum(c["weight"] * c["p"][0] for c in components) / total_w
    pd = sum(c["weight"] * c["p"][1] for c in components) / total_w
    pa = sum(c["weight"] * c["p"][2] for c in components) / total_w
    ph, pd, pa = _normalize(ph, pd, pa)
    base_probs = (ph, pd, pa)

    # ---- Layer 2: 信号修正 ----
    adjustments = []
    pattern = odds_pattern_matcher.match_pattern(odds)
    hint = pattern.get("adjustment_hint")
    if hint and hint.get("direction"):
        d = hint["direction"]
        bump = 0.03
        if d == "home":
            ph, pa = ph + bump, pa - bump * 0.6
        elif d == "away":
            pa, ph = pa + bump, ph - bump * 0.6
        else:
            pd = pd + bump
        ph, pd, pa = _normalize(ph, pd, pa)
        adjustments.append({"source": "盘赔相似度", "text": hint["text"]})

    alert = sentiment_alert.detect(odds)
    if alert["level"] in ("medium", "high") and alert["alerts"]:
        a = alert["alerts"][0]
        bump = 0.04 if alert["level"] == "high" else 0.02
        if a["side"] == "主队":
            ph, pa = ph + bump, pa - bump * 0.6
        else:
            pa, ph = pa + bump, ph - bump * 0.6
        ph, pd, pa = _normalize(ph, pd, pa)
        adjustments.append({"source": "临场异动", "text": a["text"]})

    final_probs = {"p_home": round(ph, 4), "p_draw": round(pd, 4), "p_away": round(pa, 4)}

    # ---- 最可能比分：以泊松 top_scores 为骨架，按最终胜平负概率轻度再加权 ----
    top_scores = _reweight_scores(poisson["top_scores"], base_probs, (ph, pd, pa))

    # ---- 组件权重贡献 (供前端"查看预测细节") ----
    contrib = [{"model": c["model"], "weight": round(c["weight"] / total_w, 3),
                "rationale": c["rationale"]} for c in components]

    summary = _build_summary(home, away, final_probs, adjustments)

    return {
        "final": final_probs,
        "top_scores": top_scores[:3],
        "components": contrib,
        "adjustments": adjustments,
        "base_probs": {"p_home": round(base_probs[0], 4),
                       "p_draw": round(base_probs[1], 4),
                       "p_away": round(base_probs[2], 4)},
        "weights_used": weights,
        "summary": summary,
        "sub_models": {
            "poisson": poisson,
            "market": market,
            "pattern": pattern,
            "alert": alert,
        },
    }


def _reweight_scores(top_scores, base, final):
    """根据最终概率相对基础概率的偏移，对比分概率做温和再加权。"""
    out = []
    for s in top_scores:
        h, a = map(int, s["score"].split("-"))
        if h > a:
            factor = final[0] / max(1e-6, base[0])
        elif h == a:
            factor = final[1] / max(1e-6, base[1])
        else:
            factor = final[2] / max(1e-6, base[2])
        out.append({"score": s["score"], "prob": s["prob"] * factor})
    tot = sum(s["prob"] for s in out) or 1.0
    for s in out:
        s["prob"] = round(s["prob"] / tot, 4)
    out.sort(key=lambda x: x["prob"], reverse=True)
    return out


def _build_summary(home, away, fp, adjustments):
    parts = [
        f"综合泊松统计与市场共识，{home} 主胜 {fp['p_home']*100:.1f}%、"
        f"平局 {fp['p_draw']*100:.1f}%、{away} 客胜 {fp['p_away']*100:.1f}%。"
    ]
    for adj in adjustments:
        parts.append(adj["text"])
    return " ".join(parts)
