from src.locale import ko


def test_midnight_is_night_and_one_oclock_is_dawn():
    assert [ko.clock(m) for m in (20 * 60, 0, 20, 60, 4 * 60, 12 * 60)] == \
        ["밤 8시", "자정", "밤 12시 20분", "새벽 1시", "새벽 4시", "오후 12시"]



def test_a_roll_shows_how_the_total_is_made():
    assert ko.roll("press", [5, 1], 8, 8) == "몰아세운다 · 5 + 1 + 2 = 8 · 8 이상"
    assert ko.roll("press", [5, 1], 5, 8) == "몰아세운다 · 5 + 1 - 1 = 5 · 8 이상"
    assert ko.roll("press", [5, 1], 6, 8) == "몰아세운다 · 5 + 1 = 6 · 8 이상"


def test_particles_follow_the_last_sound():
    assert [ko.ro(w) for w in ("구둣주걱", "칼", "드라이버")] == ["구둣주걱으로", "칼로", "드라이버로"]
    assert ko.bet("press", 72, person="최두식") == "최두식을 몰아세운다 · 72% · 1턴"
