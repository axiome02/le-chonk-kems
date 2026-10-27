"""Procedural card table renderer for Mistral Large 4 vision harness.

Renders high-contrast, visually clean poker-table frames (table felt, center cards,
private hand, and Le Chonk branding) using Pillow. Encodes to base64 for multimodal LLM calls.
"""
from __future__ import annotations

import base64
import functools
import io
from typing import TYPE_CHECKING

from PIL import Image, ImageDraw, ImageFont

if TYPE_CHECKING:
    from .cards import Card
    from .views import PlayerView


@functools.lru_cache(maxsize=16)
def _get_font(size: int = 12) -> ImageFont.ImageFont:
    """Attempts to load a clean TrueType font for card ranks and Unicode symbols."""
    for font_name in ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf", "tahoma.ttf"):
        try:
            return ImageFont.truetype(font_name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_suit_color(suit: str) -> tuple[int, int, int]:
    if suit in ("♥", "♦", "H", "D"):
        return (196, 30, 58)  # Rich Crimson Red
    return (25, 25, 28)       # Crisp Card Black


def draw_card(draw: ImageDraw.ImageDraw, x: int, y: int, w: int, h: int,
              card: Card | None) -> None:
    """Draws a single playing card with clean borders and suit colors."""
    font = _get_font(12)
    font_large = _get_font(16)

    # Drop shadow
    draw.rounded_rectangle([x + 3, y + 4, x + w + 3, y + h + 4], radius=6, fill=(0, 0, 0, 140))
    # Card base
    draw.rounded_rectangle([x, y, x + w, y + h], radius=6, fill=(250, 250, 252), outline=(180, 180, 190), width=2)

    if card is None:
        draw.text((x + w // 2 - 16, y + h // 2 - 8), "Empty", fill=(150, 150, 150), font=font)
        return

    color = _get_suit_color(card.suit)
    rank_str = str(card.rank)
    suit_str = card.suit

    # Top-left corner
    draw.text((x + 8, y + 6), f"{rank_str}", fill=color, font=font)
    draw.text((x + 8, y + 20), f"{suit_str}", fill=color, font=font)

    # Center suit watermark
    draw.text((x + w // 2 - 6, y + h // 2 - 10), f"{suit_str}", fill=color, font=font_large)

    # Bottom-right corner (inverted look)
    draw.text((x + w - 20, y + h - 28), f"{suit_str}", fill=color, font=font)
    draw.text((x + w - 20, y + h - 16), f"{rank_str}", fill=color, font=font)


def render_table_image(view: PlayerView, width: int = 760, height: int = 460) -> Image.Image:
    """Renders the game table from the viewpoint of a specific player."""
    img = Image.new("RGB", (width, height), color=(14, 14, 18))
    draw = ImageDraw.Draw(img)

    # Outer dark border & Mistral orange inner rim
    draw.rectangle([(0, 0), (width - 1, height - 1)], outline=(24, 24, 30), width=10)
    draw.rectangle([(10, 10), (width - 11, height - 11)], outline=(255, 82, 0), width=2)

    # Inner subtle rim
    draw.rectangle([(16, 16), (width - 17, height - 17)], outline=(32, 32, 42), width=4)

    # Header
    draw.text((40, 30), "KEMS ARENA MULTI-AGENT HARNESS", fill=(255, 82, 0))
    draw.text((40, 48), f"Round {view.round} | Player: {view.name} (Team {view.team}) | Partner: {view.partner_name}",
              fill=(180, 180, 195))

    card_w, card_h = 75, 110
    spacing = 20

    # 1. CENTER CARDS SECTION
    draw.text((40, 95), "══ CENTER TABLE (Cards available to swap) ══", fill=(240, 240, 245))
    start_x_center = (width - (4 * card_w + 3 * spacing)) // 2
    for i in range(4):
        card = view.center[i] if i < len(view.center) else None
        cx = start_x_center + i * (card_w + spacing)
        cy = 120
        draw_card(draw, cx, cy, card_w, card_h, card)
        draw.text((cx + card_w // 2 - 12, cy + card_h + 5), f"Slot {i+1}", fill=(160, 160, 175))

    # 2. PLAYER HAND SECTION
    draw.text((40, 265), f"══ YOUR PRIVATE HAND ({view.name}) ══", fill=(240, 240, 245))
    if view.has_square:
        draw.text((width - 260, 265), "★ 4 OF A KIND! (SQUARE) ★", fill=(255, 82, 0))

    start_x_hand = (width - (4 * card_w + 3 * spacing)) // 2
    for i in range(4):
        card = view.my_hand[i] if i < len(view.my_hand) else None
        hx = start_x_hand + i * (card_w + spacing)
        hy = 290
        # If square, draw subtle orange aura behind hand cards
        if view.has_square:
            draw.rounded_rectangle([hx - 3, hy - 3, hx + card_w + 3, hy + card_h + 3],
                                   radius=8, outline=(255, 82, 0), width=2)
        draw_card(draw, hx, hy, card_w, card_h, card)
        draw.text((hx + card_w // 2 - 12, hy + card_h + 5), f"Card {i+1}", fill=(160, 160, 175))

    # Bottom status bar
    scores_str = " | ".join(f"Team {k}: {v} pts" for k, v in sorted(view.scores.items())) if view.scores else "0 - 0"
    draw.rectangle([(16, height - 34), (width - 17, height - 16)], fill=(20, 20, 26))
    draw.text((30, height - 30), f"Match Score: [{scores_str}]", fill=(220, 220, 230))
    if view.my_signal:
        draw.text((width - 320, height - 30), f"Agreed Secret Signal: '{view.my_signal}'", fill=(255, 82, 0))

    return img


def render_table_base64(view: PlayerView) -> str:
    """Renders table to a base64-encoded PNG image string for multimodal API calls."""
    img = render_table_image(view)
    buffered = io.BytesIO()
    img.save(buffered, format="PNG", optimize=True)
    return base64.b64encode(buffered.getvalue()).decode("utf-8")
