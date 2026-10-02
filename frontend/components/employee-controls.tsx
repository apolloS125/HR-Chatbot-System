"use client";

import { useActionState } from "react";
import { createEmployee, deleteEmployee, updateEmployee, type EmployeeState } from "../app/actions";
import type { Employee } from "../lib/api";

const initialState: EmployeeState = { error: "" };
const field = "min-w-0 rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5 outline-none transition placeholder:text-[#96a199] focus:border-[#55b987] focus:ring-3 focus:ring-[#55b987]/20";

export function EmployeeForm({ canManageRoles = false }: { canManageRoles?: boolean }) {
  const [state, action, pending] = useActionState(createEmployee, initialState);
  return (
    <form action={action} className="grid grid-cols-[1fr_1.6fr_1.8fr_1fr_auto] gap-2.5 p-5 max-xl:grid-cols-2 max-sm:grid-cols-1">
      <input className={field} name="employee_code" placeholder="รหัสพนักงาน" required />
      <input className={field} name="name" placeholder="ชื่อ-นามสกุล" required />
      <input className={field} name="work_email" type="email" placeholder="อีเมลบริษัท" required />
      <select aria-label="บทบาท" className={field} name="role" defaultValue="employee"><option value="employee">พนักงาน</option>{canManageRoles && <><option value="hr">HR</option><option value="admin">Admin</option></>}</select>
      <button className="min-h-10 rounded-lg bg-[#087747] px-3 font-bold text-white transition hover:bg-[#06643b] disabled:cursor-wait disabled:opacity-60 max-xl:col-start-2 max-sm:col-auto" disabled={pending}>{pending ? "กำลังเพิ่ม…" : "เพิ่มพนักงาน"}</button>
      {state.error && <small className="col-span-full text-xs text-[#b32222]">{state.error}</small>}
    </form>
  );
}

export function EmployeeStatusButton({ employeeId, name, active }: { employeeId: string; name: string; active: boolean }) {
  const [state, action, pending] = useActionState(deleteEmployee, initialState);
  return (
    <form action={action} onSubmit={(event) => {
      if (!window.confirm(`${active ? "ปิด" : "เปิด"}ใช้งาน ${name} ใช่หรือไม่? ประวัติและเอกสารจะถูกเก็บไว้`)) event.preventDefault();
    }}>
      <input type="hidden" name="employee_id" value={employeeId} />
      <input type="hidden" name="active" value={String(!active)} />
      <button type="submit" disabled={pending} className="whitespace-nowrap border-0 bg-transparent px-0 py-2 text-xs text-[#a32727] disabled:opacity-50">{active ? "ปิดใช้งาน" : "เปิดใช้งาน"}</button>
      {state.error && <p role="alert" className="text-xs text-red-700">{state.error}</p>}
    </form>
  );
}

export function EditEmployeeForm({ employee, canManageRoles }: { employee: Employee; canManageRoles: boolean }) {
  const [state, action, pending] = useActionState(updateEmployee, initialState);
  return <details className="mt-3 border-t pt-3 text-sm">
    <summary className="cursor-pointer text-[#087747]">แก้ไขข้อมูลและวันลา</summary>
    <form action={action} className="mt-3 grid gap-3">
      <input type="hidden" name="employee_code" value={employee.employee_code} />
      <label>ชื่อ<input className={`${field} mt-1 w-full`} name="name" defaultValue={employee.name} required /></label>
      <label>อีเมล<input className={`${field} mt-1 w-full`} name="work_email" type="email" defaultValue={employee.work_email} required /></label>
      {canManageRoles ? <><label>บทบาท<select className={`${field} mt-1 w-full`} name="role" defaultValue={employee.role}><option value="employee">พนักงาน</option><option value="hr">HR</option><option value="admin">Admin</option></select></label><label>รหัสผ่าน Dashboard ใหม่<input className={`${field} mt-1 w-full`} name="password" type="password" minLength={10} maxLength={128} autoComplete="new-password" placeholder="เว้นว่างเพื่อคงรหัสเดิม" /><small>ใช้รหัสพนักงานเข้าสู่ระบบได้เฉพาะ HR และ Admin</small></label></> : <input type="hidden" name="role" value={employee.role} />}
      <p className="text-xs">วันลาปี {employee.balances_year}: คงเหลือ / สิทธิ์ต่อปี</p>
      {([['vacation', 'พักร้อน'], ['sick', 'ลาป่วย'], ['personal', 'ลากิจ']] as const).map(([key, label]) => <div key={key} className="grid grid-cols-2 gap-2"><label>{label} คงเหลือ<input className={`${field} mt-1 w-full`} name={key} type="number" min={0} max={366} step={0.5} defaultValue={employee.balances[key]} required /></label><label>สิทธิ์ต่อปี<input className={`${field} mt-1 w-full`} name={`${key}_entitlement`} type="number" min={0} max={366} step={0.5} defaultValue={employee.entitlements[key]} required /></label></div>)}
      <button disabled={pending} className="rounded-lg bg-[#087747] p-2 text-white disabled:opacity-50">{pending ? "กำลังบันทึก…" : "บันทึก"}</button>
      {state.error && <p role="alert" className="text-red-700">{state.error}</p>}
    </form>
  </details>;
}
