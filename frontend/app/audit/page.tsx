import { formatDateTime, get } from "../../lib/api";

const actionLabels: Record<string, string> = {
  "employee.create": "เพิ่มพนักงาน", "employee.update": "แก้ไขข้อมูลพนักงาน", "employee.activate": "เปิดใช้งานพนักงาน", "employee.deactivate": "ปิดใช้งานพนักงาน", "employee.line_link": "ออกลิงก์เชื่อม LINE",
  "leave.approved": "อนุมัติลา", "leave.rejected": "ปฏิเสธลา", "leave.notify": "ส่งแจ้งผลลาอีกครั้ง",
  "announcement.create": "สร้างประกาศ", "announcement.retry": "ส่งประกาศอีกครั้ง", "holiday.save": "บันทึกวันหยุด", "holiday.delete": "ลบวันหยุด",
  "faq.create": "เพิ่ม FAQ", "faq.update": "แก้ไข FAQ", "document.upload": "นำเข้าเอกสาร", "document.archive": "หยุดใช้เอกสาร", "knowledge.reindex": "สร้างดัชนีค้นหาใหม่",
};

export default async function AuditPage() {
  const actor = await get<{ role: string }>("/api/admin/session");
  if (actor.role !== "admin") return <main className="p-6">เฉพาะ Admin ดูประวัติการจัดการได้</main>;
  const records = await get<{ id: string; actor: string; action: string; subject: string; created_at: string }[]>("/api/admin/audit");
  return <main className="mx-auto max-w-5xl p-6"><h1 className="mb-6 text-2xl font-bold">ประวัติการจัดการ 100 รายการล่าสุด</h1><div className="overflow-x-auto rounded-xl bg-white"><table className="w-full text-left text-sm"><thead><tr>{["เวลา", "ผู้ดำเนินการ", "การเปลี่ยนแปลง", "รายการ"].map((label) => <th className="p-3" key={label}>{label}</th>)}</tr></thead><tbody>{records.map((item) => <tr className="border-t" key={item.id}><td className="p-3">{formatDateTime(item.created_at)}</td><td className="p-3">{item.actor}</td><td className="p-3">{actionLabels[item.action] ?? item.action}</td><td className="p-3">{item.subject}</td></tr>)}</tbody></table></div>{!records.length && <p className="mt-4">ยังไม่มีรายการ</p>}</main>;
}
