# HR Chatbot via LINE Official Account

MVP ที่รันได้จริงตามข้อเสนอโครงงาน: พนักงานยืนยันตัวด้วย LINE Login, ใช้แชทดูวันลาคงเหลือ/ประกาศ/FAQ/ส่งคำขอลา และ HR ออกลิงก์เชื่อมบัญชีกับอนุมัติการลาผ่าน Dashboard

## เริ่มใช้งาน

1. สร้างไฟล์ตั้งค่าและเปลี่ยนรหัสผ่านทุกค่า

   ```bash
   cp .env.example .env
   ```

2. รันระบบ

   ```bash
   docker compose up --build
   ```

3. เปิด Dashboard ที่ `http://localhost:3000` และล็อกอินด้วย `HR_USERNAME` / `HR_PASSWORD`

ข้อมูลตัวอย่างมีพนักงาน `E001` พร้อมวันลาเริ่มต้น เมื่อเพิ่มพนักงานผ่าน Dashboard ระบบจะสร้างสิทธิ์วันลา พักร้อน 10 วัน, ลาป่วย 30 วัน และลากิจ 5 วันให้อัตโนมัติ

## ตั้งค่า LINE

สร้าง `LINE Login channel` และ `Messaging API channel` ภายใต้ Provider เดียวกัน แล้วตั้งค่าดังนี้

- LINE Login callback URL: `https://<โดเมน-backend>/auth/line/callback`
- Messaging API webhook URL: `https://<โดเมน-backend>/line/webhook`
- ใส่ Channel ID/Secret/Access token ลง `.env`
- ตั้ง `PUBLIC_BASE_URL` เป็น URL HTTPS ของ backend ที่ LINE เข้าถึงได้

จาก Dashboard กด **ออกลิงก์ LINE** ที่พนักงาน ส่งลิงก์นั้นให้เจ้าตัว และให้เปิดภายใน 30 นาที ลิงก์ใช้ได้ครั้งเดียว หลัง LINE Login สำเร็จ `LINE user ID` จะถูกผูกกับรหัสพนักงาน และ chatbot จะอนุญาตเฉพาะพนักงานที่ยัง Active

## คำสั่งในแชท

```text
เมนู
วันลาคงเหลือ
ประกาศ
ขอลา พักร้อน 2026-08-20 2026-08-21 ธุระครอบครัว
```

คำถามอื่นจะค้นจากตาราง `faqs` ก่อน ระบบตั้งใจยังไม่เรียก LLM/RAG จนกว่าจะมีเอกสารนโยบายบริษัทและ API key จริง เพื่อไม่ให้ตอบข้อมูล HR ที่แต่งขึ้นเอง

## ทดสอบ backend

```bash
cd backend
uv sync
uv run pytest
```

API สำหรับทดสอบและดู schema อยู่ที่ `http://localhost:8000/docs`

## ขอบเขต MVP

- Dashboard ใช้ HTTP Basic Auth และ backend ใช้ admin API key เหมาะกับต้นแบบภายในเท่านั้น ก่อน production ควรเปลี่ยนเป็น Company SSO
- วันลานับเฉพาะจันทร์–ศุกร์ ยังไม่หักวันหยุดบริษัท
- ยังไม่รวมไฟล์แนบ, Rich Menu/Flex Message, push notification, RAG และ Langfuse
