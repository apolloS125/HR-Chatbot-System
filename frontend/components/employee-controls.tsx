"use client";

import { useActionState, useRef, type FormEvent } from "react";

import {
  createEmployee,
  deleteEmployee,
  removeEmployee,
  updateEmployee,
  type EmployeeState,
} from "../app/actions";
import type { Employee } from "../lib/api";

const initialState: EmployeeState = { error: "" };
const field = `min-w-0 rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5
  outline-none transition placeholder:text-[#96a199] focus:border-[#55b987]
  focus:ring-3 focus:ring-[#55b987]/20`;

export function EmployeeForm({ canManageRoles = false }: { canManageRoles?: boolean }) {
  const [state, action, pending] = useActionState(createEmployee, initialState);

  return (
    <form
      action={action}
      className="grid grid-cols-[1fr_1.6fr_1.8fr_1fr_auto] gap-2.5 p-5 max-xl:grid-cols-2 max-sm:grid-cols-1"
    >
      <label className="grid gap-1.5 text-sm font-medium">
        รหัสพนักงาน
        <input className={field} name="employee_code" placeholder="เช่น 001" required />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        ชื่อ-นามสกุล
        <input className={field} name="name" autoComplete="name" required />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        อีเมลบริษัท
        <input className={field} name="work_email" type="email" autoComplete="email" required />
      </label>
      <label className="grid gap-1.5 text-sm font-medium">
        บทบาท
      <select className={field} name="role" defaultValue="employee">
        <option value="employee">พนักงาน</option>
        {canManageRoles && (
          <>
            <option value="hr">HR</option>
            <option value="admin">Admin</option>
          </>
        )}
      </select>
      </label>
      <button
        className="min-h-11 self-end rounded-lg bg-[#087747] px-3 font-bold text-white transition hover:bg-[#06643b] disabled:cursor-wait disabled:opacity-60 max-xl:col-start-2 max-sm:col-auto"
        disabled={pending}
      >
        {pending ? "กำลังเพิ่ม…" : "เพิ่มพนักงาน"}
      </button>
      {state.error && <small role="alert" className="col-span-full text-sm text-[#b32222]">{state.error}</small>}
    </form>
  );
}

export function EmployeeStatusButton({
  employeeId,
  name,
  active,
}: {
  employeeId: string;
  name: string;
  active: boolean;
}) {
  const [state, action, pending] = useActionState(deleteEmployee, initialState);

  function confirmStatusChange(event: FormEvent<HTMLFormElement>) {
    const nextStatus = active ? "ปิด" : "เปิด";
    const message = `${nextStatus}ใช้งาน ${name} ใช่หรือไม่? ประวัติและเอกสารจะถูกเก็บไว้`;

    if (!window.confirm(message)) {
      event.preventDefault();
    }
  }

  return (
    <form action={action} onSubmit={confirmStatusChange}>
      <input type="hidden" name="employee_id" value={employeeId} />
      <input type="hidden" name="active" value={String(!active)} />
      <button
        type="submit"
        disabled={pending}
        className="min-h-11 whitespace-nowrap rounded-lg px-2 text-sm text-[#6d7a72] hover:bg-[#f2f5f3] disabled:opacity-50"
      >
        {active ? "ปิดใช้งาน" : "เปิดใช้งาน"}
      </button>
      {state.error && <p role="alert" className="text-xs text-red-700">{state.error}</p>}
    </form>
  );
}

export function EmployeeDeleteButton({
  employeeId,
  name,
}: {
  employeeId: string;
  name: string;
}) {
  const [state, action, pending] = useActionState(removeEmployee, initialState);

  function confirmDeletion(event: FormEvent<HTMLFormElement>) {
    const message = `ลบข้อมูล ${name} ทั้งหมดถาวรหรือไม่? ประวัติวันลาและเอกสารจะถูกลบ และนำอีเมลกลับมาใช้ได้`;

    if (!window.confirm(message)) {
      event.preventDefault();
    }
  }

  return (
    <form action={action} onSubmit={confirmDeletion}>
      <input type="hidden" name="employee_id" value={employeeId} />
      <button
        type="submit"
        disabled={pending}
        className="min-h-11 whitespace-nowrap rounded-lg px-2 text-sm text-[#a32727] hover:bg-red-50 disabled:opacity-50"
      >
        {pending ? "กำลังลบ…" : "ลบถาวร"}
      </button>
      {state.error && <p role="alert" className="text-xs text-red-700">{state.error}</p>}
    </form>
  );
}

