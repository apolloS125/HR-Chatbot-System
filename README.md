# HR Chatbot via LINE Official Account

Employees verify identity using LINE Login, ask policy questions and check leave balances through the LINE OA, and use the LIFF Mini App to request leave, view benefits, history, attached documents, and announcements. HR manages data through the Dashboard.

Application data uses MongoDB, policy vectors use Weaviate, Redis caches read-heavy data, and SeaweedFS stores attachments. PostgreSQL is not part of the runtime stack.

| Service | Responsibility | Data durability |
| --- | --- | --- |
| MongoDB | employees, leave, announcements, LINE sessions, FAQ, file metadata | `mongo_data` volume |
| Weaviate | rebuildable HR policy vector index | `weaviate_data` volume |
| Redis | short-lived dashboard cache | cache only |
| SeaweedFS | uploaded leave documents | `seaweed_data` volume |

`backend/app/tools.py` is an allowlisted Tool Calling registry. Future external sources register a named async handler there; requests cannot select arbitrary URLs or commands.

## Getting Started

1. Create the configuration file and replace all placeholder secrets. The backend refuses to start with default admin credentials or signing keys.

   ```bash
   cp .env.example .env
   ```

2. Start the system

   ```bash
   rtk docker compose up --build
   ```

3. Open the Dashboard at `http://localhost:3000` and log in with `HR_USERNAME` / `HR_PASSWORD`

MongoDB runs as a single-member replica set so leave requests and balance changes can use native transactions. Existing `mongo_data` is preserved. A sample employee, `E001`, is included with initial leave balances. When a new employee is added through the Dashboard, the system automatically creates leave entitlements: 10 days of annual leave, 30 days of sick leave, and 5 days of personal leave.

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

Policy questions search active FAQs and imported policy documents. Answers include the FAQ question or document filename and page as a source. HR can add/edit/disable FAQs, upload text-based PDF or UTF-8 TXT policies, archive documents, rebuild the search index, and preview chatbot answers at `/knowledge`.

Documents are limited to 10 MB, 100 PDF pages, and 200,000 extracted characters. LangChain splits text into 1,000-character chunks with 200-character overlap. Scanned or encrypted PDFs are rejected; OCR is outside this scope. Extracted text and source metadata are stored in MongoDB. The original policy file is not retained.

The chatbot uses LangChain prompt and model chains with OpenAI-compatible Chat Completions. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`; defaults use `https://ai.psu.blue/v1` and `openai/gpt-6-luna`. Keep the key in the ignored `.env` file. Weaviate retrieves relevant policy chunks; the LangChain model summarizes those sources and includes citations. If Weaviate or the provider is unavailable, search falls back to active MongoDB policy text and direct source answers. Archived sources are filtered out even if their vectors remain in the index.

Common email addresses, phone numbers, national ID numbers, and employee IDs are masked before external model calls. This does not detect personal names or all PII; upload company policies, not personnel records.

### Jev guardrails and routing

