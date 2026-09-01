"use client";

import { FormEvent, useEffect, useState } from "react";
import { type Announcement, type Balance, type Leave, type LiffTab, LiffView } from "./liff-view";

type Liff = { init: (value: { liffId: string }) => Promise<void>; getIDToken: () => string | null; isLoggedIn: () => boolean; login: () => void };
declare global { interface Window { liff?: Liff } }

const backend = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

export function LiffApp() {
  const [token, setToken] = useState(""); const [name, setName] = useState(""); const [tab, setTab] = useState<LiffTab>("leave");
  const [balances, setBalances] = useState<Balance[]>([]); const [leaves, setLeaves] = useState<Leave[]>([]); const [announcements, setAnnouncements] = useState<Announcement[]>([]); const [message, setMessage] = useState("กำลังเชื่อมต่อ LINE...");
  useEffect(() => { const script = document.createElement("script"); script.src = "https://static.line-scdn.net/liff/edge/2/sdk.js"; script.onload = async () => { const id = process.env.NEXT_PUBLIC_LIFF_ID; if (!id || !window.liff) return setMessage("ยังไม่ได้ตั้งค่า NEXT_PUBLIC_LIFF_ID"); await window.liff.init({ liffId: id }); if (!window.liff.isLoggedIn()) return window.liff.login(); const idToken = window.liff.getIDToken(); if (!idToken) return setMessage("ไม่พบ LINE ID token"); const response = await fetch(`${backend}/api/liff/session`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id_token: idToken }) }); const data = await response.json(); if (!response.ok) return setMessage(data.detail ?? "ยืนยันตัวตนไม่สำเร็จ"); setToken(data.token); setName(data.name); setMessage(""); }; script.onerror = () => setMessage("โหลด LIFF SDK ไม่สำเร็จ"); document.head.append(script); return () => script.remove(); }, []);
  async function api<T>(path: string, init?: RequestInit): Promise<T> { const response = await fetch(`${backend}/api/liff${path}`, { ...init, headers: { Authorization: `Bearer ${token}`, ...init?.headers } }); const data = await response.json(); if (!response.ok) throw new Error(data.detail ?? "ทำรายการไม่สำเร็จ"); return data as T; }
  async function open(next: LiffTab) { setTab(next); if (!token) return; try { if (next === "balance") setBalances(await api<Balance[]>("/balances")); if (next === "history") setLeaves(await api<Leave[]>("/leaves")); if (next === "news") setAnnouncements(await api<Announcement[]>("/announcements")); } catch (error) { setMessage(error instanceof Error ? error.message : "โหลดข้อมูลไม่สำเร็จ"); } }
  async function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); const form = new FormData(event.currentTarget); try { let attachment_url: string | undefined; const file = form.get("attachment"); if (file instanceof File && file.size) { const attachment = new FormData(); attachment.append("file", file); attachment_url = (await api<{ url: string }>("/attachments", { method: "POST", body: attachment })).url; } const result = await api<{ id: string; days: number }>("/leaves", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ leave_type: form.get("leave_type"), start_date: form.get("start_date"), end_date: form.get("end_date"), reason: form.get("reason"), attachment_url }) }); event.currentTarget.reset(); setMessage(`ส่งคำขอลา #${result.id} แล้ว (${result.days} วัน)`); } catch (error) { setMessage(error instanceof Error ? error.message : "ส่งคำขอลาไม่สำเร็จ"); } }
  return <LiffView token={token} name={name} tab={tab} message={message} balances={balances} leaves={leaves} announcements={announcements} open={open} submit={submit} />;
}
