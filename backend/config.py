"""
config.py
全局配置：从环境变量读取，提供默认值以便本地开发。
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ---- 门禁 ----
    ACCESS_PASSWORD: str = os.getenv("ACCESS_PASSWORD", "worldcup2026")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # ---- 防暴力破解 ----
    MAX_FAILED_ATTEMPTS: int = int(os.getenv("MAX_FAILED_ATTEMPTS", "5"))
    LOCKOUT_SECONDS: int = int(os.getenv("LOCKOUT_SECONDS", "300"))  # 5 分钟

    # ---- CORS ----
    ALLOWED_ORIGINS: list = [
        o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip()
    ]

    # ---- 赔率数据源 ----
    ODDS_API_KEY: str = os.getenv("ODDS_API_KEY", "")  # 为空则使用模拟引擎
    ODDS_API_BASE: str = "https://api.the-odds-api.com/v4"

    # ---- 赛程数据源 (openfootball via jsDelivr) ----
    # 注：世界杯年份目录。2026 数据在赛前可能尚未完整，代码会优雅降级到内置队伍池。
    FIXTURES_URL: str = os.getenv(
        "FIXTURES_URL",
        "https://cdn.jsdelivr.net/gh/openfootball/worldcup.json@master/2022/worldcup.json",
    )

    # ---- 蒙特卡洛 ----
    MC_SIMULATIONS: int = int(os.getenv("MC_SIMULATIONS", "10000"))

    # ---- 缓存 ----
    CACHE_DIR: str = os.path.join(os.path.dirname(__file__), "data", "cache")
    DB_PATH: str = os.path.join(os.path.dirname(__file__), "worldcup.db")

    # ---- 调度 ----
    UPDATE_INTERVAL_MINUTES: int = int(os.getenv("UPDATE_INTERVAL_MINUTES", "30"))


config = Config()

# 确保缓存目录存在
os.makedirs(config.CACHE_DIR, exist_ok=True)
