import { DeleteEmployeeButton, EmployeeForm } from "../../components/employee-controls";
import { InviteButton } from "../../components/invite-button";
import { get, type Employee } from "../../lib/api";

export default async function EmployeesPage() {
  const employees = await get<Employee[]>("/api/admin/employees");
  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6 max-sm:block">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">PEOPLE</span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">พนักงาน</h1>
          <p className="text-sm text-[#6d7a72]">เพิ่มพนักงานและจัดการการเชื่อมบัญชี LINE</p>
        </div>
        <span className="shrink-0 rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72] max-sm:mt-3 max-sm:inline-flex">{employees.length} คน</span>
      </header>

      <section className="mb-[18px] overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]">
        <div className="flex min-h-[74px] items-center border-b border-[#eaf0eb] px-5 py-4">
          <div><h2 className="mb-1 text-base font-bold">เพิ่มพนักงาน</h2><p className="text-xs text-[#6d7a72]">สร้างบัญชีก่อนออกลิงก์ยืนยันตัวตน</p></div>
        </div>
        <EmployeeForm />
      </section>

      <section className="grid grid-cols-3 gap-3.5 max-xl:grid-cols-2 max-sm:grid-cols-1">
        {employees.map((employee) => (
          <article className="flex min-w-0 flex-col rounded-2xl border border-[#e1e9e3] bg-white p-[18px] shadow-[0_10px_30px_#264c3510]" key={employee.id}>
            <div className="flex items-center gap-3">
              <span className="grid size-11 shrink-0 place-items-center rounded-[13px] bg-[#123c2a] text-lg font-extrabold text-white">{employee.name.slice(0, 1)}</span>
              <div className="min-w-0">
                <b className="block truncate">{employee.name}</b>
                <small className="mt-0.5 block text-xs text-[#6d7a72]">{employee.employee_code} · {employee.role}</small>
              </div>
            </div>
            <p className="my-4 [overflow-wrap:anywhere] text-sm text-[#6d7a72]">{employee.work_email}</p>
            <div className="mb-4">
              {employee.line_linked
                ? <span className="inline-flex rounded-full bg-[#e4f5eb] px-2.5 py-1 text-[11px] font-bold text-[#087747]">✓ เชื่อม LINE แล้ว</span>
                : <span className="inline-flex rounded-full bg-[#edf1ee] px-2.5 py-1 text-[11px] font-bold text-[#6a716c]">ยังไม่เชื่อม LINE</span>}
            </div>
            <div className="mt-auto flex items-end justify-between gap-2.5 border-t border-[#edf1ee] pt-3.5">
              {!employee.line_linked && <InviteButton employeeId={employee.id} />}
              <DeleteEmployeeButton employeeId={employee.id} name={employee.name} />
            </div>
          </article>
        ))}
        {!employees.length && <div className="col-span-full rounded-2xl border border-[#e1e9e3] bg-white p-10 text-center text-sm text-[#6d7a72]">ยังไม่มีพนักงานในระบบ</div>}
      </section>
    </main>
  );
}
