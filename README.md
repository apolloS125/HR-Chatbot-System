# HR Chatbot via LINE Official Account

Employees verify identity using LINE Login, ask policy questions and check leave balances through the LINE OA, and use the LIFF Mini App to request leave, view benefits, history, attached documents, and announcements. HR manages data through the Dashboard.

Application data uses MongoDB, policy vectors use Weaviate, Redis caches read-heavy data, and SeaweedFS stores attachments. PostgreSQL is not part of the runtime stack.

| Service | Responsibility | Data durability |
| --- | --- | --- |
| MongoDB | employees, leave, announcements, LINE sessions, FAQ, file metadata | `mongo_data` volume |
| Weaviate | rebuildable HR policy vector index | `weaviate_data` volume |
| Redis | dashboard sessions, rate limits, event deduplication, policy/summary caches | ephemeral; restart signs users out |
| SeaweedFS | uploaded leave documents | `seaweed_data` volume |

`backend/app/tools.py` is an allowlisted Tool Calling registry. Future external sources register a named async handler there; requests cannot select arbitrary URLs or commands.

## Getting Started

1. Create the configuration file and replace all placeholder secrets. Use independently generated random values for `ADMIN_API_KEY` and `LIFF_SESSION_SECRET` (at least 32 characters), `HR_PASSWORD` (at least 12 characters), and `WEAVIATE_API_KEY`. The backend rejects short, repetitive, placeholder, or shared signing secrets. Generate each value separately with `openssl rand -hex 32`. For local HTTP only, set `SESSION_COOKIE_SECURE=false`; keep it `true` behind production HTTPS.

   ```bash
   cp .env.example .env
   ```

2. Start the system

   ```bash
   docker compose up --build
   ```

The backend port binds to `127.0.0.1:8000`; expose the required LINE/LIFF routes through an HTTPS reverse proxy. Weaviate requires an API key and has no published host port. Services have health checks and restart policies. Frontend receives public configuration, its backend URL, and the cookie security flag; backend secrets stay in backend services.

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

When `NEXT_PUBLIC_LIFF_ID` is configured, `เมนู` and `ขอลา` include a Quick Reply button opening the LIFF leave form. The existing typed leave command remains supported.

LINE webhook verifies the signature and schedules bounded, concurrent background processing after sending HTTP 200. A failed event does not fail the batch. Redis suppresses duplicate completed events for 24 hours; leave submissions also keep their database idempotency keys. Background tasks are in-process: a process crash after acknowledgement can lose pending work. Use a durable inbox/worker if crash recovery is required.

Policy questions search active FAQs and imported policy documents. Answers include the FAQ question or document filename and page as a source. HR can add/edit/disable FAQs, upload text-based PDF or UTF-8 TXT policies, archive documents, rebuild the search index, and preview chatbot answers at `/knowledge`.

Documents are limited to 10 MB, 100 PDF pages, and 200,000 extracted characters. LangChain splits text into 1,000-character chunks with 200-character overlap. Scanned or encrypted PDFs are rejected; OCR is outside this scope. Extracted text and source metadata are stored in MongoDB. The original policy file is not retained.

The chatbot uses LangChain prompt and model chains with OpenAI-compatible Chat Completions. Set `OPENAI_API_KEY`, `OPENAI_BASE_URL`, and `OPENAI_MODEL`; defaults use `https://ai.psu.blue/v1` and `openai/gpt-6-luna`. Keep the key in the ignored `.env` file. Weaviate retrieves relevant policy chunks; the LangChain model summarizes those sources and includes citations. If Weaviate is unavailable, search uses at most 100 active MongoDB chunks. Without the chat key, or when the provider fails, the bot returns a short service-unavailable message with source titles instead of dumping raw documents. Normal retrieval loads FAQ keywords and the matched documents, rather than the whole document library. Archived sources are filtered out even if their vectors remain in the index.

Common email addresses, phone numbers, national ID numbers, and employee IDs are masked before external model calls. Titled Thai/English names and names in labeled fields are also masked. Unmarked names and all forms of PII are not covered; upload company policies, not personnel records.

### Jev guardrails and routing

