"""Step 3: profile endpoints — seed, param spec, create / update / activate / delete, and validation errors.
Every response is checked against the contract shapes in docs/API_CONTRACT.md.
"""
from app.engine.params import DEFAULTS

API = "/api/v1/profiles"
PROFILE_KEYS = {"id", "name", "owner", "is_active", "params", "params_summary", "created_at", "updated_at"}


def _create(client, name="Manager – Quality Large Caps", owner="Manager", params=None):
    body = {"name": name, "owner": owner}
    if params is not None:
        body["params"] = params
    return client.post(API, json=body)


def test_first_startup_seeds_one_active_default(client):
    profiles = client.get(API).json()
    assert len(profiles) == 1
    p = profiles[0]
    assert set(p) == PROFILE_KEYS
    assert (p["name"], p["owner"], p["is_active"]) == ("Default – Balanced", "Roshan", True)
    assert p["params"] == DEFAULTS
    assert p["params_summary"] == "score ≥ 65, top 10, Medium (1-3 months), P/E ≤ 50, ROE ≥ 15%, RSI 45-70"
    assert p["created_at"].endswith("Z")
    assert client.get(f"{API}/active").json()["id"] == p["id"]


def test_param_spec_shape(client):
    spec = client.get(f"{API}/param-spec").json()
    assert set(spec) == {"defaults", "horizons", "cap_buckets", "sections"}
    assert spec["defaults"] == DEFAULTS
    assert spec["cap_buckets"] == ["Large Cap", "Mid Cap", "Small Cap", "Unknown"]
    keys = [f["key"] for s in spec["sections"] for f in s["fields"]]
    assert set(keys) == set(DEFAULTS)
    caps = next(f for s in spec["sections"] for f in s["fields"] if f["key"] == "allowed_caps")
    assert caps["type"] == "multiselect" and "min" not in caps  # optional keys are omitted, not null


def test_create_merges_defaults_and_is_not_active(client):
    r = _create(client, params={"allowed_caps": ["Large Cap"], "min_roe_pct": 15, "max_pe": 40,
                                "w_fundamental_quality": 25, "w_earnings_acceleration": 20, "w_technical_setup": 10,
                                "w_early_price_position": 15, "w_valuation": 15})
    assert r.status_code == 201, r.text
    p = r.json()
    assert p["is_active"] is False
    assert p["params"]["allowed_caps"] == ["Large Cap"]
    assert p["params"]["min_roe_pct"] == 15.0
    assert p["params"]["rsi_min"] == DEFAULTS["rsi_min"]  # untouched keys take defaults
    assert isinstance(p["params"]["w_technical_setup"], int)
    assert client.get(f"{API}/{p['id']}").json() == p


def test_update_is_partial(client):
    pid = _create(client).json()["id"]
    r = client.put(f"{API}/{pid}", json={"owner": "MD", "params": {"rsi_min": 50, "rsi_max": 80}})
    assert r.status_code == 200, r.text
    p = r.json()
    assert p["owner"] == "MD" and p["name"] == "Manager – Quality Large Caps"
    assert (p["params"]["rsi_min"], p["params"]["rsi_max"]) == (50.0, 80.0)
    assert p["params_summary"].endswith("RSI 50-80")

    r = client.put(f"{API}/{pid}", json={"params": {"horizon": "Short (2-6 weeks)"}})
    assert r.json()["params"]["rsi_min"] == 50.0  # earlier change kept


def test_activate_switches_exactly_one(client):
    default_id = client.get(f"{API}/active").json()["id"]
    pid = _create(client).json()["id"]
    r = client.post(f"{API}/{pid}/activate")
    assert r.status_code == 200 and r.json()["is_active"] is True
    active = [p["id"] for p in client.get(API).json() if p["is_active"]]
    assert active == [pid]
    assert client.get(f"{API}/{default_id}").json()["is_active"] is False


def test_invalid_weights_rejected(client):
    r = _create(client, params={"w_valuation": 40})  # sums to 125
    assert r.status_code == 400
    assert "must add up to 100" in r.json()["detail"]


