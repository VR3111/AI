import os
from fastapi import Request, HTTPException
from jose import jwt, JWTError
from fastapi.responses import JSONResponse


JWT_SECRET = os.getenv("P1_JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("P1_JWT_SECRET is not set")
JWT_ALGO = "HS256"

EXEMPT_PATHS = {"/health"}

def auth_middleware(app):
    @app.middleware("http")
    async def authenticate(request: Request, call_next):

        # Allow CORS preflight to pass without auth
        if request.method == "OPTIONS":
            return await call_next(request)

        if request.url.path in EXEMPT_PATHS:
            return await call_next(request)

        auth = request.headers.get("Authorization")
        if not auth or not auth.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing Authorization header"}
            )


        token = auth.split(" ", 1)[1]

        try:
             payload = jwt.decode(
	         token,
                 JWT_SECRET,
                 algorithms=[JWT_ALGO],
                 options={"verify_aud": False}
             )

        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token"}
            )


        tenant_id = payload.get("tenant_id")
        if not tenant_id:
            return JSONResponse(
                status_code=401,
                content={"detail": "tenant_id missing in token"}
            )


        # Attach tenant to request context
        request.state.tenant_id = tenant_id

        # Enforce tenant match for ingestion routes
        parts = request.url.path.split("/")
        if len(parts) > 2 and parts[1] == "tenants":
            if parts[2] != tenant_id:
                return JSONResponse(
                    status_code=403,
                    content={"detail": "Tenant access denied"}
                )

        return await call_next(request)
