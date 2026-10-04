"use client";

import { useActionState } from "react";
import { previewAnswer, reindexPolicies, saveFaq, uploadPolicy } from "../app/actions";

export type Faq = { id: string; keyword: string; question: string; answer: string; active: boolean };
const initial = { message: "", error: "" };
const field = "mt-1.5 min-h-11 w-full rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5";

export function FaqForm({ faq }: { faq?: Faq }) {
  const [state, action, pending] = useActionState(saveFaq, initial);
  return <form action={action} className="grid gap-3 rounded-xl bg-white p-4">
    <input name="id" type="hidden" value={faq?.id ?? ""} />
    <label>คำค้น<input className={field} name="keyword" defaultValue={faq?.keyword} maxLength={120} required /></label>
    <label>คำถาม<input className={field} name="question" defaultValue={faq?.question} maxLength={300} required /></label>
    <label>คำตอบ<textarea className={field} name="answer" defaultValue={faq?.answer} maxLength={10000} rows={4} required /></label>
    <label><input name="active" type="checkbox" defaultChecked={faq?.active ?? true} /> เปิดใช้งาน</label>
    <button disabled={pending} className="rounded-lg bg-[#087747] p-2 text-white disabled:opacity-50">{pending ? "กำลังบันทึก…" : "บันทึก FAQ"}</button>
    <p role="status" className={state.error ? "text-sm text-red-700" : "text-sm text-[#087747]"}>{state.error || state.message}</p>
  </form>;
}

export function PolicyUpload() {
  const [state, action, pending] = useActionState(uploadPolicy, initial);
  return <form action={action} className="grid gap-3 rounded-xl bg-white p-4">
    <label>คู่มือหรือนโยบายบริษัท<input className="mt-2 block w-full" name="file" type="file" accept=".pdf,.txt" required /></label>
    <p className="text-xs text-[#6d7a72]">PDF ที่มีข้อความหรือ TXT UTF-8 ไม่เกิน 10 MB และ 100 หน้า</p>
    <button disabled={pending} className="rounded-lg bg-[#087747] p-2 text-white disabled:opacity-50">{pending ? "กำลังนำเข้า…" : "นำเข้าเอกสาร"}</button>
    <p role="status" className={state.error ? "text-sm text-red-700" : "text-sm text-[#087747]"}>{state.error || state.message}</p>
  </form>;
}

export function ReindexButton() {
  const [state, action, pending] = useActionState(reindexPolicies, initial);
  return <form action={action}><button disabled={pending} className="rounded-lg border bg-white p-2 text-sm disabled:opacity-50">{pending ? "กำลังสร้าง…" : "สร้างดัชนีค้นหาใหม่"}</button><p role="status" className="mt-2 text-sm">{state.error || state.message}</p></form>;
}

export function AnswerPreview() {
  const [state, action, pending] = useActionState(previewAnswer, initial);
  return (
    <form action={action} className="my-6 grid gap-3 rounded-2xl border border-[#e1e9e3] bg-white p-5">
      <label className="font-semibold">
        ทดสอบคำตอบแชทบอท
        <input className={field} name="question" placeholder="เช่น ลาพักร้อนได้กี่วัน" maxLength={1500} required />
      </label>
      <button disabled={pending} className="min-h-11 rounded-lg bg-[#087747] px-4 py-2 font-semibold text-white disabled:opacity-50">
        {pending ? "กำลังค้น…" : "ทดสอบคำตอบ"}
      </button>
      {(state.error || state.message) && (
        <p role={state.error ? "alert" : "status"} className={`whitespace-pre-wrap rounded-lg bg-[#f7faf8] p-4 text-sm leading-relaxed ${state.error ? "text-red-700" : "text-[#30533e]"}`}>
          {state.error || state.message}
        </p>
      )}
    </form>
  );
}