def test_invalid_types_ranges_and_unknown_keys_rejected(client):
    r = _create(client, params={"rsi_min": "high", "min_price": 0, "horizon": "Forever", "colour": "red"})
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Unknown parameter: colour" in detail
    assert "RSI minimum: must be a number" in detail
    assert "Minimum share price (₹): 0 is below the minimum 1" in detail
    assert "Preferred holding horizon: must be one of" in detail

    r = _create(client, params={"rsi_min": 80, "rsi_max": 70})
    assert r.status_code == 400 and "RSI minimum must be below RSI maximum" in r.json()["detail"]

    pid = _create(client, name="Valid one").json()["id"]
    r = client.put(f"{API}/{pid}", json={"params": {"allowed_caps": []}})
    assert r.status_code == 400
    assert client.get(f"{API}/{pid}").json()["params"]["allowed_caps"] == DEFAULTS["allowed_caps"]  # unchanged


def test_bad_body_and_missing_ids(client):
    r = client.post(API, json={"owner": "x"})  # no name
    assert r.status_code == 400 and r.json()["detail"].startswith("name")
    assert client.post(API, json={"name": "  ", "owner": "x"}).status_code == 400
    assert client.get(f"{API}/9999").status_code == 404
    assert client.get(f"{API}/9999").json() == {"detail": "Profile 9999 not found."}
    assert client.put(f"{API}/9999", json={"owner": "x"}).status_code == 404
    assert client.post(f"{API}/9999/activate").status_code == 404


def test_duplicate_name_conflicts(client):
    assert _create(client, name="Same").status_code == 201
    assert _create(client, name="Same").status_code == 409


def test_delete_active_hands_over_and_last_delete_leaves_none(client):
    default_id = client.get(f"{API}/active").json()["id"]
    other_id = _create(client).json()["id"]
    assert client.delete(f"{API}/{default_id}").status_code == 204
    assert client.get(f"{API}/active").json()["id"] == other_id
    assert client.delete(f"{API}/{other_id}").status_code == 204
    assert client.get(API).json() == []
    assert client.get(f"{API}/active").status_code == 404
    assert client.delete(f"{API}/{other_id}").status_code == 404


def test_seed_profiles_are_valid_and_idempotent(clean_db, capsys):
    import importlib.util
    import json
    from pathlib import Path

    from app.db.session import SessionLocal
    from app.engine.params import ScreenParams
    from app.models import Profile

    old_defaults = {**DEFAULTS, "min_score": 60.0, "max_pe": 60.0}
    old_defaults.pop("max_dist_from_52w_high_pct")  # stored before the field existed
    with SessionLocal() as db:
        db.add_all([Profile(name="Default – Balanced", owner="Roshan", params_json=json.dumps(old_defaults), is_active=True),
                    Profile(name="MD – Momentum", owner="MD", params_json="{}")])
        db.commit()

    spec = importlib.util.spec_from_file_location("seed", Path(__file__).resolve().parents[1] / "scripts" / "seed_profiles.py")
    seed = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(seed)
    assert seed.main() == 0
    assert seed.main() == 0
    out = capsys.readouterr().out
    assert out.count("created") == 3 and out.count("updated") == 1 and out.count("skip") == 4  # 2nd run: all skips

    with SessionLocal() as db:
        by_name = {p.name: p for p in db.query(Profile)}
        assert set(by_name) == {"Default – Balanced", "MD – Momentum", "Developer suggested – Quality Momentum",
                                "Conservative – Large Caps", "Aggressive – Breakouts"}  # nothing deleted
        assert [n for n, p in by_name.items() if p.is_active] == ["Developer suggested – Quality Momentum"]
        assert json.loads(by_name["Default – Balanced"].params_json) == DEFAULTS  # replaced in place, new key included
        for name in ("Developer suggested – Quality Momentum", "Conservative – Large Caps", "Aggressive – Breakouts"):
            params = ScreenParams.from_json(by_name[name].params_json)
            assert params.validate() == [] and sum(params.weights.values()) == 100
        cons = ScreenParams.from_json(by_name["Conservative – Large Caps"].params_json)
        assert (cons.allowed_caps, cons.min_roe_pct, cons.horizon) == (["Large Cap"], 18.0, "Long (3-6 months)")
        aggr = ScreenParams.from_json(by_name["Aggressive – Breakouts"].params_json)
        assert (aggr.w_technical_setup, aggr.min_volume_ratio, aggr.horizon) == (30, 1.5, "Short (2-6 weeks)")
