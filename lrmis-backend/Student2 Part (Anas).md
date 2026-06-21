# Student 2 — Applicants, Documents & Objections + Registrar Console UI
### Anas Qalalwa — COMP4382 Final Project

---

## Overview

This document covers everything implemented for **Student 2's module** of the Land Registration Management Information System (LRMIS). The module handles applicant profiles, document management, objections, and the Registrar Staff Console UI.

---

## Files Created / Modified

| File | Action | Description |
|---|---|---|
| `app/modules/applicants/models.py` | **Created** | All Pydantic request/response models |
| `app/modules/applicants/router.py` | **Replaced** | Full implementation of all 10 endpoints |
| `ui/registrar.html` | **Created** | Registrar & Staff Console UI |
| `scripts/create_indexes.py` | **Updated** | Added indexes for applicant_id, document_id, objection_id |
| `ui/portal.html` | **Updated** | Fixed port 8000 → 8080 |
| `ui/index.html` | **Updated** | Fixed port 8000 → 8080 |
| `.env` | **Created** | MongoDB Atlas connection string |
| `tests/smoke_applicants.py` | **Created** | Automated smoke tests (24 tests) |

---

## Environment Setup

### `.env` file (inside `lrmis-backend/`)

```
MONGODB_URI=mongodb+srv://yahiarayyan20_db_user:4HsWrw1L4rVjL9sS@cluster0.7lpa4rf.mongodb.net/?appName=Cluster0
DB_NAME=lrmis
APP_ENV=development
```

### Run the project (every session)

```powershell
# From the lrmis-backend/ folder:

# One-time setup
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m scripts.create_indexes
python -m scripts.seed_data

# Every session
.venv\Scripts\activate
uvicorn app.main:app --reload --port 8080
```

> Server runs at **http://127.0.0.1:8080**  
> Interactive docs at **http://127.0.0.1:8080/docs**

---

## Pydantic Models — `app/modules/applicants/models.py`

| Model | Purpose |
|---|---|
| `ApplicantIdentity` | National ID + verification method |
| `ApplicantContacts` | Email and phone |
| `ApplicantAddress` | City, neighborhood, zone_id |
| `NotificationPrefs` | on_status_change, on_missing_documents, on_certificate_ready |
| `ApplicantPreferences` | preferred_contact, language, notifications |
| `PrivacySettings` | share_contact_with_staff, show_in_public_registry |
| `ApplicantCreate` | Full applicant profile creation request |
| `DocumentCreate` | Document metadata submission |
| `CommentCreate` | Comment / staff note |
| `ObjectionCreate` | Objection submission (min 10 chars reason) |
| `DocumentReviewRequest` | Accept or reject a document (verified / rejected) |

---

## API Endpoints — `app/modules/applicants/router.py`

### 1. `POST /applicants/` — Create Applicant Profile

Creates a new applicant profile in the `applicants` collection.

**Rules:**
- `national_id` must be unique (409 if duplicate)
- `applicant_id` is auto-generated as `APP-2026-XXXX` if not provided
- Custom `applicant_id` must also be unique (409 if taken)
- `verification_state` defaults to `unverified`

**Request body:**
```json
{
  "full_name": "Nour Ahmad",
  "applicant_type": "citizen",
  "identity": { "national_id": "400000001" },
  "contacts": { "email": "nour@example.com", "phone": "+970599000000" },
  "address": { "city": "Ramallah", "neighborhood": "Al Tireh", "zone_id": "ZONE-A" },
  "preferences": {
    "preferred_contact": "email",
    "language": "ar",
    "notifications": {
      "on_status_change": true,
      "on_missing_documents": true,
      "on_certificate_ready": true
    }
  }
}
```

**Response:** `201 Created` — full applicant document

---

### 2. `GET /applicants/{applicant_id}` — Get Applicant Profile

Retrieves an applicant profile with live stats computed from the database.

**Notes:**
- `privacy` field is removed from the response (restricted)
- `stats` is computed live: total_applications, approved_applications, pending_applications
- Returns `404` if applicant not found

