"""Project colours: how they are handed out, and how a project reads on screen.

Streamlit's named badge colours only run to seven, which is fewer than a year's
worth of projects, so colours are stored as hex and drawn with Markdown's custom
colour syntax. Every project gets a colour no other project holds.
"""

from __future__ import annotations

import colorsys
import re

import pandas as pd

#: Distinct hues, muted to sit against the warm background.
PALETTE = [
    "#4E86E3",  # blue        #14B8A6 teal onwards are the extras that take
    "#32B562",  # green       a project list past the seven named colours
    "#DE9822",  # orange
    "#DE5555",  # red
    "#916BE7",  # violet
    "#D3A71F",  # yellow
    "#727279",  # gray
    "#24A899",  # teal
    "#DC5899",  # pink
    "#249DD3",  # sky
    "#80BA28",  # lime
    "#A865E7",  # purple
    "#E2772D",  # deep orange
    "#1BA7BF",  # cyan
    "#CD3153",  # rose
    "#687587",  # slate
]

#: Named colours that may still be stored, and their hex.
LEGACY = {"blue": PALETTE[0], "green": PALETTE[1], "orange": PALETTE[2],
          "red": PALETTE[3], "violet": PALETTE[4], "yellow": PALETTE[5],
          "gray": PALETTE[6], "grey": PALETTE[6]}

DEFAULT_COLOUR = PALETTE[0]

#: What an archived project turns. Not in PALETTE, so archiving frees a colour
#: rather than spending one.
ARCHIVED_COLOUR = "#AEA185"

#: What a project selector shows for no project.
NO_PROJECT = "-"

#: How much colour washes into a card, a chip or a badge.
WASH_ALPHA = 0.16

#: Outline of a bordered section.
BORDER_WIDTH = "2px"

#: Only bordered containers have a border style, so this shows on those alone.
SECTION_CSS = (f'<style>[data-testid="stVerticalBlock"] '
               f'{{ border-width: {BORDER_WIDTH}; }}</style>')

#: What an input is filled with, matching a button. `secondaryBackgroundColor`
#: covers widgets and containers alike, so config cannot separate them.
INPUT_FILL = "#FFFFFF"

INPUT_CSS = f"""<style>
[data-testid="stTextInputRootElement"],
[data-testid="stTextAreaRootElement"],
[data-testid="stNumberInputContainer"],
[data-testid="stDateInputField"],
[data-testid="stTimeInputTimeDisplay"],
[data-testid="stSelectbox"] > div,
/* the select paints two nested divs, not one */
[data-testid="stSelectbox"] > div > div {{ background-color: {INPUT_FILL}; }}
</style>"""

#: Mirrors `borderColor` in .streamlit/config.toml, which CSS cannot read.
BORDER_COLOUR = "#C8BFAA"

#: Bar height; has to clear the tabs inside it.
NAV_HEIGHT = "72px"

#: Between tabs, so neighbouring highlights do not run together.
NAV_GAP = "10px"

NAV_CSS = f"""<style>
.stAppHeader {{
    /* Tall enough to hold a tab: the bar is 53px by default and the tabs are
       taller than that, so without this the active tab's highlight hangs over
       the divider instead of sitting inside the bar. */
    min-height: {NAV_HEIGHT};
    border-bottom: 1px solid {BORDER_COLOUR} !important;
    box-shadow: 0 2px 6px rgba(31, 36, 48, 0.06) !important;
}}
.stAppHeader .rc-overflow {{ width: 100%; gap: {NAV_GAP}; }}
.stAppHeader .rc-overflow-item {{ flex: 1 1 0; min-width: 0; }}
/* Streamlit keeps 175px here for the Deploy button, which is hidden; without
   this the tabs stop short of the right edge and sit off centre. */
.stAppHeader div:has(> [data-testid="stToolbarActions"]) {{ min-width: auto; }}
.stAppHeader .rc-overflow-item > div,
.stAppHeader [data-testid="stTopNavLinkContainer"] {{ width: 100%; }}
.stAppHeader [data-testid="stTopNavLink"] {{
    width: 100%;
    justify-content: center;
    padding: 14px 4px !important;
}}
.stAppHeader [data-testid="stTopNavLink"] span {{ font-size: 1.2rem !important; }}
/* Clicking the logo goes to the home page by default and no parameter turns
   that off. Away from the home page Streamlit wraps it in a button; the image
   itself is never the target. */
[data-testid="stLogoLink"] {{ pointer-events: none; }}
</style>"""

#: Golden angle: successive hues land as far apart as possible.
_GOLDEN = 0.6180339887498949


def as_hex(colour) -> str:
    """A stored colour as hex, whether it was saved as a name or already hex."""
    if colour is None or (isinstance(colour, float) and pd.isna(colour)):
        return DEFAULT_COLOUR
    colour = str(colour)
    return colour if colour.startswith("#") else LEGACY.get(colour, DEFAULT_COLOUR)


