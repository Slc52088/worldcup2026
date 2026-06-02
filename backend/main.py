"""
main.py
FastAPI 应用：路由、密码中间件、调度器、API 端点。
"""
from __future__ import annotations
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler

from config import config
import auth
from data import store, data_fetcher
from data.odds_provider import get_provider
from models import ultimate_ensemble, market_sentiment, sentiment_alert, tournament_simulator, betting_strategy, optimizer

# ---------------- 全局状态 ----------------
_state = {"fixtures": [], "fixtures_meta": {}, "champion": None, "dashboard": None}
scheduler = BackgroundScheduler(daemon=True)


def refresh_data():
    """定时刷新赛程与冠军模拟。"""
    res = data_fetcher.get_worldcup_fixtures()
    _state["fixtures"] = res["fixtures"]
    _state["fixtures_meta"] = {k: v for k, v in res.items() if k != "fixtures"}
    store.write_cache("fixtures", res)
    # 冠军模拟较重，缓存
    champ = tournament_simulator.simulate()
    _state["champion"] = champ
    store.write_cache("champion", champ)
    # 优化器评估
    opt = optimizer.evaluate_and_optimize()
    _state["dashboard"] = _build_dashboard(opt)
    store.write_cache("dashboard", _state["dashboard"])


def _build_dashboard(opt: dict) -> dict:
    return {
        "optimizer": opt,
        "model_weights": opt.get("weights", {}),
        "accuracy_note": "随着比赛结果累积，下方将展示各模型命中率与 Brier 趋势。",
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    store.init_db()
    # 优先读缓存，避免冷启动阻塞
    cached = store.read_cache("fixtures")
    if cached:
        _state["fixtures"] = cached["fixtures"]
        _state["fixtures_meta"] = {k: v for k, v in cached.items() if k != "fixtures"}
    _state["champion"] = store.read_cache("champion")
    _state["dashboard"] = store.read_cache("dashboard")
    try:
        refresh_data()
    except Exception as e:
        print("Initial refresh failed:", e)
    scheduler.add_job(refresh_data, "interval", minutes=config.UPDATE_INTERVAL_MINUTES,
                      id="refresh", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="WorldCup 2026 Prediction API", version="1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.ALLOWED_ORIGINS or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------- 认证 ----------------
class PasswordIn(BaseModel):
    password: str
    remember: bool = False


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def require_auth(authorization: str = Header(default="")) -> bool:
    token = authorization.replace("Bearer ", "").strip()
    if not auth.validate_token(token):
        raise HTTPException(status_code=401, detail="未授权或会话已过期，请重新登录。")
    return True


@app.post("/api/verify-password")
async def verify_password(body: PasswordIn, request: Request):
    ip = client_ip(request)
    locked, remaining = auth.is_locked(ip)
    if locked:
        raise HTTPException(status_code=429,
                            detail=f"尝试次数过多，请 {remaining} 秒后再试。")
    if auth.verify_password(body.password):
        auth.record_success(ip)
        token = auth.issue_token(remember=body.remember)
        return {"success": True, "token": token}
    auth.record_failure(ip)
    _, remaining_attempts = auth.is_locked(ip)
    raise HTTPException(status_code=401, detail="密码错误。")


# ---------------- 业务端点 ----------------
def _now_iso():
    return datetime.now(timezone.utc).isoformat()


@app.get("/api/health")
async def health():
    return {"status": "ok", "time": _now_iso()}


@app.get("/api/matches")
async def get_matches(_: bool = Depends(require_auth)):
    provider = get_provider()
    matches = []
    for f in _state["fixtures"][:40]:
        odds = provider.get_odds(f["id"], f["home"], f["away"])
        sent = market_sentiment.analyze(odds)
        # 轻量预览概率 (仅用市场或泊松快速值)
        pred = ultimate_ensemble.predict(f["home"], f["away"], odds)
        matches.append({
            **f,
            "preview": {
                "p_home": pred["final"]["p_home"],
                "p_draw": pred["final"]["p_draw"],
                "p_away": pred["final"]["p_away"],
            },
            "heat_index": sent.get("heat_index"),
            "is_real_odds": odds.get("is_real", False),
        })
    return {"matches": matches, "meta": _state["fixtures_meta"], "last_updated": _now_iso()}


@app.get("/api/matches/{match_id}")
async def get_match(match_id: str, _: bool = Depends(require_auth)):
    f = data_fetcher.get_match_detail(match_id, _state["fixtures"])
    if not f:
        raise HTTPException(status_code=404, detail="未找到该比赛。")
    provider = get_provider()
    odds = provider.get_odds(match_id, f["home"], f["away"])

    pred = ultimate_ensemble.predict(f["home"], f["away"], odds)
    sentiment = market_sentiment.analyze(odds)
    alert = sentiment_alert.detect(odds)
    betting = betting_strategy.evaluate(pred["final"], odds)

    # 记录预测供优化器学习
    for comp in pred["components"]:
        sub = pred["sub_models"].get(comp["model"])
        if sub and sub.get("p_home") is not None:
            store.save_prediction(match_id, comp["model"], sub["p_home"], sub["p_draw"], sub["p_away"])

    home_form = data_fetcher.get_team_recent_form(f["home"])
    away_form = data_fetcher.get_team_recent_form(f["away"])

    return {
        "match": f,
        "prediction": {
            "final": pred["final"],
            "summary": pred["summary"],
            "top_scores": pred["top_scores"],
            "components": pred["components"],
            "adjustments": pred["adjustments"],
            "base_probs": pred["base_probs"],
            "weights_used": pred["weights_used"],
        },
        "sentiment": {**sentiment, "alert": alert},
        "pattern_matches": pred["sub_models"]["pattern"],
        "betting": betting,
        "team_form": {"home": home_form, "away": away_form},
        "odds": {
            "is_real": odds.get("is_real", False),
            "source": odds.get("source"),
            "bookmakers": odds.get("bookmakers", []),
            "handicap": odds.get("handicap"),
            "totals": odds.get("totals"),
            "history": odds.get("history", []),
            "note": odds.get("note"),
        },
        "last_updated": _now_iso(),
    }


@app.get("/api/matches/{match_id}/sentiment")
async def get_sentiment(match_id: str, _: bool = Depends(require_auth)):
    f = data_fetcher.get_match_detail(match_id, _state["fixtures"])
    if not f:
        raise HTTPException(status_code=404, detail="未找到该比赛。")
    provider = get_provider()
    odds = provider.get_odds(match_id, f["home"], f["away"])
    sentiment = market_sentiment.analyze(odds)
    alert = sentiment_alert.detect(odds)
    return {"sentiment": sentiment, "alert": alert, "last_updated": _now_iso()}


@app.get("/api/market-overview")
async def market_overview(_: bool = Depends(require_auth)):
    provider = get_provider()
    rows = []
    for f in _state["fixtures"][:40]:
        odds = provider.get_odds(f["id"], f["home"], f["away"])
        sent = market_sentiment.analyze(odds)
        alert = sentiment_alert.detect(odds)
        rows.append({
            "id": f["id"], "home": f["home"], "away": f["away"],
            "home_flag": f["home_flag"], "away_flag": f["away_flag"],
            "kickoff": f["kickoff"],
            "heat_index": sent.get("heat_index") or 0,
            "alert_level": alert["level"],
        })
    rows.sort(key=lambda r: r["heat_index"], reverse=True)
    return {"rankings": rows, "last_updated": _now_iso()}


@app.get("/api/odds-events")
async def odds_events(_: bool = Depends(require_auth)):
    """赛事自动发现：列出当前赔率源提供的所有世界杯场次。"""
    provider = get_provider()
    result = provider.list_events()
    return {**result, "last_updated": _now_iso()}


@app.get("/api/champion")
async def champion(_: bool = Depends(require_auth)):
    if not _state["champion"]:
        _state["champion"] = tournament_simulator.simulate()
    return {**_state["champion"], "last_updated": _now_iso()}


@app.get("/api/dashboard")
async def dashboard(_: bool = Depends(require_auth)):
    if not _state["dashboard"]:
        _state["dashboard"] = _build_dashboard(optimizer.evaluate_and_optimize())
    return {**_state["dashboard"], "last_updated": _now_iso()}


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,
                        content={"detail": exc.detail, "last_updated": _now_iso()})
