"""One-time push of LOCAL dev data into the STAGING server (local -> staging).

Staging is a dev playground (will be wiped before real prod), so merging
local fixtures there is fine. This is NOT a sync: no schedule, no reverse
safety needed. Reruns are safe (match by natural keys, skip existing).

How it works (all through the public admin API, no DB access needed):
  masters:  match by email -> create via superadmin, reset password to the
            staging password, login as master, push services/bundles/hours
            with the master token (own-scope endpoints just work)
  clients:  match by email/phone -> create via superadmin
  appointments: remap master/service/bundle/client ids, book via superadmin
  reviews/audit/tokens/notifications/avatars are NOT transferred
  (reviews regenerate from appointments via seed; avatars re-upload).

Usage (run from online-booking/backend):
    set STAGING_API=https://beauty-specialist.ru
    set STAGING_EMAIL=<superadmin email>
    set STAGING_PASSWORD=<superadmin password>
    set STAGING_USER_PASSWORD=StagePass123!   # set for every pushed user
    python push_staging.py --yes [--db ./online_booking.db]
"""
import argparse
import getpass
import os
import sqlite3
import sys

try:
    import httpx
except ImportError:
    print("httpx is required (already in requirements)", file=sys.stderr)
    raise SystemExit(2)


def load_dotenv():
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                 ".env"), override=False)
    except ImportError:
        pass


class Api:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.client = httpx.Client(timeout=30.0)

    def login(self, email, password):
        r = self.client.post(f"{self.base}/api/v1/auth/login",
                             json={"email": email, "password": password})
        r.raise_for_status()
        tok = r.json().get("access_token", "")
        if not tok:
            raise RuntimeError("Login response has no access_token")
        self.client.headers["Authorization"] = f"Bearer {tok}"

    def get(self, path, params=None):
        r = self.client.get(f"{self.base}{path}", params=params or {})
        r.raise_for_status()
        return r.json()

    def post(self, path, payload):
        r = self.client.post(f"{self.base}{path}", json=payload)
        if r.status_code >= 400:
            print(f"  POST {path} -> {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        return r.json()

    def patch(self, path, payload):
        r = self.client.patch(f"{self.base}{path}", json=payload)
        if r.status_code >= 400:
            print(f"  PATCH {path} -> {r.status_code}: {r.text[:200]}")
        r.raise_for_status()
        return r.json()


def rows(db, sql, args=()):
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in con.execute(sql, args)]
    finally:
        con.close()


