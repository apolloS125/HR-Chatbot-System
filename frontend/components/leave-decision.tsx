"use client";

import { useActionState } from "react";
import { decideLeave } from "../app/actions";

export function LeaveDecisionForm({ id }: { id: string }) {
  const [state, action, pending] = useActionState(decideLeave, { error: "" });
  return <form action={action}>
    <input type="hidden" name="leave_id" value={id} />
    <div className="flex gap-1.5">
      <button name="decision" value="approved" disabled={pending} className="min-h-8 rounded-lg bg-[#087747] px-2.5 text-[11px] font-bold text-white disabled:opacity-50">อนุมัติ</button>
      <button name="decision" value="rejected" disabled={pending} className="min-h-8 rounded-lg bg-[#f8eded] px-2.5 text-[11px] font-bold text-[#a32727] disabled:opacity-50">ปฏิเสธ</button>
    </div>
    {state.error && <p role="alert" className="mt-2 text-xs text-red-700">{state.error}</p>}
  </form>;
}
