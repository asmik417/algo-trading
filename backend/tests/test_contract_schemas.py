"""Keeps app/schemas in lock-step with docs/API_CONTRACT.md by parsing its TypeScript interfaces.
If the guide changes the contract, this test names exactly which fields drifted.
"""
import re
from pathlib import Path

import pytest

from app.engine.params import CAP_BUCKETS
from app.engine.scoring import signal as engine_signal
from app.engine.scoring import stage as engine_stage
from app.schemas import auth, health, job, position, profile, review, run, stock, suggestion

CONTRACT = Path(__file__).resolve().parents[2] / "docs" / "API_CONTRACT.md"

# TS interface name -> Pydantic model
MODELS = {
    "ParamField": profile.ParamField,
    "ParamSection": profile.ParamSection,
    "ParamSpec": profile.ParamSpec,
    "Profile": profile.Profile,
    "RunProgress": run.RunProgress,
    "Run": run.Run,
    "SuggestionSummary": suggestion.SuggestionSummary,
    "Reasons": suggestion.Reasons,
    "Plan": suggestion.Plan,
    "PillarScore": suggestion.PillarScore,
    "Indicators": suggestion.Indicators,
    "Fundamentals": suggestion.Fundamentals,
    "ChartData": suggestion.ChartData,
    "FilterResult": suggestion.FilterResult,
    "SuggestionDetail": suggestion.SuggestionDetail,
    "SuggestionsResponse": suggestion.SuggestionsResponse,
    "StockRow": stock.StockRow,
    "StocksResponse": stock.StocksResponse,
    "StockDetail": stock.StockDetail,
    "Position": position.Position,
    "Mark": position.Mark,
    "PositionEvent": position.PositionEvent,
    "Benchmark": position.Benchmark,
    "PositionDetail": position.PositionDetail,
    "ProfileStats": position.ProfileStats,
    "ReviewTag": review.ReviewTag,
    "Review": review.Review,
    "LossesResponse": review.LossesResponse,
    "LossSummary": review.LossSummary,
    "JobStatus": job.JobStatus,
    "Health": health.Health,
    "Me": auth.Me,
    "WatchlistHit": suggestion.WatchlistHit,
    "WatchlistMiss": suggestion.WatchlistMiss,
    "WatchlistResults": suggestion.WatchlistResults,
}


# Request bodies: every non-optional contract field must be required by the schema.
REQUEST_MODELS = {
    "CreateProfileBody": profile.CreateProfileBody,
    "UpdateProfileBody": profile.UpdateProfileBody,
    "StartRunBody": run.StartRunBody,
    "CreatePositionBody": position.CreatePositionBody,
    "ChangeExitBody": position.ChangeExitBody,
    "ClosePositionBody": position.ClosePositionBody,
    "NoteBody": position.NoteBody,
    "ReviewBody": review.ReviewBody,
    "LoginBody": auth.LoginBody,
    "WatchlistRunBody": run.WatchlistRunBody,
}


def _ts_interfaces() -> dict[str, tuple[list[str], set[str], set[str]]]:
    """name -> (field names incl. inherited, optional (`?`) names, nullable (`| null`) names)."""
    text = CONTRACT.read_text()
    # The contract has several ```ts blocks (Auth near the top, the main block near the end); read them all.
    block = "\n".join(part.split("```", 1)[0] for part in text.split("```ts")[1:])
    raw: dict[str, tuple[str | None, str]] = {}
    for m in re.finditer(r"export interface (\w+)(?: extends (\w+))? \{(.*?)\}\s*$", block, re.M):
        raw[m.group(1)] = (m.group(2), m.group(3))

    def fields(name: str) -> tuple[list[str], set[str], set[str]]:
        parent, body = raw[name]
        # Strip inline object types ({ symbol: string; ... }) so only top-level keys remain.
        while "{" in body:
            body = re.sub(r"\{[^{}]*\}", "X", body)
        keys, optional, nullable = [], set(), set()
        for part in body.split(";"):
            fm = re.match(r"\s*(\w+)(\?)?\s*:(.*)", part)
            if fm:
                keys.append(fm.group(1))
                if fm.group(2):
                    optional.add(fm.group(1))
                if re.search(r"(^|\|)\s*null\s*$", fm.group(3).strip()):  # `X | null` or plain `null`
                    nullable.add(fm.group(1))
        if parent:
            pk, po, pn = fields(parent)
            keys, optional, nullable = pk + keys, po | optional, pn | nullable
        return keys, optional, nullable

    return {name: fields(name) for name in raw}


TS = _ts_interfaces()


def test_every_contract_interface_has_a_schema():
    mapped = set(MODELS) | set(REQUEST_MODELS)
    assert set(TS) == mapped, f"unmapped: {set(TS) ^ mapped}"


@pytest.mark.parametrize("name", sorted(REQUEST_MODELS))
def test_request_bodies_match_contract(name):
    ts_fields, ts_optional, _ = TS[name]
    model_fields = REQUEST_MODELS[name].model_fields
    assert set(model_fields) == set(ts_fields), (
        f"{name}: missing {set(ts_fields) - set(model_fields)}, extra {set(model_fields) - set(ts_fields)}"
    )
    for key in ts_fields:
        assert model_fields[key].is_required() == (key not in ts_optional), f"{name}.{key} required-ness differs"


def _enumeration(label: str) -> list[str]:
    section = CONTRACT.read_text().split("## Enumerations", 1)[1].split("\n## ", 1)[0]
    line = next(ln for ln in section.splitlines() if ln.startswith(f"`{label}`"))
    return re.findall(r"`([^`]+)`", line.split(":", 1)[1])


def test_enumerations_pinned_to_engine():
    assert _enumeration("signal") == list(engine_signal.SIGNALS.values())
    assert _enumeration("stage") == list(engine_stage.STAGES)
    assert _enumeration("market_cap_bucket") == list(CAP_BUCKETS)


@pytest.mark.parametrize("name", sorted(MODELS))
def test_schema_fields_match_contract(name):
    ts_fields, ts_optional, ts_nullable = TS[name]
    model = MODELS[name]
    model_fields = model.model_fields
    assert set(model_fields) == set(ts_fields), (
        f"{name}: missing {set(ts_fields) - set(model_fields)}, extra {set(model_fields) - set(ts_fields)}"
    )
    for key in ts_optional:
        assert not model_fields[key].is_required(), f"{name}.{key} is optional in the contract"
    schema = model.model_json_schema()["properties"]
    for key in ts_fields:
        prop = schema[key]
        accepts_null = prop.get("type") == "null" or any(alt.get("type") == "null" for alt in prop.get("anyOf", []))
        if key in ts_nullable:
            assert accepts_null, f"{name}.{key} must accept null"
        elif key not in ts_optional:
            assert not accepts_null, f"{name}.{key} is never null in the contract"
