import Link from "next/link";

import {
  EditEmployeeForm,
  EmployeeDeleteButton,
  EmployeeForm,
  EmployeeStatusButton,
} from "../../components/employee-controls";
import { InviteButton } from "../../components/invite-button";
import { get, type Employee } from "../../lib/api";

const roleLabels: Record<string, string> = {
  employee: "พนักงาน",
  hr: "HR",
  admin: "ผู้ดูแลระบบ",
};

export default async function EmployeesPage({
  searchParams,
}: {
  searchParams: Promise<{ show_inactive?: string; q?: string }>;
}) {
  const [employees, actor] = await Promise.all([
    get<Employee[]>("/api/admin/employees"),
    get<{ id: string; role: string }>("/api/admin/session"),
  ]);
  const params = await searchParams;
  const showInactive = params.show_inactive === "1";
  const query = params.q?.trim() ?? "";
  const inactiveCount = employees.filter((employee) => !employee.active).length;
  const visibleEmployees = employees.filter((employee) => {
    const matchesStatus = showInactive || employee.active;
    const searchable = `${employee.name} ${employee.employee_code} ${employee.work_email}`;
    return matchesStatus && searchable.toLocaleLowerCase().includes(query.toLocaleLowerCase());
  });
  const canManageRoles = actor.role === "admin";

  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6 max-sm:block">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">
            PEOPLE
          </span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">
            พนักงาน
          </h1>
          <p className="text-sm text-[#6d7a72]">
            เพิ่มพนักงานและจัดการการเชื่อมบัญชี LINE
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3 max-sm:mt-3">
          <span className="rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72]">
            {visibleEmployees.length} คน
          </span>
          {inactiveCount > 0 && (
            <Link
              className="text-xs font-semibold text-[#087747]"
              href={`/employees?${new URLSearchParams({ q: query, show_inactive: showInactive ? "0" : "1" })}`}
            >
              {showInactive
                ? "ซ่อนพนักงานที่ปิดใช้งาน"
                : `ดูพนักงานที่ปิดใช้งาน (${inactiveCount})`}
            </Link>
          )}
        </div>
      </header>

      <details className="mb-[18px] overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]">
        <summary className="min-h-[74px] cursor-pointer px-5 py-4 text-[#087747]">
          <div>
            <h2 className="mb-1 text-base font-bold">เพิ่มพนักงาน</h2>
            <p className="text-xs text-[#6d7a72]">สร้างบัญชีก่อนออกลิงก์ยืนยันตัวตน</p>
          </div>
        </summary>
        <EmployeeForm canManageRoles={canManageRoles} />
      </details>

      <form className="mb-5 flex flex-wrap items-end gap-3" role="search">
        {showInactive && <input type="hidden" name="show_inactive" value="1" />}
        <label className="min-w-0 flex-1 text-sm font-semibold">
          ค้นหาพนักงาน
          <input
            className="mt-1.5 min-h-11 w-full rounded-xl border border-[#cad7ce] bg-white px-3 font-normal"
            type="search"
            name="q"
            defaultValue={query}
            placeholder="ชื่อ รหัสพนักงาน หรืออีเมล"
          />
        </label>
        <button className="min-h-11 rounded-xl bg-[#087747] px-5 text-sm font-bold text-white">ค้นหา</button>
        {query && (
          <Link href={showInactive ? "/employees?show_inactive=1" : "/employees"} className="flex min-h-11 items-center text-sm text-[#087747]">
            ล้างการค้นหา
          </Link>
        )}
      </form>

      <section className="grid grid-cols-3 gap-3.5 max-xl:grid-cols-2 max-sm:grid-cols-1">
        {visibleEmployees.map((employee) => (
          <article
            className="flex min-w-0 flex-col rounded-2xl border border-[#e1e9e3] bg-white p-[18px] shadow-[0_10px_30px_#264c3510]"
            key={employee.id}
          >
            <div className="flex items-center gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-[13px] bg-[#123c2a] text-lg font-extrabold text-white">
                {employee.name.slice(0, 1)}
              </span>
              <div className="min-w-0">
                <b className="block truncate">{employee.name}</b>
                <small className="mt-0.5 block text-xs text-[#6d7a72]">
                  {employee.employee_code} · {roleLabels[employee.role] ?? employee.role}
                </small>
              </div>
            </div>
            <p className="my-4 [overflow-wrap:anywhere] text-sm text-[#6d7a72]">
              {employee.work_email}
            </p>
            <div className="mb-4">
              {!employee.active && (
                <span className="mr-2 text-xs text-red-700">ปิดใช้งาน</span>
              )}
              {employee.line_linked ? (
                <span className="inline-flex rounded-full bg-[#e4f5eb] px-2.5 py-1 text-[11px] font-bold text-[#087747]">
                  ✓ เชื่อม LINE แล้ว
                </span>
              ) : (
                <span className="inline-flex rounded-full bg-[#edf1ee] px-2.5 py-1 text-[11px] font-bold text-[#6a716c]">
                  ยังไม่เชื่อม LINE
                </span>
              )}
            </div>
            <div className="mt-auto flex flex-wrap items-end justify-between gap-2.5 border-t border-[#edf1ee] pt-3.5">
              {employee.active &&
                !employee.line_linked &&
                (canManageRoles || employee.role === "employee") && (
                  <InviteButton employeeId={employee.id} />
                )}
              {(canManageRoles || employee.role === "employee") && employee.id !== actor.id && (
                <div className="flex gap-3">
                  <EmployeeStatusButton
                    employeeId={employee.id}
                    name={employee.name}
                    active={employee.active}
                  />
                  <EmployeeDeleteButton employeeId={employee.id} name={employee.name} />
                </div>
              )}
            </div>
            {(canManageRoles || employee.role === "employee") && (
              <EditEmployeeForm employee={employee} canManageRoles={canManageRoles} />
            )}
          </article>
        ))}
        {!visibleEmployees.length && (
          <div className="col-span-full rounded-2xl border border-[#e1e9e3] bg-white p-10 text-center text-sm text-[#6d7a72]">
            {query ? "ไม่พบพนักงาน ลองค้นหาด้วยชื่อ รหัส หรืออีเมลอื่น" : showInactive ? "ยังไม่มีพนักงานในระบบ เริ่มจากเพิ่มพนักงานด้านบน" : "ไม่มีพนักงานที่เปิดใช้งาน"}
          </div>
        )}
      </section>
    </main>
  );
}
