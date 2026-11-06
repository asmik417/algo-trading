"""Pick lists (docs/API_CONTRACT.md -> Pick lists): CRUD rules, case-insensitive unique names, symbol cleaning,
watchlist runs from a list (list_id or symbols, exactly one), list_name at read time, delete keeps runs, the
?list_id= filter, and the in-place upgrade of an existing database. Synthetic market, no network.
"""
from sqlalchemy import create_engine, event, inspect, text

from app.services import pick_list_service, suggestion_service
from tests.test_suggestion_runs import _profile, market  # noqa: F401  (fixture)

API = "/api/v1/pick-lists"


def _create(client, name="Manager holdings", symbols=("GOODCO", "PRICEYCO"), expect=201):
    r = client.post(API, json={"name": name, "symbols": list(symbols)})
    assert r.status_code == expect, r.text
    return r.json()


# --- CRUD ------------------------------------------------------------------------------------------

def test_create_cleans_name_and_symbols(client):
    pl = _create(client, name="  Manager holdings  ", symbols=["hegam", " AMBER ", "", "Hegam", "TI"])
    assert set(pl) == {"id", "name", "symbols", "created_at", "updated_at"}
    assert pl["name"] == "Manager holdings" and pl["symbols"] == ["HEGAM", "AMBER", "TI"]  # order kept, deduped
    assert client.get(API).json() == [pl]


def test_duplicate_name_is_409_ignoring_case_and_spaces(client):
    first = _create(client, name="Manager holdings")
    _create(client, name="  manager HOLDINGS ", expect=409)
    other = _create(client, name="Momentum")
    assert client.put(f"{API}/{other['id']}", json={"name": "MANAGER holdings"}).status_code == 409
    renamed = client.put(f"{API}/{first['id']}", json={"name": "MANAGER Holdings"})  # own name, new case: fine
    assert renamed.status_code == 200 and renamed.json()["name"] == "MANAGER Holdings"


def test_validation(client):
    _create(client, name="   ", expect=400)
    _create(client, name="x" * 61, expect=400)
    _create(client, name="y" * 60, symbols=["TCS"])          # 60 chars is the limit
    _create(client, name="No symbols", symbols=[], expect=400)
    _create(client, name="Blank symbols", symbols=["", "  "], expect=400)
    _create(client, name="Too many", symbols=[f"S{i}" for i in range(51)], expect=400)
    assert client.post(API, json={"name": "Missing symbols"}).status_code == 400


def test_put_merges_and_unknown_ids_404(client):
    pl = _create(client, symbols=["TCS", "INFY"])
    renamed = client.put(f"{API}/{pl['id']}", json={"name": "Renamed"}).json()
    assert (renamed["name"], renamed["symbols"]) == ("Renamed", ["TCS", "INFY"])              # symbols kept
    replaced = client.put(f"{API}/{pl['id']}", json={"symbols": ["wipro", "tcs"]}).json()
    assert (replaced["name"], replaced["symbols"]) == ("Renamed", ["WIPRO", "TCS"])          # name kept
    assert client.put(f"{API}/{pl['id']}", json={"symbols": []}).status_code == 400
    assert client.put(f"{API}/999", json={"name": "x"}).status_code == 404
    assert client.delete(f"{API}/999").status_code == 404


def test_get_is_ordered_by_updated_at_desc(client, monkeypatch):
    a = _create(client, name="A")
    b = _create(client, name="B")
    assert [p["name"] for p in client.get(API).json()] == ["B", "A"]  # same second: newest id first
    monkeypatch.setattr(pick_list_service, "utc_now_iso", lambda: "2099-01-01T00:00:00Z")
    client.put(f"{API}/{a['id']}", json={"symbols": ["TCS"]})
    assert [p["name"] for p in client.get(API).json()] == ["A", "B"]
    assert b["id"] != a["id"]


def test_requires_login(anon_client):
    assert anon_client.get(API).status_code == 401
    assert anon_client.post(API, json={"name": "x", "symbols": ["TCS"]}).status_code == 401


# --- watchlist runs from a list ----------------------------------------------------------------------

def _inline(monkeypatch):
    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", suggestion_service.execute_watchlist_run)


def _watch(client, pid, expect=202, **body):
    r = client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json=body)
    assert r.status_code == expect, r.text
    return r.json()