**Response example:**
```json
{
  "applicant_id": "APP-2026-0001",
  "full_name": "Nour Ahmad",
  "applicant_type": "citizen",
  "verification_state": "unverified",
  "identity": { "national_id": "400000001", "verified": false },
  "contacts": { "email": "nour@example.com", "phone": "+970599000000" },
  "stats": { "total_applications": 3, "approved_applications": 1, "pending_applications": 2 }
}
```

---

### 3. `GET /applicants/{applicant_id}/applications` — List Applicant's Applications

Returns all land applications submitted by an applicant, paginated.

**Query parameters:**
- `page` (default: 1)
- `limit` (default: 20, max: 100)

**Response:** Envelope `{ data, total, page, limit }`

---

### 4. `POST /applications/{application_id}/documents` — Upload Document

Registers document metadata in the `application_documents` collection and logs a `document_uploaded` event in `performance_logs`.

**Request body:**
```json
{
  "document_type": "ownership_deed",
  "document_name": "Title Deed — Plot 145",
  "applicant_id": "APP-2026-0001",
  "notes": "Original signed copy"
}
```

**Response:** `201 Created` — document record with `document_id` (format: `DOC-2026-XXXX`)

---

### 5. `POST /applications/{application_id}/comments` — Add Comment

Appends a comment to the application's `comments` array and logs a `comment_added` event.

**Request body:**
```json
{
  "comment": "Waiting for the applicant to provide the original deed.",
  "applicant_id": "registrar_001",
  "actor_type": "registrar"
}
```

**Response:** `201 Created` — `{ message, comment }`

---

### 6. `POST /applications/{application_id}/objections` — Raise Objection

Stores an objection in the `objections` collection, updates the application's `objection` fields, and **automatically transitions the application to `under_objection`** if the workflow allows it from the current state.

**Request body:**
```json
{
  "reason": "The parcel boundaries are disputed by a neighbour.",
  "applicant_id": "APP-2026-0001",
  "supporting_details": "See attached boundary map."
}
```

**Response:** `201 Created` — objection record with `objection_id` (format: `OBJ-2026-XXXX`)

**Workflow transition:** If the application is in `surveyed` or `legal_review`, it is automatically moved to `under_objection`.

---

### 7. `GET /applications/{application_id}/timeline` — View Event Timeline

Returns the full event history from `performance_logs` for the application, paginated.

**Query parameters:**
- `page` (default: 1)
- `limit` (default: 100, max: 500)

**Response:** Envelope `{ data: [events], total, page, limit }`

**Event types logged:** `submitted`, `pre_checked`, `survey_required`, `surveyed`, `legal_review`, `approved`, `certificate_issued`, `document_uploaded`, `document_verified`, `document_rejected`, `comment_added`, `objection_raised`, `on_hold`, `rejected`

---

### 8. `PATCH /applications/{application_id}/documents/{document_id}/review` — Review Document

Allows a registrar to **accept or reject** an uploaded document.

**Request body:**
```json
{
  "status": "verified",
  "reviewer_id": "registrar_001",
  "review_notes": "Original deed confirmed authentic."
}
```

**Valid status values:** `verified`, `rejected`

**Response:** Updated document record with `reviewed_at` and `reviewed_by` timestamps.

---

### 9. `GET /parcels/{parcel_code}` — Get Parcel with GeoJSON

Returns a parcel document including its GeoJSON polygon geometry. Used by the Registrar Console map view.

**Response example:**
```json
{
  "parcel_code": "PARCEL-001",
  "zone_id": "ZONE-A",
  "area_sqm": 1000.0,
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[36.8172, 1.2921], [36.8182, 1.2921], ...]]
  }
}
```

---

### 10. `GET /applications/{application_id}/certificate-status` — Get Certificate

Returns the issued certificate for an application, or `null` if none has been issued yet.

**Response (issued):**
```json
{
  "certificate": {
    "certificate_id": "CERT-2026-0001",
    "application_id": "LRMIS-2026-0001",
    "certificate_type": "ownership_certificate",
    "status": "issued",
    "issued_by": "registrar_001",
    "issued_at": "2026-06-21T...",
    "verification": {
      "qr_code_url": "/certificates/CERT-2026-0001/verify",
      "digital_signature_stub": "signed_hash_example"
    }
  }
}
```

