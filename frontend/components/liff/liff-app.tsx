"use client";

import liff from "@line/liff";
import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";

import { type Announcement, type Balance, type Leave, type LiffTab, LiffView } from "./liff-view";

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
  const [loading, setLoading] = useState(false);
  const [messageType, setMessageType] = useState<"info" | "success" | "error">("info");
  const loadVersion = useRef(0);
  const busy = useRef(false);
  const request = useRef({ key: "", fingerprint: "", attachment_id: "" });

  useEffect(() => {
    let disposed = false;

    async function initializeLiff() {
      try {
        const liffId = process.env.NEXT_PUBLIC_LIFF_ID;
        if (!liffId) {
          throw new Error("ยังไม่ได้ตั้งค่า NEXT_PUBLIC_LIFF_ID");
        }

        await liff.init({ liffId });
        if (disposed) {
          return;
        }

        if (!liff.isLoggedIn()) {
          liff.login();
          return;
        }

        const idToken = liff.getIDToken();
        if (!idToken) {
          throw new Error("ไม่พบ LINE ID token");
        }

        const response = await fetch(`${backend}/api/liff/session`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ id_token: idToken }),
        });
        const data = await response.json();
        if (!response.ok) {
          throw new Error(data.detail ?? "ยืนยันตัวตนไม่สำเร็จ");
        }

        if (!disposed) {
          setToken(data.token);
          setName(data.name);
          setMessage("");
        }
      } catch (error) {
        if (!disposed) {
          setMessageType("error");
          setMessage(error instanceof Error ? error.message : "เชื่อมต่อ LINE ไม่สำเร็จ");
        }
      }
    }

    void initializeLiff();
    return () => {
      disposed = true;
    };
  }, []);

  async function api<T>(path: string, init?: RequestInit): Promise<T> {
    const response = await fetch(`${backend}/api/liff${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${token}`,
        ...init?.headers,
      },
    });
    const data = await response.json();

    if (response.status === 401) {
      throw new Error("เซสชันหมดอายุ กรุณาปิดแล้วเปิดแอปใหม่");
    }
    if (!response.ok) {
      const detail = Array.isArray(data.detail)
        ? data.detail.map((item: { msg: string }) => item.msg).join("; ")
        : data.detail;
      throw new Error(detail ?? "ทำรายการไม่สำเร็จ");
    }

    return data as T;
  }

  async function open(next: LiffTab) {
    const version = ++loadVersion.current;
    setTab(next);
    if (!token) {
      return;
    }

    setMessage("");
    setMessageType("info");
    setLoading(next !== "leave");
    try {
      if (next === "balance") {
        const data = await api<Balance[]>("/balances");
        if (version === loadVersion.current) {
          setBalances(data);
        }
      }
      if (next === "history") {
        const data = await api<Leave[]>("/leaves");
        if (version === loadVersion.current) {
          setLeaves(data);
        }
      }
      if (next === "news") {
        const data = await api<Announcement[]>("/announcements");
        if (version === loadVersion.current) {
          setAnnouncements(data);
        }
      }
    } catch (error) {
      if (version === loadVersion.current) {
        setMessageType("error");
        setMessage(error instanceof Error ? error.message : "โหลดข้อมูลไม่สำเร็จ");
      }
    } finally {
      if (version === loadVersion.current) {
        setLoading(false);
      }
    }
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy.current || !token) {
      return;
    }

    busy.current = true;
    setPending(true);
    setMessage("");
    const element = event.currentTarget;
    const form = new FormData(element);
    const file = form.get("attachment");
    const payload = {
      leave_type: form.get("leave_type"),
      start_date: form.get("start_date"),
      end_date: form.get("end_date"),
      reason: form.get("reason"),
      half_day: form.get("half_day") || null,
    };
    const attachmentFingerprint =
      file instanceof File ? [file.name, file.size, file.lastModified] : null;
    const fingerprint = JSON.stringify([payload, attachmentFingerprint]);

    if (request.current.fingerprint !== fingerprint) {
      request.current = { key: crypto.randomUUID(), fingerprint, attachment_id: "" };
    }

    try {
      if (file instanceof File && file.size && !request.current.attachment_id) {
        if (file.size > 10 * 1024 * 1024) {
          throw new Error("ไฟล์ต้องไม่เกิน 10 MB");
        }

        const attachment = new FormData();
        attachment.append("file", file);
        const result = await api<{ id: string }>("/attachments", {
          method: "POST",
          body: attachment,
        });
        request.current.attachment_id = result.id;
      }

      const result = await api<{ id: string; days: number }>("/leaves", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...payload,
          request_key: request.current.key,
          attachment_id: request.current.attachment_id || null,
        }),
      });
      element.reset();
      request.current = { key: "", fingerprint: "", attachment_id: "" };
      setMessageType("success");
      setMessage(`ส่งคำขอลา #${result.id} แล้ว (${result.days} วัน)`);
    } catch (error) {
      setMessageType("error");
      setMessage(error instanceof Error ? error.message : "ส่งคำขอลาไม่สำเร็จ");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function cancel(id: string) {
    if (busy.current) {
      return;
    }
    if (!window.confirm("ยกเลิกคำขอลานี้ใช่หรือไม่?")) {
      return;
    }

    busy.current = true;
    setPending(true);
    try {
      await api(`/leaves/${id}/cancel`, { method: "POST" });
      setLeaves(await api<Leave[]>("/leaves"));
      setMessageType("success");
      setMessage("ยกเลิกคำขอแล้ว");
    } catch (error) {
      setMessageType("error");
      setMessage(error instanceof Error ? error.message : "ยกเลิกไม่สำเร็จ");
    } finally {
      busy.current = false;
      setPending(false);
    }
  }

  async function download(id: string) {
    try {
      const response = await fetch(`${backend}/api/liff/attachments/${id}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        throw new Error("เปิดเอกสารไม่ได้ กรุณาลองเข้าสู่ระบบใหม่");
      }

      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = url;
      const filename = response.headers.get("content-disposition")?.split("UTF-8''")[1];
      link.download = filename ? decodeURIComponent(filename) : "เอกสารแนบ";
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) {
      setMessageType("error");
      setMessage(error instanceof Error ? error.message : "เปิดเอกสารไม่ได้");
    }
  }

  return (
    <LiffView
      token={token}
      name={name}
      tab={tab}
      message={message}
      pending={pending}
      loading={loading}
      messageType={messageType}
      retry={() => token ? void open(tab) : window.location.reload()}
      balances={balances}
      leaves={leaves}
      announcements={announcements}
      open={open}
      submit={submit}
      cancel={cancel}
      download={download}
    />
  );
}
