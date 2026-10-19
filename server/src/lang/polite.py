from __future__ import annotations

import re

QUOTED = re.compile(r"\"[^\"]*\"|“[^”]*”|'[^']*'|‘[^’]*’")
_HANGUL, _FINAL_N, _FINAL_B, _FINAL_BS, _FINAL_SS = 0xAC00, 4, 17, 18, 20
_PLAIN_END = re.compile(r"([가-힣])다(?=[.!]?(?:\s|$))")


def _polite_end(m: re.Match) -> str:
    """'내민다' → '내밉니다', '잡는다' → '잡습니다', '했다' → '했습니다'; other endings stay."""
    syllable = m[1]
    final = (ord(syllable) - _HANGUL) % 28
    if syllable == "는":
        return "습니다"
    if syllable in "니":
        return m[0]
    if final == _FINAL_N:
        return chr(ord(syllable) - _FINAL_N + _FINAL_B) + "니다"
    if final in (_FINAL_SS, _FINAL_BS):
        return syllable + "습니다"
    return m[0]


def outside_quotes(text: str, f) -> str:
    out, last = [], 0
    for m in QUOTED.finditer(text):
        out += [f(text[last:m.start()]), m[0]]
        last = m.end()
    out.append(f(text[last:]))
    return "".join(out)


def polite(text: str) -> str:
    return outside_quotes(text, lambda part: _PLAIN_END.sub(_polite_end, part))


def plain(sentence: str) -> bool:
    """A sentence outside quotes that does not end in 합니다체 (or a question/exclamation in it)."""
    bare = QUOTED.sub("", sentence).strip().rstrip(".!?…").strip()
    if not bare:
        return False
    return bare.endswith("다") and not bare.endswith("니다")
