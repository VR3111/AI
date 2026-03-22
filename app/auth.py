import json
import os
import time
import uuid
from typing import Any
from urllib.request import Request as UrlRequest, urlopen

from dotenv import load_dotenv
from fastapi import Request
from fastapi.responses import JSONResponse
from jose import JWTError, jwk, jwt
from jose.utils import base64url_decode

load_dotenv()


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_ISSUER = f"{SUPABASE_URL}/auth/v1" if SUPABASE_URL else ""
SUPABASE_JWKS_URL = (
    f"{SUPABASE_ISSUER}/.well-known/jwks.json" if SUPABASE_ISSUER else ""
)
SUPABASE_JWT_AUDIENCE = os.getenv("SUPABASE_JWT_AUDIENCE", "authenticated")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
LEGACY_JWT_SECRET = os.getenv("P1_JWT_SECRET")
GUEST_SESSION_SECRET = os.getenv("P1_GUEST_SESSION_SECRET") or LEGACY_JWT_SECRET
GUEST_SESSION_COOKIE_NAME = os.getenv("P1_GUEST_SESSION_COOKIE_NAME", "p1_guest_session")
GUEST_SESSION_COOKIE_SECURE = (
    os.getenv("P1_GUEST_SESSION_COOKIE_SECURE", "false").lower() == "true"
)
GUEST_SESSION_COOKIE_MAX_AGE_SECONDS = int(
    os.getenv("P1_GUEST_SESSION_COOKIE_MAX_AGE_SECONDS", str(60 * 60 * 24 * 30))
)
GUEST_SESSION_ISSUER = os.getenv("P1_GUEST_SESSION_ISSUER", "p1-guest")
GUEST_SESSION_AUDIENCE = os.getenv("P1_GUEST_SESSION_AUDIENCE", "p1-guest")
GUEST_UPGRADE_TICKET_ISSUER = os.getenv(
    "P1_GUEST_UPGRADE_TICKET_ISSUER", "p1-guest-upgrade"
)
GUEST_UPGRADE_TICKET_AUDIENCE = os.getenv(
    "P1_GUEST_UPGRADE_TICKET_AUDIENCE", "p1-guest-upgrade"
)
GUEST_UPGRADE_TICKET_TTL_SECONDS = int(
    os.getenv("P1_GUEST_UPGRADE_TICKET_TTL_SECONDS", str(60 * 60 * 24 * 7))
)
JWKS_CACHE_TTL_SECONDS = 300

EXEMPT_PATHS = {
    "/health",
    "/auth/session",
    "/auth/guest-session",
    "/auth/guest-session/upgrade",
    "/auth/guest-session/upgrade-ticket",
}

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
        payload.get("sub"),
        payload.get("id"),
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and candidate.strip():
            return candidate

    return None


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


def _supabase_admin_request(path: str, method: str = "GET") -> Any:
    supabase_url = os.getenv("SUPABASE_URL", SUPABASE_URL).rstrip("/")
    service_role_key = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY", SUPABASE_SERVICE_ROLE_KEY
    )

    if not supabase_url or not service_role_key:
        raise RuntimeError("Supabase admin auth is not configured")

    request = UrlRequest(
        f"{supabase_url}{path}",
        method=method,
        headers={
            "apikey": service_role_key,
            "Authorization": f"Bearer {service_role_key}",
        },
    )

    with urlopen(request, timeout=10) as response:
        if response.status == 204:
            return None
        body = response.read()
        if not body:
            return None
        return json.loads(body.decode("utf-8"))


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


def _require_guest_session_secret() -> str:
    if not GUEST_SESSION_SECRET:
        raise RuntimeError("P1_GUEST_SESSION_SECRET is not configured")
    return GUEST_SESSION_SECRET


def _require_authenticated_bearer_token(request: Request) -> str:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        raise JWTError("Authenticated bearer token required")
    return auth.split(" ", 1)[1]


def _issue_guest_session_payload() -> dict:
    now = int(time.time())
    guest_user_id = f"guest-user-{uuid.uuid4()}"
    guest_tenant_id = f"guest-tenant-{uuid.uuid4()}"
    return {
        "sub": guest_user_id,
        "guest_user_id": guest_user_id,
        "tenant_id": guest_tenant_id,
        "guest_tenant_id": guest_tenant_id,
        "identity_type": "guest",
        "can_upgrade": True,
        "iss": GUEST_SESSION_ISSUER,
        "aud": GUEST_SESSION_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + GUEST_SESSION_COOKIE_MAX_AGE_SECONDS,
    }


def issue_guest_session() -> tuple[str, dict]:
    payload = _issue_guest_session_payload()
    token = jwt.encode(payload, _require_guest_session_secret(), algorithm="HS256")
    return token, payload


