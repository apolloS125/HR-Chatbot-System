"use client";

import type { FormEvent } from "react";

export type Balance = { leave_type: string; remaining_days: number };
export type Leave = {
  id: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  days: number;
  reason: string;
  status: string;
  attachment_id?: string;
  half_day?: string;
};
export type Announcement = {
  id: string;
  title: string;
  body: string;
  published_at: string;
};
export type LiffTab = "leave" | "balance" | "history" | "news";

const labels: Record<string, string> = {
  vacation: "พักร้อน",
  sick: "ลาป่วย",
  personal: "ลากิจ",
  pending: "รออนุมัติ",
  approved: "อนุมัติแล้ว",
  rejected: "ไม่อนุมัติ",
  cancelled: "ยกเลิกแล้ว",
};

type Props = {
  token: string;
  name: string;
  tab: LiffTab;
  message: string;
  balances: Balance[];
  leaves: Leave[];
  announcements: Announcement[];
  pending: boolean;
  cancel: (id: string) => void;
  download: (id: string) => void;
  open: (tab: LiffTab) => void;
  submit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LiffView({
  token,
  name,
  tab,
  message,
  balances,
  leaves,
  announcements,
  open,
  submit,
  pending,
  cancel,
  download,
}: Props) {
  function Tab({ id, label }: { id: LiffTab; label: string }) {
    const className = tab === id
      ? "rounded-lg bg-[#123c2a] p-2 text-white"
      : "p-2";

    return (
      <button type="button" onClick={() => open(id)} className={className}>
        {label}
      </button>
    );
  }

  return (
    <main className="liff-app mx-auto min-h-dvh max-w-xl bg-[#f4f7f5] px-5 py-7 text-[#17241d]">
      <header className="mb-6">
        <span className="text-xs font-bold tracking-[.16em] text-[#087747]">PEOPLE HUB</span>
        <h1 className="mt-1 text-2xl font-bold">
          {name ? `สวัสดี ${name}` : "HR Self-service"}
        </h1>
        <p className="text-sm text-[#6d7a72]">ขอลา ดูสิทธิ์ และติดตามข้อมูล HR</p>
      </header>

      {message && (
        <p className="mb-4 rounded-xl bg-[#e7f5ed] p-3 text-sm text-[#087747]">
          {message}
        </p>
      )}

      <nav className="mb-5 grid grid-cols-4 gap-1 rounded-xl bg-white p-1 text-xs font-semibold">
        <Tab id="leave" label="ขอลา" />
        <Tab id="balance" label="วันลา" />
        <Tab id="history" label="ประวัติ" />
        <Tab id="news" label="ประกาศ" />
      </nav>

      {tab === "leave" && (
        <form onSubmit={submit} className="grid gap-4 rounded-2xl bg-white p-5 shadow-sm">
          <label>
            ประเภทการลา
            <select name="leave_type" defaultValue="vacation" className="mt-1 w-full rounded-lg border p-3">
              <option value="vacation">พักร้อน</option>
              <option value="sick">ลาป่วย</option>
              <option value="personal">ลากิจ</option>
            </select>
          </label>
          <div className="grid grid-cols-2 gap-3">
            <label>
              วันเริ่ม
              <input required name="start_date" type="date" className="mt-1 w-full rounded-lg border p-3" />
            </label>
            <label>
              วันสิ้นสุด
              <input required name="end_date" type="date" className="mt-1 w-full rounded-lg border p-3" />
            </label>
          </div>
          <label>
            ระยะเวลา
            <select name="half_day" className="mt-1 w-full rounded-lg border p-3">
              <option value="">เต็มวัน</option>
              <option value="morning">ครึ่งวันเช้า</option>
              <option value="afternoon">ครึ่งวันบ่าย</option>
            </select>
          </label>
          <label>
            เหตุผล
            <textarea required name="reason" className="mt-1 w-full rounded-lg border p-3" />
          </label>
          <label>
            แนบเอกสาร (PDF/JPG/PNG, ไม่เกิน 10 MB)
            <input
              name="attachment"
              type="file"
              accept="application/pdf,image/jpeg,image/png"
              className="mt-1 block w-full text-sm"
            />
          </label>
          <button
            disabled={!token || pending}
            className="rounded-xl bg-[#087747] p-3 font-bold text-white disabled:opacity-50"
          >
            {pending ? "กำลังส่ง…" : "ส่งคำขอลา"}
          </button>
        </form>
      )}

      {tab === "balance" && (
        <section className="grid gap-3">
          {balances.map((item) => (
            <article key={item.leave_type} className="rounded-xl bg-white p-4">
              <b>{labels[item.leave_type]}</b>
              <strong className="float-right text-xl text-[#087747]">
                {item.remaining_days} วัน
              </strong>
            </article>
          ))}
        </section>
      )}

      {tab === "history" && (
        <section className="grid gap-3">
          {!leaves.length && <p className="p-4 text-sm">ยังไม่มีประวัติการลา</p>}
          {leaves.map((item) => (
            <article key={item.id} className="rounded-xl bg-white p-4">
              <b>{labels[item.leave_type]}</b>
              <span className="float-right text-sm text-[#087747]">{labels[item.status]}</span>
              <p className="mt-2 text-sm">
                {item.start_date} – {item.end_date} · {item.days} วัน
              </p>
              <p className="text-sm text-[#6d7a72]">{item.reason}</p>
              {item.half_day && (
                <p className="text-xs">
                  {item.half_day === "morning" ? "ครึ่งวันเช้า" : "ครึ่งวันบ่าย"}
                </p>
              )}
              {item.attachment_id && (
                <button
                  type="button"
                  className="mr-4 text-sm text-[#087747]"
                  onClick={() => download(item.attachment_id!)}
                >
                  เอกสารแนบ
                </button>
              )}
              {item.status === "pending" && (
                <button
                  type="button"
                  className="text-sm text-red-700"
                  onClick={() => cancel(item.id)}
                >
                  ยกเลิกคำขอ
                </button>
              )}
            </article>
          ))}
        </section>
      )}

      {tab === "news" && (
        <section className="grid gap-3">
          {!announcements.length && <p className="p-4 text-sm">ยังไม่มีประกาศ</p>}
          {announcements.map((item) => (
            <article key={item.id} className="rounded-xl bg-white p-4">
              <b>{item.title}</b>
              <p className="mt-2 whitespace-pre-wrap text-sm text-[#5d6961]">{item.body}</p>
              <time className="mt-2 block text-xs text-[#8a958e]">
                {new Date(item.published_at).toLocaleString("th-TH")}
              </time>
            </article>
          ))}
        </section>
      )}
    </main>
  );
}
