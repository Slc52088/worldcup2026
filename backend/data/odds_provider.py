"""
odds_provider.py
可插拔赔率适配层。

设计：定义抽象 OddsProvider 接口；提供两种实现：
  - SimulatedOddsProvider: 确定性模拟，零外部依赖，永远可用，界面标注"模拟"。
  - TheOddsApiProvider: 当配置了 ODDS_API_KEY 时启用，对接 the-odds-api.com。
工厂函数 get_provider() 根据环境自动选择。

模拟引擎以球队 Elo 为基础生成多家博彩公司的胜平负/让球/大小球赔率，
并模拟一段"赔率变动历史"用于盘赔相似度与资金流向反推。所有数值确定性可复现。
"""
from __future__ import annotations
import math
import random
import httpx
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from config import config
from data.data_fetcher import TEAM_POOL

BOOKMAKERS = ["PinnacleSim", "Bet365Sim", "WilliamHillSim", "MarathonSim", "1xBetSim"]


def _elo_win_prob(home_elo: int, away_elo: int, home_adv: int = 60) -> float:
    """标准 Elo 期望胜率 (含主场优势)。"""
    diff = (home_elo + home_adv) - away_elo
    return 1.0 / (1.0 + 10 ** (-diff / 400.0))


def _three_way_from_elo(home_elo: int, away_elo: int) -> tuple[float, float, float]:
    """由 Elo 推出胜/平/负真概率 (平局概率随实力接近而升高)。"""
    p_home_core = _elo_win_prob(home_elo, away_elo)
    # 平局概率: 实力越接近越高，封顶 ~0.30
    closeness = 1.0 - min(1.0, abs(home_elo - away_elo) / 400.0)
    p_draw = 0.18 + 0.12 * closeness
    p_home = p_home_core * (1 - p_draw)
    p_away = (1 - p_home_core) * (1 - p_draw)
    s = p_home + p_draw + p_away
    return p_home / s, p_draw / s, p_away / s


def _prob_to_odds(p: float, margin: float) -> float:
    """真概率 + 抽水 → 小数赔率。"""
    p_adj = min(0.97, p * (1 + margin))
    return round(1.0 / p_adj, 2)


class OddsProvider(ABC):
    name: str = "abstract"
    is_real: bool = False

    @abstractmethod
    def get_odds(self, match_id: str, home: str, away: str) -> dict:
        ...

    def list_events(self) -> dict:
        """列出该数据源当前可用的赛事场次 (供赛事自动发现)。默认空。"""
        return {"events": [], "is_real": self.is_real, "source": self.name}


