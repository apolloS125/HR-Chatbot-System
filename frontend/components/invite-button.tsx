"use client";

import { useActionState, useEffect, useRef, useState } from "react";
import { issueLink, type InviteState } from "../app/actions";

const initialState: InviteState = { link: "", error: "" };

export function InviteButton({ employeeId }: { employeeId: string }) {
  const [state, action, pending] = useActionState(issueLink, initialState);
  const input = useRef<HTMLInputElement>(null);
  const [copyStatus, setCopyStatus] = useState("");

  useEffect(() => setCopyStatus(""), [state.link]);

  async function copyLink() {
    try {
      await navigator.clipboard.writeText(state.link);
      setCopyStatus("คัดลอกลิงก์แล้ว");
    } catch {
      input.current?.select();
      setCopyStatus(document.execCommand("copy") ? "คัดลอกลิงก์แล้ว" : "คัดลอกไม่ได้ แตะค้างที่ลิงก์เพื่อคัดลอก");
    }
  }

  return (
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <form action={action}>
        <input type="hidden" name="employee_id" value={employeeId} />
        <button
          className="min-h-11 rounded-lg bg-[#e7f5ed] px-3 text-sm font-bold text-[#087747] disabled:cursor-wait disabled:opacity-60"
          disabled={pending}
        >
          {pending ? "กำลังสร้าง…" : "ออกลิงก์ LINE"}
        </button>
      </form>
      {state.link && (
        <>
          <a
            className="basis-full [overflow-wrap:anywhere] text-[11px] text-[#087747]"
            href={state.link}
            target="_blank"
            rel="noreferrer"
          >
            เปิดลิงก์ (ใช้ได้ครั้งเดียว · หมดอายุใน 30 นาที)
          </a>
          <input
            ref={input}
            aria-label="ลิงก์ยืนยัน LINE"
            className="min-h-11 min-w-0 flex-1 rounded-lg border border-[#cad7ce] px-3 text-sm"
            readOnly
            value={state.link}
            onFocus={(event) => event.currentTarget.select()}
          />
          <button
            className="min-h-11 rounded-lg bg-[#e7f5ed] px-3 text-sm font-bold text-[#087747]"
            type="button"
            onClick={copyLink}
          >
            คัดลอกลิงก์
          </button>
          {copyStatus && (
            <small role="status" className="basis-full text-xs text-[#087747]">
              {copyStatus}
            </small>
          )}
        </>
      )}
      {state.error && (
        <small role="alert" className="basis-full text-sm text-[#b32222]">{state.error}</small>
      )}
    </div>
  );
}
