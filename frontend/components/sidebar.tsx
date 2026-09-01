"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", icon: "⌂", label: "ภาพรวม" },
  { href: "/employees", icon: "♙", label: "พนักงาน" },
  { href: "/leaves", icon: "✓", label: "คำขอลา" },
  { href: "/announcements", icon: "◫", label: "ประกาศ" },
];

export function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 z-50 flex bg-[#123c2a] px-4 py-2.5 text-[#d9e8df] shadow-lg md:h-dvh md:flex-col md:px-[18px] md:py-6 md:shadow-none">
      <div className="flex items-center gap-3 pr-4 md:px-2 md:pb-7 md:pr-2">
        <span className="grid size-9 shrink-0 place-items-center rounded-[11px] bg-[#b9f0cf] text-xs font-black tracking-wider text-[#123c2a] md:size-10">
          HR
        </span>
        <div className="hidden md:block">
          <b className="block text-sm text-white">People Hub</b>
          <small className="mt-0.5 block text-[11px] text-[#9bb5a5]">HR Chatbot</small>
        </div>
      </div>
      <nav aria-label="เมนูหลัก" className="flex min-w-0 flex-1 gap-1 overflow-x-auto md:grid md:flex-none md:gap-1.5">
        {items.map((item) => (
          <Link
            href={item.href}
            key={item.href}
            className={`flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-[11px] px-3 text-xs font-semibold transition md:min-h-11 md:justify-start md:gap-3 md:text-sm ${
              pathname === item.href
                ? "bg-white/10 text-white shadow-[inset_0_-2px_#70d99c] md:shadow-[inset_3px_0_#70d99c]"
                : "text-[#b8cbbf] hover:bg-white/5 hover:text-white"
            }`}
          >
            <span aria-hidden="true" className="w-4 text-center text-base md:w-5">{item.icon}</span>
            {item.label}
          </Link>
        ))}
      </nav>
      <div className="mt-auto hidden items-center gap-2 rounded-xl border border-white/10 p-3 text-xs text-[#a7bbae] md:flex">
        <span className="size-2 rounded-full bg-[#62da93] shadow-[0_0_0_4px_#62da9320]" />
        ระบบพร้อมใช้งาน
      </div>
    </aside>
  );
}
