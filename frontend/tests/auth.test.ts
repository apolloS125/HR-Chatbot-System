import { afterEach, beforeEach, describe, expect, mock, spyOn, test } from "bun:test";
import { NextRequest } from "next/server";

const values = new Map<string, string>();
let cookieOptions: Record<string, unknown> = {};
mock.module("next/headers", () => ({
  cookies: async () => ({
    get: (name: string) => (values.has(name) ? { value: values.get(name) } : undefined),
    set: (name: string, value: string, options: Record<string, unknown>) => {
      values.set(name, value);
      cookieOptions = options;
    },
    delete: (name: string) => values.delete(name),
  }),
}));
mock.module("next/navigation", () => ({
  redirect: (path: string) => {
    throw new Error(`redirect:${path}`);
  },
  unstable_rethrow: (error: unknown) => {
    if (error instanceof Error && error.message.startsWith("redirect:")) {
      throw error;
    }
  },
}));
mock.module("next/cache", () => ({ revalidatePath: () => {} }));

const { login, logout } = await import("../app/login/actions");
const { api } = await import("../lib/api");
const { proxy } = await import("../proxy");
const { createEmployee } = await import("../app/actions");

beforeEach(() => {
  values.clear();
  cookieOptions = {};
});
afterEach(() => mock.restore());

function credentials() {
  const data = new FormData();
  data.set("username", "HR001");
  data.set("password", "strong-password");
  return data;
}

describe("Dashboard sessions", () => {
  test("proxy redirects without calling the backend", () => {
    const fetch = spyOn(globalThis, "fetch");
    const response = proxy(new NextRequest("http://localhost/employees"));
    expect(response.headers.get("location")).toBe("http://localhost/login");
    const authenticated = proxy(
      new NextRequest("http://localhost/employees", {
        headers: { cookie: "hr_session=test-token" },
      }),
    );
    expect(authenticated.headers.get("x-middleware-next")).toBe("1");
    expect(fetch).not.toHaveBeenCalled();
  });

  test("login stores an HttpOnly session, never the password", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(
      Response.json({ token: "session-token", expires_in: 3600 }),
    );
    await expect(login({ error: "" }, credentials())).rejects.toThrow("redirect:/");
    expect(values.get("hr_session")).toBe("session-token");
    expect(cookieOptions.httpOnly).toBe(true);
    expect(cookieOptions.secure).toBe(process.env.SESSION_COOKIE_SECURE !== "false");
    expect(cookieOptions.sameSite).toBe("strict");
    expect(cookieOptions.maxAge).toBe(3600);
    expect(JSON.stringify([...values])).not.toContain("strong-password");
  });

  test("rate-limited login does not create a cookie", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 429 }));
    const result = await login({ error: "" }, credentials());
    expect(result.error).toContain("5 นาที");
    expect(values.size).toBe(0);
  });

  test("API uses the session and redirects expired sessions", async () => {
    values.set("hr_session", "session-token");
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ ok: true }));
    await api("/api/admin/employees");
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer session-token");
    fetch.mockResolvedValue(new Response("", { status: 401 }));
    await expect(api("/api/admin/employees")).rejects.toThrow("redirect:/login?expired=1");
  });

  test("logout revokes the backend session and removes the cookie", async () => {
    values.set("hr_session", "session-token");
    const fetch = spyOn(globalThis, "fetch").mockResolvedValue(Response.json({ ok: true }));
    await expect(logout()).rejects.toThrow("redirect:/login");
    expect(values.has("hr_session")).toBe(false);
    const options = fetch.mock.calls[0][1] as RequestInit;
    expect(options.method).toBe("DELETE");
    expect(new Headers(options.headers).get("Authorization")).toBe("Bearer session-token");
  });

  test("logout removes the cookie during a backend outage", async () => {
    values.set("hr_session", "session-token");
    spyOn(globalThis, "fetch").mockRejectedValue(new Error("offline"));
    await expect(logout()).rejects.toThrow("redirect:/login");
    expect(values.has("hr_session")).toBe(false);
  });

  test("server actions preserve redirects when sessions expire", async () => {
    spyOn(globalThis, "fetch").mockResolvedValue(new Response("", { status: 401 }));
    await expect(createEmployee({ error: "" }, new FormData())).rejects.toThrow(
      "redirect:/login?expired=1",
    );
  });
});
