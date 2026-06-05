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
    "Argentina": {"flag": "🇦🇷", "iso": "ar", "elo": 2103, "group": "A"},
    "France": {"flag": "🇫🇷", "iso": "fr", "elo": 2073, "group": "B"},
    "Spain": {"flag": "🇪🇸", "iso": "es", "elo": 2048, "group": "C"},
    "England": {"flag": "🏴", "iso": "gb-eng", "elo": 2025, "group": "D"},
    "Brazil": {"flag": "🇧🇷", "iso": "br", "elo": 2018, "group": "E"},
    "Portugal": {"flag": "🇵🇹", "iso": "pt", "elo": 2003, "group": "F"},
    "Netherlands": {"flag": "🇳🇱", "iso": "nl", "elo": 1990, "group": "G"},
    "Belgium": {"flag": "🇧🇪", "iso": "be", "elo": 1965, "group": "H"},
    "Germany": {"flag": "🇩🇪", "iso": "de", "elo": 1958, "group": "A"},
    "Croatia": {"flag": "🇭🇷", "iso": "hr", "elo": 1945, "group": "B"},
    "Italy": {"flag": "🇮🇹", "iso": "it", "elo": 1938, "group": "C"},
    "Uruguay": {"flag": "🇺🇾", "iso": "uy", "elo": 1920, "group": "D"},
    "Colombia": {"flag": "🇨🇴", "iso": "co", "elo": 1905, "group": "E"},
    "Morocco": {"flag": "🇲🇦", "iso": "ma", "elo": 1898, "group": "F"},
    "USA": {"flag": "🇺🇸", "iso": "us", "elo": 1860, "group": "G"},
    "Mexico": {"flag": "🇲🇽", "iso": "mx", "elo": 1855, "group": "H"},
    "Switzerland": {"flag": "🇨🇭", "iso": "ch", "elo": 1850, "group": "A"},
    "Japan": {"flag": "🇯🇵", "iso": "jp", "elo": 1845, "group": "B"},
    "Senegal": {"flag": "🇸🇳", "iso": "sn", "elo": 1840, "group": "C"},
    "Denmark": {"flag": "🇩🇰", "iso": "dk", "elo": 1835, "group": "D"},
    "Korea Republic": {"flag": "🇰🇷", "iso": "kr", "elo": 1815, "group": "E"},
    "Ecuador": {"flag": "🇪🇨", "iso": "ec", "elo": 1810, "group": "F"},
    "Austria": {"flag": "🇦🇹", "iso": "at", "elo": 1805, "group": "G"},
    "Canada": {"flag": "🇨🇦", "iso": "ca", "elo": 1790, "group": "H"},
    "Poland": {"flag": "🇵🇱", "iso": "pl", "elo": 1785, "group": "A"},
    "Australia": {"flag": "🇦🇺", "iso": "au", "elo": 1770, "group": "B"},
    "Nigeria": {"flag": "🇳🇬", "iso": "ng", "elo": 1760, "group": "C"},
    "Cameroon": {"flag": "🇨🇲", "iso": "cm", "elo": 1745, "group": "D"},
    "Saudi Arabia": {"flag": "🇸🇦", "iso": "sa", "elo": 1700, "group": "E"},
    "Ghana": {"flag": "🇬🇭", "iso": "gh", "elo": 1690, "group": "F"},
    "Qatar": {"flag": "🇶🇦", "iso": "qa", "elo": 1650, "group": "G"},
    "New Zealand": {"flag": "🇳🇿", "iso": "nz", "elo": 1600, "group": "H"},
    # ---- 2026 真实参赛队补充(部分队伍 Elo 为大致基线估算) ----
    "South Africa": {"flag": "🇿🇦", "iso": "za", "elo": 1620, "group": "A"},
    "South Korea": {"flag": "🇰🇷", "iso": "kr", "elo": 1815, "group": "A"},
    "Czech Republic": {"flag": "🇨🇿", "iso": "cz", "elo": 1700, "group": "A"},
    "Bosnia & Herzegovina": {"flag": "🇧🇦", "iso": "ba", "elo": 1680, "group": "B"},
    "Haiti": {"flag": "🇭🇹", "iso": "ht", "elo": 1480, "group": "C"},
    "Scotland": {"flag": "🏴󠁧󠁢󠁳󠁣󠁴󠁿", "iso": "gb-sct", "elo": 1730, "group": "C"},
    "Paraguay": {"flag": "🇵🇾", "iso": "py", "elo": 1690, "group": "D"},
    "Turkey": {"flag": "🇹🇷", "iso": "tr", "elo": 1755, "group": "D"},
    "Curaçao": {"flag": "🇨🇼", "iso": "cw", "elo": 1450, "group": "E"},
    "Curacao": {"flag": "🇨🇼", "iso": "cw", "elo": 1450, "group": "E"},
    "Ivory Coast": {"flag": "🇨🇮", "iso": "ci", "elo": 1715, "group": "E"},
    "Sweden": {"flag": "🇸🇪", "iso": "se", "elo": 1760, "group": "F"},
    "Tunisia": {"flag": "🇹🇳", "iso": "tn", "elo": 1660, "group": "F"},
    "Egypt": {"flag": "🇪🇬", "iso": "eg", "elo": 1700, "group": "G"},
    "Iran": {"flag": "🇮🇷", "iso": "ir", "elo": 1730, "group": "G"},
    "Cape Verde": {"flag": "🇨🇻", "iso": "cv", "elo": 1540, "group": "H"},
    "Iraq": {"flag": "🇮🇶", "iso": "iq", "elo": 1580, "group": "I"},
    "Norway": {"flag": "🇳🇴", "iso": "no", "elo": 1770, "group": "I"},
    "Algeria": {"flag": "🇩🇿", "iso": "dz", "elo": 1720, "group": "J"},
    "Jordan": {"flag": "🇯🇴", "iso": "jo", "elo": 1610, "group": "J"},
    "DR Congo": {"flag": "🇨🇩", "iso": "cd", "elo": 1660, "group": "K"},
    "Uzbekistan": {"flag": "🇺🇿", "iso": "uz", "elo": 1620, "group": "K"},
    "Panama": {"flag": "🇵🇦", "iso": "pa", "elo": 1620, "group": "L"},
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

        # 新格式 (2026 数据): 顶层 matches 数组,扁平结构
        # 旧格式 (2022 及更早): 顶层 rounds: [{matches: [...]}]
        if "matches" in raw:
            match_list = raw["matches"]
            grouped = [(None, match_list)]
        else:
            grouped = [(r.get("name", "Group Stage"), r.get("matches", [])) for r in raw.get("rounds", [])]

        for round_name_default, match_list in grouped:
            for m in match_list:
                home = m.get("team1", {}).get("name") if isinstance(m.get("team1"), dict) else m.get("team1")
                away = m.get("team2", {}).get("name") if isinstance(m.get("team2"), dict) else m.get("team2")
                if not home or not away:
                    continue
                # 跳过淘汰赛占位符 (1A, W1, L101 等表示尚未确定的对手)
                if _is_placeholder(home) or _is_placeholder(away):
                    continue
                # 解析时间: "13:00 UTC-6" -> 转 ISO 时间
                kickoff = _parse_kickoff(m.get("date", ""), m.get("time", "18:00"))
                score = None
                if m.get("score", {}).get("ft"):
                    ft = m["score"]["ft"]
                    score = {"home": ft[0], "away": ft[1]}
                fixtures.append({
                    "id": _match_id(home, away, kickoff),
                    "home": home,
                    "away": away,
                    "home_flag": TEAM_POOL.get(home, {}).get("flag", "🏳️"),
                    "away_flag": TEAM_POOL.get(away, {}).get("flag", "🏳️"),
                    "group": m.get("group", ""),
                    "round": m.get("round") or round_name_default or "Group Stage",
                    "venue": m.get("ground") or m.get("stadium") or "",
                    "kickoff": kickoff,
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


def _is_placeholder(team_name: str) -> bool:
    """检测淘汰赛占位符,例如 '1A','2B','W1','L101','Winner 1'。"""
    if not team_name:
        return True
    s = team_name.strip()
    # 1A, 2B 这种组别占位
    if len(s) <= 3 and s[0].isdigit() and s[1:].isalpha():
        return True
    # W1, L101 这种胜/负方占位
    if s and s[0] in ("W", "L", "R") and s[1:].replace(" ", "").isdigit():
        return True
    if s.lower().startswith(("winner ", "runner", "loser ", "third ")):
        return True
    return False


def _parse_kickoff(date_str: str, time_str: str) -> str:
    """解析 '2026-06-11' + '13:00 UTC-6' -> ISO8601 UTC 时间。"""
    if not date_str:
        return datetime.now(timezone.utc).isoformat()
    # 提取时区偏移
    tz_offset_hours = 0
    parts = (time_str or "18:00").strip().split()
    hhmm = parts[0] if parts else "18:00"
    if len(parts) > 1 and parts[1].startswith("UTC"):
        try:
            tz_offset_hours = int(parts[1][3:]) if parts[1][3:] else 0
        except ValueError:
            tz_offset_hours = 0
    try:
        h, mi = hhmm.split(":")
        h, mi = int(h), int(mi)
        # 在本地时区构造时间,再换算到 UTC
        y, mo, d = map(int, date_str.split("-"))
        local = datetime(y, mo, d, h, mi, tzinfo=timezone(timedelta(hours=tz_offset_hours)))
        return local.astimezone(timezone.utc).isoformat()
    except (ValueError, AttributeError):
        return f"{date_str}T{hhmm}:00Z"


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
