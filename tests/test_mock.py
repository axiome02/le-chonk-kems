from kems.config import Config
from kems.engine.views import view_for
from kems.llm.mock import MockClient
from kems.orchestrator import setup, play_round, negotiation


def test_mock_client_responses():
    client = MockClient()
    cfg = Config(master_seed=42)
    state = setup(cfg, ["mock-bot"] * 4)
    view = view_for(state, 0)

    # 1. Negotiation
    nego_sys = "You are privately agreeing with your teammate on a SECRET TRIGGER..."
    res = client.chat(nego_sys, "Match context")
    assert "PROPOSAL: purrfect" in res
    assert "TRIGGER: purrfect" in res

    # 2. Card exchange
    card_sys = "Goal: assemble four of a kind... It's your exchange turn: take ONE card..."
    res = client.chat(card_sys, "YOUR HAND: 7♥")
    assert "ACTION: PASS" in res

    # 3. Reflection
    refl_sys = "Take a moment to think (inner monologue) to analyze..."
    res = client.chat(refl_sys, "Context")
    assert len(res) > 10

    # 4. Brain discussion
    brain_sys = "Kems Public Discussion: you speak in the chat seen by all 4 players.\nDECISION_MESSAGE: <msg>"
    res = client.chat(brain_sys, "Context")
    assert "DECISION_MESSAGE:" in res
    assert "DECISION_CALL:" in res

    # 5. Executor discussion
    exec_sys = "Format the player's decision into the exact game format without altering content.\nSIGNAL_RECEIVED: ..."
    res = client.chat(exec_sys, "Context")
    assert "MESSAGE:" in res
    assert "CALL:" in res


def test_mock_full_match_end_to_end(tmp_path):
    from kems.run import play_match
    out_file = str(tmp_path / "match_test.txt")
    settings = {
        "seed": 42,
        "players": [{"agent": "mock", "model": "mock-bot"} for _ in range(4)],
        "max_rounds": 1,
        "max_turns": 2,
        "out": out_file,
    }
    res = play_match(settings)
    assert res["state"] is not None
    assert res["state"].round >= 1
    assert res["usage"]["grand_total"] > 0
