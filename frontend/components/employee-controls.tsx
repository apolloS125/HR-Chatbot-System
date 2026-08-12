"use client";

import { useActionState } from "react";
import { createEmployee, deleteEmployee, type EmployeeState } from "../app/actions";

const initialState: EmployeeState = { error: "" };

export function EmployeeForm() {
  const [state, action, pending] = useActionState(createEmployee, initialState);
  return (
    <form action={action} className="employee-form">
      <input name="employee_code" placeholder="รหัสพนักงาน" required />
      <input name="name" placeholder="ชื่อ-นามสกุล" required />
      <input name="work_email" type="email" placeholder="อีเมลบริษัท" required />
      <select name="role" defaultValue="employee"><option value="employee">พนักงาน</option><option value="hr">HR</option><option value="admin">Admin</option></select>
      <button className="primary" disabled={pending}>{pending ? "กำลังเพิ่ม…" : "เพิ่มพนักงาน"}</button>
      {state.error && <small className="error">{state.error}</small>}
    </form>
  );
}

export function DeleteEmployeeButton({ employeeId, name }: { employeeId: number; name: string }) {
  return (
    <form action={deleteEmployee} onSubmit={(event) => {
      if (!window.confirm(`ลบ ${name} ถาวร รวมประวัติคำขอลาและข้อมูล LINE ใช่หรือไม่?`)) event.preventDefault();
    }}>
      <input type="hidden" name="employee_id" value={employeeId} />
      <button type="submit" className="delete">ลบพนักงาน</button>
    </form>
  );
}
