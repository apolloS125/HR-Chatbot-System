const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
const headers = { "X-Admin-Key": process.env.ADMIN_API_KEY ?? "change-me" };

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
};

export type Leave = {
  id: string;
  employee_code: string;
  name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: string;
  reason: string;
  status: string;
};

export type Announcement = {
  id: string;
  title: string;
  body: string;
  published_at: string;
};

export async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${backend}${path}`, { headers, cache: "no-store" });
  if (!response.ok) throw new Error(`โหลดข้อมูลไม่สำเร็จ: ${path}`);
  return response.json();
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
};
