"""
statistical_model.py
泊松分布比赛模型。

思路：以两队进攻强度(场均进球)与对手防守强度估计本场各自期望进球 λ，
对 0..max_goals 构建比分概率矩阵 → 聚合出胜/平/负概率与最可能比分。
所有输出附自然语言依据。
"""
from __future__ import annotations
import math
from data.data_fetcher import get_team_recent_form, TEAM_POOL

MAX_GOALS = 7
HOME_ADV = 1.12  # 主场进球放大系数


def _poisson_pmf(k: int, lam: float) -> float:
    return math.exp(-lam) * lam ** k / math.factorial(k)


def _expected_goals(home: str, away: str) -> tuple[float, float]:
    hf = get_team_recent_form(home)
    af = get_team_recent_form(away)
    league_avg = 1.35  # 世界杯单队场均进球基线
    # 期望进球 = 自身进攻强度 * 对手防守弱度 (相对联盟均值)
    home_lambda = (hf["avg_goals_for"] / league_avg) * (af["avg_goals_against"] / league_avg) * league_avg * HOME_ADV
    away_lambda = (af["avg_goals_for"] / league_avg) * (hf["avg_goals_against"] / league_avg) * league_avg
    return round(max(0.2, home_lambda), 2), round(max(0.2, away_lambda), 2)


def predict(home: str, away: str) -> dict:
    home_lambda, away_lambda = _expected_goals(home, away)

    # 比分概率矩阵
    matrix = [[_poisson_pmf(i, home_lambda) * _poisson_pmf(j, away_lambda)
               for j in range(MAX_GOALS + 1)] for i in range(MAX_GOALS + 1)]

    p_home = p_draw = p_away = 0.0
    scorelines = []
    for i in range(MAX_GOALS + 1):
        for j in range(MAX_GOALS + 1):
            p = matrix[i][j]
            scorelines.append({"score": f"{i}-{j}", "prob": p})
            if i > j:
                p_home += p
            elif i == j:
                p_draw += p
            else:
                p_away += p

    total = p_home + p_draw + p_away
    p_home, p_draw, p_away = p_home / total, p_draw / total, p_away / total

    scorelines.sort(key=lambda x: x["prob"], reverse=True)
    top_scores = [{"score": s["score"], "prob": round(s["prob"] / total, 4)} for s in scorelines[:5]]

    hf = get_team_recent_form(home)
    af = get_team_recent_form(away)
    rationale = (
        f"基于{home}近期场均{hf['avg_goals_for']}球的进攻与{away}场均失{af['avg_goals_against']}球的防守，"
        f"结合主场优势，泊松模型估计本场期望进球 {home_lambda} : {away_lambda}，"
        f"由此推导比分概率矩阵。"
    )

    return {
        "model": "poisson",
        "p_home": round(p_home, 4),
        "p_draw": round(p_draw, 4),
        "p_away": round(p_away, 4),
        "lambdas": {"home": home_lambda, "away": away_lambda},
        "top_scores": top_scores,
        "rationale": rationale,
    }
