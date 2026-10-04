import { AnswerPreview, FaqForm, PolicyUpload, ReindexButton, type Faq } from "../../components/knowledge-form";
import { get } from "../../lib/api";
import { archivePolicy } from "../actions";

export default async function KnowledgePage() {
  const [faqs, documents] = await Promise.all([
    get<Faq[]>("/api/admin/faqs"),
    get<{ id: string; name: string; chunk_count: number }[]>("/api/admin/documents"),
  ]);

  return (
    <main className="mx-auto w-[calc(100%-3rem)] max-w-[1240px] py-10 max-md:w-[calc(100%-1.75rem)] max-md:py-7">
      <header className="mb-7">
        <h1 className="mb-2 text-3xl font-bold">FAQ และเอกสารบริษัท</h1>
        <p className="text-sm leading-relaxed text-[#6d7a72]">
          เพิ่มข้อมูลให้แชทบอทตอบพนักงานได้ถูกต้อง แล้วทดสอบคำตอบก่อนใช้งาน
        </p>
      </header>
      <section className="grid items-start gap-5 md:grid-cols-2">
        <details className="rounded-2xl border border-[#e1e9e3] bg-white p-5">
          <summary className="cursor-pointer font-bold text-[#087747]">เพิ่ม FAQ ใหม่</summary>
          <FaqForm />
        </details>
        <article className="rounded-2xl border border-[#e1e9e3] bg-white p-5">
          <h2 className="font-bold">นำเข้าเอกสารบริษัท</h2>
          <PolicyUpload />
          <details className="mt-3 border-t border-[#e1e9e3] pt-3">
            <summary className="cursor-pointer text-sm text-[#6d7a72]">เครื่องมือเพิ่มเติม</summary>
            <p className="my-3 text-xs text-[#6d7a72]">สร้างดัชนีใหม่เมื่อข้อมูลค้นหาไม่ครบหรือผู้ดูแลแนะนำ</p>
            <ReindexButton />
          </details>
        </article>
      </section>
      <AnswerPreview />
      <section className="mb-6 overflow-hidden rounded-2xl border border-[#e1e9e3] bg-white">
        <h2 className="border-b border-[#e1e9e3] p-5 font-bold">เอกสารที่ใช้ตอบคำถาม · {documents.length} เอกสาร</h2>
        <ul>
          {documents.map((item) => (
            <li className="flex flex-wrap items-center justify-between gap-3 border-b border-[#edf1ee] p-5 last:border-0" key={item.id}>
              <span className="min-w-0 break-words font-medium">{item.name}</span>
              <form action={archivePolicy}>
                <input name="id" type="hidden" value={item.id} />
                <button className="min-h-11 rounded-lg px-3 text-sm text-red-700 hover:bg-red-50">หยุดใช้เอกสารนี้</button>
              </form>
            </li>
          ))}
        </ul>
        {!documents.length && <p className="p-8 text-center text-sm text-[#6d7a72]">ยังไม่มีเอกสาร นำเข้าคู่มือหรือนโยบายด้านบน</p>}
      </section>
      <h2 className="mb-3 font-bold">FAQ ทั้งหมด · {faqs.length} รายการ</h2>
      <section className="grid gap-3">
        {faqs.map((faq) => (
          <details className="rounded-2xl border border-[#e1e9e3] bg-white p-5" key={faq.id}>
            <summary className="cursor-pointer font-semibold leading-relaxed">
              {faq.question}{!faq.active && " (ปิดใช้งาน)"}
            </summary>
            <FaqForm faq={faq} />
          </details>
        ))}
        {!faqs.length && <p className="rounded-2xl border border-[#e1e9e3] bg-white p-8 text-center text-sm text-[#6d7a72]">ยังไม่มี FAQ เริ่มจากเพิ่มคำถามที่พนักงานถามบ่อย</p>}
      </section>
    </main>
  );
}
