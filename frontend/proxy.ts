import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  if (request.cookies.get("hr_session")?.value) {
    return NextResponse.next();
  }
  return NextResponse.redirect(new URL("/login", request.url));
}

export const config = {
  matcher: "/((?!login(?:/|$)|liff(?:/|$)|_next/static|_next/image|favicon.ico).*)",
};
