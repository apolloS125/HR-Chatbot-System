import Link from "next/link";
import {
  formatDate,
  formatDateTime,
  get,
  leaveLabels,
  statusLabels,
  type Announcement,
  type Leave,
  type Summary,
} from "../lib/api";

const panel = "overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]";

export default async function Dashboard() {
  const [summary, leaves, announcements] = await Promise.all([
    get<Summary>("/api/admin/summary"),
    get<Leave[]>("/api/admin/leaves"),
    get<Announcement[]>("/api/admin/announcements"),
  ]);
  const pending = leaves.filter((leave) => leave.status === "pending").slice(0, 5);

  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">OVERVIEW</span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">สวัสดี ทีม HR</h1>
          <p className="text-sm text-[#6d7a72]">ภาพรวมระบบและรายการที่ต้องจัดการวันนี้</p>
        </div>
        <time className="shrink-0 rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72] max-md:hidden">
          {new Intl.DateTimeFormat("th-TH", { dateStyle: "full" }).format(new Date())}
        </time>
      </header>

      <section className="grid grid-cols-3 gap-3.5 max-md:grid-cols-1 max-md:gap-2" aria-label="สถิติระบบ">
        <Stat href="/employees" icon="♙" tone="green" value={summary.active_employees} label="พนักงานที่ใช้งาน" />
        <Stat href="/employees" icon="↗" tone="blue" value={summary.linked_employees} label="เชื่อม LINE แล้ว" />
        <Stat href="/leaves" icon="✓" tone="amber" value={summary.pending_leaves} label="คำขอลารออนุมัติ" />
      </section>

      <section className="mt-[18px] grid grid-cols-[minmax(0,1.25fr)_minmax(330px,.75fr)] items-start gap-[18px] max-lg:grid-cols-1">
        <article className={panel}>
          <PanelTitle title="คำขอลาที่รอดำเนินการ" detail="รายการล่าสุดที่ต้องตรวจสอบ" href="/leaves" link="ดูทั้งหมด →" />
          <div>
            {pending.map((leave) => (
              <Link className="grid min-h-[67px] grid-cols-[auto_1fr_auto] items-center gap-3 border-b border-[#edf2ee] px-5 py-3 transition last:border-b-0 hover:bg-[#f9fbfa]" href="/leaves" key={leave.id}>
                <span className="grid size-[38px] place-items-center rounded-xl bg-[#123c2a] font-extrabold text-white">{leave.name.slice(0, 1)}</span>
                <div className="min-w-0">
                  <b className="block truncate text-sm">{leave.name}</b>
                  <small className="mt-0.5 block truncate text-xs text-[#6d7a72]">
                    {leaveLabels[leave.leave_type] ?? leave.leave_type} · {formatDate(leave.start_date)} – {formatDate(leave.end_date)} · {leave.days} วัน
                  </small>
                </div>
                <span className="rounded-full bg-[#fff3d1] px-2.5 py-1 text-[11px] font-bold text-[#885b00] max-sm:hidden">{statusLabels.pending}</span>
              </Link>
            ))}
            {!pending.length && <p className="m-0 p-10 text-center text-sm text-[#6d7a72]">ไม่มีคำขอที่รออนุมัติ</p>}
          </div>
        </article>

        <article className={panel}>
          <PanelTitle title="ประกาศล่าสุด" detail="ข่าวสารที่ส่งถึงพนักงาน" href="/announcements" link="จัดการ →" />
          <div>
            {announcements.slice(0, 4).map((announcement) => (
              <Link className="grid min-h-[67px] grid-cols-[auto_1fr] items-center gap-3 border-b border-[#edf2ee] px-5 py-3 transition last:border-b-0 hover:bg-[#f9fbfa]" href="/announcements" key={announcement.id}>
                <span className="grid size-9 place-items-center rounded-[10px] bg-[#e7f5ed] text-[#087747]">◫</span>
                <div className="min-w-0">
                  <b className="block truncate text-sm">{announcement.title}</b>
                  <small className="mt-0.5 block text-xs text-[#6d7a72]">{formatDateTime(announcement.published_at)}</small>
                </div>
              </Link>
            ))}
            {!announcements.length && <p className="m-0 p-10 text-center text-sm text-[#6d7a72]">ยังไม่มีประกาศ</p>}
          </div>
        </article>
      </section>
    </main>
  );
}

function Stat({ href, icon, tone, value, label }: { href: string; icon: string; tone: "green" | "blue" | "amber"; value: number; label: string }) {
  const tones = {
    green: "bg-[#e2f4e9] text-[#087747]",
    blue: "bg-[#e8f2fa] text-[#2d6da1]",
    amber: "bg-[#fff2cf] text-[#9a6500]",
  };
  return (
    <Link href={href} className="grid grid-cols-[auto_1fr_auto] items-center gap-3.5 rounded-2xl border border-[#e1e9e3] bg-white p-5 shadow-[0_10px_30px_#264c3510] transition hover:-translate-y-0.5 hover:shadow-[0_14px_32px_#264c3519] max-md:p-4">
      <span className={`grid size-[42px] place-items-center rounded-xl font-extrabold ${tones[tone]}`}>{icon}</span>
      <div><strong className="block text-3xl leading-none tracking-[-.04em]">{value}</strong><span className="mt-1 block text-xs text-[#6d7a72]">{label}</span></div>
      <b className="text-2xl font-normal text-[#9aaba0]">›</b>
    </Link>
  );
}

function PanelTitle({ title, detail, href, link }: { title: string; detail: string; href: string; link: string }) {
  return (
    <div className="flex min-h-[74px] items-center justify-between gap-4 border-b border-[#eaf0eb] px-5 py-4">
      <div><h2 className="mb-1 text-base font-bold">{title}</h2><p className="text-xs text-[#6d7a72]">{detail}</p></div>
      <Link className="shrink-0 text-xs font-bold text-[#087747]" href={href}>{link}</Link>
    </div>
  );
}
