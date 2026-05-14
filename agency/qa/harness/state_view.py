def format_state_summary(front_state: dict) -> str:
    lines: list[str] = []

    place = front_state.get("place")
    if place:
        description = place.get("description") or ""
        lines.append(f"장소: {place['name']} — {description}")
        exits = place.get("exits") or []
        if exits:
            lines.append("이동 가능: " + ", ".join(s["name"] for s in exits))
        targets = place.get("targets") or []
        if targets:
            lines.append(
                "눈앞 대상: "
                + ", ".join(f"{target['name']}({target['kind']})" for target in targets)
            )

    hero = front_state.get("hero")
    if hero:
        hp = hero["resources"]["hp"]
        mp = hero["resources"]["mp"]
        level_hint = " — 레벨업 가능" if hero.get("canLevelUp") else ""
        lines.append(
            f"나: {hero['name']} Lv {hero['level']} "
            f"HP {hp['current']}/{hp['maximum']} "
            f"MP {mp['current']}/{mp['maximum']} "
            f"xp {hero['exp']}/{hero['expMax']}{level_hint}"
        )
        skills = hero.get("skills") or []
        if skills:
            lines.append("사용 가능한 기술: " + ", ".join(skills))
        else:
            lines.append("사용 가능한 기술: (없음)")
        inv = hero.get("inventory") or []
        if inv:
            lines.append(
                "인벤토리: " + ", ".join(f"{i['name']}×{i['qty']}" for i in inv)
            )
        else:
            lines.append("인벤토리: (비어 있음)")

    quest = front_state.get("quest")
    if quest:
        lines.append(f"진행 퀘스트: {quest['title']} — {quest.get('summary') or ''}")
    quest_offers = front_state.get("questOffers") or []
    if quest_offers:
        lines.append(
            "제안 퀘스트: " + ", ".join(quest["title"] for quest in quest_offers)
        )

    return "\n".join(lines) or "(상황 정보 없음)"


def last_gm_text(log_entries: list[dict]) -> str:
    for e in reversed(log_entries):
        if e.get("kind") == "gm":
            return e.get("text", "")
    return ""
