"use client";

import { useActionState } from "react";
import { createAnnouncement, type AnnouncementState } from "../app/actions";

const initialState: AnnouncementState = { message: "", error: "" };
const field = "w-full min-w-0 rounded-lg border border-[#cad7ce] bg-white px-3 py-2.5 outline-none transition placeholder:text-[#96a199] focus:border-[#55b987] focus:ring-3 focus:ring-[#55b987]/20";

export function AnnouncementForm() {
  const [state, action, pending] = useActionState(createAnnouncement, initialState);
  return (
    <form action={action} className="grid gap-3 p-5">
      <input className={field} name="title" placeholder="หัวข้อประกาศ" maxLength={120} required />
      <textarea className={`${field} resize-y leading-relaxed`} name="body" placeholder="รายละเอียดประกาศ" maxLength={1500} rows={6} required />
      <button className="min-h-10 rounded-lg bg-[#087747] px-3 font-bold text-white transition hover:bg-[#06643b] disabled:cursor-wait disabled:opacity-60" disabled={pending}>
        {pending ? "กำลังส่ง…" : "สร้างและส่งเข้า LINE"}
      </button>
      {state.message && <small className="text-xs text-[#087747]">{state.message}</small>}
      {state.error && <small className="text-xs text-[#b32222]">{state.error}</small>}
    </form>
  );
}
