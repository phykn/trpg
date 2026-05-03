"""tool.py CLI 진입점 — 인자 없으면 usage 에러로 종료."""
import pytest

from agency.story import tool


def test_no_args_exits_with_usage(capsys):
    with pytest.raises(SystemExit) as exc:
        tool._main([])
    # argparse는 required=True 서브파서가 누락되면 exit code 2
    assert exc.value.code == 2
    err = capsys.readouterr().err
    assert "usage" in err.lower() or "required" in err.lower()
