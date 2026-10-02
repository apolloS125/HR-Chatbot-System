"use client";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <main className="p-6"><h1 className="mb-3 text-xl font-bold">ทำรายการไม่สำเร็จ</h1><p className="mb-4">ตรวจสอบข้อมูลและการเชื่อมต่อ แล้วลองใหม่</p><button onClick={reset} className="rounded bg-[#087747] p-3 text-white">ลองใหม่</button></main>;
}
