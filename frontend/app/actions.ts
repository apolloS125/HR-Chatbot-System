"use server";

import { revalidatePath } from "next/cache";

import { api, type Announcement } from "../lib/api";

export type EmployeeState = { error: string };
export type InviteState = { link: string; error: string };
export type AnnouncementState = { message: string; error: string };

export async function createEmployee(
  _: EmployeeState,
  formData: FormData,
): Promise<EmployeeState> {
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
    const duplicateMessage = "รหัสพนักงานหรืออีเมลนี้มีอยู่แล้ว";

    return {
      error: message === "employee code or email already exists" ? duplicateMessage : message,
    };
  }
}

export async function deleteEmployee(
  _: EmployeeState,
  formData: FormData,
): Promise<EmployeeState> {
  try {
    const employeeId = formData.get("employee_id");
    const active = formData.get("active") === "true";

    await api(`/api/admin/employees/${employeeId}/active`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    });
    revalidatePath("/employees");
    revalidatePath("/");
    return { error: "" };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "เปลี่ยนสถานะไม่สำเร็จ",
    };
  }
}

export async function removeEmployee(
  _: EmployeeState,
  formData: FormData,
): Promise<EmployeeState> {
  try {
    const employeeId = formData.get("employee_id");
    await api(`/api/admin/employees/${employeeId}`, { method: "DELETE" });
    revalidatePath("/employees");
    revalidatePath("/");
    return { error: "" };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "ลบพนักงานไม่สำเร็จ",
    };
  }
}

export async function issueLink(
  _: InviteState,
  formData: FormData,
): Promise<InviteState> {
  try {
    const employeeId = formData.get("employee_id");
    const data = await api<{ link: string }>(`/api/admin/employees/${employeeId}/link`, {
      method: "POST",
    });
    return { link: data.link, error: "" };
  } catch (error) {
    return {
      link: "",
      error: error instanceof Error ? error.message : "ออกลิงก์ไม่สำเร็จ",
    };
  }
}

export async function decideLeave(
  _: EmployeeState,
  formData: FormData,
): Promise<EmployeeState> {
  try {
    const leaveId = formData.get("leave_id");
    const decision = formData.get("decision");

    await api(`/api/admin/leaves/${leaveId}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision }),
    });
    revalidatePath("/leaves");
    revalidatePath("/");
    return { error: "" };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "พิจารณาคำขอไม่สำเร็จ",
    };
  }
}

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

    let message = "บันทึกประกาศแล้ว ส่ง LINE ยังไม่ครบ กดส่งอีกครั้งจากประวัติประกาศได้";
    if (data.delivery_status === "sent") {
      message = `บันทึกและส่งประกาศไปยัง ${data.sent_count} บัญชีแล้ว`;
    } else if (data.delivery_status === "no_recipients") {
      message = "บันทึกแล้ว แต่ยังไม่มีพนักงานที่เชื่อม LINE";
    }

    return { message, error: "" };
  } catch (error) {
    revalidatePath("/announcements");
    revalidatePath("/");
    return {
      message: "",
      error: error instanceof Error ? error.message : "สร้างประกาศไม่สำเร็จ",
    };
  }
}

export async function updateEmployee(
  _: EmployeeState,
  formData: FormData,
): Promise<EmployeeState> {
  try {
    const body: Record<string, unknown> = Object.fromEntries(formData);
    const numericFields = [
      "vacation",
      "sick",
      "personal",
      "vacation_entitlement",
      "sick_entitlement",
      "personal_entitlement",
    ];
    for (const key of numericFields) {
      body[key] = Number(body[key]);
    }
    if (!body.password) {
      delete body.password;
    }

    const employeeCode = formData.get("employee_code");
    await api(`/api/admin/employees/${employeeCode}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    });
    revalidatePath("/employees");
    return { error: "" };
  } catch (error) {
    return {
      error: error instanceof Error ? error.message : "บันทึกไม่สำเร็จ",
    };
  }
}

