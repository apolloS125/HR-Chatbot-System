# HR Chatbot via LINE Official Account

MVP: employees verify identity using LINE Login, ask policy questions and check leave balances through the LINE OA, and use the LIFF Mini App to request leave, view benefits, history, attached documents, and announcements. HR manages data through the Dashboard.

Application data uses MongoDB, policy vectors use Weaviate, Redis caches read-heavy data, and SeaweedFS stores attachments. PostgreSQL is not part of the runtime stack.

| Service | Responsibility | Data durability |
| --- | --- | --- |
| MongoDB | employees, leave, announcements, LINE sessions, FAQ, file metadata | `mongo_data` volume |
| Weaviate | rebuildable HR policy vector index | `weaviate_data` volume |
| Redis | short-lived dashboard cache | cache only |
| SeaweedFS | uploaded leave documents | `seaweed_data` volume |

`backend/app/tools.py` is an allowlisted Tool Calling registry. Future external sources register a named async handler there; requests cannot select arbitrary URLs or commands.

## Getting Started

1. Create the configuration file and replace all default values

   ```bash
   cp .env.example .env
   ```

2. Start the system

   ```bash
   rtk docker compose up --build
   ```

3. Open the Dashboard at `http://localhost:3000` and log in with `HR_USERNAME` / `HR_PASSWORD`

A sample employee, `E001`, is included with initial leave balances. When a new employee is added through the Dashboard, the system automatically creates leave entitlements: 10 days of annual leave, 30 days of sick leave, and 5 days of personal leave.

The default compose stack starts MongoDB, Redis, Weaviate, SeaweedFS, backend, and frontend. Do not add PostgreSQL settings; use `MONGODB_URL`, `MONGODB_DATABASE`, `REDIS_URL`, `WEAVIATE_URL`, and `SEAWEED_MASTER_URL` from `.env.example`.

## LINE Setup

Create a `LINE Login channel` and a `Messaging API channel` under the same Provider, then configure the following:

- LINE Login callback URL: `https://<backend-domain>/auth/line/callback`
- Messaging API webhook URL: `https://<backend-domain>/line/webhook`
- Put the Channel ID, Secret, and Access token in `.env`
- Set `PUBLIC_BASE_URL` to the HTTPS URL of the backend that LINE can access
- Create a LIFF app in the LINE Login channel, set the Endpoint URL to `https://<frontend-domain>/liff`, and then set `NEXT_PUBLIC_LIFF_ID`
- Set `PUBLIC_BACKEND_URL` to the HTTPS URL of the backend that the browser can access, and `LIFF_ORIGIN` to the frontend URL
- Set `LIFF_SESSION_SECRET` to a long random value and do not use the default

### Open LIFF from the LINE chat

Create a Rich Menu in the LINE Official Account Manager and add a **HR Self-service** button of type `URI`:

```text
https://liff.line.me/<LIFF_ID>
```

When an employee taps the button, the system opens LIFF in LINE and verifies identity using the LINE account linked by HR. Within LIFF, employees can request leave, view remaining leave balances, leave history, attach documents, and view announcements.

Use this URL instead of opening `https://<frontend-domain>/liff` directly so the LIFF SDK can receive a complete LINE ID token.

From the Dashboard, click **Issue LINE link** for the employee, send the generated link to the employee, and ask them to open it within 30 minutes. The link is single-use. After successful LINE Login, the `LINE user ID` is bound to the employee code, and the chatbot only allows employees whose status is still `Active`.

## Chat Commands

```text
เมนู
วันลาคงเหลือ
ประกาศ
ขอลา พักร้อน 2026-08-20 2026-08-21 ธุระครอบครัว
```

Policy questions are searched in `faqs` first. If `OPENAI_API_KEY` is set, the system uses the LLM to summarize answers only from the matching FAQs; if the key is not set, it returns the FAQ text directly.

LIFF must be used with a LINE account already linked to the employee. If it is not linked, the system will instruct the employee to contact HR.

## Backend Testing

```bash
rtk uv run pytest
```

The API documentation and schema can be viewed at `http://localhost:8000/docs`

## MVP Scope

- The Dashboard uses HTTP Basic Auth, and the backend uses an admin API key. This is suitable only for internal prototypes; before production, it should be replaced with Company SSO.
- Leave is counted only Monday to Friday; company holidays are not deducted yet.
- Uploaded documents are stored in SeaweedFS; MongoDB stores only file metadata and ownership. Download requests are authorized through the backend.
- Weaviate is an index. Rebuild it from MongoDB FAQ/policy data if it is lost or changed.
