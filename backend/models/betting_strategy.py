"""
betting_strategy.py
价值投注建议：基于模型概率与市场赔率计算期望值(EV)与凯利(Kelly)建议比例。

EV = p_model * (odd - 1) - (1 - p_model)
Kelly fraction f* = (b*p - q) / b,  其中 b = odd-1, p = p_model, q = 1-p
为稳健起见使用 1/4 Kelly。所有建议附明确风险说明。
"""
from __future__ import annotations
import statistics


def _best_odds(odds: dict) -> dict:
    """取各结果在所有博彩公司中的最优(最高)赔率。"""
    best = {"home": 0.0, "draw": 0.0, "away": 0.0}
    for bm in odds.get("bookmakers", []):
        h2h = bm.get("h2h", {})
        for k in best:
            if h2h.get(k, 0) > best[k]:
                best[k] = h2h[k]
    return best


def evaluate(final_probs: dict, odds: dict) -> dict:
    best = _best_odds(odds)
    outcomes = {"home": "主胜", "draw": "平局", "away": "客胜"}
    suggestions = []

    for key, label in outcomes.items():
        p = final_probs.get(f"p_{key}")
        odd = best.get(key, 0)
        if not p or not odd or odd <= 1:
            continue
        b = odd - 1
        ev = p * b - (1 - p)
        kelly_full = (b * p - (1 - p)) / b if b > 0 else 0
        kelly_quarter = max(0.0, kelly_full / 4.0)
        suggestions.append({
            "outcome": key,
            "label": label,
            "model_prob": round(p * 100, 1),
            "best_odd": round(odd, 2),
            "implied_prob": round(1 / odd * 100, 1),
            "edge_pct": round((p - 1 / odd) * 100, 1),  # 模型概率 - 隐含概率
            "ev": round(ev, 3),
            "kelly_quarter_pct": round(kelly_quarter * 100, 1),
        })

    # 选出 EV 最高且为正的作为推荐
    positive = [s for s in suggestions if s["ev"] > 0.03 and s["edge_pct"] > 2]
    positive.sort(key=lambda s: s["ev"], reverse=True)

    if positive:
        top = positive[0]
        verdict = {
            "has_value": True,
            "pick": top["outcome"],
            "pick_label": top["label"],
            "headline": f"价值投注：{top['label']} @ {top['best_odd']}",
            "reason": (
                f"模型估计{top['label']}概率 {top['model_prob']}%，高于市场隐含的 {top['implied_prob']}%，"
                f"存在 {top['edge_pct']}% 正向价值，期望值 EV={top['ev']}。"
                f"按 1/4 凯利建议仓位约为本金的 {top['kelly_quarter_pct']}%。"
            ),
        }
    else:
        verdict = {
            "has_value": False,
            "pick": None,
            "headline": "本场无明显价值",
            "reason": "各结果的模型概率与市场隐含概率接近，未发现稳定的正向期望，建议观望。",
        }

    verdict["risk_note"] = (
        "⚠️ 风险提示：以上为统计模型输出，仅供学习娱乐，不构成博彩建议。"
        "模型存在误差，赔率随时变化，任何投注均有损失全部本金的风险。请理性对待，量力而行。"
    )

    return {"verdict": verdict, "all_outcomes": suggestions}
