"use client";

import { useEffect, useRef, useState } from "react";
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
const tabs: { id: LiffTab; label: string; path: string }[] = [
  { id: "leave", label: "ขอลา", path: "M8 3H5v18h14V3h-3M8 3v4h8V3H8Zm0 9h8m-8 4h5" },
  { id: "balance", label: "วันลา", path: "M4 8h16M8 3v4m8-4v4M4 5h16v16H4V5Zm4 7h2m4 0h2m-8 4h2m4 0h2" },
  { id: "history", label: "ประวัติ", path: "M3 11a9 9 0 1 1 2 7M3 4v7h7m2-4v5l3 2" },
  { id: "news", label: "ประกาศ", path: "m4 9 14-5v16L4 15V9Zm0 0H2v6h2m3 1 2 5h3l-2-4m11-8v6" },
];
const dateFormat = new Intl.DateTimeFormat("th-TH", {
  day: "numeric",
  month: "short",
  year: "numeric",
});
const titles = {
  leave: ["ยื่นคำขอลา", "กรอกข้อมูลแล้วส่งให้ HR พิจารณา"],
  balance: ["วันลาของคุณ", "ตรวจสอบสิทธิ์ก่อนวางแผนวันหยุด"],
  history: ["ประวัติการลา", "ติดตามสถานะและจัดการคำขอของคุณ"],
  news: ["ประกาศบริษัท", "ข่าวสารล่าสุดจากฝ่าย HR"],
};

function formatDate(value: string): string {
  return dateFormat.format(new Date(value + "T00:00:00"));
}

type Props = {
  token: string;
  name: string;
  tab: LiffTab;
  message: string;
  messageType: "info" | "success" | "error";
  balances: Balance[];
  leaves: Leave[];
  announcements: Announcement[];
  pending: boolean;
  loading: boolean;
  retry: () => void;
  cancel: (id: string) => void;
  download: (id: string) => void;
  open: (tab: LiffTab) => void;
  submit: (event: FormEvent<HTMLFormElement>) => void;
};

