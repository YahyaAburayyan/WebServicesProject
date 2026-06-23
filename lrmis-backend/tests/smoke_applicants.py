"""
Quick smoke test for Student 2 endpoints.
Run with:  python tests/smoke_applicants.py
Server must be running on port 8080.
"""
import sys, json, urllib.request, urllib.error, uuid

BASE = "http://127.0.0.1:8000"
RUN  = uuid.uuid4().hex[:6]
GREEN = "\033[32m"; RED = "\033[31m"; RESET = "\033[0m"
results = []

def check(label, passed, detail=""):
    tag = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"  {tag}  {label}")
    if not passed and detail:
        print(f"       -> {detail}")
    results.append(passed)

def call(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method=method,
    )
    try:
        r = urllib.request.urlopen(req)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())

print("\n" + "="*60)
print("  SMOKE TEST — Student 2 Endpoints")
print("="*60)

# ── Health ────────────────────────────────────────────────────
print("\n── Health")
s, d = call("GET", "/")
check("GET / returns 200", s == 200)

# ── Create applicant ──────────────────────────────────────────
print("\n── POST /applicants/")
s, d = call("POST", "/applicants/", {
    "full_name":      "Test User " + RUN,
    "applicant_type": "citizen",
    "identity":       {"national_id": "9" + RUN},
    "contacts":       {"email": f"test{RUN}@example.com", "phone": "+970599000099"},
    "address":        {"city": "Ramallah", "neighborhood": "Test", "zone_id": "ZONE-A"},
})
check("status 201", s == 201, f"got {s}: {d}")
check("applicant_id present", bool(d.get("applicant_id")), str(d))
check("full_name matches",    d.get("full_name") == "Test User " + RUN)
check("verification_state = unverified", d.get("verification_state") == "unverified")
APPLICANT_ID = d.get("applicant_id", "")

# Duplicate national_id → 409
s2, d2 = call("POST", "/applicants/", {
    "full_name": "Dup", "applicant_type": "citizen",
    "identity": {"national_id": "9" + RUN},
})
check("duplicate national_id → 409", s2 == 409, f"got {s2}")

# ── Get applicant ─────────────────────────────────────────────
print(f"\n── GET /applicants/{APPLICANT_ID}")
s, d = call("GET", f"/applicants/{APPLICANT_ID}")
check("status 200",           s == 200, f"got {s}")
check("correct applicant_id", d.get("applicant_id") == APPLICANT_ID)
check("stats key present",    "stats" in d)
check("privacy not exposed",  "privacy" not in d)

# 404 for unknown applicant
s, _ = call("GET", "/applicants/DOES-NOT-EXIST")
check("unknown applicant → 404", s == 404)

# ── Get applicant applications ────────────────────────────────
print(f"\n── GET /applicants/{APPLICANT_ID}/applications")
s, d = call("GET", f"/applicants/{APPLICANT_ID}/applications")
check("status 200",           s == 200, f"got {s}")
check("envelope shape",       all(k in d for k in ("data","total","page","limit")))

# ── Create an application first (to test docs/comments/objections/timeline)
s_app, d_app = call("POST", "/applications/", {
    "application_type": "ownership_transfer",
    "applicant_ref":    {"applicant_id": APPLICANT_ID, "applicant_type": "citizen"},
    "parcel_ref":       {"parcel_number": "PARCEL-001", "block_number": "12",
                         "basin_number": "3", "zone_id": "ZONE-A"},
})
APP_ID = d_app.get("application_id", "")
print(f"\n   (Created application {APP_ID} for further tests)")

# ── Upload document ───────────────────────────────────────────
print(f"\n── POST /applications/{APP_ID}/documents")
s, d = call("POST", f"/applications/{APP_ID}/documents", {
    "document_type": "ownership_deed",
    "document_name": "Test Deed",
    "applicant_id":  APPLICANT_ID,
})
check("status 201",          s == 201, f"got {s}: {d}")
check("document_id present", bool(d.get("document_id")))
check("status = pending_review", d.get("status") == "pending_review")

# ── Add comment ───────────────────────────────────────────────
print(f"\n── POST /applications/{APP_ID}/comments")
s, d = call("POST", f"/applications/{APP_ID}/comments", {
    "comment":      "This is a test note from the registrar.",
    "applicant_id": "registrar_001",
    "actor_type":   "registrar",
})
check("status 201",    s == 201, f"got {s}: {d}")
check("message present", "message" in d)

# ── Raise objection ───────────────────────────────────────────
print(f"\n── POST /applications/{APP_ID}/objections")
s, d = call("POST", f"/applications/{APP_ID}/objections", {
    "reason":       "The parcel boundaries are disputed by a neighbour.",
    "applicant_id": APPLICANT_ID,
})
check("status 201",           s == 201, f"got {s}: {d}")
check("objection_id present", bool(d.get("objection_id")))
check("status = pending",     d.get("status") == "pending")

# ── Get timeline ──────────────────────────────────────────────
print(f"\n── GET /applications/{APP_ID}/timeline")
s, d = call("GET", f"/applications/{APP_ID}/timeline")
check("status 200",         s == 200, f"got {s}")
check("envelope shape",     all(k in d for k in ("data","total","page","limit")))
check("total >= 2 events",  isinstance(d.get("total"), int) and d["total"] >= 2,
      f"total={d.get('total')}")

# ── Summary ───────────────────────────────────────────────────
total  = len(results)
passed = sum(results)
failed = total - passed
print(f"\n{'='*60}")
print(f"  {GREEN}{passed} passed{RESET}  /  {RED}{failed} failed{RESET}  /  {total} total")
print(f"{'='*60}\n")
sys.exit(0 if failed == 0 else 1)
