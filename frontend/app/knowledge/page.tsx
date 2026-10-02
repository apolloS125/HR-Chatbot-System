import { AnswerPreview, FaqForm, PolicyUpload, ReindexButton, type Faq } from "../../components/knowledge-form";
import { get } from "../../lib/api";
import { archivePolicy } from "../actions";

export default async function KnowledgePage() {
  const [faqs, documents] = await Promise.all([get<Faq[]>("/api/admin/faqs"), get<{ id: string; name: string; chunk_count: number }[]>("/api/admin/documents")]);
  return <main className="mx-auto max-w-5xl p-6">
    <h1 className="mb-2 text-2xl font-bold">FAQ และเอกสารบริษัท</h1>
    <p className="mb-6 text-sm text-[#6d7a72]">คำตอบของแชทบอทค้นจากข้อมูลที่เปิดใช้งาน พร้อมแสดงแหล่งอ้างอิง</p>
    <section className="mb-6 grid gap-4 md:grid-cols-2"><div><h2 className="mb-3 font-bold">เพิ่ม FAQ</h2><FaqForm /></div><div><h2 className="mb-3 font-bold">นำเข้าเอกสาร</h2><PolicyUpload /><div className="mt-4"><ReindexButton /></div></div></section>
    <h2 className="mb-3 font-bold">เอกสารที่ใช้ตอบคำถาม</h2>
    <ul className="mb-6 grid gap-2">{documents.map((item) => <li className="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-white p-4" key={item.id}><span>{item.name} · {item.chunk_count} ส่วน</span><form action={archivePolicy}><input name="id" type="hidden" value={item.id} /><button className="text-sm text-red-700">หยุดใช้เอกสารนี้</button></form></li>)}</ul>
    {!documents.length && <p className="mb-6 text-sm">ยังไม่มีเอกสาร</p>}
    <AnswerPreview />
    <h2 className="mb-3 font-bold">FAQ ทั้งหมด</h2>
    <section className="grid gap-3">{faqs.map((faq) => <details className="rounded-xl bg-white p-4" key={faq.id}><summary className="cursor-pointer font-semibold">{faq.question}{!faq.active && " (ปิดใช้งาน)"}</summary><FaqForm faq={faq} /></details>)}</section>
  </main>;
}
