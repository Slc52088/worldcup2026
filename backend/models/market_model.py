"""
market_model.py
市场模型：多家赔率 → 去抽水 → 市场共识隐含概率。

方法：对每家博彩公司的胜平负赔率取倒数得到"含水概率"，归一化去除 overround，
再对各家取中位数得到稳健的市场共识。输出附依据。
"""
from __future__ import annotations
import statistics


def _devig(home_odd: float, draw_odd: float, away_odd: float) -> tuple[float, float, float]:
    inv = [1 / home_odd, 1 / draw_odd, 1 / away_odd]
    s = sum(inv)  # = 1 + overround
    return inv[0] / s, inv[1] / s, inv[2] / s


def predict(odds: dict) -> dict:
    bms = odds.get("bookmakers", [])
    if not bms:
        return {
            "model": "market",
            "p_home": None, "p_draw": None, "p_away": None,
            "rationale": "无可用赔率数据，市场模型本场未参与。",
            "overround": None, "n_bookmakers": 0,
        }

    homes, draws, aways, overrounds = [], [], [], []
    for bm in bms:
        h2h = bm.get("h2h", {})
        try:
            ho, do, ao = h2h["home"], h2h["draw"], h2h["away"]
            ph, pd, pa = _devig(ho, do, ao)
            homes.append(ph); draws.append(pd); aways.append(pa)
            overrounds.append((1 / ho + 1 / do + 1 / ao) - 1)
        except (KeyError, ZeroDivisionError, TypeError):
            continue

    if not homes:
        return {
            "model": "market", "p_home": None, "p_draw": None, "p_away": None,
            "rationale": "赔率字段不完整，市场模型本场未参与。",
            "overround": None, "n_bookmakers": 0,
        }

    p_home = statistics.median(homes)
    p_draw = statistics.median(draws)
    p_away = statistics.median(aways)
    s = p_home + p_draw + p_away
    p_home, p_draw, p_away = p_home / s, p_draw / s, p_away / s
    avg_overround = statistics.mean(overrounds)

    rationale = (
        f"汇总 {len(homes)} 家博彩公司赔率，去除平均 {avg_overround*100:.1f}% 抽水后取中位数，"
        f"得到市场共识隐含概率，反映专业资金的整体预期。"
    )

    return {
        "model": "market",
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
        "overround": round(avg_overround, 4),
        "n_bookmakers": len(homes),
        "rationale": rationale,
    }
