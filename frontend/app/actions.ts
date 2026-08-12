"use server";

import { revalidatePath } from "next/cache";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

async function api(path: string, init?: RequestInit) {
  const response = await fetch(`${backend}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      "X-Admin-Key": process.env.ADMIN_API_KEY ?? "change-me",
      ...init?.headers,
    },
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail ?? "Backend request failed");
  }
  return response.json();
}

export type EmployeeState = { error: string };

export async function createEmployee(_: EmployeeState, formData: FormData): Promise<EmployeeState> {
  try {
    await api("/api/admin/employees", {
      method: "POST",
      body: JSON.stringify({
        employee_code: formData.get("employee_code"),
        name: formData.get("name"),
        work_email: formData.get("work_email"),
        role: formData.get("role"),
      }),
    });
    revalidatePath("/");
    return { error: "" };
  } catch (error) {
    const message = error instanceof Error ? error.message : "เพิ่มพนักงานไม่สำเร็จ";
    return { error: message === "employee code or email already exists" ? "รหัสพนักงานหรืออีเมลนี้มีอยู่แล้ว" : message };
  }
}

export async function deleteEmployee(formData: FormData) {
  await api(`/api/admin/employees/${formData.get("employee_id")}`, {
    method: "DELETE",
  });
  revalidatePath("/");
}

export type InviteState = { link: string; error: string };

export async function issueLink(_: InviteState, formData: FormData): Promise<InviteState> {
  try {
    const data = await api(`/api/admin/employees/${formData.get("employee_id")}/link`, {
      method: "POST",
    });
    return { link: data.link, error: "" };
  } catch (error) {
    return { link: "", error: error instanceof Error ? error.message : "ออกลิงก์ไม่สำเร็จ" };
  }
}

export async function decideLeave(formData: FormData) {
  await api(`/api/admin/leaves/${formData.get("leave_id")}/decision`, {
    method: "POST",
    body: JSON.stringify({
      decision: formData.get("decision"),
      decided_by: process.env.HR_DISPLAY_NAME ?? "HR",
    }),
  });
  revalidatePath("/");
}

export type AnnouncementState = { message: string; error: string };

export async function createAnnouncement(
  _: AnnouncementState,
  formData: FormData,
): Promise<AnnouncementState> {
  try {
    const data = await api("/api/admin/announcements", {
      method: "POST",
      body: JSON.stringify({
        title: formData.get("title"),
        body: formData.get("body"),
      }),
    });
    revalidatePath("/");
    return {
      message: data.recipient_count
        ? `บันทึกและส่งประกาศไปยัง ${data.recipient_count} บัญชีแล้ว`
        : "บันทึกแล้ว แต่ยังไม่มีพนักงานที่เชื่อม LINE",
      error: "",
    };
  } catch (error) {
    revalidatePath("/");
    return {
      message: "",
      error: error instanceof Error ? error.message : "สร้างประกาศไม่สำเร็จ",
    };
  }
}
