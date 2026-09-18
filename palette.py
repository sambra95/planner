"""Project colours: how they are handed out, and how a project reads on screen.

Streamlit's named badge colours only run to seven, which is fewer than a year's
worth of projects, so colours are stored as hex and drawn with Markdown's custom
colour syntax. Every project gets a colour no other project holds.
"""

from __future__ import annotations

import colorsys
import re

import pandas as pd

#: Distinct hues, spaced around the wheel and legible on a light or dark theme.
#: The first seven match the Streamlit badge colours projects used to be given,
#: so existing projects keep the colour they already had.
PALETTE = [
    "#3B82F6",  # blue        #14B8A6 teal onwards are the extras that take
    "#22C55E",  # green       a project list past the seven named colours
    "#F59E0B",  # orange
    "#EF4444",  # red
    "#8B5CF6",  # violet
    "#EAB308",  # yellow
    "#71717A",  # gray
    "#14B8A6",  # teal
    "#EC4899",  # pink
    "#0EA5E9",  # sky
    "#84CC16",  # lime
    "#A855F7",  # purple
    "#F97316",  # deep orange
    "#06B6D4",  # cyan
    "#E11D48",  # rose
    "#64748B",  # slate
]

#: What the seven old named colours became, so stored names still resolve.
LEGACY = {"blue": PALETTE[0], "green": PALETTE[1], "orange": PALETTE[2],
          "red": PALETTE[3], "violet": PALETTE[4], "yellow": PALETTE[5],
          "gray": PALETTE[6], "grey": PALETTE[6]}

DEFAULT_COLOUR = PALETTE[0]

#: What an archived project and everything under it turns. Deliberately not one
#: of PALETTE, so archiving frees the project's old colour without spending a
#: new one: no live project ever needs to be this grey.
ARCHIVED_COLOUR = "#9CA3AF"

#: What a project selector shows for "no project at all".
NO_PROJECT = "—"

#: How much of the project colour washes into a task's card, and into its chip.
TINT_ALPHA = 0.07
CHIP_ALPHA = 0.16

#: Outline of a bordered section, and the heavier left edge of a project's card.
BORDER_WIDTH = "2px"
ACCENT_WIDTH = "5px"

#: Bordered containers are the only `stVerticalBlock`s with a border style, so a
#: width set on all of them shows up on exactly those and is a no-op elsewhere.
SECTION_CSS = (f'<style>[data-testid="stVerticalBlock"] '
               f'{{ border-width: {BORDER_WIDTH}; }}</style>')

#: The top navigation, spread the width of the bar instead of bunched at the
#: left. Each tab is given an equal share of the row and its label centred in it;
#: `rc-overflow` and `rc-overflow-item` are the menu Streamlit builds the bar
#: from, and the chain between them has to be widened too or the link keeps
#: hugging its text.
#: Mirrors `borderColor` in .streamlit/config.toml, which CSS cannot read.
BORDER_COLOUR = "#B9C0CB"

#: Height of the navigation bar, which has to clear the tabs inside it.
NAV_HEIGHT = "72px"

NAV_CSS = f"""<style>
.stAppHeader {{
    /* Tall enough to hold a tab: the bar is 53px by default and the tabs are
       taller than that, so without this the active tab's highlight hangs over
       the divider instead of sitting inside the bar. */
    min-height: {NAV_HEIGHT};
    border-bottom: 1px solid {BORDER_COLOUR} !important;
    box-shadow: 0 2px 6px rgba(31, 36, 48, 0.06) !important;
}}
.stAppHeader .rc-overflow {{ width: 100%; }}
.stAppHeader .rc-overflow-item {{ flex: 1 1 0; min-width: 0; }}
.stAppHeader .rc-overflow-item > div,
.stAppHeader [data-testid="stTopNavLinkContainer"] {{ width: 100%; }}
.stAppHeader [data-testid="stTopNavLink"] {{
    width: 100%;
    justify-content: center;
    padding: 14px 4px !important;
}}
.stAppHeader [data-testid="stTopNavLink"] span {{ font-size: 1.2rem !important; }}
</style>"""

#: Golden angle: successive hues land as far from each other as possible.
_GOLDEN = 0.6180339887498949


def as_hex(colour) -> str:
    """A stored colour as hex, whether it was saved as a name or already hex."""
    if colour is None or (isinstance(colour, float) and pd.isna(colour)):
        return DEFAULT_COLOUR
    colour = str(colour)
    return colour if colour.startswith("#") else LEGACY.get(colour, DEFAULT_COLOUR)


def next_colour(used) -> str:
    """A colour no existing project holds.

    The palette is tried in order first, so a short project list stays on the
    hand-picked hues. Past that, walk the hue wheel by the golden angle until
    landing on something unused - which always terminates, because each turn
    yields a new hue and only finitely many are taken.
    """
    taken = {as_hex(colour) for colour in used}
    for colour in PALETTE:
        if colour not in taken:
            return colour
    step = len(taken)
    while True:
        red, green, blue = colorsys.hls_to_rgb((step * _GOLDEN) % 1.0, 0.58, 0.62)
        colour = "#%02X%02X%02X" % (round(red * 255), round(green * 255),
                                    round(blue * 255))
        if colour not in taken:
            return colour
        step += 1


def css_class(key: str) -> str:
    """The class Streamlit puts on a widget given its key.

    It keeps letters, digits, underscores and hyphens and turns everything else
    into a hyphen, so a key like "week:open:3" becomes "st-key-week-open-3".
    Selectors have to be built from this, not from the key itself.
    """
    return "st-key-" + re.sub(r"[^A-Za-z0-9_-]", "-", key)


def _rgba(colour: str, alpha: float) -> str:
    """Hex as a comma-separated rgba(), the form Streamlit's Markdown accepts."""
    red, green, blue = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    return f"rgba({red},{green},{blue},{alpha})"


def badge(name, colour) -> str:
    """A project as a coloured chip, or nothing when a task has no project."""
    if not name or pd.isna(name):
        return ""
    tint = as_hex(colour)
    return (f':color[{name}]{{foreground="{tint}" '
            f'background="{_rgba(tint, CHIP_ALPHA)}"}}')


def card_css(key: str, colour) -> str:
    """CSS tinting one `st.container(key=...)` card with a project's colour.

    The key class lands on the card's own `stVerticalBlock`, which is the element
    carrying the border, so one selector is enough. It has to be the card alone:
    the wash is translucent, and repeating it on the children inside would stack
    the alpha and darken the tint with every layer.
    """
    tint = as_hex(colour)
    return (f'.{css_class(key)} {{ background-color: {_rgba(tint, TINT_ALPHA)} '
            f'!important; border-color: {tint} !important; '
            f'border-left-width: {ACCENT_WIDTH} !important; }}')


def strike(text: str, done: bool) -> str:
    """Text struck through once it is finished."""
    return f"~~{text}~~" if done else text


def chip_css(key: str, colour) -> str:
    """CSS making one `st.button(key=...)` read as a project chip: the project's
    colour on a wash of it, rather than a default grey button."""
    tint = as_hex(colour)
    return (f'.{css_class(key)} button {{ '
            f'background-color: {_rgba(tint, CHIP_ALPHA)} !important; '
            f'color: {tint} !important; border-color: transparent !important; }}')


def label(title: str, name, colour, done: bool = False) -> str:
    """A task's title with its project chip in front, when it has one.

    Only the title is struck through: the chip is a Markdown colour directive
    and wrapping that in tildes would stop it rendering as a chip.
    """
    return f"{badge(name, colour)} {strike(title, done)}".strip()
