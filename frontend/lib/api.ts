import { headers as requestHeaders } from "next/headers";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
export async function adminHeaders() {
  return { Authorization: (await requestHeaders()).get("authorization") ?? "" };
}

export type Summary = {
  active_employees: number;
  linked_employees: number;
  pending_leaves: number;
};

export type Employee = {
  id: string;
  employee_code: string;
  name: string;
  work_email: string;
  role: string;
  active: boolean;
  line_linked: boolean;
  balances: Record<string, number>;
  entitlements: Record<string, number>;
  balances_year: number;
};

export type Leave = {
  id: string;
  employee_code: string;
  name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  attachment_id?: string;
  half_day?: string;
  notification_status?: string;
  reason: string;
  status: string;
};

export type Announcement = {
  id: string;
  title: string;
  body: string;
  published_at: string;
  delivery_status: string;
  recipient_count: number;
  sent_count: number;
};

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${backend}${path}`, {
    ...init,
    headers: { ...(init?.body instanceof FormData ? {} : { "Content-Type": "application/json" }), ...await adminHeaders(), ...init?.headers },
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = Array.isArray(data.detail)
      ? data.detail.map((item: { msg: string }) => item.msg).join("; ")
      : data.detail;
    throw new Error(detail ?? "ทำรายการไม่สำเร็จ");
  }
  return response.json();
}

export function get<T>(path: string): Promise<T> {
  return api<T>(path);
}

export function formatDate(value: string) {
  return new Intl.DateTimeFormat("th-TH", { dateStyle: "medium" }).format(new Date(value));
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("th-TH", {
    dateStyle: "medium",
    timeStyle: "short",
    timeZone: "Asia/Bangkok",
  }).format(new Date(value));
}

export const leaveLabels: Record<string, string> = {
  vacation: "พักร้อน",
  sick: "ลาป่วย",
  personal: "ลากิจ",
};

export const statusLabels: Record<string, string> = {
  pending: "รออนุมัติ",
  approved: "อนุมัติแล้ว",
  rejected: "ปฏิเสธ",
  cancelled: "ยกเลิกแล้ว",
};
