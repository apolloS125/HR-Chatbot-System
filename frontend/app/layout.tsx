import type { Metadata } from "next";
import { Sidebar } from "../components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "HR Chatbot Dashboard",
  description: "จัดการพนักงานและคำขอลา",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="th" className="bg-[#123c2a]">
      <body className="m-0 bg-[#f4f7f5] text-[#17241d] antialiased">
        <div className="min-h-dvh md:grid md:grid-cols-[248px_minmax(0,1fr)]">
          <Sidebar />
          <div className="min-w-0">{children}</div>
        </div>
      </body>
    </html>
  );
}
