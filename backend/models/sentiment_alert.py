"""
sentiment_alert.py
异动预警 (steam move 检测)。

steam move：短时间内多家盘口出现同向、快速的赔率移动，通常被解读为
有信息/大额资金集中介入的信号。本模块从赔率历史中检测这种快速单向移动，
并生成可读的预警级别与文案。
"""
from __future__ import annotations


def _implied_home(pt: dict) -> float:
    inv_h = 1 / pt["home"]
    inv_d = 1 / pt["draw"]
    inv_a = 1 / pt["away"]
    return inv_h / (inv_h + inv_d + inv_a)


def detect(odds: dict) -> dict:
    history = odds.get("history", [])
    if len(history) < 3:
        return {"level": "none", "alerts": [],
                "explanation": "赔率历史不足，未启用异动预警。"}

    series = [_implied_home(p) for p in history]
    alerts = []
    max_jump = 0.0
    jump_window = None
    # 滑动检测最近 3 个采样窗口内的最大单向移动
    for i in range(2, len(series)):
        delta = series[i] - series[i - 2]
        if abs(delta) > abs(max_jump):
            max_jump = delta
            jump_window = (history[i - 2]["t_minus_hours"], history[i]["t_minus_hours"])

    abs_jump = abs(max_jump)
    if abs_jump >= 0.06:
        level = "high"
    elif abs_jump >= 0.03:
        level = "medium"
    elif abs_jump >= 0.015:
        level = "low"
    else:
        level = "none"

    if level != "none" and jump_window:
        side = "主队" if max_jump > 0 else "客队"
        alerts.append({
            "type": "steam_move",
            "side": side,
            "magnitude_pct": round(abs_jump * 100, 1),
            "window": f"赛前 {jump_window[0]}h → {jump_window[1]}h",
            "text": f"检测到{side}方向的临场快速资金介入，隐含概率在该时段移动 {abs_jump*100:.1f}%，"
                    f"属于{'强' if level=='high' else '中等' if level=='medium' else '轻微'}异动信号。",
        })

    return {
        "level": level,
        "alerts": alerts,
        "explanation": "异动预警：检测赔率隐含概率在短窗口内的快速单向移动 (steam move)，"
                       "幅度越大、越集中，越可能反映有信息或大额资金介入。",
    }
