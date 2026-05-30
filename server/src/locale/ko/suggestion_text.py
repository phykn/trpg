"""Korean phrase atoms for server-composed suggestion text."""

TARGETLESS_GENERIC_SUGGESTIONS = (
    "대화시작하기",
    "대화시도하기",
    "말걸기",
    "말을건다",
    "상황파악하기",
)

TARGETLESS_TALK_LABELS = (
    "대화시작하기",
    "대화시도하기",
    "말걸기",
    "말을건다",
    "계속 질문하기",
)

TARGET_PARTICLES = ("에게", "한테", "께")


def ko_accept() -> str:
    return "수락"


def ko_abandon() -> str:
    return "포기"


def ko_object() -> str:
    return "을"


def ko_to_person() -> str:
    return "에게"


def ko_start_talk() -> str:
    return "말을 겁니다"


def ko_start_talk_label() -> str:
    return "말 걸기"


def ko_ask_label() -> str:
    return "묻기"


def ko_open_quote() -> str:
    return "「"


def ko_close_quote() -> str:
    return "」"


def ko_as_ask() -> str:
    return "라고 묻습니다"


def ko_room() -> str:
    return "방"


def ko_meaning() -> str:
    return "의미"


def ko_situation() -> str:
    return "상황"


def ko_current_situation() -> str:
    return "현재 상황"


def ko_room_question() -> str:
    return "이 방은 어떤 곳인가요?"


def ko_at_topic() -> str:
    return "에서는"


def ko_what_to_check_question() -> str:
    return "무엇을 확인해야 하나요?"


def ko_here() -> str:
    return "여기"


def ko_inspect() -> str:
    return "살핍니다"


def ko_inspect_label() -> str:
    return "살피기"


def ko_move() -> str:
    return "이동합니다"


def ko_surroundings() -> str:
    return "주변"


def ko_possessive() -> str:
    return "의"


def ko_direction_particle(text: str) -> str:
    if not text:
        return _ko_direction_with_final()
    code = ord(text[-1])
    if not (0xAC00 <= code <= 0xD7A3):
        return _ko_direction_with_final()
    final = (code - 0xAC00) % 28
    return _ko_direction_without_final() if final == 0 or final == 8 else _ko_direction_with_final()


def _ko_direction_without_final() -> str:
    return "로"


def _ko_direction_with_final() -> str:
    return "으로"
