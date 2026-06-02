"""
data_fetcher.py
赛程 / 球队 / 近况获取。

主源: openfootball/worldcup.json (via jsDelivr CDN, 无需密钥)。
策略: 拉取真实赛程；若网络失败或 2026 数据未就绪，优雅降级到内置 32 队池
并生成结构合理的赛程，保证 App 永远可用。所有降级数据均标注 source='fallback'。
"""
from __future__ import annotations
import json
import hashlib
import httpx
from datetime import datetime, timedelta, timezone
from config import config

# 2026 世界杯参赛热门球队池 (含 Elo 近似实力，用于模型；非官方，仅作基线)
TEAM_POOL = {
    "Argentina": {"flag": "🇦🇷", "elo": 2103, "group": "A"},
    "France": {"flag": "🇫🇷", "elo": 2073, "group": "B"},
    "Spain": {"flag": "🇪🇸", "elo": 2048, "group": "C"},
    "England": {"flag": "🏴", "elo": 2025, "group": "D"},
    "Brazil": {"flag": "🇧🇷", "elo": 2018, "group": "E"},
    "Portugal": {"flag": "🇵🇹", "elo": 2003, "group": "F"},
    "Netherlands": {"flag": "🇳🇱", "elo": 1990, "group": "G"},
    "Belgium": {"flag": "🇧🇪", "elo": 1965, "group": "H"},
    "Germany": {"flag": "🇩🇪", "elo": 1958, "group": "A"},
    "Croatia": {"flag": "🇭🇷", "elo": 1945, "group": "B"},
    "Italy": {"flag": "🇮🇹", "elo": 1938, "group": "C"},
    "Uruguay": {"flag": "🇺🇾", "elo": 1920, "group": "D"},
    "Colombia": {"flag": "🇨🇴", "elo": 1905, "group": "E"},
    "Morocco": {"flag": "🇲🇦", "elo": 1898, "group": "F"},
    "USA": {"flag": "🇺🇸", "elo": 1860, "group": "G"},
    "Mexico": {"flag": "🇲🇽", "elo": 1855, "group": "H"},
    "Switzerland": {"flag": "🇨🇭", "elo": 1850, "group": "A"},
    "Japan": {"flag": "🇯🇵", "elo": 1845, "group": "B"},
    "Senegal": {"flag": "🇸🇳", "elo": 1840, "group": "C"},
    "Denmark": {"flag": "🇩🇰", "elo": 1835, "group": "D"},
    "Korea Republic": {"flag": "🇰🇷", "elo": 1815, "group": "E"},
    "Ecuador": {"flag": "🇪🇨", "elo": 1810, "group": "F"},
    "Austria": {"flag": "🇦🇹", "elo": 1805, "group": "G"},
    "Canada": {"flag": "🇨🇦", "elo": 1790, "group": "H"},
    "Poland": {"flag": "🇵🇱", "elo": 1785, "group": "A"},
    "Australia": {"flag": "🇦🇺", "elo": 1770, "group": "B"},
    "Nigeria": {"flag": "🇳🇬", "elo": 1760, "group": "C"},
    "Cameroon": {"flag": "🇨🇲", "elo": 1745, "group": "D"},
    "Saudi Arabia": {"flag": "🇸🇦", "elo": 1700, "group": "E"},
    "Ghana": {"flag": "🇬🇭", "elo": 1690, "group": "F"},
    "Qatar": {"flag": "🇶🇦", "elo": 1650, "group": "G"},
    "New Zealand": {"flag": "🇳🇿", "elo": 1600, "group": "H"},
}


