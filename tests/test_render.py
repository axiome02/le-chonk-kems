from kems.engine.cards import Card
from kems.engine.render import render_table_base64, render_table_image
from kems.engine.views import PlayerView


def test_render_table_image():
    view = PlayerView(
        pid=0, name="Le Chonk", team=0, partner_name="Chonk Buddy",
        my_hand=[Card(7, "♠"), Card(7, "♥"), Card(7, "♦"), Card(7, "♣")],
        has_square=True, my_signal="purr", my_trigger="purr", my_plan="play fast",
        my_team_chat=[], my_journal=[],
        center=[Card(2, "♠"), Card(5, "♥"), Card(9, "♦"), Card(10, "♣")],
        global_chat=[], scores={0: 1, 1: 0}, round=1
    )
    img = render_table_image(view)
    assert img.size == (760, 460)

    b64 = render_table_base64(view)
    assert isinstance(b64, str)
    assert len(b64) > 5000
