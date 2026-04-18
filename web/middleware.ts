import { NextResponse, type NextRequest } from "next/server";

const PUBLIC_PATHS = new Set(["/login", "/favicon.ico"]);

export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;
  if (PUBLIC_PATHS.has(pathname) || pathname.startsWith("/_next") || pathname.startsWith("/api/")) {
    return NextResponse.next();
  }

  const hasSession = request.cookies.has("langperf_session");
  if (hasSession) {
    if (pathname === "/") {
      const url = request.nextUrl.clone();
      url.pathname = "/queue";
      return NextResponse.redirect(url);
    }
    return NextResponse.next();
  }

  const apiBase = process.env.LANGPERF_API_URL ?? "http://localhost:4318";
  try {
    const res = await fetch(`${apiBase}/api/auth/mode`, { cache: "no-store" });
    if (res.ok) {
      const body = (await res.json()) as { mode: "single_user" | "multi_user" };
      if (body.mode === "single_user") return NextResponse.next();
    }
  } catch {
    // If API unreachable, fall through to redirect
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = "/login";
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
