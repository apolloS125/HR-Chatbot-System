"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { type Announcement, type Balance, type Leave, type LiffTab, LiffView } from "./liff-view";

type Liff = { init: (value: { liffId: string }) => Promise<void>; getIDToken: () => string | null; isLoggedIn: () => boolean; login: () => void };
declare global { interface Window { liff?: Liff } }
const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function LiffApp() {
  const [token, setToken] = useState("");
  const [name, setName] = useState("");
  const [tab, setTab] = useState<LiffTab>("leave");
  const [balances, setBalances] = useState<Balance[]>([]);
  const [leaves, setLeaves] = useState<Leave[]>([]);
  const [announcements, setAnnouncements] = useState<Announcement[]>([]);
  const [message, setMessage] = useState("กำลังเชื่อมต่อ LINE...");
  const [pending, setPending] = useState(false);
  const busy = useRef(false);
  const request = useRef({ key: "", fingerprint: "", attachment_id: "" });

  useEffect(() => {
    const script = document.createElement("script");
    let disposed = false;
    script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js";
    script.onload = async () => {
      try {
        const id = process.env.NEXT_PUBLIC_LIFF_ID;
        if (!id || !window.liff) throw new Error("ยังไม่ได้ตั้งค่า NEXT_PUBLIC_LIFF_ID");
        await window.liff.init({ liffId: id });
        if (disposed) return;
        if (!window.liff.isLoggedIn()) return window.liff.login();
        const idToken = window.liff.getIDToken();
        if (!idToken) throw new Error("ไม่พบ LINE ID token");
        const response = await fetch(`${backend}/api/liff/session`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id_token: idToken }) });
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail ?? "ยืนยันตัวตนไม่สำเร็จ");
        if (!disposed) { setToken(data.token); setName(data.name); setMessage(""); }
      } catch (error) {
        if (!disposed) setMessage(error instanceof Error ? error.message : "เชื่อมต่อ LINE ไม่สำเร็จ");
      }
    };
    script.onerror = () => setMessage("โหลด LIFF SDK ไม่สำเร็จ");
    document.head.append(script);
    return () => { disposed = true; script.remove(); };
  }, []);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${backend}/api/liff${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, ...init?.headers } });
    const data = await response.json();
    if (response.status === 401) throw new Error("เซสชันหมดอายุ กรุณาปิดแล้วเปิดแอปใหม่");
    if (!response.ok) throw new Error(Array.isArray(data.detail) ? data.detail.map((item: { msg: string }) => item.msg).join("; ") : data.detail ?? "ทำรายการไม่สำเร็จ");
    return data as T;
  }

  async function open(next: LiffTab) {
    setTab(next);
    if (!token) return;
    setMessage("");
    try {
      if (next === "balance") setBalances(await api<Balance[]>("/balances"));
      if (next === "history") setLeaves(await api<Leave[]>("/leaves"));
      if (next === "news") setAnnouncements(await api<Announcement[]>("/announcements"));
    } catch (error) { setMessage(error instanceof Error ? error.message : "โหลดข้อมูลไม่สำเร็จ"); }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current) return;
    busy.current = true;
    setPending(true);
    const element = event.currentTarget;
    const form = new FormData(element);
    const file = form.get("attachment");
    const payload = { leave_type: form.get("leave_type"), start_date: form.get("start_date"), end_date: form.get("end_date"), reason: form.get("reason"), half_day: form.get("half_day") || null };
    const fingerprint = JSON.stringify([payload, file instanceof File ? [file.name, file.size, file.lastModified] : null]);
    if (request.current.fingerprint !== fingerprint) request.current = { key: crypto.randomUUID(), fingerprint, attachment_id: "" };
    try {
      if (file instanceof File && file.size && !request.current.attachment_id) {
        if (file.size > 10 * 1024 * 1024) throw new Error("ไฟล์ต้องไม่เกิน 10 MB");
        const attachment = new FormData();
        attachment.append("file", file);
        request.current.attachment_id = (await api<{ id: string }>("/attachments", { method: "POST", body: attachment })).id;
      }
      const result = await api<{ id: string; days: number }>("/leaves", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...payload, request_key: request.current.key, attachment_id: request.current.attachment_id || null }) });
      element.reset();
      request.current = { key: "", fingerprint: "", attachment_id: "" };
      setMessage(`ส่งคำขอลา #${result.id} แล้ว (${result.days} วัน)`);
    } catch (error) { setMessage(error instanceof Error ? error.message : "ส่งคำขอลาไม่สำเร็จ"); }
    finally { busy.current = false; setPending(false); }
  }

  async function cancel(id: string) {
    if (!window.confirm("ยกเลิกคำขอลานี้ใช่หรือไม่?")) return;
    try { await api(`/leaves/${id}/cancel`, { method: "POST" }); setLeaves(await api<Leave[]>("/leaves")); setMessage("ยกเลิกคำขอแล้ว"); }
    catch (error) { setMessage(error instanceof Error ? error.message : "ยกเลิกไม่สำเร็จ"); }
  }

  async function download(id: string) {
    try {
      const response = await fetch(`${backend}/api/liff/attachments/${id}`, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("เปิดเอกสารไม่ได้ กรุณาลองเข้าสู่ระบบใหม่");
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      const filename = response.headers.get("content-disposition")?.split("UTF-8''")[1];
      link.download = filename ? decodeURIComponent(filename) : "เอกสารแนบ";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setMessage(error instanceof Error ? error.message : "เปิดเอกสารไม่ได้"); }
  }

  return <LiffView token={token} name={name} tab={tab} message={message} pending={pending} balances={balances} leaves={leaves} announcements={announcements} open={open} submit={submit} cancel={cancel} download={download} />;
}