export function LiffView({
  token, name, tab, message, messageType, balances, leaves, announcements,
  open, submit, pending, loading, retry, cancel, download,
}: Props) {
  const [startDate, setStartDate] = useState("");
  const [filename, setFilename] = useState("");
  const notice = useRef<HTMLDivElement>(null);
  const year = Number(new Intl.DateTimeFormat("en", {
    timeZone: "Asia/Bangkok", year: "numeric",
  }).format(new Date()));

  useEffect(() => {
    setStartDate("");
    setFilename("");
  }, [tab]);

  useEffect(() => {
    if (message && token) {
      notice.current?.scrollIntoView({ block: "nearest" });
    }
  }, [message, token]);

  return (
    <main className="liff-app">
      <header className="liff-header">
        <div className="liff-brand">
          <span className="liff-brand-mark" aria-hidden="true">P</span>
          <span>PEOPLE HUB<small>HR Self Service</small></span>
        </div>
        <p className="liff-greeting">{name ? "สวัสดี คุณ" + name : "สวัสดี ยินดีต้อนรับ"}</p>
        <h1>{titles[tab][0]}</h1>
        <p className="liff-subtitle">{titles[tab][1]}</p>
      </header>

      <div className="liff-content">
        {message && (
          <div ref={notice} className={"liff-notice liff-notice-" + messageType}
            role={messageType === "error" ? "alert" : "status"}>
            <p>{message}</p>
            {messageType === "error" && (!token || tab !== "leave") && (
              <button type="button" className="liff-secondary" onClick={retry} disabled={loading}>
                ลองใหม่
              </button>
            )}
            {messageType === "success" && tab === "leave" && (
              <button type="button" className="liff-secondary" onClick={() => open("history")}>
                ดูสถานะคำขอ
              </button>
            )}
          </div>
        )}

        {!token ? (
          <section className="liff-empty" aria-busy={messageType !== "error"}>
            {messageType !== "error" && <span className="liff-spinner" aria-hidden="true" />}
            <h2>{messageType === "error" ? "ยังเข้าใช้งานไม่ได้" : "กำลังยืนยันบัญชีของคุณ"}</h2>
            <p>{messageType === "error" ? "ลองใหม่ หรือติดต่อ HR เพื่อช่วยตรวจสอบบัญชี" : "รอสักครู่ เรากำลังเชื่อมต่อกับ LINE"}</p>
          </section>
        ) : (
          <>
            {tab === "leave" && (
              <form className="liff-form" onSubmit={submit}
                onReset={() => {
                  setStartDate("");
                  setFilename("");
                }}>
                <fieldset className="liff-card" disabled={pending}>
                  <legend className="sr-only">ข้อมูลคำขอลา</legend>
                  <div className="liff-section-heading"><span>01</span><h2>รายละเอียดการลา</h2></div>
                  <label className="liff-field">ประเภทการลา
                    <select name="leave_type" defaultValue="vacation">
                      <option value="vacation">พักร้อน</option>
                      <option value="sick">ลาป่วย</option>
                      <option value="personal">ลากิจ</option>
                    </select>
                  </label>
                  <label className="liff-field">วันเริ่มลา
                    <input required name="start_date" type="date" min={year + "-01-01"}
                      max={year + "-12-31"} onChange={(event) => setStartDate(event.target.value)} />
                  </label>
                  <label className="liff-field">วันสิ้นสุด
                    <input required name="end_date" type="date" min={startDate || year + "-01-01"}
                      max={year + "-12-31"} />
                  </label>
                  <label className="liff-field">ระยะเวลา
                    <select name="half_day" aria-describedby="half-day-hint">
                      <option value="">เต็มวัน</option>
                      <option value="morning">ครึ่งวันเช้า</option>
                      <option value="afternoon">ครึ่งวันบ่าย</option>
                    </select>
                    <small id="half-day-hint">ลาครึ่งวัน ให้เลือกวันเริ่มและวันสิ้นสุดเป็นวันเดียวกัน</small>
                  </label>
                </fieldset>

                <fieldset className="liff-card" disabled={pending}>
                  <legend className="sr-only">เหตุผลและเอกสารแนบ</legend>
                  <div className="liff-section-heading"><span>02</span><h2>เหตุผลและเอกสาร</h2></div>
                  <label className="liff-field">เหตุผลการลา
                    <textarea required name="reason" rows={3} maxLength={1500}
                      placeholder="ระบุเหตุผลเพื่อให้ HR พิจารณา" />
                  </label>
                  <label className="liff-field">เอกสารแนบ <span className="liff-optional">ไม่บังคับ</span>
                    <input name="attachment" type="file" accept="application/pdf,image/jpeg,image/png"
                      aria-describedby="attachment-hint"
                      onChange={(event) => setFilename(event.target.files?.[0]?.name ?? "")} />
                    <small id="attachment-hint">PDF, JPG หรือ PNG ขนาดไม่เกิน 10 MB</small>
                    {filename && <small className="liff-file-name">เลือกแล้ว: {filename}</small>}
                  </label>
                </fieldset>
                <p className="liff-form-note">วันลาจะถูกหักเมื่อคำขอได้รับการอนุมัติ</p>
                <button disabled={pending} className="liff-primary" type="submit">
                  {pending ? "กำลังส่งคำขอ…" : "ส่งคำขอลา"}
                </button>
              </form>
            )}

            {loading ? (
              <div className="liff-empty" role="status">
                <span className="liff-spinner" aria-hidden="true" />
                <p>กำลังโหลดข้อมูล…</p>
              </div>
            ) : (
              <>
                {tab === "balance" && (
                  <section className="liff-list" aria-label="วันลาคงเหลือ">
                    <p className="liff-year">สิทธิ์การลา ปี {year + 543}</p>
                    {balances.map((item) => (
                      <article key={item.leave_type} className="liff-card liff-balance-card">
                        <div><h2>{labels[item.leave_type] ?? item.leave_type}</h2><p>วันลาคงเหลือ</p></div>
                        <p className="liff-balance-number">{item.remaining_days}<small>วัน</small></p>
                      </article>
                    ))}
                    {!balances.length && messageType !== "error" && (
                      <Empty title="ยังไม่มีข้อมูลวันลา" detail="ติดต่อ HR เพื่อตรวจสอบสิทธิ์การลาของคุณ" />
                    )}
                    {!!balances.length && <p className="liff-form-note">ยอดนี้ยังไม่หักคำขอที่รออนุมัติ</p>}
                    <button type="button" className="liff-primary" onClick={() => open("leave")}>ยื่นคำขอลา</button>
                  </section>
                )}

                {tab === "history" && (
                  <section className="liff-list" aria-label="ประวัติคำขอลา">
                    {!leaves.length && messageType !== "error" && (
                      <Empty title="ยังไม่มีคำขอลา" detail="เมื่อส่งคำขอแล้ว คุณติดตามสถานะได้ที่นี่" />
                    )}
                    {leaves.map((item) => (
                      <article key={item.id} className="liff-card">
                        <div className="liff-row">
                          <h2>{labels[item.leave_type] ?? item.leave_type}</h2>
                          <span className={"liff-badge liff-badge-" + item.status}>
                            {labels[item.status] ?? item.status}
                          </span>
                        </div>
                        <p className="liff-leave-date">
                          {formatDate(item.start_date)}
                          {item.end_date !== item.start_date && " – " + formatDate(item.end_date)}
                        </p>
                        <p className="liff-leave-duration">
                          {item.days} วัน
                          {item.half_day && " · " + (item.half_day === "morning" ? "ครึ่งวันเช้า" : "ครึ่งวันบ่าย")}
                        </p>
                        <p className="liff-reason">{item.reason}</p>
                        <p className="liff-request-id">รหัสคำขอ {item.id}</p>
                        {(item.attachment_id || item.status === "pending") && (
                          <div className="liff-card-actions">
                            {item.attachment_id && (
                              <button type="button" className="liff-secondary"
                                onClick={() => download(item.attachment_id!)}>ดูเอกสารแนบ</button>
                            )}
                            {item.status === "pending" && (
                              <button type="button" className="liff-danger"
                                disabled={pending} onClick={() => cancel(item.id)}>
                                {pending ? "กำลังดำเนินการ…" : "ยกเลิกคำขอ"}
                              </button>
                            )}
                          </div>
                        )}
                      </article>
                    ))}
                  </section>
                )}

                {tab === "news" && (
                  <section className="liff-list" aria-label="ประกาศบริษัท">
                    {!announcements.length && messageType !== "error" && (
                      <Empty title="ยังไม่มีประกาศใหม่" detail="ข่าวสารจาก HR จะแสดงที่นี่" />
                    )}
                    {announcements.map((item) => (
                      <article key={item.id} className="liff-card liff-news-card">
                        <span className="liff-news-label">ข่าวสารจาก HR</span>
                        <h2>{item.title}</h2>
                        <p className="liff-news-body">{item.body}</p>
                        <time dateTime={item.published_at}>
                          {dateFormat.format(new Date(item.published_at))}
                        </time>
                      </article>
                    ))}
                  </section>
                )}
              </>
            )}
          </>
        )}
      </div>

      <nav className="liff-bottom-nav" aria-label="เมนูพนักงาน">
        {tabs.map((item) => (
          <button type="button" key={item.id} disabled={!token || pending}
            aria-current={tab === item.id ? "page" : undefined}
            onClick={() => open(item.id)}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7"
              strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d={item.path} />
            </svg>
            <span>{item.label}</span>
          </button>
        ))}
      </nav>
    </main>
  );
}

function Empty({ title, detail }: { title: string; detail: string }) {
  return (
    <div className="liff-empty"><h2>{title}</h2><p>{detail}</p></div>
  );
}
