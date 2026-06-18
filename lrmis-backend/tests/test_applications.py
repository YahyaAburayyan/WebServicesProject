"""
End-to-end tests for Student 1 -- Land Application Management.

Usage:
    python tests/test_applications.py

Requirements:
    - Server must be running:  uvicorn app.main:app --reload
    - Seed parcel must exist:  python -m scripts.seed_data
    - requests must be installed (dev-only, not in requirements.txt)
"""
import re
import sys
import uuid

try:
    import requests
except ImportError:
    print("ERROR: 'requests' is not installed.")
    print("Run: pip install requests")
    sys.exit(1)

BASE = "http://127.0.0.1:8000"

GREEN  = "\033[32m"
RED    = "\033[31m"
YELLOW = "\033[33m"
RESET  = "\033[0m"
PASS_LABEL = f"{GREEN}PASS{RESET}"
FAIL_LABEL = f"{RED}FAIL{RESET}"

results: list[tuple[str, bool]] = []


def check(label: str, passed: bool, detail: str = "") -> None:
    tag = PASS_LABEL if passed else FAIL_LABEL
    print(f"  {tag}  {label}")
    if not passed and detail:
        print(f"       {YELLOW}-> {detail}{RESET}")
    results.append((label, passed))


def section(title: str) -> None:
    print(f"\n{'-' * 62}")
    print(f"  {title}")
    print(f"{'-' * 62}")


# ---------- 0. Server health check ------------------------------------------
section("SERVER HEALTH CHECK")
try:
    r = requests.get(f"{BASE}/", timeout=5)
    check("GET / returns 200", r.status_code == 200, f"got {r.status_code}")
except requests.exceptions.ConnectionError:
    print(f"  {RED}ERROR{RESET}: Cannot reach {BASE}")
    print("  Please start the server first:")
    print("      uvicorn app.main:app --reload")
    sys.exit(1)

# Unique token so repeated runs never collide on idempotency keys / applicant ids
RUN = uuid.uuid4().hex[:8]

# Values that match the parcel inserted by seed_data.py:
#   parcel_code="PARCEL-001", zone_id="ZONE-A"
PARCEL_NUMBER = "PARCEL-001"
PARCEL_ZONE   = "ZONE-A"


def make_body(suffix: str = "") -> dict:
    """Return a valid ApplicationCreate payload, unique per run."""
    return {
        "application_type": "ownership_transfer",
        "applicant_ref": {
            "applicant_id": f"A-{RUN}{suffix}",
            "applicant_type": "citizen",
        },
        "parcel_ref": {
            "parcel_number": PARCEL_NUMBER,
            "block_number":  "12",
            "basin_number":  "3",
            "zone_id":       PARCEL_ZONE,
        },
    }


def post_app(suffix: str = "") -> tuple[str | None, int]:
    """POST /applications/ and return (application_id, status_code)."""
    resp = requests.post(f"{BASE}/applications/", json=make_body(suffix))
    app_id = resp.json().get("application_id") if resp.ok else None
    return app_id, resp.status_code


# ---------- TEST 1 -- Create application ------------------------------------
section("TEST 1 -- POST /applications/ -> 201 + LRMIS-2026-XXXX id")

r = requests.post(f"{BASE}/applications/", json=make_body())
check("status code is 201",
      r.status_code == 201,
      f"got {r.status_code} -- body: {r.text[:300]}")

data1   = r.json() if r.status_code == 201 else {}
main_id = data1.get("application_id", "")
check("application_id matches LRMIS-2026-NNNN",
      bool(re.match(r"^LRMIS-2026-\d{4}$", main_id)),
      f"got {main_id!r}")


# ---------- TEST 2 -- Idempotency -------------------------------------------
section("TEST 2 -- Idempotency: same key twice -> same application_id")

