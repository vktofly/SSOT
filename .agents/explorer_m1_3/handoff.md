# Milestone 1 Investigation Report: Backend Foundation & SQLite DB Migration

## 1. Observation

### 1.1 Database & Schema Integrity (`data/ssot.db`)
- **File Existence & Integrity**: `data/ssot.db` is present. Executing `PRAGMA integrity_check;` returns `[('ok',)]`.
- **Table Record Counts**:
  - `support_tracker`: 715 records
  - `finance_tracker`: 680 records
  - `escalations`: 155 records
  - `audit_logs`: 0 records
- **SQLAlchemy ORM Models**: Defined in `backend/app/models/`:
  - `SupportTicket` (`backend/app/models/support.py:9`): Table `support_tracker`, Primary Key `Ticket ID` (VARCHAR(50)), Float `Refund Amount (INR)`, indexed on `Agent`, `Status`, `Ticket ID`.
  - `FinanceRecord` (`backend/app/models/finance.py:9`): Table `finance_tracker`, Primary Key `Ref No` (VARCHAR(50)), Float `Amount Paid (INR)`, Float `Deduction (INR)`, indexed on `Ref No`, `Agent Name`, `Payout Status`.
  - `Escalation` (`backend/app/models/escalation.py:9`): Table `escalations`, Primary Key `Escalation ID` (VARCHAR(50)), Float `Days Open`, indexed on `Escalation ID`, `Ticket ID`, `Agent`, `Status`.
  - `AuditLog` (`backend/app/models/audit.py:14`): Table `audit_logs`, Primary Key `id` (INTEGER autoincrement), DateTime `timestamp`, indexed primary key.
- **Hydration Script**: `backend/app/scripts/seed_db.py`:
  - `clean_money_string()` handles currency symbols (`₹`, `$`, `INR`, `,`) and `NaN`/`None` (`seed_db.py:21-36`).
  - `clean_str()` normalizes string values and converts empty/`nan` values to `None` (`seed_db.py:39-46`).
  - `seed_database()` populates tables from `data/Support_Tracker.csv`, `data/Finance_Tracker.csv`, `data/Escalations.csv`.

### 1.2 FastAPI Application Initialization (`backend/app/main.py`)
- **App Factory & Lifespan**: `backend/app/main.py:24-42` defines `lifespan(app)` which executes `Base.metadata.create_all(bind=engine)` and calls `seed_database(db=db, force=False)` on startup.
- **CORS Middleware**: `backend/app/main.py:54-60` configures `CORSMiddleware` with `settings.CORS_ORIGINS = ["*"]`, allow credentials, all HTTP methods and headers.
- **Routers Registered**: Prefix `/api/v1` registered at `backend/app/main.py:63-66`:
  - `support_router` mounted at `/api/v1/support-tickets`
  - `finance_router` mounted at `/api/v1/finance-records`
  - `escalations_router` mounted at `/api/v1/escalations`
- **System Routes**: `GET /` (root metadata) and `GET /health` (health check status).
- **Error Handling**: `backend/app/main.py:87-93` registers global exception handler returning HTTP 500 JSON response.

### 1.3 CRUD Endpoints, Search, Filtering, and Pagination
- **Support Tickets Router** (`backend/app/routers/support.py`):
  - `GET /api/v1/support-tickets`: Query params `status`, `agent`, `search`, `skip`, `limit`. Case-insensitive search on `ticket_id`, `agent`, `route`, `notes`.
  - `POST /api/v1/support-tickets`: Validates with `SupportTicketCreate`, normalizes uppercase ticket ID, returns 201 Created or 409 Conflict for duplicates.
  - `GET /api/v1/support-tickets/{ticket_id}`: Returns single ticket or 404 Not Found.
  - `PATCH /api/v1/support-tickets/{ticket_id}` & `PUT`: Partial update with `exclude_unset=True`, returns 404 if not found.
  - `DELETE /api/v1/support-tickets/{ticket_id}`: Deletes record, returns 200 OK or 404 if not found.
