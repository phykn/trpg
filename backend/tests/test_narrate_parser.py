from src.llm_client.agents.narrate.parser import (
    NarrativeDelta,
    NarrativeFinal,
    split_stream,
)


async def _feed(*tokens):
    for t in tokens:
        yield t


async def _collect(stream):
    items = []
    async for it in stream:
        items.append(it)
    return items


async def test_full_at_once():
    items = await _collect(
        split_stream(_feed('본문이다.\n---JSON---\n{"turn_summary": "테스트"}'))
    )
    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].body == "본문이다.\n"
    assert finals[0].output.turn_summary == "테스트"


async def test_separator_split_across_chunks():
    items = await _collect(
        split_stream(
            _feed("본문", "의 ", "일부.\n---", "JSON---\n", '{"memorable": true}')
        )
    )
    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].body == "본문의 일부.\n"
    assert finals[0].output.memorable is True
    body_text = "".join(i.text for i in items if isinstance(i, NarrativeDelta))
    assert body_text == "본문의 일부.\n"


async def test_no_separator_yields_default_output():
    items = await _collect(split_stream(_feed("본문만")))
    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].body == "본문만"
    assert finals[0].output.memorable is False
    assert finals[0].output.turn_summary == ""


async def test_invalid_json_falls_back_to_default():
    items = await _collect(split_stream(_feed("본문\n---JSON---\nthis is not json")))
    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].body == "본문\n"
    assert finals[0].output.memorable is False
    assert finals[0].output.state_changes == []


async def test_deltas_yielded_progressively():
    items = await _collect(
        split_stream(_feed("첫", " 문장. ", "두 번째.", " 끝.\n---JSON---\n{}"))
    )
    deltas = [i for i in items if isinstance(i, NarrativeDelta)]
    body_text = "".join(d.text for d in deltas)
    assert body_text == "첫 문장. 두 번째. 끝.\n"
    assert len(deltas) >= 2


async def test_body_unescapes_json_style_escapes():
    items = await _collect(
        split_stream(
            _feed('경비병이 \\"안녕\\"이라 말한다.\\n다시 본다.\n---JSON---\n{}')
        )
    )
    finals = [i for i in items if isinstance(i, NarrativeFinal)]
    assert finals[0].body == '경비병이 "안녕"이라 말한다.\n다시 본다.\n'
