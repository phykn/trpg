from pathlib import Path

import pytest

from agency import run_qa
from agency.qa.harness import runner
from agency.qa.harness.transcript import append_transcript_block
from src.db.scenario.local_fs import LocalFsScenarioRepo


def test_qa_defaults_to_dev_test_and_isolated_output_root():
    parser = run_qa._build_parser()

    args = parser.parse_args([])

    assert args.profile == "dev_test"
    assert run_qa.QA_RUN_ROOT == run_qa.ROOT / "qa_test" / "agency"


def test_socialite_persona_is_short_transition_probe():
    text = (run_qa.ROOT / "agency" / "qa" / "agents" / "socialite.md").read_text(
        encoding="utf-8"
    )

    assert "| 12 |" in text
    assert "| 13 |" not in text
    assert "protected=false인 우호/동료 NPC 공격은 버그가 아니다" in text
    assert "우호 NPC 공격 금지" not in text
    assert "출력에는 `X`, `타깃`, `NPC` 같은 대명사를 쓰지 말고 실제 이름을 쓴다" in text


def test_qa_scenario_repo_is_local_and_resolves_like_server(monkeypatch):
    monkeypatch.delenv("SUPABASE_URL", raising=False)
    monkeypatch.delenv("SUPABASE_SERVICE_KEY", raising=False)
    monkeypatch.delenv("SUPABASE_SCENARIO_BUCKET", raising=False)
    monkeypatch.setenv("SCENARIO_DIR", "../scenarios")

    repo = runner._build_scenario_repo()

    assert isinstance(repo, LocalFsScenarioRepo)
    assert Path(repo.profile_dir) == (runner.ROOT / "server" / "../scenarios").resolve()


def test_qa_runner_builds_roll_request_for_public_pending_roll():
    request = runner._pending_resolution_request(
        "game-1",
        {
            "pendingConfirmation": None,
            "pendingRoll": {
                "id": "roll-1",
                "kind": "perceive",
                "title": "지력 판정이 필요합니다",
                "stat": "mind",
                "statLabel": "지력",
                "requiredRoll": 13,
            },
        },
    )

    assert request == (
        "roll",
        "/session/game-1/graph/roll",
        {"roll_id": "roll-1"},
        {
            "id": "roll-1",
            "kind": "perceive",
            "title": "지력 판정이 필요합니다",
            "stat": "mind",
            "statLabel": "지력",
            "requiredRoll": 13,
        },
    )


def test_qa_transcript_formats_public_pending_roll(tmp_path):
    transcript_path = tmp_path / "transcript.md"

    append_transcript_block(
        transcript_path,
        turn_no=1,
        kind="roll",
        pending={
            "id": "roll-1",
            "kind": "perceive",
            "title": "지력 판정이 필요합니다",
            "body": "자세히 살펴보려면 집중해야 합니다.",
            "stat": "mind",
            "statLabel": "지력",
            "requiredRoll": 13,
        },
    )

    text = transcript_path.read_text(encoding="utf-8")
    assert "**굴림 대기**: 지력 (13+ 필요)" in text
    assert "자세히 살펴보려면 집중해야 합니다." in text


def test_qa_turn_body_omits_stale_log_when_pending_resolution_exists():
    result = {"message": None}
    front = {
        "log": [
            {"kind": "gm", "text": "이전 GM 응답"},
        ],
        "pendingRoll": {
            "id": "roll-1",
            "kind": "speak",
            "title": "매력 판정이 필요합니다",
        },
    }

    assert runner._turn_body(result, front) == ""


def test_qa_turn_body_uses_log_when_no_pending_resolution_exists():
    result = {"message": None}
    front = {
        "log": [
            {"kind": "gm", "text": "새 GM 응답"},
        ],
        "pendingRoll": None,
        "pendingConfirmation": None,
    }

    assert runner._turn_body(result, front) == "새 GM 응답"


@pytest.mark.asyncio
async def test_qa_single_run_uses_env_llm_profiles_without_base_url(
    monkeypatch, tmp_path
):
    calls: dict[str, object] = {}

    class FakeLLMClient:
        @classmethod
        def from_env(cls, *, log_dir):
            calls["log_dir"] = log_dir
            return "llm-from-env"

    class FakePlayerAgent:
        def __init__(self, *, name, prompt_path, llm, max_turns):
            calls["agent"] = (name, prompt_path.name, llm, max_turns)

    async def fake_run_qa_session(**kwargs):
        calls["session"] = kwargs
        return {"turn_count": 0, "error_count": 0}

    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.setattr(run_qa, "LLMClient", FakeLLMClient)
    monkeypatch.setattr(run_qa, "PlayerAgent", FakePlayerAgent)
    monkeypatch.setattr(run_qa, "run_qa_session", fake_run_qa_session)

    summary = await run_qa._run_single(
        agent_name="socialite",
        run_root=tmp_path,
        profile="dev_test",
        max_turns=1,
        run_id="test-run",
    )

    assert summary == {"turn_count": 0, "error_count": 0}
    assert calls["log_dir"] == tmp_path / "socialite" / "llm"
    assert calls["agent"] == ("socialite", "socialite.md", "llm-from-env", 1)
    assert calls["session"]["llm"] == "llm-from-env"


@pytest.mark.asyncio
async def test_qa_main_does_not_require_legacy_base_url(monkeypatch, tmp_path):
    calls: list[dict[str, object]] = []

    async def fake_run_single(**kwargs):
        calls.append(kwargs)
        return {"turn_count": 0, "error_count": 0}

    monkeypatch.delenv("BASE_URL", raising=False)
    monkeypatch.setattr(run_qa, "QA_RUN_ROOT", tmp_path)
    monkeypatch.setattr(run_qa, "_run_single", fake_run_single)
    monkeypatch.setattr(run_qa, "_write_index", lambda *args, **kwargs: None)

    args = run_qa._build_parser().parse_args(["--agent", "socialite", "--turns", "1"])

    await run_qa.main_async(args)

    assert calls == [
        {
            "agent_name": "socialite",
            "run_root": tmp_path,
            "profile": "dev_test",
            "max_turns": 1,
            "run_id": calls[0]["run_id"],
        }
    ]