Set `TYPESAFE_API_KEY` to enable [Jev by TypeSafe](https://docs.typesafe.ai/introduction). Free-text questions are classified as balance, announcements, menu, policy, or other. Confident balance/menu/news requests use ordinary application code; exact commands bypass Jev. Low-confidence, invalid, or failed decisions fall back to policy search. Jev does not approve leave or change employee data. Jev HTTP calls use the existing `httpx` client library.

Before intent routing, Jev screens free-text input using `policy_violation` (Choice), `jailbreak` (Noul), and `severity` (Score). The state contains `user_message` and six `assistant_policy` rules shared with the answer model. Policy answers also screen the question and retrieved reference text together before generation or cache reuse, including Dashboard previews. This checks for instructions injected into policy documents.

Jailbreak probability >= 0.5 or severity >= 2 (Serious) blocks the request. Severity confidence < 0.8, missing credentials, timeout, HTTP errors, or malformed results stop the AI path with a temporary-unavailable reply. Exact HR commands still work. The supplied Choice has no “no violation” option, so it labels a policy and does not independently block safe messages. These thresholds need evaluation on real HR traffic; model screening cannot guarantee detection of every injection.

LIFF must be used with a LINE account already linked to the employee. If it is not linked, the system will instruct the employee to contact HR.

## HR operations

- Dashboard login creates a one-hour opaque Redis session in an HttpOnly, SameSite=Strict cookie. Logout revokes the server session and clears the cookie. Every backend request rechecks active status, role, and password version; frontend proxy only checks cookie presence. Redis atomically limits failed/concurrent authentication to 10 attempts per account and 60 per backend peer over 5 minutes, with HTTP 429 and Retry-After. Forwarded IP headers are not trusted by application code.
- Bootstrap Dashboard login uses `HR_USERNAME` / `HR_PASSWORD`. An Admin can set an individual password (at least 10 characters) on an HR/Admin employee record. Those users log in with their employee code. Employee roles cannot enter the Dashboard.
- HR manages ordinary employees, policies, holidays, announcements, and leave decisions. Only Admin can manage HR/Admin records, roles, passwords, and view the audit history. Password hashes never appear in API responses.
- Employee records can be edited, deactivated, and reactivated. DELETE and the status control both set `active=false` inside a transaction with an audit entry; neither deletes employee records, audit history, leave history, or SeaweedFS attachments. There is no permanent employee purge endpoint. Deactivation blocks LINE/LIFF and Dashboard access and preserves leave history and attachments. Employee codes and email addresses remain reserved after deactivation.
- HR can adjust remaining balances and annual entitlements separately. On the first balance read or leave operation in a new year, balances reset to annual entitlements. Unused balances do not carry over automatically. Legacy records without a year keep their current balances and are assigned the current year.
- Leave counts Monday–Friday minus configured company holidays. Half-day requests must cover one workday. Requests must stay within the current year. Holiday changes affect new requests; existing requests retain their saved day count.
- Pending requests reserve available entitlement when accepting another request. Overlapping pending/approved leave is rejected; opposite half-days on one date are allowed. LIFF submits have an idempotency key, and employees can cancel their own pending requests. Approved cancellation/refunds require HR review and are not automated.
- Approval and deduction use one MongoDB transaction. LINE notification failures do not undo the decision. HR can retry a failed notification in the Dashboard.
- Linked HR/Admin accounts can send `คำขอลารออนุมัติ`, `อนุมัติ <LR-id>`, or `ปฏิเสธ <LR-id>` in LINE. Ordinary employees cannot use these commands.
- Leave list APIs accept bounded `limit` and `offset` values. Dashboard pages load 100 entries at a time; LIFF history loads 50 with a load-more button. Dashboard name/status filters apply to the displayed page.
- Leave attachments store a file ID, not a session URL. Employees download their own documents with a current LIFF token; HR downloads through the authenticated Dashboard. Older generated attachment URLs are read as file IDs without exposing their embedded token.
- Announcements keep recipient batches, delivery state, and stable LINE retry keys. Retry sends unfinished batches from the same announcement. After the safe retry window expires, HR must check delivery manually rather than risk duplicates.

## Backend Testing

GitHub Actions runs backend lint/format checks and tests against disposable MongoDB/Redis, plus frontend format checks, tests, type checking, and a production build. The workflow is in [checks.yml](.github/workflows/checks.yml).

From `backend/`:

```bash
uv run pytest
uv run ruff check app tests
uv run ruff format --check app tests
```

To include integration tests, start the disposable MongoDB replica set and Redis from the repository root, then run tests from `backend/`:

```bash
docker compose -p hr-tests -f compose.test.yaml up -d --wait
cd backend
TEST_MONGODB_URL='mongodb://localhost:27018/?replicaSet=rs0&directConnection=true' TEST_REDIS_URL='redis://localhost:6380/15' uv run pytest
```

Integration tests create randomly named `hr_test_*` databases and drop only those databases. The dedicated test Redis database is flushed between scenarios; never point `TEST_REDIS_URL` at production Redis. Without both test URLs, integration tests are skipped. For local frontend development, copy `frontend/.env.example` to `frontend/.env.local` and set only the public LIFF/backend values there. Next.js does not load the root backend `.env`. From `frontend/`, run:

```bash
bun run test
bun run typecheck
bun run format:check
bun run build
```

Use HTTPS for both public domains when configuring LINE. Rebuild the frontend after changing `NEXT_PUBLIC_LIFF_ID` or `PUBLIC_BACKEND_URL`; these values are passed into the Docker build.

The API documentation and schema can be viewed at `http://localhost:8000/docs`

## Current Scope

- Basic Auth is used for the initial Dashboard login and trusted API clients. Browser requests use revocable Redis sessions. The admin API key remains available for trusted server integrations. Company SSO and account recovery remain future work.
- Policy answer caching uses Redis after guardrail screening and retrieval. Exact matches work without an embedding key; `OPENAI_EMBEDDING_API_KEY` enables semantic matches with cosine similarity >= 0.99 and matching number/negation constraints. Entries expire after 5 minutes, with at most 20 per source/prompt/model bucket. Changed source text, prompts, or models change the cache key; archived sources are excluded before cache lookup. Approximate matches still need evaluation on HR traffic.
- Optional [Langfuse tracing](https://langfuse.com/docs/observability/sdk/instrumentation) records masked policy-model inputs/outputs, duration, model, and token usage. Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_BASE_URL` for your Langfuse v4/Cloud project. Telemetry failures do not block answers. No Langfuse server is deployed by compose.
- No Payroll integration, model fine-tuning, or additional database is introduced.
- Leave attachments are stored in SeaweedFS; MongoDB stores their metadata and ownership. Imported policy text is stored in MongoDB. Download requests are authorized through the backend.
- Weaviate is an index. Rebuild it from MongoDB FAQ/policy data if it is lost or changed.


Historical proposal PDFs remain local and are ignored by Git, along with `.codex/` logs. Previously committed copies remain in Git history; this cleanup does not rewrite history. The runtime remains MongoDB + Weaviate. Coding conventions are in [code-guidelines.md](code-guidelines.md).
