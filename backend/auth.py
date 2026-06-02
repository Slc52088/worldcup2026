"""
auth.py
密码校验 + 防暴力破解 + 简单会话令牌签发。

安全说明：
- 使用 hmac.compare_digest 做恒定时间比较，避免时序攻击。
- 按客户端 IP 计失败次数，超过阈值进入冷却。
- 令牌为 HMAC 签名的时间戳，无状态校验，避免服务端存会话(适配 Render 免费档)。
"""
import hmac
import hashlib
import time
import base64
from collections import defaultdict
from config import config

# IP -> (失败次数, 首次失败时间戳)
_failed = defaultdict(lambda: [0, 0.0])


def _now() -> float:
    return time.time()


def is_locked(ip: str) -> tuple[bool, int]:
    """返回 (是否锁定, 剩余秒数)。"""
    count, first_ts = _failed[ip]
    if count < config.MAX_FAILED_ATTEMPTS:
        return False, 0
    elapsed = _now() - first_ts
    if elapsed >= config.LOCKOUT_SECONDS:
        # 冷却结束，重置
        _failed[ip] = [0, 0.0]
        return False, 0
    return True, int(config.LOCKOUT_SECONDS - elapsed)


def record_failure(ip: str) -> None:
    count, first_ts = _failed[ip]
    if count == 0:
        _failed[ip] = [1, _now()]
    else:
        _failed[ip][0] = count + 1


def record_success(ip: str) -> None:
    _failed[ip] = [0, 0.0]


def verify_password(candidate: str) -> bool:
    expected = config.ACCESS_PASSWORD.encode("utf-8")
    given = (candidate or "").encode("utf-8")
    return hmac.compare_digest(expected, given)


# ---------- 无状态令牌 ----------

def issue_token(remember: bool = False) -> str:
    """签发一个 HMAC 令牌：base64(expiry).signature"""
    ttl = 30 * 24 * 3600 if remember else 12 * 3600
    expiry = int(_now() + ttl)
    payload = str(expiry).encode()
    sig = hmac.new(config.SECRET_KEY.encode(), payload, hashlib.sha256).digest()
    token = base64.urlsafe_b64encode(payload).decode() + "." + base64.urlsafe_b64encode(sig).decode()
    return token


def validate_token(token: str) -> bool:
    try:
        payload_b64, sig_b64 = token.split(".")
        payload = base64.urlsafe_b64decode(payload_b64)
        sig = base64.urlsafe_b64decode(sig_b64)
        expected_sig = hmac.new(config.SECRET_KEY.encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(sig, expected_sig):
            return False
        expiry = int(payload.decode())
        return _now() < expiry
    except Exception:
        return False
