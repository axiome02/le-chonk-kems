import os
from kems.run import play_match


def test_play_match_mock(tmp_path):
    out_file = str(tmp_path / "test_match.txt")
    settings = {
        "seed": 999,
        "ranks": 10,
        "max_turns": 2,
        "max_rounds": 1,
        "max_centers": 2,
        "points_to_win": 1,
        "out": out_file,
        "players": [{"agent": "mock", "model": "mock-bot"} for _ in range(4)],
        "eval_signals": False,
    }
    result = play_match(settings)
    assert result["state"] is not None
    assert result["interrupted"] is None
    assert os.path.exists(out_file)
    with open(out_file, encoding="utf-8") as f:
        content = f.read()
    assert "KEMS ARENA — MATCH TRANSCRIPT" in content
