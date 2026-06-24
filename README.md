# LRMIS — Land Registration Management Information System

FastAPI + PyMongo backend for the State of Palestine Land Registry.
COMP4382 Group Project — Birzeit University, 2026.

---

## Team

| Student | Module | Folder |
|---------|--------|--------|
| Yahya (Student 1) | Land Application Management + Workflow | `app/modules/applications/` |
| Anas (Student 2) | Applicants, Documents, Objections + Registrar Console UI | `app/modules/applicants/` |
| Huthaifa (Student 3) | Staff, Surveyors, Assignment, Analytics, Map UI | `app/modules/staff/` + `app/modules/analytics/` |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API server | FastAPI 0.137.1 |
| Database driver | PyMongo 4.17.0 |
| Database | MongoDB Atlas (cloud) |
| Runtime | Python 3.14.3 |
| Map | Leaflet.js 1.9.4 + OpenStreetMap |
| Charts | Chart.js 4.4.0 |

---

## Environment Variables

Create a `.env` file in the `lrmis-backend/` directory (copy from `.env.example`):

```
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/
DB_NAME=lrmis
APP_ENV=development
```

---

## Setup & Run

Open a terminal inside the `lrmis-backend/` folder and run:

```bash
# 1. Create virtual environment (one time)
python -m venv .venv

# 2. Activate it
#    Windows:
.venv\Scripts\activate
#    Mac/Linux:
source .venv/bin/activate

# 3. Install packages (one time)
pip install -r requirements.txt

# 4. Create MongoDB indexes (one time — run after .env is set)
python -m scripts.create_indexes

# 5. Seed sample data (one time)
python -m scripts.seed_staff
python -m scripts.seed_parcels

# 6. Start the server (every session)
uvicorn app.main:app --reload
```