idem_key = f"idem-{RUN}"
headers  = {"idempotency-key": idem_key}
r1 = requests.post(f"{BASE}/applications/", json=make_body("-idem"), headers=headers)
r2 = requests.post(f"{BASE}/applications/", json=make_body("-idem"), headers=headers)

id1 = r1.json().get("application_id") if r1.ok else None
id2 = r2.json().get("application_id") if r2.ok else None

check("both requests succeed (2xx)",
      r1.ok and r2.ok,
      f"codes: {r1.status_code} / {r2.status_code}")
check("returned the same application_id",
      id1 is not None and id1 == id2,
      f"first={id1!r}  second={id2!r}")

if id1:
    main_id = id1   # use the idempotent app as our main subject


# ---------- TEST 3 -- GET by id ---------------------------------------------
section(f"TEST 3 -- GET /applications/{{id}} -> 200 with full record")

r = requests.get(f"{BASE}/applications/{main_id}")
check("status 200", r.status_code == 200, f"got {r.status_code}")
fetched_id = r.json().get("application_id") if r.ok else None
check("returned application_id matches",
      fetched_id == main_id,
      f"expected {main_id!r}, got {fetched_id!r}")
_status3 = r.json().get("status") if r.ok else "N/A"
check("status field is 'submitted'",
      _status3 == "submitted",
      f"got {_status3!r}")


# ---------- TEST 4 -- GET non-existent -> 404 --------------------------------
section("TEST 4 -- GET /applications/NONEXISTENT -> 404")

r = requests.get(f"{BASE}/applications/LRMIS-DOES-NOT-EXIST-{RUN}")
check("status 404", r.status_code == 404, f"got {r.status_code}")


# ---------- TEST 5 -- Illegal transition: submitted->approved -> 409 ----------
section("TEST 5 -- PATCH transition submitted->approved -> 409 (illegal)")

r = requests.patch(
    f"{BASE}/applications/{main_id}/transition",
    json={"target_state": "approved"},
)
check("status 409",
      r.status_code == 409,
      f"got {r.status_code} -- {r.text[:200]}")


# ---------- TEST 6 -- Legal transition: submitted->pre_checked -> 200 ---------
section("TEST 6 -- PATCH transition submitted->pre_checked -> 200")

r = requests.patch(
    f"{BASE}/applications/{main_id}/transition",
    json={"target_state": "pre_checked"},
)
check("status 200", r.status_code == 200, f"got {r.status_code} -- {r.text[:200]}")
new_status = r.json().get("status") if r.ok else None
check("status field is now 'pre_checked'",
      new_status == "pre_checked",
      f"got {new_status!r}")


# ---------- TEST 7 -- Transition pre_checked->survey_required ----------------
section(
    "TEST 7 -- PATCH transition pre_checked->survey_required -> 200\n"
    f"  (requires seed parcel  parcel_code={PARCEL_NUMBER!r}  zone_id={PARCEL_ZONE!r})"
)

r = requests.patch(
    f"{BASE}/applications/{main_id}/transition",
    json={"target_state": "survey_required"},
)

if r.status_code == 400:
    detail = r.json().get("detail", "")
    if "GeoJSON" in detail or "Parcel" in detail:
        print(f"\n  {YELLOW}WARNING: Parcel not found in the database.{RESET}")
        print(f"     Run:  python -m scripts.seed_data   then re-run this script.\n")
    check("survey_required transition (parcel missing -- run seed_data first)",
          False, f"guard blocked: {detail}")
else:
    check("status 200", r.status_code == 200, f"got {r.status_code} -- {r.text[:200]}")
    new_status = r.json().get("status") if r.ok else None
    check("status field is now 'survey_required'",
          new_status == "survey_required",
          f"got {new_status!r}")


# ---------- TEST 8 -- Certificate on non-approved app -> 409 -----------------
section("TEST 8 -- POST /certificate on non-approved app -> 409")

r = requests.post(f"{BASE}/applications/{main_id}/certificate", json={})
check("status 409", r.status_code == 409, f"got {r.status_code} -- {r.text[:200]}")