def next_colour(used) -> str:
    """A colour no existing project holds: the palette in order, then the hue
    wheel by golden angle until one is free."""
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
    """The class Streamlit gives a keyed widget: "week:open:3" becomes
    "st-key-week-open-3". Selectors must be built from this, not the key."""
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
            f'background="{_rgba(tint, WASH_ALPHA)}"}}')


def wash(colour) -> str:
    """A project colour at the wash alpha, for anything coloured directly rather
    than through a stylesheet."""
    return _rgba(as_hex(colour), WASH_ALPHA)


def card_css(key: str, colour) -> str:
    """CSS washing one `st.container(key=...)` card in its project colour.
    The border is hidden rather than dropped, so the card keeps its box and
    radius and reads as a chip, the way a meeting does in the calendar. The
    card alone: the wash is translucent, so repeating it on children would
    stack the alpha."""
    wash = _rgba(as_hex(colour), WASH_ALPHA)
    return (f'.{css_class(key)} {{ background-color: {wash} !important; '
            f'border-color: transparent !important; }}')

def strike(text: str, done: bool) -> str:
    """Text struck through once it is finished."""
    return f"~~{text}~~" if done else text


def lightened(colour: str, amount: float = 0.05) -> str:
    """`colour` with its lightness raised. Streamlit fills a plain button with
    the page background lightened this far, and has no variable to borrow, so
    anything meant to match one works it out the same way."""
    red, green, blue = (int(colour[i:i + 2], 16) / 255 for i in (1, 3, 5))
    hue, light, saturation = colorsys.rgb_to_hls(red, green, blue)
    channels = colorsys.hls_to_rgb(hue, min(1.0, light + amount), saturation)
    return "#" + "".join(f"{round(channel * 255):02X}" for channel in channels)


def chip_css(key: str, colour) -> str:
    """CSS making one `st.button(key=...)` read as a project chip: the project's
    colour on a wash of it, rather than a default grey button. With no project
    there is no colour to wash it in, so it keeps the page behind it and loses
    its outline all the same - a chip with no colour, not a button among chips."""
    if colour is None or pd.isna(colour):
        return f'.{css_class(key)} button {{ border-color: transparent !important; }}'
    tint = as_hex(colour)
    return (f'.{css_class(key)} button {{ '
            f'background-color: {_rgba(tint, WASH_ALPHA)} !important; '
            f'color: {tint} !important; border-color: transparent !important; }}')


def label(title: str, name, colour, done: bool = False) -> str:
    """A task's title behind its project chip. Only the title is struck: the
    chip is a colour directive and tildes would stop it rendering."""
    return f"{badge(name, colour)} {strike(title, done)}".strip()


def select_css(key: str, colour) -> str:
    """CSS painting one `st.selectbox(key=...)` in the colour of the project it
    is showing. Two nested divs, as INPUT_CSS fills the same pair."""
    tint = as_hex(colour)
    return (f'.{css_class(key)} [data-testid="stSelectbox"] > div, '
            f'.{css_class(key)} [data-testid="stSelectbox"] > div > div {{ '
            f'background-color: {_rgba(tint, WASH_ALPHA)} !important; '
            f'color: {tint} !important; border-color: transparent !important; }}')


def style_block(rules: list[str]) -> str:
    """A page's card rules as one style element, empty when there are none."""
    return "<style>" + "\n".join(rules) + "</style>" if rules else ""


#: Enter starts the next bullet in every text area. Streamlit cannot see a
#: keypress inside one, so the page does it, writing the value the way React
#: listens for. db.as_bullets tidies the same text on save.
BULLET_JS = """<script>
(() => {
  // st.html runs again on every rerun, so without this the listeners stack up
  // and one Enter inserts one bullet per rerun that has happened.
  if (window.plannerBullets) return;
  window.plannerBullets = true;

  const ours = (box) => box.tagName === "TEXTAREA";
  const write = (box, value, caret) => {
    const setter = Object.getOwnPropertyDescriptor(
        window.HTMLTextAreaElement.prototype, "value").set;
    setter.call(box, value);
    box.dispatchEvent(new Event("input", {bubbles: true}));
    box.setSelectionRange(caret, caret);
  };
  document.addEventListener("keydown", (event) => {
    const box = event.target;
    // Shift+Enter is a plain newline, and Cmd/Ctrl+Enter is how Streamlit
    // applies a text area: leave all of those alone.
    if (!ours(box) || event.key !== "Enter" || event.shiftKey
        || event.metaKey || event.ctrlKey || event.altKey) return;
    event.preventDefault();
    const at = box.selectionStart;
    const added = "\\n- ";
    write(box, box.value.slice(0, at) + added + box.value.slice(box.selectionEnd),
          at + added.length);
  }, true);
  document.addEventListener("input", (event) => {
    const box = event.target;
    if (!ours(box) || box.value === "" || box.value.startsWith("- ")) return;
    write(box, "- " + box.value, box.selectionStart + 2);
  }, true);
})();
</script>"""

