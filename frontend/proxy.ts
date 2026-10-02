import { NextRequest, NextResponse } from "next/server";

export async function proxy(request: NextRequest) {
  try {
    const response = await fetch(`${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/admin/session`, {
      headers: { Authorization: request.headers.get("authorization") ?? "" },
      cache: "no-store",
    });
    if (response.ok) return NextResponse.next();
    if (response.status === 403) return new NextResponse("บัญชีนี้ไม่มีสิทธิ์เข้าถึงฝ่าย HR", { status: 403 });
    if (response.status !== 401) return new NextResponse("ระบบกำลังขัดข้อง กรุณาลองใหม่", { status: 503 });
    return new NextResponse("Authentication required", { status: 401, headers: { "WWW-Authenticate": 'Basic realm="HR Dashboard"' } });
  } catch {
    return new NextResponse("เชื่อมต่อระบบไม่สำเร็จ กรุณาลองใหม่", { status: 503 });
  }
}

export const config = { matcher: "/((?!liff(?:/|$)|_next/static|_next/image|favicon.ico).*)" };
