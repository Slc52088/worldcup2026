"""
optimizer.py
自进化权重优化器。

原理：对每个基础模型，用其历史预测与真实结果计算 Brier Score (越低越好) 与
命中率 (argmax 是否命中)。将各模型权重设为 (1 - 归一化Brier) 的函数，
表现越好权重越高。提供优化依据文本供前端展示。

Brier Score (多分类) = Σ (p_i - o_i)^2,  o_i 为实际结果 one-hot。
"""
from __future__ import annotations
from data import store


def _brier(p_home, p_draw, p_away, outcome) -> float:
    o = {"home": (1, 0, 0), "draw": (0, 1, 0), "away": (0, 0, 1)}[outcome]
    return (p_home - o[0]) ** 2 + (p_draw - o[1]) ** 2 + (p_away - o[2]) ** 2


def _hit(p_home, p_draw, p_away, outcome) -> bool:
    pred = max([("home", p_home), ("draw", p_draw), ("away", p_away)], key=lambda x: x[1])[0]
    return pred == outcome


def evaluate_and_optimize() -> dict:
    rows = store.get_predictions_with_results()
    if not rows:
        return {
            "updated": False,
            "note": "尚无已结算的历史预测，权重保持默认。随着比赛结果累积，系统将自动学习并再平衡。",
            "weights": {"poisson": 0.45, "market": 0.55},
            "per_model": {},
        }

    agg = {}  # model -> {briers:[], hits:[]}
    for r in rows:
        m = r["model"]
        agg.setdefault(m, {"briers": [], "hits": []})
        b = _brier(r["p_home"], r["p_draw"], r["p_away"], r["outcome"])
        h = _hit(r["p_home"], r["p_draw"], r["p_away"], r["outcome"])
        agg[m]["briers"].append(b)
        agg[m]["hits"].append(1 if h else 0)

    per_model = {}
    scores = {}
    for m, d in agg.items():
        n = len(d["briers"])
        mean_brier = sum(d["briers"]) / n
        hit_rate = sum(d["hits"]) / n
        # 分数：Brier 越低越好 (最大 2.0)，转成 0..1 的"好"度
        goodness = max(0.0, 1.0 - mean_brier / 2.0)
        scores[m] = goodness
        per_model[m] = {"n": n, "brier": round(mean_brier, 4),
                        "hit_rate": round(hit_rate, 4), "goodness": round(goodness, 4)}

    total = sum(scores.values()) or 1.0
    weights = {m: round(s / total, 4) for m, s in scores.items()}

    # 持久化
    for m in weights:
        store.set_model_weight(m, weights[m], per_model[m]["brier"], per_model[m]["hit_rate"])

    best = max(per_model, key=lambda m: per_model[m]["goodness"]) if per_model else None
    note = (
        f"已基于 {len(rows)} 条已结算预测重新评估各模型。"
        + (f"表现最佳的是 {best} (命中率 {per_model[best]['hit_rate']*100:.0f}%、"
           f"Brier {per_model[best]['brier']})，其集成权重相应上调。" if best else "")
        + " 系统将随每场结果持续自我校准。"
    )

    return {"updated": True, "note": note, "weights": weights, "per_model": per_model}
