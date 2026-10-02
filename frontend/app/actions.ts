"use server";

import { revalidatePath } from "next/cache";

import { api, type Announcement } from "../lib/api";

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
    revalidatePath("/employees");
    revalidatePath("/");
    return { error: "" };
  } catch (error) {
    const message = error instanceof Error ? error.message : "เพิ่มพนักงานไม่สำเร็จ";
    return { error: message === "employee code or email already exists" ? "รหัสพนักงานหรืออีเมลนี้มีอยู่แล้ว" : message };
  }
}

export async function deleteEmployee(_: EmployeeState, formData: FormData): Promise<EmployeeState> {
  try {
    await api(`/api/admin/employees/${formData.get("employee_id")}/active`, { method: "PATCH", body: JSON.stringify({ active: formData.get("active") === "true" }) });
    revalidatePath("/employees");
    revalidatePath("/");
    return { error: "" };
  } catch (error) { return { error: error instanceof Error ? error.message : "เปลี่ยนสถานะไม่สำเร็จ" }; }
}

export type InviteState = { link: string; error: string };

export async function issueLink(_: InviteState, formData: FormData): Promise<InviteState> {
  try {
    const data = await api<{ link: string }>(`/api/admin/employees/${formData.get("employee_id")}/link`, {
      method: "POST",
    });
    return { link: data.link, error: "" };
  } catch (error) {
    return { link: "", error: error instanceof Error ? error.message : "ออกลิงก์ไม่สำเร็จ" };
  }
}

export async function decideLeave(_: EmployeeState, formData: FormData): Promise<EmployeeState> {
  try {
    await api(`/api/admin/leaves/${formData.get("leave_id")}/decision`, { method: "POST", body: JSON.stringify({ decision: formData.get("decision") }) });
    revalidatePath("/leaves");
    revalidatePath("/");
    return { error: "" };
  } catch (error) { return { error: error instanceof Error ? error.message : "พิจารณาคำขอไม่สำเร็จ" }; }
}

export type AnnouncementState = { message: string; error: string };

export async function createAnnouncement(
  _: AnnouncementState,
  formData: FormData,
): Promise<AnnouncementState> {
  try {
    const data = await api<Announcement>("/api/admin/announcements", {
      method: "POST",
      body: JSON.stringify({
        title: formData.get("title"),
        body: formData.get("body"),
        request_key: formData.get("request_key"),
      }),
    });
    revalidatePath("/announcements");
    revalidatePath("/");
    return {
      message: data.delivery_status === "sent"
        ? `บันทึกและส่งประกาศไปยัง ${data.sent_count} บัญชีแล้ว`
        : data.delivery_status === "no_recipients"
          ? "บันทึกแล้ว แต่ยังไม่มีพนักงานที่เชื่อม LINE"
          : "บันทึกประกาศแล้ว ส่ง LINE ยังไม่ครบ กดส่งอีกครั้งจากประวัติประกาศได้",
      error: "",
    };
  } catch (error) {
    revalidatePath("/announcements");
    revalidatePath("/");
    return {
      message: "",
      error: error instanceof Error ? error.message : "สร้างประกาศไม่สำเร็จ",
    };
  }
}

export async function updateEmployee(_: EmployeeState, formData: FormData): Promise<EmployeeState> {
  try {
    const body: Record<string, unknown> = Object.fromEntries(formData);
    for (const key of ["vacation", "sick", "personal", "vacation_entitlement", "sick_entitlement", "personal_entitlement"]) body[key] = Number(body[key]);
    if (!body.password) delete body.password;
    await api(`/api/admin/employees/${formData.get("employee_code")}`, { method: "PATCH", body: JSON.stringify(body) });
    revalidatePath("/employees");
    return { error: "" };
  } catch (error) {
    return { error: error instanceof Error ? error.message : "บันทึกไม่สำเร็จ" };
  }
}

export async function retryAnnouncement(formData: FormData) {
  await api(`/api/admin/announcements/${formData.get("id")}/retry`, { method: "POST" });
  revalidatePath("/announcements");
}

export async function retryLeaveNotification(formData: FormData) {
  await api(`/api/admin/leaves/${formData.get("id")}/notify`, { method: "POST" });
  revalidatePath("/leaves");
}

export async function saveHoliday(formData: FormData) {
  await api("/api/admin/holidays", { method: "POST", body: JSON.stringify({ date: formData.get("date"), name: formData.get("name") }) });
  revalidatePath("/holidays");
}

export async function deleteHoliday(formData: FormData) {
  await api(`/api/admin/holidays/${formData.get("id")}`, { method: "DELETE" });
  revalidatePath("/holidays");
}

export async function saveFaq(_: AnnouncementState, formData: FormData): Promise<AnnouncementState> {
  try {
    const id = formData.get("id");
    const result = await api<{ indexed: boolean }>(`/api/admin/faqs${id ? `/${id}` : ""}`, { method: id ? "PATCH" : "POST", body: JSON.stringify({ keyword: formData.get("keyword"), question: formData.get("question"), answer: formData.get("answer"), active: formData.get("active") === "on" }) });
    revalidatePath("/knowledge");
    return { message: result.indexed ? "บันทึก FAQ แล้ว" : "บันทึกแล้ว ใช้การค้นสำรองจนกว่าจะสร้างดัชนีได้", error: "" };
  } catch (error) { return { message: "", error: error instanceof Error ? error.message : "บันทึกไม่สำเร็จ" }; }
}

export async function uploadPolicy(_: AnnouncementState, formData: FormData): Promise<AnnouncementState> {
  try {
    const result = await api<{ indexed: boolean; chunk_count: number }>("/api/admin/documents", { method: "POST", body: formData });
    revalidatePath("/knowledge");
    return { message: `นำเข้าเอกสารแล้ว ${result.chunk_count} ส่วน${result.indexed ? "" : " ใช้การค้นสำรองจนกว่าจะสร้างดัชนีได้"}`, error: "" };
  } catch (error) { return { message: "", error: error instanceof Error ? error.message : "นำเข้าไม่สำเร็จ" }; }
}

export async function archivePolicy(formData: FormData) {
  await api(`/api/admin/documents/${formData.get("id")}`, { method: "DELETE" });
  revalidatePath("/knowledge");
}

export async function reindexPolicies(_: AnnouncementState): Promise<AnnouncementState> {
  try {
    const result = await api<{ indexed: boolean }>("/api/admin/documents/reindex", { method: "POST" });
    return { message: result.indexed ? "สร้างดัชนีค้นหาแล้ว" : "สร้างดัชนีไม่สำเร็จ ระบบยังใช้การค้นสำรองได้", error: "" };
  } catch (error) { return { message: "", error: error instanceof Error ? error.message : "สร้างดัชนีไม่สำเร็จ" }; }
}

export async function previewAnswer(_: AnnouncementState, formData: FormData): Promise<AnnouncementState> {
  try {
    const result = await api<{ answer: string | null }>("/api/admin/knowledge/search", { method: "POST", body: JSON.stringify({ question: formData.get("question") }) });
    return { message: result.answer ?? "ไม่พบคำตอบในฐานข้อมูล HR", error: "" };
  } catch (error) { return { message: "", error: error instanceof Error ? error.message : "ค้นหาไม่สำเร็จ" }; }
}
