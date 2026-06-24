# LRMIS — Land Registration Management Information System

FastAPI + PyMongo backend for the State of Palestine Land Registry.
COMP4382 Group Project — Birzeit University, 2026.

**Team:**

| Student | Module |
|---------|--------|
| Yahya (Student 1) | Land Application Management + Workflow |
| Anas (Student 2) | Applicants, Documents, Objections + Registrar UI |
| Huthaifa (Student 3) | Staff, Surveyors, Assignment, Analytics, Map UI |

---

## Getting Started (first time after cloning)

### 1. Get the MongoDB connection string

Ask a team member for the `.env` file, or create one yourself inside `lrmis-backend/`:

```
MONGODB_URI=mongodb+srv://<username>:<password>@<cluster>.mongodb.net/
DB_NAME=lrmis
APP_ENV=development
```

### 2. Open a terminal inside `lrmis-backend/` and run these once

```bash
# Create and activate a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create MongoDB indexes (needs .env set up first)
python -m scripts.create_indexes

# Seed sample staff and parcels
python -m scripts.seed_staff
python -m scripts.seed_parcels
```

### 3. Start the server

```bash
uvicorn app.main:app --reload
```

The API will be running at `http://127.0.0.1:8000`
Swagger docs: `http://127.0.0.1:8000/docs`

### 4. Open the UI

Open any HTML file from `lrmis-backend/ui/` directly in your browser while the server is running. Start with `lrmis.html`.

> **Note:** Steps 2 (indexes + seed) only need to run once. After that, just activate the venv and run `uvicorn` each session.

---

## Test Accounts

After seeding, use these accounts on the login page (`lrmis.html`):

### Registrars

| Name | Staff ID |
|------|----------|
| Omar Al-Khalidi | `STAF-2026-0001` |
| Layla Mansour | `STAF-2026-0002` |

### Surveyors

| Name | Staff ID | Zones |
|------|----------|-------|
| Kareem Nasser | `STAF-2026-0003` | ZONE-A, ZONE-B |
| Hana Barakat | `STAF-2026-0004` | ZONE-B, ZONE-C |
| Tariq Saleh | `STAF-2026-0005` | ZONE-A, ZONE-C |

### Citizens

Register a new account at `lrmis-citizen-register.html`

---

## UI Pages

| File | Role | Purpose |
|------|------|---------|
| `lrmis.html` | All | Login / role selection |
| `lrmis-citizen-register.html` | Public | Register a citizen account |
| `portal.html` | Citizen | Submit applications, upload docs, track status |
| `lrmis-citizen-dashboard.html` | Citizen | All citizen applications |
| `lrmis-new-application.html` | Citizen | New application form |
| `lrmis-app-detail.html` | Citizen | Application detail + timeline |
| `lrmis-registrar-center.html` | Registrar | Applications list + filter |
| `lrmis-registrar-review.html` | Registrar | Review application, documents, transitions |
| `lrmis-registrar-analytics.html` | Registrar | Analytics dashboard |
| `lrmis-certificate.html` | Registrar | Issue and view certificates |
| `lrmis-create-staff.html` | Registrar | Create staff accounts |
| `surveyor.html` | Surveyor | Tasks, milestones, survey report, map, analytics |

---

## Application Workflow

```
submitted → pre_checked → survey_required → surveyed → legal_review → approved → certificate_issued → closed
     ↓           ↓               ↓              ↓            ↓             ↓
  rejected    on_hold         on_hold        on_hold      on_hold      rejected
  on_hold   missing_docs                             under_objection
```

Business rules enforced in `workflow.py`:
- **pre_checked**: applicant_id + parcel_number + zone_id must be present
- **survey_required**: parcel must have a valid GeoJSON Polygon in the `parcels` collection
- **surveyed**: a survey report must exist
- **legal_review**: at least one ownership document uploaded
- **approved**: all documents reviewed, at least one ownership doc verified

---

## Tech Stack

| Layer | Technology |
| ----- | ---------- |
| API server | FastAPI 0.137.1 |
| Database driver | PyMongo 4.17.0 |
| Database | MongoDB Atlas |
| Runtime | Python 3.14.3 |
| Map | Leaflet.js 1.9.4 + OpenStreetMap |
| Charts | Chart.js 4.4.0 |

---

## Project Structure

```
lrmis-backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── config.py            # reads .env
│   ├── database.py          # shared MongoClient
│   └── modules/
│       ├── applications/    # Student 1 — workflow, CRUD
│       ├── applicants/      # Student 2 — portal, documents, objections
│       ├── staff/           # Student 3 — models
│       └── analytics/       # Student 3 — staff, survey, assignment, analytics, map
├── scripts/
│   ├── create_indexes.py    # run once
│   ├── seed_staff.py        # seeds 2 registrars + 3 surveyors
│   └── seed_parcels.py      # seeds parcels with GeoJSON geometry
├── ui/                      # all HTML pages
├── .env.example
└── requirements.txt
```
