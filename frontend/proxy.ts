import { timingSafeEqual } from "node:crypto";
import { NextRequest, NextResponse } from "next/server";

export function proxy(request: NextRequest) {
  const authorization = request.headers.get("authorization") ?? "";
  const expected = `Basic ${Buffer.from(`${process.env.HR_USERNAME ?? "hr"}:${process.env.HR_PASSWORD ?? "change-me"}`).toString("base64")}`;
  const actualBuffer = Buffer.from(authorization);
  const expectedBuffer = Buffer.from(expected);
  if (actualBuffer.length !== expectedBuffer.length || !timingSafeEqual(actualBuffer, expectedBuffer)) {
    return new NextResponse("Authentication required", {
      status: 401,
      headers: { "WWW-Authenticate": 'Basic realm="HR Dashboard"' },
    });
  }
  return NextResponse.next();
}

export const config = { matcher: "/((?!liff|_next/static|_next/image|favicon.ico).*)" };
