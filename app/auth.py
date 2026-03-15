import json
import os
import time
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else ""
SUPABASE_JWKS_URL = (
    f"{SUPABASE_ISSUER}/.well-known/jwks.json" if SUPABASE_ISSUER else ""
)
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
LEGACY_JWT_SECRET = os.getenv("P1_JWT_SECRET")
DEFAULT_TENANT_ID = "acme"
JWKS_CACHE_TTL_SECONDS = 300

EXEMPT_PATHS = {"/health"}

_jwks_cache: dict | None = None
_jwks_cache_fetched_at = 0.0


def _fetch_jwks() -> dict:
    global _jwks_cache, _jwks_cache_fetched_at

    if (
        _jwks_cache is not None
        and time.time() - _jwks_cache_fetched_at < JWKS_CACHE_TTL_SECONDS
    ):
        return _jwks_cache

    if not SUPABASE_JWKS_URL:
        raise RuntimeError("SUPABASE_URL is not set")

    with urlopen(SUPABASE_JWKS_URL, timeout=5) as response:
        _jwks_cache = json.loads(response.read().decode("utf-8"))
        _jwks_cache_fetched_at = time.time()
        return _jwks_cache


def _verify_supabase_token(token: str) -> dict:
    header = jwt.get_unverified_header(token)
    algorithm = header.get("alg")
    key_id = header.get("kid")

    if algorithm and algorithm.startswith("HS"):
        if not LEGACY_JWT_SECRET:
            raise JWTError("Legacy JWT secret is not configured")

        return jwt.decode(
            token,
            LEGACY_JWT_SECRET,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )

    keys = _fetch_jwks().get("keys", [])
    key_data = next((candidate for candidate in keys if candidate.get("kid") == key_id), None)
    if not key_data:
        raise JWTError("Signing key not found")

    signing_input, encoded_signature = token.rsplit(".", 1)
    decoded_signature = base64url_decode(encoded_signature.encode("utf-8"))
    public_key = jwk.construct(key_data, algorithm=algorithm)

    if not public_key.verify(signing_input.encode("utf-8"), decoded_signature):
        raise JWTError("Invalid token signature")

    payload = jwt.get_unverified_claims(token)
    _validate_claims(payload)
    return payload


def _validate_claims(payload: dict) -> None:
    now = time.time()
    exp = payload.get("exp")
    if exp is None or float(exp) <= now:
        raise JWTError("Token expired")

    nbf = payload.get("nbf")
    if nbf is not None and float(nbf) > now:
        raise JWTError("Token not active")

    issuer = payload.get("iss")
    if SUPABASE_ISSUER and issuer != SUPABASE_ISSUER:
        raise JWTError("Invalid token issuer")

    if SUPABASE_JWT_AUDIENCE:
        audience = payload.get("aud")
        if isinstance(audience, str):
            audiences = {audience}
        elif isinstance(audience, list):
            audiences = {str(item) for item in audience}
        else:
            audiences = set()

        if SUPABASE_JWT_AUDIENCE not in audiences:
            raise JWTError("Invalid token audience")


def _extract_tenant_id(payload: dict) -> str | None:
    candidates = [
        payload.get("tenant_id"),
        payload.get("app_metadata", {}).get("tenant_id")
        if isinstance(payload.get("app_metadata"), dict)
        else None,
        payload.get("user_metadata", {}).get("tenant_id")
        if isinstance(payload.get("user_metadata"), dict)
        else None,
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    return DEFAULT_TENANT_ID


def _fetch_supabase_user(token: str) -> dict:
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise RuntimeError("Supabase auth fallback is not configured")

    request = UrlRequest(
        f"{SUPABASE_URL}/auth/v1/user",
        headers={
            "apikey": SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
        },
    )

    with urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def _resolve_authenticated_payload(token: str) -> dict:
    try:
        payload = _verify_supabase_token(token)
        if _extract_tenant_id(payload):
            return payload
    except Exception:
        try:
            payload = jwt.get_unverified_claims(token)
            _validate_claims(payload)
            if _extract_tenant_id(payload):
                return payload
        except Exception:
            pass

    user = _fetch_supabase_user(token)
    tenant_id = _extract_tenant_id(user)
    if not tenant_id:
        raise JWTError("tenant_id missing in token")

    return {
        "sub": user.get("id"),
        "email": user.get("email"),
        "tenant_id": tenant_id,
        "app_metadata": user.get("app_metadata"),
        "user_metadata": user.get("user_metadata"),
    }


def auth_middleware(app):
    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"},
            )

        token = auth.split(" ", 1)[1]

        try:
            payload = _resolve_authenticated_payload(token)
        except (JWTError, RuntimeError):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        tenant_id = _extract_tenant_id(payload)
        if not tenant_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "tenant_id missing in token"},
            )

        request.state.tenant_id = tenant_id

        parts = request.url.path.split("/")
        if len(parts) > 2 and parts[1] == "tenants" and parts[2] != tenant_id:
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant access denied"},
            )

        return await call_next(request)