- **Finance Records Router** (`backend/app/routers/finance.py`):
  - `GET /api/v1/finance-records`: Query params `status`, `payout_status`, `agent_name`, `search`, `skip`, `limit`.
  - `POST /api/v1/finance-records`: Returns 201 Created or 409 Conflict.
  - `GET /api/v1/finance-records/{ref_no}`: Returns record or 404 Not Found.
  - `PATCH /api/v1/finance-records/{ref_no}` & `PUT`: Partial update or 404 Not Found.
  - `DELETE /api/v1/finance-records/{ref_no}`: Deletes record or 404 Not Found.
- **Escalations Router** (`backend/app/routers/escalations.py`):
  - `GET /api/v1/escalations`: Query params `status`, `agent`, `channel`, `ticket_id`, `search`, `skip`, `limit`.
  - `POST /api/v1/escalations`: Returns 201 Created or 409 Conflict.
  - `GET /api/v1/escalations/{escalation_id}`: Returns record or 404 Not Found.
  - `PATCH /api/v1/escalations/{escalation_id}` & `PUT`: Partial update or 404 Not Found.
  - `DELETE /api/v1/escalations/{escalation_id}`: Deletes record or 404 Not Found.

### 1.4 Test Suite Execution
- Running `python -m pytest backend/tests/test_database.py backend/tests/test_main.py backend/tests/test_support_api.py backend/tests/test_finance_api.py backend/tests/test_escalations_api.py -v`:
  - 30 out of 30 tests PASSED (100% pass rate for Milestone 1 unit and endpoint tests).

---

## 2. Logic Chain

1. Direct inspection of `data/ssot.db` and execution of `PRAGMA integrity_check;` confirmed the physical database file is valid and contains 715 support tickets, 680 finance records, and 155 escalations.
2. Direct inspection of `backend/app/models/` confirmed all 4 SQLAlchemy models (`SupportTicket`, `FinanceRecord`, `Escalation`, `AuditLog`) exist with typed attributes, primary keys, and indices matching the interface contract in `PROJECT.md`.
3. Inspection of `backend/app/main.py` confirmed FastAPI initializes cleanly with CORS middleware, lifespan database hydration, root/health endpoints, and global exception handlers.
4. Inspection of `backend/app/routers/` confirmed full CRUD support (GET list, POST create, GET detail, PATCH/PUT update, DELETE) with query parameter filtering, search (`ilike`), and standard HTTP status codes (200, 201, 404, 409, 500).
5. Pytest execution confirmed all 30 tests covering the database models, main app, and support/finance/escalations APIs pass with exit code 0.

---

## 3. Caveats

- `test_support_crud.py` requires fixtures (`seeded_db`, `operator_auth_headers`, `manager_auth_headers`) that are configured in Milestone 2 (Auth & RBAC).
- `data/ssot.db` has 0 rows in `audit_logs` because audit logging begins on user activity in subsequent milestones.

---

## 4. Conclusion

Milestone 1 (Backend Foundation & SQLite DB Migration) is fully implemented, verified, and operational:
1. SQLite database and SQLAlchemy models are in place and hydrated with 1,550 baseline records across support, finance, and escalation tables.
2. FastAPI application entrypoint is configured with lifespan hydration, CORS, error handling, and router registration under `/api/v1`.
3. All CRUD endpoints for Support Tickets, Finance Records, and Escalations support pagination, search, status filtering, and HTTP status code standards.
4. 30/30 Milestone 1 tests pass.

---

## 5. Verification Method

To independently verify this milestone:

1. **Verify Database Integrity**:
   ```powershell
   python -c "import sqlite3; conn = sqlite3.connect('data/ssot.db'); c = conn.cursor(); c.execute('PRAGMA integrity_check;'); print(c.fetchall()); c.execute('SELECT count(*) FROM support_tracker;'); print('Support count:', c.fetchone()[0]); conn.close()"
   ```
   *Expected output*: `[('ok',)]` and `Support count: 715`.

2. **Run Milestone 1 Pytest Suite**:
   ```powershell
   python -m pytest backend/tests/test_database.py backend/tests/test_main.py backend/tests/test_support_api.py backend/tests/test_finance_api.py backend/tests/test_escalations_api.py -v
   ```
   *Expected output*: `30 passed`.