def _match_id(home: str, away: str, date_str: str) -> str:
    raw = f"{home}|{away}|{date_str}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def _fallback_fixtures() -> list[dict]:
    """生成小组赛阶段赛程 (每组前两队对阵示例 + 跨组), 保证有足够比赛展示。"""
    teams = list(TEAM_POOL.items())
    fixtures = []
    base_date = datetime.now(timezone.utc) + timedelta(days=2)
    # 简单两两配对生成 24 场示例比赛
    for i in range(0, min(48, len(teams) * 2), 2):
        h = teams[i % len(teams)]
        a = teams[(i + 1) % len(teams)]
        if h[0] == a[0]:
            continue
        kickoff = base_date + timedelta(hours=6 * (i // 2))
        date_str = kickoff.strftime("%Y-%m-%dT%H:%M:%SZ")
        fixtures.append({
            "id": _match_id(h[0], a[0], date_str),
            "home": h[0],
            "away": a[0],
            "home_flag": h[1]["flag"],
            "away_flag": a[1]["flag"],
            "group": h[1]["group"],
            "round": "Group Stage",
            "kickoff": date_str,
            "status": "scheduled",
            "score": None,
            "source": "fallback",
        })
    return fixtures


def get_worldcup_fixtures() -> dict:
    """返回 {fixtures: [...], source: str, last_updated: str}。"""
    last_updated = datetime.now(timezone.utc).isoformat()
    try:
        resp = httpx.get(config.FIXTURES_URL, timeout=10.0)
        resp.raise_for_status()
        raw = resp.json()
        fixtures = []
        for rnd in raw.get("rounds", []):
            round_name = rnd.get("name", "Group Stage")
            for m in rnd.get("matches", []):
                home = m.get("team1", {}).get("name") or m.get("team1")
                away = m.get("team2", {}).get("name") or m.get("team2")
                if not home or not away:
                    continue
                date_str = m.get("date", "") + "T" + (m.get("time", "18:00")) + ":00Z"
                score = None
                if m.get("score", {}).get("ft"):
                    ft = m["score"]["ft"]
                    score = {"home": ft[0], "away": ft[1]}
                fixtures.append({
                    "id": _match_id(home, away, date_str),
                    "home": home,
                    "away": away,
                    "home_flag": TEAM_POOL.get(home, {}).get("flag", "🏳️"),
                    "away_flag": TEAM_POOL.get(away, {}).get("flag", "🏳️"),
                    "group": m.get("group", ""),
                    "round": round_name,
                    "kickoff": date_str,
                    "status": "finished" if score else "scheduled",
                    "score": score,
                    "source": "openfootball",
                })
        if not fixtures:
            raise ValueError("Empty fixtures from source")
        return {"fixtures": fixtures, "source": "openfootball", "last_updated": last_updated}
    except Exception as e:
        fb = _fallback_fixtures()
        return {
            "fixtures": fb,
            "source": "fallback",
            "note": f"实时赛程源不可用 ({type(e).__name__})，已使用内置队伍池生成示例赛程。",
            "last_updated": last_updated,
        }


def get_match_detail(match_id: str, fixtures: list[dict]) -> dict | None:
    for f in fixtures:
        if f["id"] == match_id:
            return f
    return None


def get_team_recent_form(team: str) -> dict:
    """
    返回球队近期状态。无免费逐场近况源时，用 Elo 派生一个稳定的合成近况，
    使界面有数据可展示，并标注为 derived。
    """
    info = TEAM_POOL.get(team, {"elo": 1700})
    elo = info["elo"]
    # 由 Elo 派生场均进/失球与近 5 场战绩 (确定性，保证可复现)
    attack = round(1.0 + (elo - 1600) / 300.0, 2)      # ~1.0 ~ 2.7
    defense = round(max(0.4, 2.0 - (elo - 1600) / 350.0), 2)
    seed = sum(ord(c) for c in team)
    last5 = []
    wins = draws = losses = 0
    for i in range(5):
        v = (seed * (i + 3)) % 10
        if v < (elo - 1600) / 60:
            last5.append("W"); wins += 1
        elif v < 6:
            last5.append("D"); draws += 1
        else:
            last5.append("L"); losses += 1
    return {
        "team": team,
        "elo": elo,
        "avg_goals_for": attack,
        "avg_goals_against": defense,
        "last5": last5,
        "record": {"W": wins, "D": draws, "L": losses},
        "source": "derived",
    }
