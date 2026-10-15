"use server";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

export async function login(_: { error: string }, formData: FormData) {
  const username = String(formData.get("username") ?? "");
  const password = String(formData.get("password") ?? "");
  if (!username || username.length > 120 || !password || password.length > 128) {
    return { error: "กรุณาตรวจสอบชื่อผู้ใช้และรหัสผ่าน" };
  }
  let session: { token: string; expires_in: number };
  try {
    const response = await fetch(
      `${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/admin/session`,
      {
        method: "POST",
        headers: {
          Authorization: `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`,
        },
        cache: "no-store",
      },
    );
    if (!response.ok) {
      const retryAfter = Math.max(1, Number(response.headers.get("Retry-After")) || 1);
      const error =
        response.status === 429
          ? `ลองเข้าสู่ระบบหลายครั้งเกินไป กรุณารอ ${retryAfter} วินาที`
          : response.status >= 500
            ? "ระบบเข้าสู่ระบบยังไม่พร้อม กรุณาลองใหม่"
            : "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง หรือบัญชีไม่มีสิทธิ์ HR";
      return { error };
    }
    session = await response.json();
  } catch {
    return { error: "เชื่อมต่อระบบไม่สำเร็จ กรุณาลองใหม่" };
  }
  (await cookies()).set("hr_session", session.token, {
    httpOnly: true,
    secure: process.env.SESSION_COOKIE_SECURE !== "false",
    sameSite: "strict",
    path: "/",
    maxAge: session.expires_in,
  });
  redirect("/");
}

export async function logout() {
  const jar = await cookies();
  const token = jar.get("hr_session")?.value;
  if (token) {
    try {
      await fetch(`${process.env.BACKEND_URL ?? "http://localhost:8000"}/api/admin/session`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
        cache: "no-store",
      });
    } catch {
      // The browser session is cleared even when the backend is unavailable.
    } finally {
      jar.delete("hr_session");
    }
  }
  redirect("/login");
}
