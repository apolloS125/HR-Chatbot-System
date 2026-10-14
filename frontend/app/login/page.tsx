"use client";

import { useActionState } from "react";
import { login } from "./actions";

export default function LoginPage() {
  const [state, action, pending] = useActionState(login, { error: "" });
  return (
    <main className="login-page mx-auto grid min-h-dvh max-w-md content-center p-6">
      <h1 className="mb-6 text-2xl font-bold">เข้าสู่ระบบ HR Dashboard</h1>
      <form action={action} className="grid gap-4">
        <label className="grid gap-2">
          ชื่อผู้ใช้ / รหัสพนักงาน
          <input
            name="username"
            autoComplete="username"
            maxLength={120}
            required
            className="rounded border bg-white p-3"
          />
        </label>
        <label className="grid gap-2">
          รหัสผ่าน
          <input
            name="password"
            type="password"
            autoComplete="current-password"
            maxLength={128}
            required
            className="rounded border bg-white p-3"
          />
        </label>
        {state.error && (
          <p role="alert" className="text-red-700">
            {state.error}
          </p>
        )}
        <button
          disabled={pending}
          className="rounded bg-[#087747] p-3 text-white disabled:opacity-50"
        >
          {pending ? "กำลังเข้าสู่ระบบ…" : "เข้าสู่ระบบ"}
        </button>
      </form>
    </main>
  );
}