class SimulatedOddsProvider(OddsProvider):
    name = "SimulatedOddsProvider"
    is_real = False

    def list_events(self) -> dict:
        """模拟引擎：声明所有内置队伍均可生成赔率。"""
        return {
            "events": [],
            "is_real": False,
            "source": self.name,
            "note": "当前使用模拟赔率引擎，所有赛程均可生成赔率。配置 ODDS_API_KEY 后将切换到真实赛事发现。",
        }

    def get_odds(self, match_id: str, home: str, away: str) -> dict:
        rng = random.Random(match_id)  # 确定性：同一场比赛结果稳定
        h_elo = TEAM_POOL.get(home, {}).get("elo", 1700)
        a_elo = TEAM_POOL.get(away, {}).get("elo", 1700)
        p_h, p_d, p_a = _three_way_from_elo(h_elo, a_elo)

        bookmakers = []
        for bk in BOOKMAKERS:
            margin = rng.uniform(0.03, 0.07)          # 各家抽水不同
            jitter = lambda p: max(0.01, p + rng.uniform(-0.02, 0.02))
            bookmakers.append({
                "bookmaker": bk,
                "h2h": {
                    "home": _prob_to_odds(jitter(p_h), margin),
                    "draw": _prob_to_odds(jitter(p_d), margin),
                    "away": _prob_to_odds(jitter(p_a), margin),
                },
            })

        # 让球盘 (asian handicap) 主盘口
        handicap_line = self._suggest_handicap(p_h, p_a)
        # 大小球
        total_line = round(2.5 + (h_elo + a_elo - 3400) / 2000.0, 1)

        # 赔率变动历史 (近 24 小时, 每 2 小时一个采样点)
        history = self._odds_history(rng, p_h, p_d, p_a)

        return {
            "match_id": match_id,
            "is_real": self.is_real,
            "source": self.name,
            "bookmakers": bookmakers,
            "handicap": {"line": handicap_line, "home_odds": round(1.9 + rng.uniform(-0.1, 0.1), 2),
                         "away_odds": round(1.9 + rng.uniform(-0.1, 0.1), 2)},
            "totals": {"line": total_line, "over": round(1.9 + rng.uniform(-0.1, 0.1), 2),
                       "under": round(1.9 + rng.uniform(-0.1, 0.1), 2)},
            "history": history,
            "true_probs_hint": {"home": p_h, "draw": p_d, "away": p_a},
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def _suggest_handicap(p_h: float, p_a: float) -> float:
        diff = p_h - p_a
        if diff > 0.5:
            return -1.5
        if diff > 0.25:
            return -1.0
        if diff > 0.1:
            return -0.5
        if diff < -0.5:
            return 1.5
        if diff < -0.25:
            return 1.0
        if diff < -0.1:
            return 0.5
        return 0.0

    @staticmethod
    def _odds_history(rng, p_h, p_d, p_a) -> list[dict]:
        """模拟赔率随时间漂移，制造可供分析的走势 (含可能的 steam move)。"""
        points = []
        drift = rng.uniform(-0.04, 0.04)  # 整体倾向
        steam_at = rng.choice([None, None, 8, 10])  # 偶发临场资金涌入
        for t in range(13):  # 0..24h, 每 2h
            local = drift * (t / 12.0)
            if steam_at and t >= steam_at:
                local += 0.05  # 主队被大量买入
            ph = max(0.05, min(0.9, p_h + local))
            pa = max(0.05, min(0.9, p_a - local * 0.6))
            pd = max(0.05, 1 - ph - pa)
            s = ph + pd + pa
            ph, pd, pa = ph / s, pd / s, pa / s
            margin = 0.05
            points.append({
                "t_minus_hours": 24 - t * 2,
                "home": _prob_to_odds(ph, margin),
                "draw": _prob_to_odds(pd, margin),
                "away": _prob_to_odds(pa, margin),
            })
        return points


class TheOddsApiProvider(OddsProvider):
    """
    对接 the-odds-api.com (免费档约 500 次/月)。仅在配置 ODDS_API_KEY 时使用。

    关键设计：
      - 整轮赔率结果缓存 (默认 10 分钟)，避免每场比赛各发一次请求耗尽免费额度。
      - 团队名称归一化匹配 (大小写/常见别名)。
      - 解析 h2h (胜平负) 与 totals (大小球)。
      - 赔率历史：每次成功取数时把本场快照写入 SQLite，逐步累积出真实走势，
        供盘赔相似度与资金流向分析使用 (首次只有一个点，随时间增长)。
    """
    name = "TheOddsApiProvider"
    is_real = True

    # 简单别名表：openfootball/内置池名 → The Odds API 可能用的名字
    ALIASES = {
        "Korea Republic": ["South Korea", "Korea"],
        "USA": ["United States", "USMNT"],
        "Saudi Arabia": ["Saudi Arabia"],
    }

    def _names_match(self, our_name: str, api_name: str) -> bool:
        a, b = our_name.lower().strip(), (api_name or "").lower().strip()
        if a == b or a in b or b in a:
            return True
        for alias in self.ALIASES.get(our_name, []):
            if alias.lower() in b or b in alias.lower():
                return True
        return False

    def _fetch_all(self) -> list:
        """取整轮赔率，带缓存 (减少 API 调用)。"""
        from data import store
        cached = store.read_cache("odds_api_raw", max_age_sec=600)
        if cached is not None:
            return cached
        url = f"{config.ODDS_API_BASE}/sports/soccer_fifa_world_cup/odds"
        params = {
            "apiKey": config.ODDS_API_KEY,
            "regions": "eu,uk",
            "markets": "h2h,totals",
            "oddsFormat": "decimal",
        }
        resp = httpx.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()
        store.write_cache("odds_api_raw", data)
        return data

    def list_events(self) -> dict:
        """列出 The Odds API 当前提供赔率的世界杯场次，并报告剩余配额。"""
        try:
            data = self._fetch_all()
            events = []
            for g in data:
                bk_count = len(g.get("bookmakers", []))
                events.append({
                    "api_id": g.get("id"),
                    "home_team": g.get("home_team"),
                    "away_team": g.get("away_team"),
                    "commence_time": g.get("commence_time"),
                    "bookmaker_count": bk_count,
                })
            events.sort(key=lambda e: e.get("commence_time") or "")
            return {
                "events": events,
                "is_real": True,
                "source": self.name,
                "count": len(events),
                "note": f"The Odds API 当前提供 {len(events)} 场世界杯赔率。" +
                        ("" if events else "（赛前较早时可能尚无开盘，属正常现象。）"),
            }
        except httpx.HTTPStatusError as e:
            code = e.response.status_code if e.response else "?"
            msg = {401: "API Key 无效或额度耗尽", 429: "请求过于频繁"}.get(code, f"API 错误 {code}")
            return {"events": [], "is_real": True, "source": self.name, "error": msg}
        except Exception as e:
            return {"events": [], "is_real": True, "source": self.name,
                    "error": f"请求失败: {type(e).__name__}"}

    def get_odds(self, match_id: str, home: str, away: str) -> dict:
        try:
            data = self._fetch_all()
            for game in data:
                if self._names_match(home, game.get("home_team", "")) and \
                   self._names_match(away, game.get("away_team", "")):
                    return self._parse(match_id, game, home, away)
            # 未匹配到 (该场可能尚未开盘)：降级模拟，但标注原因
            fallback = SimulatedOddsProvider().get_odds(match_id, home, away)
            fallback["note"] = "真实赔率源中暂未找到本场盘口，已使用模拟数据占位。"
            fallback["source"] = self.name + " (fallback)"
            return fallback
        except httpx.HTTPStatusError as e:
            fallback = SimulatedOddsProvider().get_odds(match_id, home, away)
            code = e.response.status_code if e.response else "?"
            if code == 401:
                fallback["note"] = "ODDS_API_KEY 无效或额度耗尽 (401)，已降级到模拟数据。"
            elif code == 429:
                fallback["note"] = "赔率 API 请求过于频繁 (429)，已降级到模拟数据。"
            else:
                fallback["note"] = f"赔率 API 返回错误 ({code})，已降级到模拟数据。"
            fallback["source"] = self.name + " (fallback)"
            return fallback
        except Exception as e:
            fallback = SimulatedOddsProvider().get_odds(match_id, home, away)
            fallback["note"] = f"赔率源请求失败 ({type(e).__name__})，已降级到模拟数据。"
            fallback["source"] = self.name + " (fallback)"
            return fallback

    def _parse(self, match_id: str, game: dict, home: str, away: str) -> dict:
        home_team = game.get("home_team", home)
        away_team = game.get("away_team", away)
        bookmakers = []
        totals_lines = []  # 收集各家大小球，取中位线

        for bk in game.get("bookmakers", []):
            h2h = {}
            for mkt in bk.get("markets", []):
                if mkt["key"] == "h2h":
                    for o in mkt.get("outcomes", []):
                        nm = o.get("name", "")
                        if self._names_match(home_team, nm):
                            h2h["home"] = o["price"]
                        elif self._names_match(away_team, nm):
                            h2h["away"] = o["price"]
                        elif nm.lower() in ("draw", "tie"):
                            h2h["draw"] = o["price"]
                elif mkt["key"] == "totals":
                    for o in mkt.get("outcomes", []):
                        if o.get("point") is not None:
                            totals_lines.append({
                                "line": o["point"],
                                "side": o.get("name", "").lower(),  # over/under
                                "price": o["price"],
                            })
            if {"home", "draw", "away"} <= set(h2h.keys()):
                bookmakers.append({"bookmaker": bk.get("title", "?"), "h2h": h2h})

        # 聚合大小球：取出现最多的盘口线
        totals = None
        if totals_lines:
            from collections import Counter
            common_line = Counter(t["line"] for t in totals_lines).most_common(1)[0][0]
            overs = [t["price"] for t in totals_lines if t["line"] == common_line and t["side"] == "over"]
            unders = [t["price"] for t in totals_lines if t["line"] == common_line and t["side"] == "under"]
            if overs and unders:
                totals = {
                    "line": common_line,
                    "over": round(sum(overs) / len(overs), 2),
                    "under": round(sum(unders) / len(unders), 2),
                }

        result = {
            "match_id": match_id,
            "is_real": True,
            "source": self.name,
            "bookmakers": bookmakers,
            "handicap": None,  # The Odds API 免费档通常不含亚盘，留空
            "totals": totals,
            "history": self._accumulate_history(match_id, bookmakers),
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }
        return result

    def _accumulate_history(self, match_id: str, bookmakers: list) -> list:
        """
        真实赔率没有历史接口，这里把每次取数的市场共识快照存入 SQLite，
        逐步累积成走势。返回按时间排序的历史点 (与模拟引擎同结构)。
        """
        from data import store
        import statistics, time, json as _json

        if not bookmakers:
            return []
        # 计算本次市场共识赔率 (各家中位数)
        homes = [b["h2h"]["home"] for b in bookmakers if "home" in b["h2h"]]
        draws = [b["h2h"]["draw"] for b in bookmakers if "draw" in b["h2h"]]
        aways = [b["h2h"]["away"] for b in bookmakers if "away" in b["h2h"]]
        if not (homes and draws and aways):
            return []
        snap = {
            "home": round(statistics.median(homes), 2),
            "draw": round(statistics.median(draws), 2),
            "away": round(statistics.median(aways), 2),
        }
        now = time.time()
        try:
            with store.db() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO odds_snapshots VALUES (?,?,?)",
                    (match_id, now, _json.dumps(snap)),
                )
                rows = conn.execute(
                    "SELECT snapshot_at, payload FROM odds_snapshots WHERE match_id=? ORDER BY snapshot_at",
                    (match_id,),
                ).fetchall()
        except Exception:
            return [{"t_minus_hours": 0, **snap}]

        # 转成 history 结构 (t_minus_hours 用相对最新快照的小时差)
        latest = rows[-1]["snapshot_at"]
        history = []
        for r in rows:
            payload = _json.loads(r["payload"])
            hrs = round((latest - r["snapshot_at"]) / 3600.0, 1)
            history.append({"t_minus_hours": hrs, **payload})
        return history


def get_provider() -> OddsProvider:
    if config.ODDS_API_KEY:
        return TheOddsApiProvider()
    return SimulatedOddsProvider()
