def format_state_summary(front_state: dict) -> str:
    lines: list[str] = []

    place = front_state.get("place")
    if place:
        lines.append(
            f"장소: {place['name']} ({place['date']} {place['period']} {place['hour']}시)"
        )
        if place.get("surroundings"):
            lines.append(f"인접: {', '.join(place['surroundings'])}")
        if place.get("features"):
            lines.append(f"환경: {', '.join(place['features'])}")
        if place.get("weather"):
            lines.append(f"날씨: {', '.join(place['weather'])}")

    hero = front_state.get("hero")
    if hero:
        lines.append(
            f"나: {hero['name']} ({hero['raceJob']}) "
            f"HP {hero['hp']}/{hero['hpMax']}"
        )
        inv = hero.get("inventory") or []
        if inv:
            lines.append("인벤토리: " + ", ".join(f"{i['name']}×{i['qty']}" for i in inv))

    subject = front_state.get("subject")
    if subject:
        lines.append(
            f"눈앞 NPC: {subject['name']} ({subject.get('role') or '-'}) — 친밀도 {subject['trust']}"
        )
        known = subject.get("known") or []
        if known:
            lines.append("  아는 정보: " + " / ".join(known))

    quest = front_state.get("quest")
    if quest:
        lines.append(f"진행 퀘스트: {quest['title']} — {quest.get('summary') or ''}")

    return "\n".join(lines) or "(상황 정보 없음)"


def last_gm_text(log_entries: list[dict]) -> str:
    for e in reversed(log_entries):
        if e.get("kind") == "gm":
            return e.get("text", "")
    return ""
