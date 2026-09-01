import { AnnouncementForm } from "../../components/announcement-form";
import { formatDateTime, get, type Announcement } from "../../lib/api";

export default async function AnnouncementsPage() {
  const announcements = await get<Announcement[]>("/api/admin/announcements");
  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7 flex items-end justify-between gap-6 max-sm:block">
        <div>
          <span className="text-[11px] font-extrabold tracking-[.17em] text-[#087747]">COMMUNICATION</span>
          <h1 className="mt-1 mb-1 text-[clamp(1.75rem,3vw,2.45rem)] leading-tight font-bold tracking-[-.04em]">ประกาศบริษัท</h1>
          <p className="text-sm text-[#6d7a72]">สร้าง Message Card และส่งถึงพนักงานผ่าน LINE</p>
        </div>
        <span className="shrink-0 rounded-full border border-[#e1e9e3] bg-white px-3 py-2 text-xs text-[#6d7a72] max-sm:mt-3 max-sm:inline-flex">{announcements.length} รายการ</span>
      </header>

      <section className="grid grid-cols-[minmax(300px,.7fr)_minmax(0,1.3fr)] items-start gap-[18px] max-lg:grid-cols-1">
        <article className="sticky top-6 overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510] max-lg:static">
          <div className="flex min-h-[74px] items-center border-b border-[#eaf0eb] px-5 py-4">
            <div><h2 className="mb-1 text-base font-bold">สร้างประกาศ</h2><p className="text-xs text-[#6d7a72]">ส่งถึงพนักงาน Active ที่เชื่อม LINE</p></div>
          </div>
          <AnnouncementForm />
        </article>

        <section className="overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white shadow-[0_10px_30px_#264c3510]">
          <div className="flex min-h-[74px] items-center border-b border-[#eaf0eb] px-5 py-4">
            <div><h2 className="mb-1 text-base font-bold">ประวัติประกาศ</h2><p className="text-xs text-[#6d7a72]">รายการที่เผยแพร่ล่าสุด</p></div>
          </div>
          <div className="grid gap-3 p-[18px]">
            {announcements.map((announcement) => (
              <article className="relative overflow-hidden rounded-xl border border-[#e5ece7] bg-[#fafcfb] py-4 pr-[18px] pl-[21px] before:absolute before:inset-y-0 before:left-0 before:w-1 before:bg-[#087747]" key={announcement.id}>
                <div className="flex justify-between gap-3 text-[11px] text-[#6d7a72] max-sm:grid max-sm:gap-1">
                  <span className="font-extrabold tracking-[.1em] text-[#087747]">HR UPDATE</span>
                  <time>{formatDateTime(announcement.published_at)}</time>
                </div>
                <h3 className="mt-3 mb-1.5 text-base font-bold">{announcement.title}</h3>
                <p className="m-0 whitespace-pre-wrap text-sm leading-relaxed text-[#58655d]">{announcement.body}</p>
              </article>
            ))}
            {!announcements.length && <p className="m-0 p-10 text-center text-sm text-[#6d7a72]">ยังไม่มีประกาศ</p>}
          </div>
        </section>
      </section>
    </main>
  );
}
