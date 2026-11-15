from src.locale import ko


def test_midnight_is_night_and_one_oclock_is_dawn():
    assert [ko.clock(m) for m in (20 * 60, 0, 20, 60, 4 * 60, 12 * 60)] == \
        ["밤 8시", "밤 12시", "밤 12시 20분", "새벽 1시", "새벽 4시", "오후 12시"]


def test_the_dm_names_people_and_places_with_the_right_particle():
    assert ko.guide("talk", "오토") == "곁에 오토가 있습니다. 무엇이든 물어보십시오."
    assert ko.guide("held", "한스").startswith("한스가 무언가 아는 눈치지만")
    assert ko.guide("unvisited", "방앗간") == "아직 방앗간에는 가 보지 않았습니다."
