"""LLM writer call helpers for generated story patches."""

from typing import Any, Awaitable, Callable

from src.game.domain.action import Action
from src.game.domain.story_contract import StoryContract
from src.game.domain.story_patch import StoryWriteIntent, StoryWriteResponse
from src.game.runtime.request_result import GraphActionRequestResult
from src.llm.context.story_write_context import build_story_write_input
from src.llm.diag import engine_diag

StoryWriter = Callable[..., Awaitable[StoryWriteResponse]]


async def call_writer_or_fallback(
    *,
    writer: StoryWriter,
    client: Any,
    result: GraphActionRequestResult,
    contract: StoryContract,
    intent: StoryWriteIntent,
    player_input: str,
    action: Action,
    accepted_narration: str | None,
    patch_required: bool,
    patch_reason: str,
) -> StoryWriteResponse:
    try:
        return await writer(
            client=client,
            input_=build_story_write_input(
                result.runtime,
                contract=contract,
                intent=intent,
                player_input=player_input,
                action=action,
                accepted_narration=accepted_narration,
                patch_required=patch_required,
                patch_reason=patch_reason,
            ),
            locale=result.runtime.progress.locale,
        )
    except Exception as exc:
        engine_diag("story_write:skip_after_error", err=type(exc).__name__)
        return StoryWriteResponse.model_validate(
            {
                "reason": f"story_write skipped after {type(exc).__name__}",
                "patches": [],
            }
        )


def is_writer_error_skip(response: StoryWriteResponse) -> bool:
    return response.reason.startswith("story_write skipped after ")


def fit_response_to_contract_budget(
    response: StoryWriteResponse,
    contract: StoryContract,
) -> StoryWriteResponse:
    patch_limit = contract.budgets.patches_per_turn
    term_limit = contract.budgets.new_terms_per_turn
    if len(response.patches) <= patch_limit and len(response.new_terms) <= term_limit:
        return response
    return response.model_copy(
        update={
            "patches": response.patches[:patch_limit],
            "new_terms": response.new_terms[:term_limit],
        }
    )