export async function retryAnnouncement(formData: FormData) {
  const announcementId = formData.get("id");
  await api(`/api/admin/announcements/${announcementId}/retry`, { method: "POST" });
  revalidatePath("/announcements");
}

export async function retryLeaveNotification(formData: FormData) {
  const leaveId = formData.get("id");
  await api(`/api/admin/leaves/${leaveId}/notify`, { method: "POST" });
  revalidatePath("/leaves");
}

export async function saveHoliday(formData: FormData) {
  await api("/api/admin/holidays", {
    method: "POST",
    body: JSON.stringify({
      date: formData.get("date"),
      name: formData.get("name"),
    }),
  });
  revalidatePath("/holidays");
}

export async function deleteHoliday(formData: FormData) {
  const holidayId = formData.get("id");
  await api(`/api/admin/holidays/${holidayId}`, { method: "DELETE" });
  revalidatePath("/holidays");
}

export async function saveFaq(
  _: AnnouncementState,
  formData: FormData,
): Promise<AnnouncementState> {
  try {
    const id = formData.get("id");
    const path = `/api/admin/faqs${id ? `/${id}` : ""}`;
    const data = await api<{ indexed: boolean }>(path, {
      method: id ? "PATCH" : "POST",
      body: JSON.stringify({
        keyword: formData.get("keyword"),
        question: formData.get("question"),
        answer: formData.get("answer"),
        active: formData.get("active") === "on",
      }),
    });
    revalidatePath("/knowledge");

    const message = data.indexed
      ? "บันทึก FAQ แล้ว"
      : "บันทึกแล้ว ใช้การค้นสำรองจนกว่าจะสร้างดัชนีได้";
    return { message, error: "" };
  } catch (error) {
    return {
      message: "",
      error: error instanceof Error ? error.message : "บันทึกไม่สำเร็จ",
    };
  }
}

export async function uploadPolicy(
  _: AnnouncementState,
  formData: FormData,
): Promise<AnnouncementState> {
  try {
    const data = await api<{ indexed: boolean; chunk_count: number }>(
      "/api/admin/documents",
      { method: "POST", body: formData },
    );
    revalidatePath("/knowledge");

    const indexMessage = data.indexed ? "" : " ใช้การค้นสำรองจนกว่าจะสร้างดัชนีได้";
    return {
      message: `นำเข้าเอกสารแล้ว ${data.chunk_count} ส่วน${indexMessage}`,
      error: "",
    };
  } catch (error) {
    return {
      message: "",
      error: error instanceof Error ? error.message : "นำเข้าไม่สำเร็จ",
    };
  }
}

export async function archivePolicy(formData: FormData) {
  const documentId = formData.get("id");
  await api(`/api/admin/documents/${documentId}`, { method: "DELETE" });
  revalidatePath("/knowledge");
}

export async function reindexPolicies(
  _: AnnouncementState,
): Promise<AnnouncementState> {
  try {
    const data = await api<{ indexed: boolean }>("/api/admin/documents/reindex", {
      method: "POST",
    });
    const message = data.indexed
      ? "สร้างดัชนีค้นหาแล้ว"
      : "สร้างดัชนีไม่สำเร็จ ระบบยังใช้การค้นสำรองได้";
    return { message, error: "" };
  } catch (error) {
    return {
      message: "",
      error: error instanceof Error ? error.message : "สร้างดัชนีไม่สำเร็จ",
    };
  }
}

export async function previewAnswer(
  _: AnnouncementState,
  formData: FormData,
): Promise<AnnouncementState> {
  try {
    const question = formData.get("question");
    const data = await api<{ answer: string | null }>("/api/admin/knowledge/search", {
      method: "POST",
      body: JSON.stringify({ question }),
    });
    return { message: data.answer ?? "ไม่พบคำตอบในฐานข้อมูล HR", error: "" };
  } catch (error) {
    return {
      message: "",
      error: error instanceof Error ? error.message : "ค้นหาไม่สำเร็จ",
    };
  }
}
