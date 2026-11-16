from ..locale import ko
from ..story.load import CASE


def show_name(story, kind, name):
    if kind == CASE:
        return CASE
    entry = {"곳": story.places, "사람": story.people, "볼 것": story.things}[kind][name]
    return entry.display or name


def show_line(story, addr):
    line = story.lines[addr]
    if line.kind == "말":
        return ko.said(show_name(story, "사람", line.name), line.text)
    if line.kind == "볼 것" and not story.things[line.name].item:
        return line.text
    return show_name(story, line.kind, line.name)
