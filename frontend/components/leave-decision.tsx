"use client";

import { useActionState, useRef } from "react";

import { decideLeave } from "../app/actions";

type LeaveDetails = {
  id: string;
  name: string;
  employee_code: string;
  days: number;
  reason: string;
  half_day?: string;
  attachment_id?: string;
};

export function LeaveDecisionForm({
  leave,
  leaveType,
  dateRange,
}: {
  leave: LeaveDetails;
  leaveType: string;
  dateRange: string;
}) {
  const [state, action, pending] = useActionState(decideLeave, { error: "" });
  const dialog = useRef<HTMLDialogElement>(null);
  const halfDayLabel = leave.half_day === "morning" ? "ครึ่งวันเช้า" : "ครึ่งวันบ่าย";

  return (
    <>
      <button
        type="button"
        onClick={() => dialog.current?.showModal()}
        className="min-h-8 rounded-lg bg-[#e7f5ed] px-2.5 text-[11px] font-bold text-[#087747]"
      >
        พิจารณาคำขอ
      </button>
      <dialog
        ref={dialog}
        aria-labelledby={`leave-${leave.id}`}
        className="m-auto max-h-[90dvh] w-[min(34rem,calc(100%-2rem))] overflow-y-auto rounded-2xl border border-[#e1e9e3] bg-white p-0 text-sm shadow-2xl backdrop:bg-black/40"
      >
        <div className="flex items-center justify-between border-b border-[#edf1ee] px-5 py-4">
          <h2 id={`leave-${leave.id}`} className="m-0 text-lg font-bold">
            คำขอลา · {leave.name}
          </h2>
          <button
            type="button"
            onClick={() => dialog.current?.close()}
            aria-label="ปิดหน้าต่าง"
            className="rounded-lg px-3 py-1 text-xl text-[#6d7a72]"
          >
            ×
          </button>
        </div>
        <div className="grid gap-3 p-5">
          <p className="m-0">
            รหัสพนักงาน: <b>{leave.employee_code}</b>
          </p>
          <p className="m-0">
            ประเภท: <b>{leaveType}</b>
          </p>
          <p className="m-0">
            วันที่: {dateRange} · {leave.days} วัน
            {leave.half_day && ` · ${halfDayLabel}`}
          </p>
          <div>
            <b>เหตุผล</b>
            <p className="my-1 whitespace-pre-wrap text-[#5d6961]">{leave.reason}</p>
          </div>
          {leave.attachment_id && (
            <a className="text-[#087747]" href={`/attachments/${leave.attachment_id}`}>
              เปิดเอกสารแนบ
            </a>
          )}
          <form action={action} className="flex flex-wrap gap-2 border-t border-[#edf1ee] pt-4">
            <input type="hidden" name="leave_id" value={leave.id} />
            <button
              name="decision"
              value="approved"
              disabled={pending}
              className="min-h-10 rounded-lg bg-[#087747] px-4 font-bold text-white disabled:opacity-50"
            >
              อนุมัติ
            </button>
            <button
              name="decision"
              value="rejected"
              disabled={pending}
              className="min-h-10 rounded-lg bg-[#f8eded] px-4 font-bold text-[#a32727] disabled:opacity-50"
            >
              ปฏิเสธ
            </button>
            {state.error && (
              <p role="alert" className="basis-full text-xs text-red-700">
                {state.error}
              </p>
            )}
          </form>
        </div>
      </dialog>
    </>
  );
}
