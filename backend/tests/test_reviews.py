"""Step 9: loss reviews — tags match docs/DATA_MODEL.md, pending vs reviewed, create/update rules, tag summary.
Reuses the tracker's synthetic price world.
"""
import re
from pathlib import Path

from tests.test_tracker import _mark, _open, world  # noqa: F401  (fixture)

DATA_MODEL = Path(__file__).resolve().parents[2] / "docs" / "DATA_MODEL.md"


def test_tags_match_data_model(client):
    section = DATA_MODEL.read_text().split("Fixed reason tags", 1)[1].split("\n\n", 1)[0]
    keys = re.findall(r"`([a-z_]+)`", section.split("\n", 1)[1])
    tags = client.get("/api/v1/reviews/tags").json()
    assert [t["key"] for t in tags] == keys
    assert tags[0] == {"key": "bought_extended", "label": "Bought when already extended"}
    assert all(t["label"] for t in tags)


def _two_losses_one_win(client, world):  # noqa: F811
    pid = world["pid"]
    a = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    b = _open(client, pid, world["suggest"](pid, "BBB")).json()["id"]
    c = _open(client, pid, world["suggest"](pid, "CCC")).json()["id"]
    world["set"]("2026-11-06", AAA={"2026-11-05": 88.0}, BBB={"2026-11-06": 85.0}, CCC={"2026-11-06": 125.0})
    _mark("2026-11-06")
    return pid, a, b, c


BODY = {"reasons": ["stop_too_tight", "whole_market_fell"], "mistakes": " Entered on a gap-up ",
        "lesson": "Wait for a retest", "algo_change": "Widen stop to 2.5x ATR"}


def test_review_flow(client, world):  # noqa: F811
    pid, a, b, c = _two_losses_one_win(client, world)
    losses = client.get(f"/api/v1/profiles/{pid}/losses").json()
    assert [p["symbol"] for p in losses["pending"]] == ["BBB", "AAA"] and losses["reviewed"] == []
    assert all(p["needs_review"] for p in losses["pending"])

    r = client.post(f"/api/v1/positions/{a}/review", json=BODY)
    assert r.status_code == 201, r.text
    rev = r.json()
    assert (rev["symbol"], rev["pnl"], rev["pnl_pct"], rev["close_reason"], rev["closed_on"]) == \
        ("AAA", -1200.0, -12.0, "stop_hit", "2026-11-05")
    assert rev["reasons"] == ["stop_too_tight", "whole_market_fell"] and rev["mistakes"] == "Entered on a gap-up"

    losses = client.get(f"/api/v1/profiles/{pid}/losses").json()
    assert [p["symbol"] for p in losses["pending"]] == ["BBB"] and [x["id"] for x in losses["reviewed"]] == [rev["id"]]
    assert client.get(f"/api/v1/positions/{a}").json()["needs_review"] is False
    assert client.get(f"/api/v1/profiles/{pid}/stats").json()["pending_reviews"] == 1

    assert client.post(f"/api/v1/positions/{a}/review", json=BODY).status_code == 409   # already reviewed
    assert client.post(f"/api/v1/positions/{c}/review", json=BODY).status_code == 409   # a win, not a loss
    assert client.post("/api/v1/positions/99999/review", json=BODY).status_code == 404
    assert client.post(f"/api/v1/positions/{b}/review", json={**BODY, "reasons": ["bad_luck"]}).status_code == 400
    assert client.post(f"/api/v1/positions/{b}/review", json={**BODY, "reasons": []}).status_code == 400
    assert client.post(f"/api/v1/positions/{b}/review", json={"reasons": ["other"]}).status_code == 400  # fields required

    upd = client.put(f"/api/v1/reviews/{rev['id']}", json={**BODY, "reasons": ["bought_extended", "bought_extended"]})
    assert upd.status_code == 200 and upd.json()["reasons"] == ["bought_extended"]
    assert client.put("/api/v1/reviews/99999", json=BODY).status_code == 404


def test_open_position_cannot_be_reviewed(client, world):  # noqa: F811
    pid = world["pid"]
    pos = _open(client, pid, world["suggest"](pid, "AAA")).json()["id"]
    assert client.post(f"/api/v1/positions/{pos}/review", json=BODY).status_code == 409


def test_summary(client, world):  # noqa: F811
    pid, a, b, _ = _two_losses_one_win(client, world)
    client.post(f"/api/v1/positions/{a}/review", json=BODY)
    client.post(f"/api/v1/positions/{b}/review", json={**BODY, "reasons": ["whole_market_fell", "sector_news"]})
    s = client.get(f"/api/v1/profiles/{pid}/losses/summary").json()
    assert (s["total_losses"], s["reviewed"], s["avg_loss_pct"]) == (2, 2, -13.5)
    assert s["by_tag"] == [
        {"key": "whole_market_fell", "label": "Whole market fell", "count": 2},
        {"key": "stop_too_tight", "label": "Stop-loss was too tight", "count": 1},
        {"key": "sector_news", "label": "Sector news", "count": 1},
    ]
    empty = client.post("/api/v1/profiles", json={"name": "Empty", "owner": "x"}).json()["id"]
    assert client.get(f"/api/v1/profiles/{empty}/losses/summary").json() == \
        {"total_losses": 0, "reviewed": 0, "by_tag": [], "avg_loss_pct": None}
    assert client.get("/api/v1/profiles/999/losses").status_code == 404
