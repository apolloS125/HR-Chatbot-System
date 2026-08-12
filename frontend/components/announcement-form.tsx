"use client";

import { useActionState } from "react";
import { createAnnouncement, type AnnouncementState } from "../app/actions";

const initialState: AnnouncementState = { message: "", error: "" };

export function AnnouncementForm() {
  const [state, action, pending] = useActionState(createAnnouncement, initialState);
  return (
    <form action={action} className="announcement-form">
      <input name="title" placeholder="หัวข้อประกาศ" maxLength={120} required />
      <textarea name="body" placeholder="รายละเอียดประกาศ" maxLength={1500} rows={4} required />
      <button className="primary" disabled={pending}>
        {pending ? "กำลังส่ง…" : "สร้างและส่งเข้า LINE"}
      </button>
      {state.message && <small className="success">{state.message}</small>}
      {state.error && <small className="error">{state.error}</small>}
    </form>
  );
}
