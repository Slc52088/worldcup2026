"""
store.py
SQLite (历史/预测准确率) + JSON 文件缓存 (API 结果)。
"""
from __future__ import annotations
import json
import os
import sqlite3
import time
from contextlib import contextmanager
from config import config


# ---------------- JSON 缓存 ----------------

def cache_path(key: str) -> str:
    return os.path.join(config.CACHE_DIR, f"{key}.json")


def write_cache(key: str, data: dict) -> None:
    with open(cache_path(key), "w", encoding="utf-8") as f:
        json.dump({"_cached_at": time.time(), "data": data}, f, ensure_ascii=False)


def read_cache(key: str, max_age_sec: int | None = None) -> dict | None:
    p = cache_path(key)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            blob = json.load(f)
        if max_age_sec is not None and (time.time() - blob["_cached_at"]) > max_age_sec:
            return None
        return blob["data"]
    except Exception:
        return None


# ---------------- SQLite ----------------

@contextmanager
def db():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with db() as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS predictions (
            match_id TEXT,
            model TEXT,
            p_home REAL, p_draw REAL, p_away REAL,
            created_at REAL,
            PRIMARY KEY (match_id, model, created_at)
        );
        CREATE TABLE IF NOT EXISTS results (
            match_id TEXT PRIMARY KEY,
            home_goals INTEGER, away_goals INTEGER,
            outcome TEXT,          -- 'home'|'draw'|'away'
            recorded_at REAL
        );
        CREATE TABLE IF NOT EXISTS model_weights (
            model TEXT PRIMARY KEY,
            weight REAL,
            brier REAL,
            hit_rate REAL,
            updated_at REAL
        );
        CREATE TABLE IF NOT EXISTS odds_snapshots (
            match_id TEXT,
            snapshot_at REAL,
            payload TEXT,
            PRIMARY KEY (match_id, snapshot_at)
        );
        """)


def save_prediction(match_id: str, model: str, ph: float, pd: float, pa: float) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?)",
            (match_id, model, ph, pd, pa, time.time()),
        )


def save_result(match_id: str, hg: int, ag: int) -> None:
    outcome = "home" if hg > ag else "away" if ag > hg else "draw"
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?)",
            (match_id, hg, ag, outcome, time.time()),
        )


def get_model_weights() -> dict:
    try:
        with db() as conn:
            rows = conn.execute("SELECT * FROM model_weights").fetchall()
        return {r["model"]: dict(r) for r in rows}
    except sqlite3.OperationalError:
        # 表尚未创建 (首次运行)，返回空让上层用默认权重
        return {}


def set_model_weight(model: str, weight: float, brier: float, hit_rate: float) -> None:
    with db() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO model_weights VALUES (?,?,?,?,?)",
            (model, weight, brier, hit_rate, time.time()),
        )


def get_predictions_with_results() -> list[dict]:
    """联表取已有结果的预测，供优化器评估。"""
    with db() as conn:
        rows = conn.execute("""
            SELECT p.match_id, p.model, p.p_home, p.p_draw, p.p_away, r.outcome
            FROM predictions p JOIN results r ON p.match_id = r.match_id
        """).fetchall()
    return [dict(r) for r in rows]
