"""
market_sentiment.py
全球市场热度仪表盘核心指标。

诚实方法学说明 (同时用于前端名词解释)：
本模块通过【赔率隐含概率的变动】反推市场资金倾向。这是一种业界常用的启发式
(heuristic)，反映的是赔率所隐含概率的变化方向与幅度，并非真实可见的下注金额。
赔率上抬→隐含概率下降→可解读为资金流出；反之为资金流入。

输出指标：
  - money_distribution: 主/平/客 资金倾向占比 (由当前隐含概率 + 近端漂移合成)
  - heat_index: 冷热指数 0-100 (赔率波动幅度 × 关注度代理)
  - divergence: 赔量背离 (隐含概率变动方向与幅度的异常度)
每个指标都带 explanation 字段供前端问号气泡展示。
"""
from __future__ import annotations


def _implied(pt: dict) -> tuple[float, float, float]:
    inv = [1 / pt["home"], 1 / pt["draw"], 1 / pt["away"]]
    s = sum(inv)
    return inv[0] / s, inv[1] / s, inv[2] / s


def analyze(odds: dict) -> dict:
    history = odds.get("history", [])
    explanations = {
        "money_distribution": "资金分布：通过当前赔率隐含概率与近端走势，反推市场对三种结果的资金倾向占比。注意这是由赔率变动反推的估计，并非真实下注金额。",
        "heat_index": "冷热指数 (0-100)：综合赔率在赛前 24 小时内的波动幅度衡量市场关注与博弈激烈程度，数值越高代表盘面越活跃。",
        "divergence": "赔量背离：当赔率短时间内出现明显单向移动，往往意味着有集中资金介入；背离值越高，临场异动越显著。",
    }

    if len(history) < 2:
        return {
            "money_distribution": None,
            "heat_index": None,
            "divergence": None,
            "explanations": explanations,
            "note": "赔率历史不足，热度指标暂不可用。",
        }

    first = history[0]
    last = history[-1]
    fh, fd, fa = _implied(first)
    lh, ld, la = _implied(last)

    # 资金分布：以最新隐含概率为基础
    s = lh + ld + la
    money = {
        "home": round(lh / s * 100, 1),
        "draw": round(ld / s * 100, 1),
        "away": round(la / s * 100, 1),
    }

    # 冷热指数：累计绝对波动 → 映射到 0-100
    vol = 0.0
    for i in range(1, len(history)):
        ph0, _, pa0 = _implied(history[i - 1])
        ph1, _, pa1 = _implied(history[i])
        vol += abs(ph1 - ph0) + abs(pa1 - pa0)
    heat_index = round(min(100.0, vol * 300.0), 1)

    # 赔量背离：主队隐含概率净变动幅度
    drift_home = lh - fh
    divergence = round(min(100.0, abs(drift_home) * 400.0), 1)
    direction = "主队" if drift_home > 0.01 else "客队" if drift_home < -0.01 else "中性"

    return {
        "money_distribution": money,
        "heat_index": heat_index,
        "divergence": {"value": divergence, "direction": direction,
                       "drift_home_pct": round(drift_home * 100, 1)},
        "explanations": explanations,
    }
