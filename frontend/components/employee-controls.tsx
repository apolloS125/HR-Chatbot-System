"use client";

import { useActionState } from "react";
import { createEmployee, deleteEmployee, type EmployeeState } from "../app/actions";

const initialState: EmployeeState = { error: "" };
const field = "min-w-0 rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5 outline-none transition placeholder:text-[#96a199] focus:border-[#55b987] focus:ring-3 focus:ring-[#55b987]/20";

export function EmployeeForm() {
  const [state, action, pending] = useActionState(createEmployee, initialState);
  return (
    <form action={action} className="grid grid-cols-[1fr_1.6fr_1.8fr_1fr_auto] gap-2.5 p-5 max-xl:grid-cols-2 max-sm:grid-cols-1">
      <input className={field} name="employee_code" placeholder="รหัสพนักงาน" required />
      <input className={field} name="name" placeholder="ชื่อ-นามสกุล" required />
      <input className={field} name="work_email" type="email" placeholder="อีเมลบริษัท" required />
      <select className={field} name="role" defaultValue="employee"><option value="employee">พนักงาน</option><option value="hr">HR</option><option value="admin">Admin</option></select>
      <button className="min-h-10 rounded-lg bg-[#087747] px-3 font-bold text-white transition hover:bg-[#06643b] disabled:cursor-wait disabled:opacity-60 max-xl:col-start-2 max-sm:col-auto" disabled={pending}>{pending ? "กำลังเพิ่ม…" : "เพิ่มพนักงาน"}</button>
      {state.error && <small className="col-span-full text-xs text-[#b32222]">{state.error}</small>}
    </form>
  );
}

export function DeleteEmployeeButton({ employeeId, name }: { employeeId: number; name: string }) {
  return (
    <form action={deleteEmployee} onSubmit={(event) => {
      if (!window.confirm(`ลบ ${name} ถาวร รวมประวัติคำขอลาและข้อมูล LINE ใช่หรือไม่?`)) event.preventDefault();
    }}>
      <input type="hidden" name="employee_id" value={employeeId} />
      <button type="submit" className="whitespace-nowrap border-0 bg-transparent px-0 py-2 text-xs text-[#a32727]">ลบพนักงาน</button>
    </form>
  );
}