def issue_guest_upgrade_ticket(*, guest_payload: dict, email: str) -> str:
    normalized_email = email.strip().lower()
    if not normalized_email:
        raise ValueError("email is required")

    now = int(time.time())
    payload = {
        "sub": f"guest-upgrade-{uuid.uuid4()}",
        "guest_tenant_id": guest_payload.get("guest_tenant_id") or guest_payload.get("tenant_id"),
        "guest_user_id": guest_payload.get("guest_user_id") or guest_payload.get("sub"),
        "email": normalized_email,
        "identity_type": "guest_upgrade",
        "iss": GUEST_UPGRADE_TICKET_ISSUER,
        "aud": GUEST_UPGRADE_TICKET_AUDIENCE,
        "iat": now,
        "nbf": now,
        "exp": now + GUEST_UPGRADE_TICKET_TTL_SECONDS,
    }
    return jwt.encode(payload, _require_guest_session_secret(), algorithm="HS256")


def decode_guest_upgrade_ticket(ticket: str) -> dict:
    payload = jwt.decode(
        ticket,
        _require_guest_session_secret(),
        algorithms=["HS256"],
        issuer=GUEST_UPGRADE_TICKET_ISSUER,
        audience=GUEST_UPGRADE_TICKET_AUDIENCE,
    )
    if payload.get("identity_type") != "guest_upgrade":
        raise JWTError("Invalid guest upgrade ticket")
    return payload


def get_authenticated_user(request: Request) -> dict:
    token = _require_authenticated_bearer_token(request)
    return _fetch_supabase_user(token)


def delete_supabase_user(user_id: str) -> None:
    _supabase_admin_request(f"/auth/v1/admin/users/{user_id}", method="DELETE")


def _decode_guest_session(token: str) -> dict:
    payload = jwt.decode(
        token,
        _require_guest_session_secret(),
        algorithms=["HS256"],
        issuer=GUEST_SESSION_ISSUER,
        audience=GUEST_SESSION_AUDIENCE,
    )
    tenant_id = _extract_tenant_id(payload)
    if not tenant_id or payload.get("identity_type") != "guest":
        raise JWTError("Invalid guest session")
    return payload


def get_guest_session_payload(request: Request) -> dict | None:
    token = request.cookies.get(GUEST_SESSION_COOKIE_NAME)
    if not token:
        return None
    try:
        return _decode_guest_session(token)
    except (JWTError, RuntimeError):
        return None


def _resolve_bearer_payload(request: Request) -> dict | None:
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("Bearer "):
        return None

    token = auth.split(" ", 1)[1]
    return _resolve_authenticated_payload(token)


def resolve_request_identity(request: Request) -> dict | None:
    try:
        payload = _resolve_bearer_payload(request)
    except (JWTError, RuntimeError):
        raise

    if payload:
        return payload

    guest_payload = get_guest_session_payload(request)
    if guest_payload:
        return guest_payload

    return None


def apply_request_identity(request: Request, payload: dict) -> None:
    tenant_id = _extract_tenant_id(payload)
    if not tenant_id:
        raise JWTError("tenant_id missing in token")

    request.state.tenant_id = tenant_id
    request.state.identity_type = (
        "guest" if payload.get("identity_type") == "guest" else "authenticated"
    )
    request.state.identity_payload = payload

    parts = request.url.path.split("/")
    if len(parts) > 2 and parts[1] == "tenants" and parts[2] != tenant_id:
        raise PermissionError("Tenant access denied")


def build_session_response(
    payload: dict,
    *,
    pending_guest_tenant_id: str | None = None,
) -> dict:
    tenant_id = _extract_tenant_id(payload)
    identity_type = (
        "guest" if payload.get("identity_type") == "guest" else "authenticated"
    )
    user_id = payload.get("sub") or payload.get("id") or tenant_id
    email = payload.get("email")
    display_name = (
        payload.get("name")
        or payload.get("preferred_username")
        or email
        or user_id
    )

    return {
        "authenticated": True,
        "identity_type": identity_type,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "email": email,
        "display_name": display_name,
        "can_upgrade": identity_type == "guest",
        "pending_guest_tenant_id": pending_guest_tenant_id,
    }


def set_guest_session_cookie(response, token: str) -> None:
    response.set_cookie(
        key=GUEST_SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=GUEST_SESSION_COOKIE_SECURE,
        samesite="lax",
        max_age=GUEST_SESSION_COOKIE_MAX_AGE_SECONDS,
        path="/",
    )


def clear_guest_session_cookie(response) -> None:
    response.delete_cookie(
        key=GUEST_SESSION_COOKIE_NAME,
        path="/",
        samesite="lax",
    )


def auth_middleware(app):
    @app.middleware("http")
    async def authenticate(request: Request, call_next):
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        try:
            payload = resolve_request_identity(request)
        except (JWTError, RuntimeError):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"},
            )

        if not payload:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
            )

        try:
            apply_request_identity(request, payload)
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "tenant_id missing in token"},
            )
        except PermissionError:
            return JSONResponse(
                status_code=403,
                content={"detail": "Tenant access denied"},
            )

        return await call_next(request)
