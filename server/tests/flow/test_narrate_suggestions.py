"""SSE-shape tests for `consume_narrate` and `run_narrate` around the new
`suggestions` field — that the parser-final → SSE wiring stays correct, and
that the reject branch blanks suggestions like the other meta fields.
"""

from collections.abc import AsyncIterator

from src.agents.narrate import NarrativeDelta, NarrativeFinal
from src.agents.narrate.schema import NarrateOutput
from src.flow.dirty import Dirty
from src.flow.narrate import consume_narrate


async def _stream(*items) -> AsyncIterator[NarrativeDelta | NarrativeFinal]:
    for it in items:
        yield it


async def _collect(it):
    out = []
    async for ev in it:
        out.append(ev)
    return out


async def test_consume_narrate_emits_suggestions_event(fresh_state):
    final = NarrativeFinal(
        body="본문.",
        output=NarrateOutput(
            turn_summary="요약",
            suggestions=["광장 상인에게 다가간다", "골목으로 향한다"],
        ),
    )
    events = await _collect(
        consume_narrate(
            fresh_state,
            Dirty(),
            _stream(NarrativeDelta(text="본문."), final),
            target_for_log=None,
            dialogue_input=None,
        )
    )
    types = [e["type"] for e in events]
    assert "suggestions" in types
    sug = next(e for e in events if e["type"] == "suggestions")
    assert sug["data"]["items"] == ["광장 상인에게 다가간다", "골목으로 향한다"]


async def test_consume_narrate_emits_empty_suggestions_when_none(fresh_state):
    final = NarrativeFinal(body="본문.", output=NarrateOutput())
    events = await _collect(
        consume_narrate(
            fresh_state,
            Dirty(),
            _stream(final),
            target_for_log=None,
            dialogue_input=None,
        )
    )
    sug = next(e for e in events if e["type"] == "suggestions")
    assert sug["data"]["items"] == []


async def test_run_narrate_reject_blanks_suggestions(fresh_state, monkeypatch):
    """run_narrate's reject branch must blank suggestions on the final, in
    addition to the existing memory/state fields, so the engine doesn't
    surface stale chips for an OOC input the LLM didn't know to clear.
    """
    from src.agents import narrate as narrate_agent
    from src.flow import narrate as narrate_flow

    fresh_state.locations["loc_01"] = (
        type(  # minimal stand-in; surroundings expects nothing more for player loc
            "L", (), {}
        )
    )  # pragma: no cover — not reached, surroundings/world stubbed below

    async def fake_stream_narrate(client, input_):
        yield NarrativeFinal(
            body="혼란.",
            output=NarrateOutput(
                turn_summary="혼란",
                suggestions=["없어야 함", "또 없어야 함"],
            ),
        )

    monkeypatch.setattr(narrate_agent, "stream_narrate", fake_stream_narrate)
    monkeypatch.setattr(narrate_flow, "stream_narrate", fake_stream_narrate)

    monkeypatch.setattr(narrate_flow, "build_world_layer", lambda *_: "")
    monkeypatch.setattr(narrate_flow, "build_session_layer", lambda *_: {})
    monkeypatch.setattr(narrate_flow, "build_history_layer", lambda *_: "")
    monkeypatch.setattr(narrate_flow, "build_surroundings", lambda *_: {})
    monkeypatch.setattr(narrate_flow, "build_player_view", lambda *_: {})

    from src.ontology.graph import GameGraph

    # reject branch never consumes the graph (no target_view assembly), so an
    # empty placeholder is fine — and avoids build_graph choking on the
    # bare-class Location stand-in this test wires into state.locations.
    items = []
    async for it in narrate_flow.run_narrate(
        client=None,
        state=fresh_state,
        profile_dir="<unused>",
        player_input="ooc",
        judge_result={"action": "reject"},
        graph=GameGraph(),
    ):
        items.append(it)

    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].output.suggestions == []
