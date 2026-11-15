from .load import StoryError, find_missing, read_story


def check_story(raw):
    missing = find_missing(raw)
    if not missing:
        return [("통과", "가리키는 것이 있다", "")]
    return [("떨어짐", "가리키는 것이 있다", m) for m in missing]


def report_checks(folder):
    try:
        results = check_story(read_story(folder))
    except StoryError as exc:
        results = [("떨어짐", "읽기", str(exc))]
    for verdict, name, detail in results:
        print(f"{verdict}  {name}  {detail}".rstrip())
    return 1 if any(verdict == "떨어짐" for verdict, _, _ in results) else 0
