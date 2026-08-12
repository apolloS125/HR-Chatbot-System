"use client";

import { useActionState } from "react";
import { issueLink, type InviteState } from "../app/actions";

const initialState: InviteState = { link: "", error: "" };

export function InviteButton({ employeeId }: { employeeId: number }) {
  const [state, action, pending] = useActionState(issueLink, initialState);
  return (
    <div className="invite">
      <form action={action}>
        <input type="hidden" name="employee_id" value={employeeId} />
        <button disabled={pending}>{pending ? "กำลังสร้าง…" : "ออกลิงก์ LINE"}</button>
      </form>
      {state.link && (
        <>
          <a href={state.link} target="_blank" rel="noreferrer">เปิดลิงก์ (หมดอายุใน 30 นาที)</a>
          <button type="button" onClick={() => navigator.clipboard.writeText(state.link)}>
            คัดลอกลิงก์
          </button>
        </>
      )}
      {state.error && <small className="error">{state.error}</small>}
    </div>
  );
}
