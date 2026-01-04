import { NextRequest, NextResponse } from "next/server";

const DEV_BYPASS = process.env.NODE_ENV === "development";

export function middleware(req: NextRequest) {
  if (DEV_BYPASS) {
    const requestHeaders = new Headers(req.headers);
    requestHeaders.set("x-tenant-id", "dev_tenant");

    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  }

  const auth =
    req.headers.get("authorization") ||
    req.cookies.get("Authorization")?.value;

  if (!auth || !auth.startsWith("Bearer ")) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  const token = auth.replace("Bearer ", "");

  const payloadPart = token.split(".")[1];
  if (!payloadPart) {
    return NextResponse.redirect(new URL("/login", req.url));
  }

  try {
    const payload = JSON.parse(
      Buffer.from(payloadPart, "base64").toString("utf-8")
    );

    if (!payload.tenant_id) {
      return NextResponse.redirect(new URL("/login", req.url));
    }

    const requestHeaders = new Headers(req.headers);
    requestHeaders.set("x-tenant-id", payload.tenant_id);

    return NextResponse.next({
      request: {
        headers: requestHeaders,
      },
    });
  } catch {
    return NextResponse.redirect(new URL("/login", req.url));
  }
}

export const config = {
  matcher: [
    "/((?!_next|favicon.ico).*)",
  ],
};

