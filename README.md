# LRMIS Backend

**Land Registration Management Information System** — FastAPI + PyMongo.
Citizens apply to register land, staff review applications, and surveyors complete field surveys.
Built as a university group project. All endpoints are stubs — find `# TODO` to see what to implement.

---

## A — Install these tools first

| Tool | Download | Confirm install |
| ---- | -------- | --------------- |
| Python 3.11+ | [python.org/downloads](https://www.python.org/downloads/) — **tick "Add Python to PATH" on Windows** | `python --version` |
| GitHub Desktop | [desktop.github.com](https://desktop.github.com/) | open the app and sign in |
| VS Code | [code.visualstudio.com](https://code.visualstudio.com/) | `code --version` |
| Postman | [postman.com/downloads](https://www.postman.com/downloads/) | open the app |

---

## B — Cloud database setup (MongoDB Atlas)

**The repo owner does steps 1–5 once. Teammates skip to the "Everyone" section below.**

1. Create a free account at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas) and create a free **M0** cluster.
2. Go to **Security → Database Access → Add New Database User**. Choose Password auth. Write down the username and password.
3. Go to **Security → Network Access → Add IP Address → Allow Access from Anywhere** (`0.0.0.0/0`). *(Fine for a student project, not for production.)*
4. Go to **Database → Connect → Drivers**, select Python, and copy the connection string. It looks like:
   `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/`
5. **Send that string to teammates privately** (WhatsApp, DM). Never paste it into GitHub — the `.env` file is gitignored for exactly this reason.

**Everyone (including the owner) — on your own computer:**

1. Copy `.env.example`, rename the copy to `.env`, and fill it in:

   ```text
   MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/
   DB_NAME=lrmis
   APP_ENV=development
   ```

---

## C — Get the code (GitHub Desktop)

**Owner (once):** open GitHub Desktop → File → Add Local Repository → select this folder → click **Publish repository** → set Private. Send the repo URL to teammates.

**Teammates (once):** open GitHub Desktop → File → Clone Repository → paste the URL → Clone.

---

## D — Run the project (everyone, every time)

Open the project folder in VS Code, then open **Terminal → New Terminal** and run these commands.

**Steps 1–4 are one-time setup. Only step 5 (activate) and step 6 (start server) run every session.**

```bash
# 1. Create a virtual environment (one time only)
python -m venv .venv

# 2. Activate it — run this EVERY time you open a new terminal
#    Windows:
.venv\Scripts\activate
#    Mac / Linux:
source .venv/bin/activate
#    You should see (.venv) at the start of your prompt.

# 3. Install packages (one time only, after activating)
pip install -r requirements.txt

# 4. Set up the database (one time only, after .env is set)
python -m scripts.create_indexes
python -m scripts.seed_data

# 5. Activate the venv (every session — same command as step 2)

# 6. Start the server (every session)
uvicorn app.main:app --reload
```

Then open [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) — this page lists every endpoint and lets you test them.
Press **Ctrl + C** in the terminal to stop the server.

---

## E — Who does what

> **Edit only the files inside your own module folder. Do not touch `app/common/` unless the whole group agrees — everyone's code depends on it.**

| Person | Module | Folder |
| ------ | ------ | ------ |
| Student 1 (owner) | Land Application Management + Applicant Portal UI | `app/modules/applications/` |
| Anas | Applicants, Documents & Objections + Registrar Console UI | `app/modules/applicants/` |
| Huthaifa | Staff, Surveyors & Assignment + Map/Analytics UI | `app/modules/staff/` |
| Everyone | Analytics API + map | `app/modules/analytics/` |

### Student 1 — `app/modules/applications/router.py` + `workflow.py`

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/applications/` | Submit new application |
| GET | `/applications/` | List all applications |
| GET | `/applications/{id}` | Get one application |
| PATCH | `/applications/{id}/transition` | Change status |
| POST | `/applications/{id}/hold` | Put on hold |
| POST | `/applications/{id}/reject` | Reject |
| POST | `/applications/{id}/certificate` | Issue certificate |

### Anas — `app/modules/applicants/router.py`

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/applicants/` | Register applicant |
| GET | `/applicants/{id}` | Get applicant |
| GET | `/applicants/{id}/applications` | List their applications |
| POST | `/applications/{id}/documents` | Upload document |
| POST | `/applications/{id}/comments` | Add comment |
| POST | `/applications/{id}/objections` | Raise objection |
| GET | `/applications/{id}/timeline` | Event history |

### Huthaifa — `app/modules/staff/router.py` + `assignment.py`

| Method | Path | Purpose |
| ------ | ---- | ------- |
| POST | `/staff/` | Add staff member |
| GET | `/staff/{id}` | Get staff member |
| POST | `/applications/{id}/auto-assign-surveyor` | Auto-assign surveyor |
| PATCH | `/applications/{id}/survey-milestone` | Update survey progress |
| POST | `/applications/{id}/survey-report` | Upload report |
| PATCH | `/applications/{id}/registrar-review` | Record review decision |

---

## F — Daily Git routine (GitHub Desktop)

1. **Before you start:** click **Fetch origin**, then **Pull origin** if it appears. This downloads your teammates' latest changes.
2. Do your work in VS Code.
3. **When you finish (or every hour):** go to GitHub Desktop, type a short message (e.g. `"added create applicant endpoint"`), click **Commit to main**, then **Push origin**.

> If GitHub Desktop shows the word **"conflict"** — stop, do not click anything, and message the repo owner.

---

## G — Folder structure

```text
lrmis-backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, router registration
│   ├── config.py            # reads .env
│   ├── database.py          # shared MongoClient — get_db()
│   ├── common/
│   │   ├── enums.py         # all shared enums — never hard-code status strings
│   │   ├── schemas.py       # PyObjectId, Envelope[T], Message
│   │   └── audit.py         # log_event() → performance_logs
│   └── modules/
│       ├── applications/    # Student 1
│       ├── applicants/      # Anas
│       ├── staff/           # Huthaifa
│       └── analytics/       # everyone
├── scripts/
│   ├── create_indexes.py
│   └── seed_data.py
├── .env.example
├── .gitignore
├── README.md
└── requirements.txt
```

---

## H — Coding conventions

- Import status/type values from `app/common/enums.py`. Never hard-code strings like `"submitted"`.
- List endpoints return `{ "data": [...], "total": 0, "page": 1, "limit": 20 }`.
- Every state change must call `common.audit.log_event(...)`.
- Search for `# TODO` in your file to find what to implement.

---

## I — Application status flow

```text
submitted → pre_checked → survey_required → surveyed → legal_review → approved → certificate_issued → closed
                ↕               ↕               ↕           ↕              ↕
            on_hold         on_hold          on_hold     on_hold     [rejected / closed are terminal]
            rejected        missing_docs   under_objection
            missing_docs
```

Full transition map and business-rule guards are in `app/modules/applications/workflow.py`.
