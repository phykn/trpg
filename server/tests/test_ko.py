from src.locale import ko


def test_midnight_is_night_and_one_oclock_is_dawn():
    assert [ko.clock(m) for m in (20 * 60, 0, 20, 60, 4 * 60, 12 * 60)] == \
        ["밤 8시", "밤 12시", "밤 12시 20분", "새벽 1시", "새벽 4시", "오후 12시"]