export function EditEmployeeForm({
  employee,
  canManageRoles,
}: {
  employee: Employee;
  canManageRoles: boolean;
}) {
  const [state, action, pending] = useActionState(updateEmployee, initialState);
  const dialog = useRef<HTMLDialogElement>(null);
  const leaveTypes = [
    ["vacation", "พักร้อน"],
    ["sick", "ลาป่วย"],
    ["personal", "ลากิจ"],
  ] as const;

  return (
    <div className="mt-3 border-t pt-3 text-sm">
      <button
        type="button"
        className="min-h-11 w-full rounded-lg border border-[#cad7ce] px-3 font-semibold text-[#087747] hover:bg-[#e7f5ed]"
        onClick={() => dialog.current?.showModal()}
      >
        แก้ไขข้อมูลและวันลา
      </button>
      <dialog
        ref={dialog}
        aria-labelledby={`edit-${employee.id}`}
        className="m-auto max-h-[90dvh] w-[min(42rem,calc(100%-2rem))] overflow-y-auto rounded-2xl border border-[#e1e9e3] bg-white p-0 text-sm shadow-2xl backdrop:bg-black/40"
      >
        <div className="flex items-center justify-between border-b border-[#edf1ee] px-5 py-4">
          <h2 id={`edit-${employee.id}`} className="m-0 text-lg font-bold">
            แก้ไขข้อมูลและวันลา · {employee.name}
          </h2>
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            aria-label="ปิดหน้าต่าง"
            className="min-h-11 min-w-11 rounded-lg text-xl text-[#6d7a72]"
          >
            ×
          </button>
        </div>
        <form action={action} className="grid gap-3 p-5">
          <input type="hidden" name="employee_code" value={employee.employee_code} />
          <label>
            ชื่อ
            <input
              className={`${field} mt-1 w-full`}
              name="name"
              defaultValue={employee.name}
              required
            />
          </label>
          <label>
            อีเมล
            <input
              className={`${field} mt-1 w-full`}
              name="work_email"
              type="email"
              defaultValue={employee.work_email}
              required
            />
          </label>
          {canManageRoles ? (
            <>
              <label>
                บทบาท
                <select className={`${field} mt-1 w-full`} name="role" defaultValue={employee.role}>
                  <option value="employee">พนักงาน</option>
                  <option value="hr">HR</option>
                  <option value="admin">Admin</option>
                </select>
              </label>
              <label>
                รหัสผ่าน Dashboard ใหม่
                <input
                  className={`${field} mt-1 w-full`}
                  name="password"
                  type="password"
                  minLength={10}
                  maxLength={128}
                  autoComplete="new-password"
                  placeholder="เว้นว่างเพื่อคงรหัสเดิม"
                />
                <small>ใช้รหัสพนักงานเข้าสู่ระบบได้เฉพาะ HR และ Admin</small>
              </label>
            </>
          ) : (
            <input type="hidden" name="role" value={employee.role} />
          )}
          <p className="text-xs">
            วันลาปี {employee.balances_year}: คงเหลือ / สิทธิ์ต่อปี
          </p>
          {leaveTypes.map(([key, label]) => (
            <div key={key} className="grid grid-cols-2 gap-2">
              <label>
                {label} คงเหลือ
                <input
                  className={`${field} mt-1 w-full`}
                  name={key}
                  type="number"
                  min={0}
                  max={366}
                  step={0.5}
                  defaultValue={employee.balances[key]}
                  required
                />
              </label>
              <label>
                สิทธิ์ต่อปี
                <input
                  className={`${field} mt-1 w-full`}
                  name={`${key}_entitlement`}
                  type="number"
                  min={0}
                  max={366}
                  step={0.5}
                  defaultValue={employee.entitlements[key]}
                  required
                />
              </label>
            </div>
          ))}
          <button
            disabled={pending}
            className="min-h-11 rounded-lg bg-[#087747] p-2 font-semibold text-white disabled:opacity-50"
          >
            {pending ? "กำลังบันทึก…" : "บันทึก"}
          </button>
          {state.error && <p role="alert" className="text-red-700">{state.error}</p>}
        </form>
      </dialog>
    </div>
  );
}
