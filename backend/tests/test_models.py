"""
test_models.py
基本单元测试：确保各模型可运行、概率归一、无异常。
运行: cd backend && python -m pytest tests/ -q   (或直接 python tests/test_models.py)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.odds_provider import get_provider
from data import data_fetcher
from models import statistical_model, market_model, ultimate_ensemble, tournament_simulator, betting_strategy, market_sentiment, sentiment_alert, odds_pattern_matcher
from data import store

store.init_db()


def _approx_one(a, b, c, tol=1e-6):
    return abs((a + b + c) - 1.0) < tol


def test_poisson():
    r = statistical_model.predict("Brazil", "Qatar")
    assert _approx_one(r["p_home"], r["p_draw"], r["p_away"], tol=1e-3)
    assert len(r["top_scores"]) >= 3
    print("✓ poisson", r["p_home"], r["p_draw"], r["p_away"])


def test_market_and_ensemble():
    provider = get_provider()
    odds = provider.get_odds("testmatch", "France", "Mexico")
    m = market_model.predict(odds)
    assert m["p_home"] is None or _approx_one(m["p_home"], m["p_draw"], m["p_away"], tol=1e-3)
    e = ultimate_ensemble.predict("France", "Mexico", odds)
    fp = e["final"]
    assert _approx_one(fp["p_home"], fp["p_draw"], fp["p_away"], tol=1e-3)
    assert len(e["top_scores"]) == 3
    print("✓ ensemble", fp)


def test_sentiment():
    provider = get_provider()
    odds = provider.get_odds("testmatch2", "England", "USA")
    s = market_sentiment.analyze(odds)
    assert "explanations" in s
    a = sentiment_alert.detect(odds)
    assert a["level"] in ("none", "low", "medium", "high")
    p = odds_pattern_matcher.match_pattern(odds)
    assert "matches" in p
    print("✓ sentiment heat=", s["heat_index"], "alert=", a["level"], "patterns=", len(p["matches"]))


def test_betting():
    provider = get_provider()
    odds = provider.get_odds("testmatch3", "Argentina", "Saudi Arabia")
    e = ultimate_ensemble.predict("Argentina", "Saudi Arabia", odds)
    b = betting_strategy.evaluate(e["final"], odds)
    assert "verdict" in b
    print("✓ betting", b["verdict"]["headline"])


def test_tournament():
    r = tournament_simulator.simulate(n_sims=1000)
    total = sum(t["prob"] for t in r["champion"])
    assert 95 <= total <= 105  # ~100%
    print("✓ tournament top champ:", r["champion"][0])


if __name__ == "__main__":
    test_poisson()
    test_market_and_ensemble()
    test_sentiment()
    test_betting()
    test_tournament()
    print("\nAll tests passed ✓")
