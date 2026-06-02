"""
tournament_simulator.py
蒙特卡洛赛事模拟器 → 冠/亚/季军概率。

方法：以各队 Elo 推导单场胜率，反复模拟淘汰赛(16 强单败赛制简化模型)，
统计每队夺冠/进决赛/进半决赛频率。默认 10000 次，输出置信说明。
"""
from __future__ import annotations
import random
from config import config
from data.data_fetcher import TEAM_POOL


def _win_prob(elo_a: int, elo_b: int) -> float:
    return 1.0 / (1.0 + 10 ** (-(elo_a - elo_b) / 400.0))


def _seed_teams(n: int = 16) -> list[tuple[str, int]]:
    ranked = sorted(TEAM_POOL.items(), key=lambda kv: kv[1]["elo"], reverse=True)
    return [(name, info["elo"]) for name, info in ranked[:n]]


def simulate(n_sims: int | None = None) -> dict:
    n_sims = n_sims or config.MC_SIMULATIONS
    teams = _seed_teams(16)
    names = [t[0] for t in teams]
    elo = {t[0]: t[1] for t in teams}

    champ = {n: 0 for n in names}
    runner = {n: 0 for n in names}
    third = {n: 0 for n in names}
    semi = {n: 0 for n in names}

    rng = random.Random(42)  # 可复现

    for _ in range(n_sims):
        bracket = names[:]  # 16 强，按种子顺序两两对阵
        rng.shuffle(bracket)
        # R16 -> QF -> SF (记录 4 强) -> Final
        rounds = [bracket]
        while len(rounds[-1]) > 1:
            cur = rounds[-1]
            nxt = []
            for i in range(0, len(cur), 2):
                a, b = cur[i], cur[i + 1]
                pa = _win_prob(elo[a], elo[b])
                nxt.append(a if rng.random() < pa else b)
            rounds.append(nxt)

        final_four = rounds[-3] if len(rounds) >= 3 else rounds[0]
        for t in final_four:
            semi[t] += 1

        finalists = rounds[-2]
        winner = rounds[-1][0]
        loser = finalists[0] if finalists[1] == winner else finalists[1]
        champ[winner] += 1
        runner[loser] += 1
        # 季军：半决赛两名落败者中 Elo 较高者(简化)
        sf_losers = [t for t in final_four if t not in finalists]
        if sf_losers:
            third_place = max(sf_losers, key=lambda t: elo[t])
            third[third_place] += 1

    def pct(d):
        return sorted(
            [{"team": k, "flag": TEAM_POOL.get(k, {}).get("flag", "🏳️"),
              "prob": round(v / n_sims * 100, 2)} for k, v in d.items()],
            key=lambda x: x["prob"], reverse=True
        )

    return {
        "n_simulations": n_sims,
        "champion": pct(champ),
        "runner_up": pct(runner),
        "third_place": pct(third),
        "semifinal": pct(semi),
        "bracket": build_bracket(n_sims),
        "confidence_note": (
            f"基于当前 16 强阵容 Elo 实力，使用蒙特卡洛方法模拟单败淘汰赛 {n_sims:,} 次。"
            f"模拟次数越多结果越稳定；本结果为统计频率估计，约 ±1% 抽样误差。"
        ),
    }


def _seeded_pairs(teams: list[tuple[str, int]]) -> list[str]:
    """标准种子对阵：1-16, 2-15, ... 让强弱分布均衡。"""
    n = len(teams)
    order = []
    for i in range(n // 2):
        order.append(teams[i][0])
        order.append(teams[n - 1 - i][0])
    return order


def build_bracket(n_sims: int | None = None) -> dict:
    """
    构建固定种子对阵树，并通过蒙特卡洛计算每队"到达每一轮"的概率。
    返回前端可直接渲染的树结构：rounds[轮次] -> 该轮每个对阵位的两个候选队及其到达概率。
    """
    n_sims = n_sims or config.MC_SIMULATIONS
    teams = _seed_teams(16)
    elo = {t[0]: t[1] for t in teams}
    seeded = _seeded_pairs(teams)  # 固定首轮顺序

    round_names = ["十六强", "八强", "四强", "决赛", "冠军"]
    n_rounds = len(round_names)  # 16->8->4->2->1
    # reach_count[r][team] = 在第 r 层出现(即赢到该层)的次数；第 0 层为首轮固定出场
    reach = [dict() for _ in range(n_rounds)]
    for t in seeded:
        reach[0][t] = n_sims  # 首轮 100% 出场

    rng = random.Random(2026)
    for _ in range(n_sims):
        cur = seeded[:]
        depth = 0
        while len(cur) > 1:
            nxt = []
            for i in range(0, len(cur), 2):
                a, b = cur[i], cur[i + 1]
                pa = _win_prob(elo[a], elo[b])
                w = a if rng.random() < pa else b
                nxt.append(w)
            depth += 1
            for w in nxt:
                reach[depth][w] = reach[depth].get(w, 0) + 1
            cur = nxt

    # 组织成树：每轮按对阵位分组（首轮 8 组，八强 4 组...）
    rounds_out = []
    block = seeded[:]
    for r in range(n_rounds - 1):  # 不含"冠军"层(单点)
        size = len(block)
        matchups = []
        for i in range(0, size, 2):
            slot_teams = block[i:i + 2]
            entries = [{
                "team": t,
                "flag": TEAM_POOL.get(t, {}).get("flag", "🏳️"),
                "elo": elo[t],
                "reach_prob": round(reach[r].get(t, 0) / n_sims * 100, 1),
            } for t in slot_teams]
            matchups.append(entries)
        rounds_out.append({"round": round_names[r], "matchups": matchups})
        # 下一轮的"代表队"用本轮该位最可能晋级者占位（仅用于布局对齐）
        nxt_block = []
        for i in range(0, size, 2):
            pair = block[i:i + 2]
            rep = max(pair, key=lambda t: reach[r + 1].get(t, 0))
            nxt_block.append(rep)
        block = nxt_block

    # 冠军层
    champ_entries = sorted(
        [{"team": t, "flag": TEAM_POOL.get(t, {}).get("flag", "🏳️"),
          "reach_prob": round(reach[n_rounds - 1].get(t, 0) / n_sims * 100, 1)}
         for t in seeded],
        key=lambda x: x["reach_prob"], reverse=True
    )[:4]

    # 每队完整晋级路径 (供点击节点时展示)
    team_paths = {}
    for t in seeded:
        team_paths[t] = {
            "team": t,
            "flag": TEAM_POOL.get(t, {}).get("flag", "🏳️"),
            "elo": elo[t],
            "stages": [
                {"round": round_names[r], "prob": round(reach[r].get(t, 0) / n_sims * 100, 1)}
                for r in range(n_rounds)
            ],
        }

    return {
        "rounds": rounds_out,
        "champion_candidates": champ_entries,
        "team_paths": team_paths,
        "round_names": round_names,
        "note": (
            "采用标准种子对阵(1-16、2-15…)固定首轮，蒙特卡洛模拟每队晋级各轮的概率。"
            "节点颜色越亮代表到达该轮概率越高。点击任意节点可查看该队完整晋级路径。"
            "注意：真实世界杯对阵由小组排名决定，此处为基于实力的示意性对阵。"
        ),
    }
