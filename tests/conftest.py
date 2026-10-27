import pytest

from kems.engine import rules

TRIGGER = "the cat is sleeping"


@pytest.fixture
def arm_signal():
    """Arm a KEMPS call: the square holder emits the trigger in public."""
    def _arm(state, team: int, holder: int) -> None:
        rules.set_signal(state, team, "our convention", trigger=TRIGGER)
        rules._log(state, "MESSAGE", holder,
                   f"{state.players[holder].name}: \"hey, {TRIGGER} already\"")
    return _arm
