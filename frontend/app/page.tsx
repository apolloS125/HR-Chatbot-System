import { decideLeave } from "./actions";
import { InviteButton } from "../components/invite-button";
import { DeleteEmployeeButton, EmployeeForm } from "../components/employee-controls";
import { AnnouncementForm } from "../components/announcement-form";

const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
const headers = { "X-Admin-Key": process.env.ADMIN_API_KEY ?? "change-me" };

type Summary = { active_employees: number; linked_employees: number; pending_leaves: number };
type Employee = {
  id: number;
  employee_code: string;
  name: string;
  work_email: string;
  role: string;
  active: boolean;
  line_linked: boolean;
};
type Leave = {
  id: number;
  employee_code: string;
  name: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: string;
  reason: string;
  status: string;
};
type Announcement = {
  id: number;
  title: string;
  body: string;
  published_at: string;
};

async function get<T>(path: string): Promise<T> {
  const response = await fetch(`${backend}${path}`, { headers, cache: "no-store" });
  if (!response.ok) throw new Error(`โหลดข้อมูลไม่สำเร็จ: ${path}`);
  return response.json();
}

export default async function Dashboard() {
  const [summary, employees, leaves, announcements] = await Promise.all([
    get<Summary>("/api/admin/summary"),
    get<Employee[]>("/api/admin/employees"),
    get<Leave[]>("/api/admin/leaves"),
    get<Announcement[]>("/api/admin/announcements"),
  ]);

  return (
    <main>
      <header>
        <div><span className="eyebrow">HR CHATBOT</span><h1>ศูนย์จัดการฝ่ายบุคคล</h1></div>
        <span className="online">● ระบบพร้อมใช้งาน</span>
      </header>

      <section className="stats">
        <article><strong>{summary.active_employees}</strong><span>พนักงานที่ใช้งาน</span></article>
        <article><strong>{summary.linked_employees}</strong><span>เชื่อม LINE แล้ว</span></article>
        <article><strong>{summary.pending_leaves}</strong><span>คำขอลารออนุมัติ</span></article>
      </section>

      <section className="panel">
        <div className="panel-title"><h2>ประกาศบริษัท</h2><span>{announcements.length} รายการล่าสุด</span></div>
        <AnnouncementForm />
        <div className="announcement-list">
          {announcements.map((announcement) => (
            <article className="announcement" key={announcement.id}>
              <small>{new Date(announcement.published_at).toLocaleString("th-TH")}</small>
              <h3>{announcement.title}</h3>
              <p>{announcement.body}</p>
            </article>
          ))}
          {!announcements.length && <p className="empty">ยังไม่มีประกาศ</p>}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title"><h2>คำขอลา</h2><span>{leaves.length} รายการ</span></div>
        <div className="table-wrap">
          <table>
            <thead><tr><th>พนักงาน</th><th>ประเภท</th><th>ช่วงวันที่</th><th>จำนวน</th><th>เหตุผล</th><th>สถานะ</th><th></th></tr></thead>
            <tbody>
              {leaves.map((leave) => (
                <tr key={leave.id}>
                  <td><b>{leave.name}</b><small>{leave.employee_code}</small></td>
                  <td>{leave.leave_type}</td>
                  <td>{leave.start_date} – {leave.end_date}</td>
                  <td>{leave.days} วัน</td>
                  <td>{leave.reason}</td>
                  <td><span className={`status ${leave.status}`}>{leave.status}</span></td>
                  <td>
                    {leave.status === "pending" && <div className="actions">
                      <form action={decideLeave}><input type="hidden" name="leave_id" value={leave.id}/><input type="hidden" name="decision" value="approved"/><button className="approve">อนุมัติ</button></form>
                      <form action={decideLeave}><input type="hidden" name="leave_id" value={leave.id}/><input type="hidden" name="decision" value="rejected"/><button className="reject">ปฏิเสธ</button></form>
                    </div>}
                  </td>
                </tr>
              ))}
              {!leaves.length && <tr><td colSpan={7} className="empty">ยังไม่มีคำขอลา</td></tr>}
            </tbody>
          </table>
        </div>
      </section>

      <section className="panel">
        <div className="panel-title"><h2>พนักงาน</h2><span>{employees.length} คน</span></div>
        <EmployeeForm />
        <div className="employee-grid">
          {employees.map((employee) => (
            <article className="employee" key={employee.id}>
              <div><span className="avatar">{employee.name.slice(0, 1)}</span><div><b>{employee.name}</b><small>{employee.employee_code} · {employee.role}</small></div></div>
              <p>{employee.work_email}</p>
              {employee.line_linked ? <span className="linked">✓ เชื่อม LINE แล้ว</span> : <InviteButton employeeId={employee.id} />}
              <DeleteEmployeeButton employeeId={employee.id} name={employee.name} />
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}