**Response (not issued yet):**
```json
{ "certificate": null, "message": "No certificate issued yet" }
```

---

## MongoDB Collections Used

### `applicants`

Stores applicant profiles.

```json
{
  "applicant_id": "APP-2026-0001",
  "full_name": "Nour Ahmad",
  "applicant_type": "citizen",
  "verification_state": "unverified",
  "identity": {
    "national_id": "400000001",
    "verified": false,
    "verification_method": "otp_stub",
    "verified_at": null
  },
  "contacts": { "email": "nour@example.com", "phone": "+970599000000" },
  "address": { "city": "Ramallah", "neighborhood": "Al Tireh", "zone_id": "ZONE-A" },
  "preferences": {
    "preferred_contact": "email",
    "language": "ar",
    "notifications": {
      "on_status_change": true,
      "on_missing_documents": true,
      "on_certificate_ready": true
    }
  },
  "privacy": { "share_contact_with_staff": true, "show_in_public_registry": false },
  "stats": { "total_applications": 0, "approved_applications": 0, "pending_applications": 0 },
  "created_at": "2026-06-21T...",
  "updated_at": "2026-06-21T..."
}
```

### `application_documents`

Stores document metadata uploaded per application.

```json
{
  "document_id": "DOC-2026-0001",
  "application_id": "LRMIS-2026-0001",
  "document_type": "ownership_deed",
  "document_name": "Title Deed — Plot 145",
  "applicant_id": "APP-2026-0001",
  "notes": null,
  "status": "pending_review",
  "uploaded_at": "2026-06-21T...",
  "reviewed_at": null,
  "reviewed_by": null
}
```

### `objections`

Stores objections raised against applications.

```json
{
  "objection_id": "OBJ-2026-0001",
  "application_id": "LRMIS-2026-0001",
  "applicant_id": "APP-2026-0001",
  "reason": "The parcel boundaries are disputed.",
  "supporting_details": null,
  "status": "pending",
  "raised_at": "2026-06-21T...",
  "resolved_at": null,
  "resolution_notes": null
}
```

### `performance_logs`

Shared audit log — read and written by this module via `log_event()`.

---

## MongoDB Indexes Added

```python
# applicants
db["applicants"].create_index("applicant_id", unique=True)
db["applicants"].create_index("identity.national_id", unique=True)

# application_documents
db["application_documents"].create_index("application_id")
db["application_documents"].create_index("document_id", unique=True)

# objections
db["objections"].create_index("application_id")
db["objections"].create_index("objection_id", unique=True)
```

---

## UI — Registrar & Staff Console (`ui/registrar.html`)

A full single-page application (SPA) for land authority staff. Built with vanilla HTML/CSS/JS + Leaflet.js for maps.

### Access

Open `ui/registrar.html` directly in a browser while the server is running on port 8080.

### Screens

#### 1. Dashboard
- **6 stat cards:** Total, Submitted, Legal Review, Missing Docs, Approved, Rejected
- Clicking a card filters the applications table to that status
- Objection alert banner if any applications are under objection
- Status distribution bar chart (all statuses with counts)
- Recent 10 applications table

#### 2. Application Management
- Full applications table with 7 filter controls:
  - Status dropdown
  - Application type dropdown
  - Zone ID text filter
  - Parcel number text filter
  - Application ID search
  - Date from (submitted after)
  - Date to (submitted before)
- Click any row to open Application Detail

#### 3. Application Detail
Opened by clicking any application. Contains:

**Dynamic Action Strip** — buttons change based on current application status:
- Pre-Check, Survey Required, Legal Review, Approve (workflow transitions)
- Hold / Reject (always visible, unless terminal state)
- Issue Certificate (only if status = `approved`)

**Tabs:**