def main() -> None:
    load_dotenv()
    ap = argparse.ArgumentParser(description="One-time push local -> staging.")
    ap.add_argument("--api", default=os.getenv("STAGING_API", ""))
    ap.add_argument("--db", default=os.getenv("LOCAL_DB", "./online_booking.db"))
    ap.add_argument("--email", default=os.getenv("STAGING_EMAIL", ""))
    ap.add_argument("--password", default=os.getenv("STAGING_PASSWORD", ""))
    ap.add_argument("--user-password", default=os.getenv("STAGING_USER_PASSWORD", ""),
                    help="password set for every pushed user (required)")
    ap.add_argument("--yes", action="store_true", help="skip confirm prompt")
    args = ap.parse_args()

    if not args.api or not args.email:
        print("Set STAGING_API and STAGING_EMAIL (or pass --api).",
              file=sys.stderr)
        raise SystemExit(2)
    password = args.password or getpass.getpass("Staging superadmin password: ")
    user_pw = args.user_password or getpass.getpass("Password for pushed users: ")
    if not args.yes:
        print(f"This will MERGE local DB '{args.db}' into staging {args.api}")
        print("(match by email/phone/name, skip existing; passwords reset).")
        if input("Continue? [y/N]: ").strip().lower() not in ("y", "yes"):
            print("Aborted.")
            return

    api = Api(args.api)
    api.login(args.email, password)
    print("Logged in as staging superadmin.")

    stats = {"masters": 0, "masters_skipped": 0, "services": 0,
             "bundles": 0, "hours": 0, "clients": 0, "clients_skipped": 0,
             "appointments": 0, "appt_skipped": 0}

    staging_masters = {}
    try:
        staging_masters = {m["email"]: m for m in
                           api.get("/api/v1/admin/masters") if m.get("email")}
    except Exception as e:
        print(f"  list masters failed: {e}")

    for mu in rows(args.db, "SELECT * FROM users WHERE role='MASTER'"):
        if not mu["email"]:
            print(f"  SKIP master id={mu['id']}: no email to match")
            continue
        try:
            if mu["email"] in staging_masters:
                mp = staging_masters[mu["email"]]
                print(f"  master exists: {mu['email']}")
            else:
                mp = api.post("/api/v1/admin/masters", {
                    "name": mu["name"], "email": mu["email"],
                    "password": user_pw, "phone": mu["phone"],
                })
                print(f"  + master: {mu['email']}")
                stats["masters"] += 1
            # Own-scope endpoints need the master token; existing staging
            # users have unknown passwords, so reset first (staging only).
            try:
                api.patch(f"/api/v1/admin/masters/{mp['id']}/password",
                          {"password": user_pw})
            except Exception as e:
                print(f"  password reset failed for {mu['email']}: {e}")
            # Act as the master for own-scope endpoints.
            mapi = Api(args.api)
            mapi.login(mu["email"], user_pw)
        except Exception as e:
            print(f"  SKIP master {mu['email']}: {e}")
            stats["masters_skipped"] = stats.get("masters_skipped", 0) + 1
            continue
        # Services (match by name).
        local_svcs = rows(args.db, "SELECT * FROM services WHERE master_id="
                          "(SELECT id FROM master_profiles WHERE user_id=?)",
                          (mu["id"],))
        remote_svc = {}
        try:
            rs = mapi.get("/api/v1/admin/services")
            items = rs if isinstance(rs, list) else rs.get("items", [])
            for it in items:
                remote_svc[it["name"]] = it
        except Exception as e:
            print(f"  services list failed: {e}")
        svc_map = {}
        for s in local_svcs:
            if s["name"] in remote_svc:
                svc_map[s["id"]] = remote_svc[s["name"]]["id"]
                continue
            try:
                created = mapi.post("/api/v1/admin/services", {
                    "name": s["name"], "description": s["description"],
                    "duration_minutes": s["duration_minutes"],
                    "price": float(s["price"] or 0),
                })
            except Exception as e:
                print(f"  SKIP service '{s['name']}': {e}")
                continue
            svc_map[s["id"]] = created["id"]
            stats["services"] += 1
        # Bundles (match by name).
        try:
            remote_b = {b["name"]: b for b in mapi.get("/api/v1/admin/bundles")}
        except Exception as e:
            print(f"  bundles list failed: {e}")
            remote_b = {}
        bundle_map = {}
        for b in rows(args.db, "SELECT * FROM service_bundles WHERE "
                               "master_id=(SELECT id FROM master_profiles "
                               "WHERE user_id=?)", (mu["id"],)):
            import json as _json
            member_ids = _json.loads(b["service_ids"] or "[]")
            members = [svc_map[i] for i in member_ids if i in svc_map]
            if len(members) < 2:
                print(f"  SKIP bundle '{b['name']}': members missing")
                continue
            if b["name"] in remote_b:
                bundle_map[b["id"]] = remote_b[b["name"]]["id"]
                continue
            try:
                created = mapi.post("/api/v1/admin/bundles", {
                    "name": b["name"], "service_ids": members,
                })
            except Exception as e:
                print(f"  SKIP bundle '{b['name']}': {e}")
                continue
            bundle_map[b["id"]] = created["id"]
            stats["bundles"] += 1
        # Working hours (match by date+start, normalized: API may
        # return full ISO while sqlite stores trimmed strings).
        try:
            remote_h = {(str(h.get("schedule_date"))[:10],
                         str(h.get("start_time"))[:5])
                        for h in mapi.get("/api/v1/admin/working-hours")}
        except Exception as e:
            print(f"  hours list failed: {e}")
            remote_h = set()
        for h in rows(args.db, "SELECT * FROM working_hours WHERE master_id="
                               "(SELECT id FROM master_profiles WHERE user_id=?)",
                      (mu["id"],)):
            key = (str(h["schedule_date"])[:10], str(h["start_time"])[:5])
            if key in remote_h:
                continue
            try:
                mapi.post("/api/v1/admin/working-hours", {
                    "schedule_date": str(h["schedule_date"])[:10],
                    "start_time": str(h["start_time"])[:5],
                    "end_time": str(h["end_time"])[:5],
                })
                stats["hours"] += 1
            except Exception as e:
                print(f"  SKIP hours {key}: {e}")
                stats["appt_skipped"] += 1

    # Clients (match by email, then phone).
    staging_clients = {}
    page = 1
    while True:
        chunk = api.get("/api/v1/admin/clients",
                        {"page": page, "page_size": 200})
        items = chunk.get("items", []) if isinstance(chunk, dict) else chunk
        if not items:
            break
        for c in items:
            if c.get("email"):
                staging_clients[("e", c["email"])] = c
            if c.get("phone"):
                staging_clients[("p", c["phone"])] = c
        if isinstance(chunk, dict) and page >= chunk.get("total_pages", 1):
            break
        page += 1
    client_map = {}
    for cu in rows(args.db, "SELECT * FROM users WHERE role='CLIENT'"):
        key = (("e", cu["email"]) if cu["email"] else
               ("p", cu["phone"]) if cu["phone"] else None)
        if key is None:
            continue
        hit = staging_clients.get(key)
        if hit:
            client_map[cu["id"]] = hit["id"]
            stats["clients_skipped"] += 1
            continue
        try:
            created = api.post("/api/v1/admin/clients", {
                "name": cu["name"], "phone": cu["phone"], "email": cu["email"],
            })
        except Exception as e:
            print(f"  SKIP client {cu['email'] or cu['phone']}: {e}")
            stats["clients_skipped"] += 1
            continue
        client_map[cu["id"]] = created["id"]
        stats["clients"] += 1

    # Appointments (skip exact dupes by master+client+date on staging).
    for a in rows(args.db, "SELECT * FROM appointments"):
        # Resolve the staging master profile by the local master's email.
        mp_row = rows(args.db, "SELECT u.email FROM users u JOIN "
                               "master_profiles mp ON mp.user_id=u.id "
                               "WHERE mp.id=?", (a["master_id"],))
        if not mp_row or not mp_row[0]["email"]:
            stats["appt_skipped"] += 1
            continue
        sm = staging_masters.get(mp_row[0]["email"])
        if not sm:
            stats["appt_skipped"] += 1
            continue
        # Staging master profile id: look up via masters list (id field).
        smp_id = sm.get("master_profile_id", sm.get("id"))
        if a["client_id"] is not None and a["client_id"] not in client_map:
            stats["appt_skipped"] += 1
            continue
        payload = {
            "master_id": smp_id,
            "client_id": client_map.get(a["client_id"]),
            "appointment_date": str(a["appointment_date"])[:19],
            "status": a["status"] or "pending",
            "notes": a["notes"],
        }
        if a["bundle_id"]:
            # Bundle ids differ; match by name.
            bn = rows(args.db, "SELECT name FROM service_bundles WHERE id=?",
                      (a["bundle_id"],))
            if not bn:
                stats["appt_skipped"] += 1
                continue
            try:
                rb = api.get("/api/v1/admin/bundles")
                hit = next((x for x in rb if x["name"] == bn[0]["name"]), None)
            except Exception:
                hit = None
            if not hit:
                stats["appt_skipped"] += 1
                continue
            payload["bundle_id"] = hit["id"]
        else:
            sn = rows(args.db, "SELECT name FROM services WHERE id=?",
                      (a["service_id"],))
            if not sn:
                stats["appt_skipped"] += 1
                continue
            try:
                rs = api.get("/api/v1/admin/services")
                items = rs if isinstance(rs, list) else rs.get("items", [])
                hit = next((x for x in items
                            if x["name"] == sn[0]["name"]), None)
            except Exception:
                hit = None
            if not hit:
                stats["appt_skipped"] += 1
                continue
            payload["service_id"] = hit["id"]
        try:
            api.post("/api/v1/admin/appointments/book", payload)
            stats["appointments"] += 1
        except Exception as e:
            print(f"  SKIP appointment id={a['id']}: {e}")
            stats["appt_skipped"] += 1

    print("Summary:")
    for k, v in stats.items():
        print(f"  {k}={v}")


if __name__ == "__main__":
    main()