# ---------- TEST 9 -- List endpoint returns envelope -------------------------
section("TEST 9 -- GET /applications/ -> 200 with envelope shape")

r = requests.get(f"{BASE}/applications/")
check("status 200", r.status_code == 200, f"got {r.status_code}")
if r.ok:
    body = r.json()
    check("envelope has keys: data, total, page, limit",
          all(k in body for k in ("data", "total", "page", "limit")),
          f"keys present: {list(body.keys())}")
    check("data is a list",
          isinstance(body.get("data"), list),
          f"got type {type(body.get('data')).__name__}")
    check("page defaults to 1",
          body.get("page") == 1,
          f"got {body.get('page')!r}")
    check("limit defaults to 20",
          body.get("limit") == 20,
          f"got {body.get('limit')!r}")
    check("total >= 1 (we created at least one app)",
          isinstance(body.get("total"), int) and body["total"] >= 1,
          f"got {body.get('total')!r}")


# ---------- TEST 10 -- Filter by status --------------------------------------
section("TEST 10 -- GET /applications/?status=survey_required -> filtered list")

r = requests.get(f"{BASE}/applications/", params={"status": "survey_required"})
check("status 200", r.status_code == 200, f"got {r.status_code}")
if r.ok:
    items = r.json().get("data", [])
    bad   = [d.get("application_id") for d in items
             if d.get("status") != "survey_required"]
    check("all returned items have status=survey_required",
          len(bad) == 0,
          f"wrong-status ids: {bad}")
    check("our app appears in filtered results (if test 7 passed)",
          any(d.get("application_id") == main_id for d in items),
          f"main_id={main_id!r} not in {[d.get('application_id') for d in items]}")


# ---------- TEST 11 -- Reject: empty body->422, with reason->200 -------------
section("TEST 11 -- POST /reject: empty body->422, with reason->200")

reject_id, code = post_app("-rej")
if not reject_id:
    check("create fresh app for reject test", False, f"POST returned {code}")
else:
    r = requests.post(f"{BASE}/applications/{reject_id}/reject", json={})
    check("empty body -> 422 (reason is mandatory)",
          r.status_code == 422,
          f"got {r.status_code} -- {r.text[:200]}")

    r = requests.post(
        f"{BASE}/applications/{reject_id}/reject",
        json={"reason": "duplicate application"},
    )
    check("with reason -> 200",
          r.status_code == 200,
          f"got {r.status_code} -- {r.text[:200]}")
    new_status = r.json().get("status") if r.ok else None
    check("status becomes 'rejected'",
          new_status == "rejected",
          f"got {new_status!r}")


# ---------- TEST 12 -- Hold --------------------------------------------------
section("TEST 12 -- POST /hold -> 200, status becomes on_hold")

hold_id, code = post_app("-hold")
if not hold_id:
    check("create fresh app for hold test", False, f"POST returned {code}")
else:
    r = requests.post(
        f"{BASE}/applications/{hold_id}/hold",
        json={"reason": "waiting on documents"},
    )
    check("status 200", r.status_code == 200, f"got {r.status_code} -- {r.text[:200]}")
    new_status = r.json().get("status") if r.ok else None
    check("status becomes 'on_hold'",
          new_status == "on_hold",
          f"got {new_status!r}")


# ---------- SUMMARY ----------------------------------------------------------
total  = len(results)
passed = sum(1 for _, p in results if p)
failed = total - passed

print(f"\n{'=' * 62}")
print(f"  RESULTS  {GREEN}{passed} passed{RESET}  /  {RED}{failed} failed{RESET}  /  {total} total")
if failed:
    print(f"\n  {RED}FAILED:{RESET}")
    for name, ok in results:
        if not ok:
            print(f"    x  {name}")
print(f"{'=' * 62}\n")

sys.exit(0 if failed == 0 else 1)