Set `TYPESAFE_API_KEY` to enable [Jev by TypeSafe](https://docs.typesafe.ai/introduction). Free-text questions are classified as balance, announcements, menu, policy, or other. Confident balance/menu/news requests use ordinary application code; exact commands bypass Jev. Low-confidence, invalid, or failed decisions fall back to policy search. Jev does not approve leave or change employee data. HTTP calls reuse `httpx`; no extra SDK or service is installed.

Before intent routing, Jev screens free-text input using `policy_violation` (Choice), `jailbreak` (Noul), and `severity` (Score). The state contains `user_message` and six `assistant_policy` rules shared with the answer model. Policy answers also screen the question and retrieved reference text together before generation or direct-source fallback, including Dashboard previews. This checks for instructions injected into policy documents.

Jailbreak probability >= 0.5 or severity >= 2 (Serious) blocks the request. Severity confidence < 0.8, missing credentials, timeout, HTTP errors, or malformed results stop the AI path with a temporary-unavailable reply. Exact HR commands still work. The supplied Choice has no “no violation” option, so it labels a policy and does not independently block safe messages. These thresholds need evaluation on real HR traffic; model screening cannot guarantee detection of every injection.

LIFF must be used with a LINE account already linked to the employee. If it is not linked, the system will instruct the employee to contact HR.

## HR operations

- Bootstrap Dashboard login uses `HR_USERNAME` / `HR_PASSWORD`. An Admin can set an individual password (at least 10 characters) on an HR/Admin employee record. Those users log in with their employee code. Employee roles cannot enter the Dashboard.
- HR manages ordinary employees, policies, holidays, announcements, and leave decisions. Only Admin can manage HR/Admin records, roles, passwords, and view the audit history. Password hashes never appear in API responses.
- Employee records can be edited, deactivated, and reactivated. Deactivation blocks LINE/LIFF and Dashboard access and preserves leave history and attachments. The legacy DELETE endpoint also deactivates instead of deleting.
- HR can adjust remaining balances and annual entitlements separately. On the first balance read or leave operation in a new year, balances reset to annual entitlements. Unused balances do not carry over automatically. Legacy records without a year keep their current balances and are assigned the current year.
- Leave counts Monday–Friday minus configured company holidays. Half-day requests must cover one workday. Requests must stay within the current year. Holiday changes affect new requests; existing requests retain their saved day count.
- Pending requests reserve available entitlement when accepting another request. Overlapping pending/approved leave is rejected; opposite half-days on one date are allowed. LIFF submits have an idempotency key, and employees can cancel their own pending requests. Approved cancellation/refunds require HR review and are not automated.
- Approval and deduction use one MongoDB transaction. LINE notification failures do not undo the decision. HR can retry a failed notification in the Dashboard.
- Linked HR/Admin accounts can send `คำขอลารออนุมัติ`, `อนุมัติ <LR-id>`, or `ปฏิเสธ <LR-id>` in LINE. Ordinary employees cannot use these commands.
- Leave attachments store a file ID, not a session URL. Employees download their own documents with a current LIFF token; HR downloads through the authenticated Dashboard. Older generated attachment URLs are read as file IDs without exposing their embedded token.
- Announcements keep recipient batches, delivery state, and stable LINE retry keys. Retry sends unfinished batches from the same announcement. After the safe retry window expires, HR must check delivery manually rather than risk duplicates.

## Backend Testing

From `backend/`:

```bash
rtk uv run pytest
```

To include transaction, concurrent approval, role, file ownership, and delivery-retry tests, point `TEST_MONGODB_URL` at a disposable replica set:

```bash
rtk proxy env TEST_MONGODB_URL='mongodb://localhost:27017/?replicaSet=rs0&directConnection=true' uv run pytest
```

Integration tests create randomly named `hr_test_*` databases and drop only those databases. Without this variable, integration tests are skipped. Frontend type checking and production builds run with:

```bash
rtk proxy bunx tsc --noEmit
rtk proxy bun run build
```

Use HTTPS for both public domains when configuring LINE. Rebuild the frontend after changing `NEXT_PUBLIC_LIFF_ID` or `PUBLIC_BACKEND_URL`; these values are passed into the Docker build.

The API documentation and schema can be viewed at `http://localhost:8000/docs`

## Current Scope

- The Dashboard forwards individual Basic Auth credentials to backend role checks. The admin API key remains available for trusted server integrations. Company SSO, account recovery, and login rate limiting remain future production work.
- Semantic Cache and Langfuse are intentionally deferred. No Payroll integration, model fine-tuning, or additional database is introduced.
- Uploaded documents are stored in SeaweedFS; MongoDB stores only file metadata and ownership. Download requests are authorized through the backend.
- Weaviate is an index. Rebuild it from MongoDB FAQ/policy data if it is lost or changed.


The original proposal PDFs describe PostgreSQL/pgvector and a larger AI scope. The runtime architecture above is the current implementation; keep those historical files unchanged and use this scope when updating the presentation and report.
