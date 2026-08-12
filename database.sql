CREATE TABLE IF NOT EXISTS employees (
  id bigserial PRIMARY KEY,
  employee_code varchar(32) NOT NULL UNIQUE,
  name varchar(120) NOT NULL,
  work_email varchar(255) NOT NULL UNIQUE,
  role varchar(16) NOT NULL DEFAULT 'employee' CHECK (role IN ('employee', 'hr', 'admin')),
  active boolean NOT NULL DEFAULT true,
  line_user_id varchar(64) UNIQUE,
  line_linked_at timestamptz,
  link_code_hash char(64),
  link_code_expires_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS line_oauth_sessions (
  state varchar(128) PRIMARY KEY,
  employee_id bigint NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  nonce varchar(128) NOT NULL,
  code_verifier varchar(128) NOT NULL,
  expires_at timestamptz NOT NULL
);

CREATE TABLE IF NOT EXISTS leave_balances (
  employee_id bigint NOT NULL REFERENCES employees(id) ON DELETE CASCADE,
  leave_type varchar(24) NOT NULL CHECK (leave_type IN ('vacation', 'sick', 'personal')),
  remaining_days numeric(5,1) NOT NULL CHECK (remaining_days >= 0),
  PRIMARY KEY (employee_id, leave_type)
);

CREATE TABLE IF NOT EXISTS leave_requests (
  id bigserial PRIMARY KEY,
  employee_id bigint NOT NULL REFERENCES employees(id),
  leave_type varchar(24) NOT NULL CHECK (leave_type IN ('vacation', 'sick', 'personal')),
  start_date date NOT NULL,
  end_date date NOT NULL,
  days numeric(5,1) NOT NULL CHECK (days > 0),
  reason text NOT NULL,
  attachment_url text,
  source_event_id varchar(128) UNIQUE,
  status varchar(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  decided_by varchar(120),
  decided_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (end_date >= start_date)
);

CREATE TABLE IF NOT EXISTS faqs (
  id bigserial PRIMARY KEY,
  keyword varchar(120) NOT NULL,
  question text NOT NULL,
  answer text NOT NULL,
  active boolean NOT NULL DEFAULT true
);

CREATE TABLE IF NOT EXISTS announcements (
  id bigserial PRIMARY KEY,
  title varchar(200) NOT NULL,
  body text NOT NULL,
  published_at timestamptz NOT NULL DEFAULT now()
);

INSERT INTO employees (employee_code, name, work_email, role)
VALUES ('E001', 'พนักงานตัวอย่าง', 'employee@example.com', 'employee')
ON CONFLICT (employee_code) DO NOTHING;

INSERT INTO leave_balances (employee_id, leave_type, remaining_days)
SELECT id, leave_type, days
FROM employees
CROSS JOIN (VALUES ('vacation', 10), ('sick', 30), ('personal', 5)) AS defaults(leave_type, days)
WHERE employee_code = 'E001'
ON CONFLICT DO NOTHING;

INSERT INTO faqs (keyword, question, answer)
SELECT 'เวลาทำงาน', 'บริษัททำงานกี่โมง', 'เวลาทำงานปกติคือ 09:00–18:00 น. วันจันทร์ถึงวันศุกร์'
WHERE NOT EXISTS (SELECT 1 FROM faqs WHERE keyword = 'เวลาทำงาน');

INSERT INTO announcements (title, body)
SELECT 'ยินดีต้อนรับ', 'เริ่มทดลองใช้งาน HR Chatbot ได้แล้ว'
WHERE NOT EXISTS (SELECT 1 FROM announcements WHERE title = 'ยินดีต้อนรับ');
