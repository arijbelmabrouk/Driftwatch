"""auth.py — lightweight user authentication for Driftwatch."""

import os
import hmac
import json
import time
import base64
import hashlib
from pathlib import Path
from dotenv import load_dotenv


load_dotenv(dotenv_path=Path(__file__).parent / ".env", override=True)

JWT_SECRET = os.getenv("JWT_SECRET", "driftwatch-default-secret").encode("utf-8")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_SECONDS = int(os.getenv("JWT_EXPIRATION_SECONDS", "86400"))


def _urlsafe_b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("utf-8")


def _urlsafe_b64decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(message: bytes) -> bytes:
    return hmac.new(JWT_SECRET, message, hashlib.sha256).digest()


def _encode_jwt(payload: dict) -> str:
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    header_bytes = json.dumps(header, separators=(",", ":")).encode("utf-8")
    payload_bytes = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    segments = [
        _urlsafe_b64encode(header_bytes),
        _urlsafe_b64encode(payload_bytes),
    ]
    signing_input = ".".join(segments).encode("utf-8")
    signature = _urlsafe_b64encode(_sign(signing_input))
    return ".".join(segments + [signature])


def _decode_jwt(token: str) -> dict | None:
    try:
        header_b64, payload_b64, signature_b64 = token.split(".")
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_signature = _sign(signing_input)
        actual_signature = _urlsafe_b64decode(signature_b64)
        if not hmac.compare_digest(expected_signature, actual_signature):
            return None
        payload_json = _urlsafe_b64decode(payload_b64)
        payload = json.loads(payload_json)
        return payload
    except Exception:
        return None


def create_access_token(user_id: str, email: str, expires_in: int | None = None) -> str:
    expires = int(time.time()) + (expires_in or JWT_EXPIRATION_SECONDS)
    payload = {
        "sub": user_id,
        "email": email,
        "exp": expires,
    }
    return _encode_jwt(payload)


def verify_access_token(token: str) -> dict | None:
    payload = _decode_jwt(token)
    if not payload:
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or time.time() > exp:
        return None
    return payload


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    hash_bytes = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180000)
    return f"{_urlsafe_b64encode(salt)}${_urlsafe_b64encode(hash_bytes)}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt_b64, hash_b64 = stored_hash.split("$", 1)
        salt = _urlsafe_b64decode(salt_b64)
        expected_hash = _urlsafe_b64decode(hash_b64)
        actual_hash = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 180000)
        return hmac.compare_digest(actual_hash, expected_hash)
    except Exception:
        return False
