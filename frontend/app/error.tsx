"use client";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <main className="p-6">
      <h1 className="mb-3 text-xl font-bold">ทำรายการไม่สำเร็จ</h1>
      <p className="mb-4">ระบบอาจขัดข้องชั่วคราว กรุณาลองใหม่ หากยังพบปัญหาให้ติดต่อผู้ดูแล</p>
      {error.digest && <p className="mb-4 text-sm">รหัสปัญหา: {error.digest}</p>}
      <button onClick={reset} className="rounded bg-[#087747] p-3 text-white">
        ลองใหม่
      </button>
    </main>
  );
}
