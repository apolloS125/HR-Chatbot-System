"use client";

import { useActionState, useEffect, useRef } from "react";
import { createAnnouncement, type AnnouncementState } from "../app/actions";

const initialState: AnnouncementState = { message: "", error: "" };
const field = "w-full min-w-0 rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5 outline-none transition placeholder:text-[#96a199] focus:border-[#55b987] focus:ring-3 focus:ring-[#55b987]/20";

export function AnnouncementForm() {
  const [state, action, pending] = useActionState(createAnnouncement, initialState);
  const requestKey = useRef("");
  useEffect(() => { if (state.message) requestKey.current = ""; }, [state.message]);
  return (
    <form action={action} className="grid gap-3 p-5" onSubmit={(event) => {
      if (!requestKey.current) requestKey.current = crypto.randomUUID();
      (event.currentTarget.elements.namedItem("request_key") as HTMLInputElement).value = requestKey.current;
    }}>
      <input type="hidden" name="request_key" />
      <label className="grid gap-1.5 text-sm font-semibold">
        หัวข้อประกาศ
        <input className={field} name="title" placeholder="เช่น แจ้งวันหยุดประจำปี" maxLength={120} required />
      </label>
      <label className="grid gap-1.5 text-sm font-semibold">
        รายละเอียดประกาศ
        <textarea className={`${field} resize-y font-normal leading-relaxed`} name="body" maxLength={1500} rows={6} required />
      </label>
      <p className="text-xs leading-relaxed text-[#6d7a72]">เมื่อกดส่ง ประกาศจะเผยแพร่และแจ้งพนักงานที่เชื่อม LINE ทันที</p>
      <button className="min-h-10 rounded-lg bg-[#087747] px-3 font-bold text-white transition hover:bg-[#06643b] disabled:cursor-wait disabled:opacity-60" disabled={pending}>
        {pending ? "กำลังส่ง…" : "สร้างและส่งเข้า LINE"}
      </button>
      {state.message && <small role="status" className="text-sm text-[#087747]">{state.message}</small>}
      {state.error && <small role="alert" className="text-sm text-[#b32222]">{state.error}</small>}
    </form>
  );
}
