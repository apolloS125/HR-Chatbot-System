import { adminHeaders } from "../../../lib/api";

export async function GET(_: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const backend = process.env.BACKEND_URL ?? "http://localhost:8000";
  const path = `/api/admin/attachments/${encodeURIComponent(id)}`;
  const response = await fetch(`${backend}${path}`, {
    headers: await adminHeaders(),
    cache: "no-store",
  });
  if (!response.ok) return new Response("เปิดเอกสารไม่สำเร็จ", { status: response.status });
  return new Response(response.body, {
    headers: {
      "Content-Type": response.headers.get("content-type") ?? "application/octet-stream",
      "Content-Disposition": response.headers.get("content-disposition") ?? "attachment",
      "Cache-Control": "private, no-store",
    },
  });
}
