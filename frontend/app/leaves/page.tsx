import Link from "next/link";

import { retryLeaveNotification } from "../actions";
import { LeaveDecisionForm } from "../../components/leave-decision";
import { formatDate, get, leaveLabels, statusLabels, type Leave } from "../../lib/api";

const statusClasses: Record<string, string> = {
  pending: "bg-[#fff3d1] text-[#885b00]",
  approved: "bg-[#e4f5eb] text-[#087747]",
  rejected: "bg-[#ffe9e9] text-[#a32727]",
};
const tableHeading =
  "bg-[#fafcfb] px-4 py-3.5 text-left text-[11px] font-bold uppercase tracking-wide text-[#728078]";

export default async function LeavesPage({
  searchParams,
}: {
  searchParams: Promise<{ status?: string; q?: string }>;
}) {
  const leaves = await get<Leave[]>("/api/admin/leaves");
  const params = await searchParams;
  const selectedStatus = params.status ?? "all";
  const query = params.q?.trim() ?? "";
  const pending = leaves.filter((leave) => leave.status === "pending").length;
  const visibleLeaves = leaves
    .filter((leave) => {
      const matchesStatus = selectedStatus === "all" || leave.status === selectedStatus;
      const searchable = `${leave.name} ${leave.employee_code}`;
      return matchesStatus && searchable.toLocaleLowerCase().includes(query.toLocaleLowerCase());
    })
    .sort((first, second) => Number(second.status === "pending") - Number(first.status === "pending"));
  const filters = [
    ["all", "ทั้งหมด"],
    ["pending", `รออนุมัติ (${pending})`],
    ["approved", "อนุมัติแล้ว"],
    ["rejected", "ปฏิเสธ"],
    ["cancelled", "ยกเลิก"],
  ];

  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6 max-sm:block">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">
            LEAVE REQUESTS
          </span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">
            คำขอลา
          </h1>
          <p className="text-sm text-[#6d7a72]">ตรวจสอบและอนุมัติคำขอลาของพนักงาน</p>
        </div>
        <span className="shrink-0 rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72] max-sm:mt-3 max-sm:inline-flex">
          {pending} รออนุมัติ
        </span>
      </header>

      <nav aria-label="กรองสถานะคำขอลา" className="mb-4 flex flex-wrap gap-2">
        {filters.map(([status, label]) => (
          <Link
            key={status}
            href={`/leaves?${new URLSearchParams({ status, q: query })}`}
            aria-current={selectedStatus === status ? "page" : undefined}
            className={`flex min-h-11 items-center rounded-xl px-4 text-sm font-semibold ${selectedStatus === status ? "bg-[#087747] text-white" : "border border-[#e1e9e3] bg-white text-[#5d6961] hover:bg-[#e7f5ed]"}`}
          >
            {label}
          </Link>
        ))}
      </nav>
      <form role="search" className="mb-5 flex flex-wrap items-end gap-3">
        <input type="hidden" name="status" value={selectedStatus} />
        <label className="min-w-0 flex-1 text-sm font-semibold">
          ค้นหาคำขอลา
          <input type="search" name="q" defaultValue={query} placeholder="ชื่อหรือรหัสพนักงาน" className="mt-1.5 min-h-11 w-full rounded-xl border border-[#cad7ce] bg-white px-3 font-normal" />
        </label>
        <button className="min-h-11 rounded-xl bg-[#087747] px-5 text-sm font-bold text-white">ค้นหา</button>
        {query && <Link href={`/leaves?status=${selectedStatus}`} className="flex min-h-11 items-center text-sm text-[#087747]">ล้างการค้นหา</Link>}
      </form>

      <section className="overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]">
        <div className="flex min-h-[74px] items-center justify-between gap-4 border-b border-[#eaf0eb] px-5 py-4">
          <div>
            <h2 className="mb-1 text-base font-bold">รายการคำขอลา</h2>
            <p className="text-xs text-[#6d7a72]">เรียงรายการที่รออนุมัติขึ้นก่อน</p>
          </div>
          <span className="text-xs text-[#6d7a72]">{visibleLeaves.length} รายการ</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[930px] border-collapse">
            <thead>
              <tr>
                <th className={tableHeading}>พนักงาน</th>
                <th className={tableHeading}>ประเภท</th>
                <th className={tableHeading}>ช่วงวันที่</th>
                <th className={tableHeading}>จำนวน</th>
                <th className={tableHeading}>เหตุผล</th>
                <th className={tableHeading}>สถานะ</th>
                <th className={tableHeading}>ดำเนินการ</th>
              </tr>
            </thead>
            <tbody>
              {visibleLeaves.map((leave) => {
                const leaveType = leaveLabels[leave.leave_type] ?? leave.leave_type;
                const dateRange = `${formatDate(leave.start_date)} – ${formatDate(leave.end_date)}`;
                const statusClass =
                  statusClasses[leave.status] ?? "bg-gray-100 text-gray-600";
                const statusLabel = statusLabels[leave.status] ?? leave.status;

                return (
                  <tr
                    className="border-b border-[#edf1ee] transition last:border-0 hover:bg-[#fbfcfb]"
                    key={leave.id}
                  >
                    <td className="px-4 py-3.5 text-sm">
                      <b className="block">{leave.name}</b>
                      <small className="mt-0.5 block text-[11px] text-[#6d7a72]">
                        {leave.employee_code}
                      </small>
                    </td>
                    <td className="px-4 py-3.5 text-sm">{leaveType}</td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-sm">{dateRange}</td>
                    <td className="whitespace-nowrap px-4 py-3.5 text-sm">{leave.days} วัน</td>
                    <td className="max-w-[220px] px-4 py-3.5 text-sm text-[#5d6961]">
                      {leave.reason}
                      {leave.half_day && (
                        <small className="block">
                          {leave.half_day === "morning" ? "ครึ่งวันเช้า" : "ครึ่งวันบ่าย"}
                        </small>
                      )}
                      {leave.attachment_id && (
                        <a
                          className="block text-[#087747]"
                          href={`/attachments/${leave.attachment_id}`}
                        >
                          เปิดเอกสารแนบ
                        </a>
                      )}
                    </td>
                    <td className="px-4 py-3.5">
                      <span
                        className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${statusClass}`}
                      >
                        {statusLabel}
                      </span>
                    </td>
                    <td className="px-4 py-3.5">
                      {leave.status === "pending" ? (
                        <LeaveDecisionForm leave={leave} leaveType={leaveType} dateRange={dateRange} />
                      ) : (
                        <span className="text-xs text-[#8a958e]">ดำเนินการแล้ว</span>
                      )}
                      {leave.notification_status === "failed" && (
                        <form action={retryLeaveNotification}>
                          <input type="hidden" name="id" value={leave.id} />
                          <button className="mt-2 text-xs text-[#a32727]">
                            แจ้งผลไม่สำเร็จ ส่งอีกครั้ง
                          </button>
                        </form>
                      )}
                    </td>
                  </tr>
                );
              })}
              {!visibleLeaves.length && (
                <tr>
                  <td colSpan={7} className="p-10 text-center text-sm text-[#6d7a72]">
                    {query ? "ไม่พบคำขอลา ลองค้นหาด้วยชื่อหรือรหัสอื่น" : "ไม่มีคำขอลาในสถานะนี้"}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
