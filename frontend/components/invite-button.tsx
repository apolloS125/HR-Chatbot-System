"use client";

import { useActionState } from "react";
import { issueLink, type InviteState } from "../app/actions";

const initialState: InviteState = { link: "", error: "" };

export function InviteButton({ employeeId }: { employeeId: string }) {
  const [state, action, pending] = useActionState(issueLink, initialState);
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <form action={action}>
        <input type="hidden" name="employee_id" value={employeeId} />
        <button className="min-h-9 rounded-lg bg-[#e7f5ed] px-2.5 text-xs font-bold text-[#087747] disabled:cursor-wait disabled:opacity-60" disabled={pending}>{pending ? "กำลังสร้าง…" : "ออกลิงก์ LINE"}</button>
      </form>
      {state.link && (
        <>
          <a className="basis-full [overflow-wrap:anywhere] text-[11px] text-[#087747]" href={state.link} target="_blank" rel="noreferrer">เปิดลิงก์ (หมดอายุใน 30 นาที)</a>
          <button className="min-h-9 rounded-lg bg-[#e7f5ed] px-2.5 text-xs font-bold text-[#087747]" type="button" onClick={() => navigator.clipboard.writeText(state.link)}>
            คัดลอกลิงก์
          </button>
        </>
      )}
      {state.error && <small className="basis-full text-xs text-[#b32222]">{state.error}</small>}
    </div>
  );
}