def test_run_from_list_copies_current_symbols_and_names_the_list(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    pl = _create(client, name="Holdings", symbols=["PRICEYCO", "GOODCO", "NOPE"])
    run = _watch(client, pid, list_id=pl["id"])
    assert (run["kind"], run["list_id"], run["list_name"], run["symbols"]) == \
        ("watchlist", pl["id"], "Holdings", ["PRICEYCO", "GOODCO", "NOPE"])
    results = client.get(f"/api/v1/runs/{run['id']}/results").json()
    assert [i["symbol"] for i in results["items"]] == ["PRICEYCO", "GOODCO", "NOPE"]

    # Editing the list later changes neither the run's symbols nor its results; list_name is read live.
    client.put(f"/api/v1/pick-lists/{pl['id']}", json={"name": "Holdings v2", "symbols": ["TCS"]})
    after = client.get(f"/api/v1/runs/{run['id']}").json()
    assert (after["symbols"], after["list_name"]) == (["PRICEYCO", "GOODCO", "NOPE"], "Holdings v2")
    assert len(client.get(f"/api/v1/runs/{run['id']}/results").json()["items"]) == 3

    adhoc = _watch(client, pid, symbols=["GOODCO"])
    assert (adhoc["list_id"], adhoc["list_name"]) == (None, None)
    full = client.post(f"/api/v1/profiles/{pid}/runs").json()
    assert (full["list_id"], full["list_name"], full["symbols"]) == (None, None, None)


def test_exactly_one_of_list_id_or_symbols(client, market, monkeypatch):  # noqa: F811
    monkeypatch.setattr(suggestion_service, "_spawn_watchlist", lambda run_id: None)
    pid = _profile(client)
    pl = _create(client)
    _watch(client, pid, expect=400)                                               # neither
    _watch(client, pid, expect=400, list_id=pl["id"], symbols=["TCS"])            # both
    _watch(client, pid, expect=404, list_id=999)                                  # unknown list
    _watch(client, pid, expect=400, symbols=[])                                   # symbols given but empty
    assert client.post(f"/api/v1/profiles/{pid}/watchlist-runs", json={"list_id": "x"}).status_code == 400


def test_deleting_a_list_keeps_its_runs(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    pl = _create(client, symbols=["GOODCO"])
    run = _watch(client, pid, list_id=pl["id"])
    assert client.delete(f"/api/v1/pick-lists/{pl['id']}").status_code == 204
    assert client.get("/api/v1/pick-lists").json() == []
    kept = client.get(f"/api/v1/runs/{run['id']}").json()
    assert (kept["status"], kept["list_id"], kept["list_name"], kept["symbols"]) == ("done", None, None, ["GOODCO"])
    assert client.get(f"/api/v1/runs/{run['id']}/results").json()["items"][0]["symbol"] == "GOODCO"


def test_watchlist_runs_list_id_filter(client, market, monkeypatch):  # noqa: F811
    _inline(monkeypatch)
    pid = _profile(client)
    a = _create(client, name="A", symbols=["GOODCO"])
    b = _create(client, name="B", symbols=["PRICEYCO"])
    a1 = _watch(client, pid, list_id=a["id"])
    b1 = _watch(client, pid, list_id=b["id"])
    a2 = _watch(client, pid, list_id=a["id"])
    adhoc = _watch(client, pid, symbols=["GOODCO"])
    base = f"/api/v1/profiles/{pid}/watchlist-runs"
    assert [r["id"] for r in client.get(f"{base}?list_id={a['id']}").json()] == [a2["id"], a1["id"]]
    assert [r["id"] for r in client.get(f"{base}?list_id={a['id']}&limit=1").json()] == [a2["id"]]  # latest only
    assert [r["id"] for r in client.get(f"{base}?list_id={b['id']}").json()] == [b1["id"]]
    assert [r["id"] for r in client.get(base).json()] == [adhoc["id"], a2["id"], b1["id"], a1["id"]]  # all
    assert client.get(f"{base}?list_id=999").json() == []


# --- upgrading an existing database in place -------------------------------------------------------------

def test_existing_database_gains_pick_lists_and_list_id_in_place(tmp_path, monkeypatch):
    """Mirrors the live DB: suggestion_runs exists (with data) but has no list_id and there is no pick_lists."""
    from app.db import session as db_session

    old = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    event.listen(old, "connect", db_session._sqlite_pragmas)
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE profiles (id INTEGER PRIMARY KEY, name VARCHAR(120) NOT NULL UNIQUE, "
                          "owner VARCHAR(80) NOT NULL, params_json TEXT NOT NULL, is_active BOOLEAN NOT NULL, "
                          "created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)"))
        conn.execute(text("CREATE TABLE suggestion_runs (id INTEGER PRIMARY KEY, profile_id INTEGER NOT NULL "
                          "REFERENCES profiles(id) ON DELETE CASCADE, trading_day VARCHAR(10), status VARCHAR(16) "
                          "NOT NULL, kind VARCHAR(16) NOT NULL DEFAULT 'full', symbols_json TEXT, item_errors_json "
                          "TEXT, universe_size INTEGER, scored_size INTEGER, passed_size INTEGER, params_json TEXT "
                          "NOT NULL, error TEXT, started_at VARCHAR(32), finished_at VARCHAR(32), created_at "
                          "VARCHAR(32) NOT NULL)"))
        conn.execute(text("INSERT INTO profiles VALUES (1, 'P', 'R', '{}', 1, 'x', 'x')"))
        conn.execute(text("INSERT INTO suggestion_runs (id, profile_id, status, params_json, created_at) "
                          "VALUES (7, 1, 'done', '{}', 'x')"))
    monkeypatch.setattr(db_session, "engine", old)
    db_session.init_db()

    insp = inspect(old)
    assert "pick_lists" in insp.get_table_names()
    assert "list_id" in {c["name"] for c in insp.get_columns("suggestion_runs")}
    with old.begin() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM suggestion_runs")).scalar() == 1  # data kept
        conn.execute(text("INSERT INTO pick_lists (id, name, symbols_json, created_at, updated_at) "
                          "VALUES (3, 'L', '[\"TCS\"]', 'x', 'x')"))
        conn.execute(text("UPDATE suggestion_runs SET list_id = 3 WHERE id = 7"))
        conn.execute(text("DELETE FROM pick_lists WHERE id = 3"))
        assert conn.execute(text("SELECT list_id FROM suggestion_runs WHERE id = 7")).scalar() is None  # set null
    db_session.init_db()  # idempotent


def test_broken_constant_name_index_is_repaired(tmp_path, monkeypatch):
    """A DB created by the short-lived build with lower('name') (constant) must end up allowing many lists."""
    from app.db import session as db_session

    old = create_engine(f"sqlite:///{tmp_path / 'bad_index.db'}")
    event.listen(old, "connect", db_session._sqlite_pragmas)
    with old.begin() as conn:
        conn.execute(text("CREATE TABLE pick_lists (id INTEGER PRIMARY KEY, name VARCHAR(60) NOT NULL, "
                          "symbols_json TEXT NOT NULL, created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)"))
        conn.execute(text("CREATE UNIQUE INDEX uq_pick_lists_name_ci ON pick_lists (lower('name'))"))
    monkeypatch.setattr(db_session, "engine", old)
    db_session.init_db()
    with old.begin() as conn:
        sql = conn.execute(text("SELECT sql FROM sqlite_master WHERE name='uq_pick_lists_name_ci'")).scalar()
        assert "lower(name)" in sql and "'name'" not in sql
        for i, name in enumerate(["A", "B"], start=1):  # two lists now fit
            conn.execute(text("INSERT INTO pick_lists VALUES (:i, :n, '[]', 'x', 'x')"), {"i": i, "n": name})
    import pytest
    from sqlalchemy.exc import IntegrityError
    with pytest.raises(IntegrityError), old.begin() as conn:  # and the case-insensitive rule still holds
        conn.execute(text("INSERT INTO pick_lists VALUES (3, 'a', '[]', 'x', 'x')"))


def test_new_list_name_is_reserved(client):
    for name in ("New list…", "new list...", "  NEW LIST…  ", "New List..."):
        r = client.post(API, json={"name": name, "symbols": ["TCS"]})
        assert r.status_code == 400 and "reserved" in r.json()["detail"], name
    pl = _create(client, name="New list for Q4")                       # only the exact menu label is reserved
    assert client.put(f"{API}/{pl['id']}", json={"name": "new list…"}).status_code == 400  # rename too
    assert _create(client, name="New list. . .")["name"] == "New list. . ."
