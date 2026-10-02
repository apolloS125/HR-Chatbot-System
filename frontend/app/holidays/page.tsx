import { deleteHoliday, saveHoliday } from "../actions";
import { formatDate, get } from "../../lib/api";

export default async function HolidaysPage() {
  const holidays = await get<{ id: string; name: string }[]>("/api/admin/holidays");
  return <main className="mx-auto max-w-3xl p-6">
    <h1 className="mb-2 text-2xl font-bold">วันหยุดบริษัท</h1>
    <p className="mb-6 text-sm text-[#6d7a72]">ใช้คำนวณคำขอลาใหม่ คำขอเดิมคงจำนวนวันที่บันทึกไว้</p>
    <form action={saveHoliday} className="mb-6 flex flex-wrap gap-3 rounded-xl bg-white p-4">
      <label>วันที่<input className="ml-2 rounded border p-2" name="date" type="date" required /></label>
      <label>ชื่อวันหยุด<input className="ml-2 rounded border p-2" name="name" maxLength={120} required /></label>
      <button className="rounded bg-[#087747] p-2 text-white">บันทึก</button>
    </form>
    <ul className="grid gap-2">{holidays.map((item) => <li className="flex items-center justify-between rounded-xl bg-white p-4" key={item.id}><span>{formatDate(item.id)} · {item.name}</span><form action={deleteHoliday}><input type="hidden" name="id" value={item.id} /><button className="text-red-700">ลบ</button></form></li>)}</ul>
    {!holidays.length && <p>ยังไม่มีวันหยุดบริษัท</p>}
  </main>;
}
