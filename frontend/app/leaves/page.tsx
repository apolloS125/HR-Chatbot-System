import { decideLeave } from "../actions";
import { formatDate, get, leaveLabels, statusLabels, type Leave } from "../../lib/api";

const statusClasses: Record<string, string> = {
  pending: "bg-[#fff3d1] text-[#885b00]",
  approved: "bg-[#e4f5eb] text-[#087747]",
  rejected: "bg-[#ffe9e9] text-[#a32727]",
};
const th = "bg-[#fafcfb] px-4 py-3.5 text-left text-[11px] font-bold uppercase tracking-wide text-[#728078]";

export default async function LeavesPage() {
  const leaves = await get<Leave[]>("/api/admin/leaves");
  const pending = leaves.filter((leave) => leave.status === "pending").length;

  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6 max-sm:block">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">LEAVE REQUESTS</span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">คำขอลา</h1>
          <p className="text-sm text-[#6d7a72]">ตรวจสอบและอนุมัติคำขอลาของพนักงาน</p>
        </div>
        <span className="shrink-0 rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72] max-sm:mt-3 max-sm:inline-flex">{pending} รออนุมัติ</span>
      </header>

      <section className="overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]">
        <div className="flex min-h-[74px] items-center justify-between gap-4 border-b border-[#eaf0eb] px-5 py-4">
          <div><h2 className="mb-1 text-base font-bold">รายการทั้งหมด</h2><p className="text-xs text-[#6d7a72]">เรียงรายการที่รออนุมัติขึ้นก่อน</p></div>
          <span className="text-xs text-[#6d7a72]">{leaves.length} รายการ</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[930px] border-collapse">
            <thead><tr><th className={th}>พนักงาน</th><th className={th}>ประเภท</th><th className={th}>ช่วงวันที่</th><th className={th}>จำนวน</th><th className={th}>เหตุผล</th><th className={th}>สถานะ</th><th className={th}>ดำเนินการ</th></tr></thead>
            <tbody>
              {leaves.map((leave) => (
                <tr className="border-b border-[#edf1ee] transition last:border-0 hover:bg-[#fbfcfb]" key={leave.id}>
                  <td className="px-4 py-3.5 text-sm"><b className="block">{leave.name}</b><small className="mt-0.5 block text-[11px] text-[#6d7a72]">{leave.employee_code}</small></td>
                  <td className="px-4 py-3.5 text-sm">{leaveLabels[leave.leave_type] ?? leave.leave_type}</td>
                  <td className="px-4 py-3.5 text-sm whitespace-nowrap">{formatDate(leave.start_date)} – {formatDate(leave.end_date)}</td>
                  <td className="px-4 py-3.5 text-sm whitespace-nowrap">{leave.days} วัน</td>
                  <td className="max-w-[220px] px-4 py-3.5 text-sm text-[#5d6961]">{leave.reason}</td>
                  <td className="px-4 py-3.5"><span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold ${statusClasses[leave.status] ?? "bg-gray-100 text-gray-600"}`}>{statusLabels[leave.status] ?? leave.status}</span></td>
                  <td className="px-4 py-3.5">
                    {leave.status === "pending" ? <div className="flex gap-1.5">
                      <form action={decideLeave}><input type="hidden" name="leave_id" value={leave.id}/><input type="hidden" name="decision" value="approved"/><button className="min-h-8 rounded-lg bg-[#087747] px-2.5 text-[11px] font-bold text-white transition hover:bg-[#06643b]">อนุมัติ</button></form>
                      <form action={decideLeave}><input type="hidden" name="leave_id" value={leave.id}/><input type="hidden" name="decision" value="rejected"/><button className="min-h-8 rounded-lg bg-[#f8eded] px-2.5 text-[11px] font-bold text-[#a32727]">ปฏิเสธ</button></form>
                    </div> : <span className="text-xs text-[#8a958e]">ดำเนินการแล้ว</span>}
                  </td>
                </tr>
              ))}
              {!leaves.length && <tr><td colSpan={7} className="p-10 text-center text-sm text-[#6d7a72]">ยังไม่มีคำขอลา</td></tr>}
            </tbody>
          </table>
        </div>
      </section>
    </main>
  );
}