API docs (Swagger UI): [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## MongoDB Indexes

Indexes are created by `scripts/create_indexes.py` and cover:

| Collection | Index |
|-----------|-------|
| `land_applications` | `application_id` (unique), `status`, `application_type`, `parcel_ref.zone_id`, `idempotency_key` (unique sparse), `timestamps.submitted_at` |
| `parcels` | `parcel_code` (unique), `geometry` (2dsphere for geospatial queries), `zone_id` |
| `applicants` | `applicant_id` (unique), `identity.national_id` (unique) |
| `application_documents` | `application_id`, `document_id` (unique) |
| `objections` | `application_id`, `objection_id` (unique) |
| `staff_members` | `staff_id` (unique), `staff_code` (unique sparse), `role` |
| `survey_tasks` | `application_id`, `assigned_to` |
| `certificates` | `certificate_id` (unique) |

---

## Sample Users

After running the seed scripts, use these accounts in the login page:

### Registrars (login as Registrar on `lrmis.html`)
| Name | Staff ID |
|------|----------|
| Omar Al-Khalidi | `STAF-2026-0001` |
| Layla Mansour | `STAF-2026-0002` |

### Surveyors (login as Surveyor on `lrmis.html`)
| Name | Staff ID | Zones |
|------|----------|-------|
| Kareem Nasser | `STAF-2026-0003` | ZONE-A, ZONE-B |
| Hana Barakat | `STAF-2026-0004` | ZONE-B, ZONE-C |
| Tariq Saleh | `STAF-2026-0005` | ZONE-A, ZONE-C |

### Citizens
Register a new citizen at `lrmis-citizen-register.html` or use the citizen register link on the login page.

---

## UI Pages

Open these HTML files directly from `lrmis-backend/ui/` while the server is running:

| File | Role | Purpose |
|------|------|---------|
| `lrmis.html` | All | Main login/role selection page |
| `portal.html` | Citizen | Application portal — submit applications, upload docs, view status |
| `lrmis-citizen-register.html` | Public | Register a new citizen account |
| `lrmis-citizen-dashboard.html` | Citizen | Dashboard showing citizen's applications |
| `lrmis-new-application.html` | Citizen | Submit a new land registration application |
| `lrmis-app-detail.html` | Citizen | View application status + timeline |
| `lrmis-registrar-center.html` | Registrar | All applications list + filter |
| `lrmis-registrar-review.html` | Registrar | Review single application, documents, transitions |
| `lrmis-registrar-analytics.html` | Registrar | Analytics dashboard (redirect to surveyor.html analytics tab) |
| `lrmis-certificate.html` | Registrar | Issue and view certificates |
| `lrmis-create-staff.html` | Registrar | Create new staff members |
| `surveyor.html` | Surveyor | Tasks, milestones, survey report, live map, analytics |

---

## Application Workflow

```
submitted → pre_checked → survey_required → surveyed → legal_review → approved → certificate_issued → closed
     ↓           ↓               ↓              ↓            ↓             ↓
  rejected    on_hold         on_hold        on_hold      on_hold      rejected
  on_hold   missing_docs   (surveyor                under_objection
  missing_docs              assigns here)
```

Business-rule guards (in `workflow.py`):
- **pre_checked**: applicant_id + parcel_number + zone_id must be present
- **survey_required**: parcel must have a valid GeoJSON Polygon geometry in the `parcels` collection
- **surveyed**: a survey report must exist in `survey_reports`
- **legal_review**: at least one ownership document (deed or sale contract) uploaded
- **approved**: all documents reviewed (none pending) + at least one ownership document verified

---

## API Endpoints Summary

### Module 1 — Applications (`/applications/`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/applications/` | Create application (supports idempotency key) |
| GET | `/applications/` | List with filters (status, type, zone), pagination |
| GET | `/applications/{id}` | Get single application |
| PATCH | `/applications/{id}/transition` | Change workflow state |
| POST | `/applications/{id}/hold` | Put on hold |
| POST | `/applications/{id}/reject` | Reject with reason |
| POST | `/applications/{id}/certificate` | Issue certificate |

### Module 2 — Applicants & Portal (`/applicants/`, `/applications/`)
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/applicants/` | Register applicant |
| GET | `/applicants/` | List all applicants |
| GET | `/applicants/{id}` | Get applicant with live stats |
| GET | `/applicants/{id}/applications` | List applicant's applications |
| POST | `/applications/{id}/documents` | Upload document |
| GET | `/applications/{id}/documents` | List documents |
| PATCH | `/applications/{id}/documents/{docId}/review` | Verify/reject document |
| POST | `/applications/{id}/comments` | Add comment |
| POST | `/applications/{id}/objections` | Raise objection |
| GET | `/applications/{id}/timeline` | Event history |
| GET | `/applications/{id}/certificate-status` | Check certificate |
| GET | `/parcels/` | List parcels (with centroids) |
| GET | `/parcels/{parcel_code}` | Get parcel with GeoJSON |

### Module 3 — Staff, Survey & Assignment
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/staff/` | Create staff member |
| GET | `/staff/` | List staff (filter by role) |
| GET | `/staff/{id}` | Get staff with live workload |
| GET | `/staff/{id}/tasks` | List surveyor's tasks |
| POST | `/applications/{id}/auto-assign-surveyor` | Auto-assign best surveyor |
| POST | `/applications/{id}/reassign-surveyor` | Manually reassign to different surveyor |
| GET | `/applications/{id}/survey-task` | Get task + surveyor details |
| PATCH | `/applications/{id}/survey-milestone` | Advance milestone |
| POST | `/applications/{id}/survey-report` | Submit survey report |
| GET | `/applications/{id}/survey-report` | Get survey report |
| PATCH | `/applications/{id}/registrar-review` | Registrar reviews survey report |

### Module 4 — Analytics & Map
| Method | Path | Purpose |
|--------|------|---------|
| GET | `/analytics/kpis` | 9 KPI metrics (cached 60s) |
| GET | `/analytics/applications-by-status` | Status + type breakdown (`$facet`) |
| GET | `/analytics/applications-by-zone` | Zone breakdown + surveyor coverage (`$facet`, `$unwind`) |
| GET | `/analytics/application-trends` | Monthly/weekly trend |
| GET | `/analytics/processing-time` | Avg/min/max days with distribution (`$bucketAuto`) |
| GET | `/analytics/surveyors` | Surveyor workload (`$lookup`, `$unwind`) |
| GET | `/analytics/registrars` | Registrar performance from audit log |
| GET | `/analytics/certificates-by-month` | Certificate issuance trend |
| GET | `/analytics/geofeeds/parcels` | All parcels as GeoJSON FeatureCollection |
| GET | `/analytics/geofeeds/pending-heatmap` | Pending application hotspots as GeoJSON |
| GET | `/analytics/geofeeds/parcels-near` | Parcels near a point (`$geoNear`) |
| GET | `/analytics/export/csv` | Export all applications as CSV |

---

## MongoDB Operators Used

`$lookup`, `$facet`, `$bucketAuto`, `$geoNear`, `$group`, `$match`, `$sort`, `$project`, `$unwind`

---

## Project Structure

```
lrmis-backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── config.py            # reads .env
│   ├── database.py          # shared MongoClient — get_db()
│   └── modules/
│       ├── applications/    # Student 1 — workflow, CRUD
│       ├── applicants/      # Student 2 — portal, documents, objections
│       ├── staff/           # Student 3 — models only (router in analytics/)
│       └── analytics/       # Student 3 — staff, survey, assignment, analytics, map
├── scripts/
│   ├── create_indexes.py    # run once to set up MongoDB indexes
│   ├── seed_staff.py        # seeds 2 registrars + 3 surveyors
│   └── seed_parcels.py      # seeds sample parcels with GeoJSON geometry
├── ui/
│   ├── lrmis.html           # login / role selection
│   ├── portal.html          # citizen portal
│   ├── surveyor.html        # surveyor console + analytics + map
│   ├── lrmis-registrar-center.html
│   ├── lrmis-registrar-review.html
│   └── ...                  # other UI pages
├── .env.example
├── requirements.txt
└── README.md
```