| Tab | Content |
|---|---|
| Overview | Application info, parcel info, assignment info, description |
| Documents | List of uploaded documents with **Verify / Reject** buttons per document; register new document form |
| Map | **Leaflet.js map** showing the parcel polygon on OpenStreetMap; fetches GeoJSON from `/parcels/{parcel_code}` |
| Notes / Comments | Staff notes thread; add note form |
| Timeline | Full event history (newest first) with icons per event type |
| Registrar Review | Approve (with note), Reject (with reason), Hold (with reason); shows certificate info if already issued |

#### 4. Certificate Issuance Screen
- Table of all **approved** applications ready for certificate issuance
- One-click "Issue Certificate" button per row
- Table of all **issued certificates** with certificate ID, type, issuer, date, and status badge

#### 5. Applicant Lookup
- Search by Applicant ID
- Shows full profile: name, type, verification state, national ID, contact info, stats

---

## Applicant Types Supported

| Value | Meaning |
|---|---|
| `citizen` | Individual citizen |
| `lawyer` | Legal representative |
| `company` | Corporate entity |
| `surveyor` | Surveyor (also a staff type) |
| `representative` | Authorized representative |

## Verification States

| Value | Meaning |
|---|---|
| `unverified` | Default — identity not yet confirmed |
| `verified` | Identity confirmed (via OTP stub) |
| `suspended` | Account suspended |

## Document Statuses

| Value | Meaning |
|---|---|
| `pending_review` | Default after upload |
| `verified` | Accepted by registrar |
| `rejected` | Rejected by registrar |

---

## Running the Smoke Tests

```powershell
# From lrmis-backend/ with the server running on port 8080:
$env:PYTHONIOENCODING = "utf-8"
.venv\Scripts\python tests\smoke_applicants.py
```

**24 tests covering:**
- `POST /applicants/` — success + duplicate rejection
- `GET /applicants/{id}` — success + 404
- `GET /applicants/{id}/applications` — envelope shape
- `POST /applications/{id}/documents` — document_id, status
- `POST /applications/{id}/comments` — success
- `POST /applications/{id}/objections` — objection_id, status
- `GET /applications/{id}/timeline` — envelope + event count

---

## Design Decisions

1. **Auto-generated IDs** — `applicant_id` is auto-generated as `APP-2026-XXXX` using the shared atomic `counters` collection, but a custom ID can be provided (portal compatibility).

2. **Live stats** — `stats` on `GET /applicants/{id}` are computed from `land_applications` at query time rather than stored, keeping them always accurate without requiring sync logic.

3. **Objection auto-transition** — When an objection is raised, the application automatically transitions to `under_objection` if the workflow permits (from `surveyed` or `legal_review`). This enforces the business rule that disputed applications cannot proceed until resolved.

4. **Privacy field** — The `privacy` object is stored in the DB but stripped from `GET /applicants/{id}` responses to protect applicant preferences from exposure.

5. **Document review via timeline** — Document statuses are surfaced in the UI by reading `document_uploaded/verified/rejected` events from `performance_logs`, keeping a full audit trail of every review decision.

6. **Map with Leaflet.js** — The parcel map uses OpenStreetMap tiles (free, no API key needed). The `/parcels/{parcel_code}` endpoint returns the GeoJSON polygon which is rendered as a blue polygon with a marker popup.

---

## API Summary Table

| # | Method | Path | Description |
|---|---|---|---|
| 1 | `POST` | `/applicants/` | Create applicant profile |
| 2 | `GET` | `/applicants/{id}` | Get applicant (restricted fields) |
| 3 | `GET` | `/applicants/{id}/applications` | List applicant's applications |
| 4 | `POST` | `/applications/{id}/documents` | Upload document metadata |
| 5 | `POST` | `/applications/{id}/comments` | Add comment or staff note |
| 6 | `POST` | `/applications/{id}/objections` | Raise objection |
| 7 | `GET` | `/applications/{id}/timeline` | View event timeline |
| 8 | `PATCH` | `/applications/{id}/documents/{doc_id}/review` | Accept or reject document |
| 9 | `GET` | `/parcels/{parcel_code}` | Get parcel GeoJSON (for map) |
| 10 | `GET` | `/applications/{id}/certificate-status` | Get issued certificate |
