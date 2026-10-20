"""Channel-agnostic message types + the §2.5 formatting rules.

Nothing in journeys/agent knows about WhatsApp. A channel turns its native input
into an InboundMessage and renders an OutboundMessage. Message rules (spec 2.5):
  - say who, what, when; "Ravi from Reliance Digital"; never the partner name
  - three lines or fewer
  - do not ask for data we already have (address, serial, invoice, warranty)
  - reply in the language of the customer's last message
  - up to 3 reply buttons of <=20 chars, OR a list (up to 10 rows)
  - photos go through the capture link; phone numbers stay hidden
"""
from __future__ import annotations

from dataclasses import dataclass, field

from app.domain import Role

MAX_BUTTONS = 3
MAX_BUTTON_LEN = 20
MAX_LIST_ROWS = 10
MAX_LINES = 3


@dataclass
class Media:
    kind: str  # image | video | audio | document
    url: str | None = None
    caption: str | None = None


@dataclass
class InboundMessage:
    role: Role
    from_id: str  # masked identity / bpid / wa id
    text: str | None = None
    button_id: str | None = None  # id of a tapped button / list row
    media: list[Media] = field(default_factory=list)
    language: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def intent(self) -> str:
        """Button id if present, else the lowercased text — the routing key."""
        return (self.button_id or (self.text or "")).strip()


@dataclass
class Button:
    id: str
    title: str


@dataclass
class OutboundMessage:
    to_id: str
    role: Role
    text: str
    buttons: list[Button] = field(default_factory=list)
    list_rows: list[Button] = field(default_factory=list)
    list_button: str = "Choose"
    template: str | None = None  # approved template name (outside 24h window)
    media: list[Media] = field(default_factory=list)

    def validate(self) -> "OutboundMessage":
        """Enforce §2.5. Truncates/raises to keep every outbound compliant."""
        lines = [ln for ln in self.text.splitlines() if ln.strip()]
        if len(lines) > MAX_LINES:
            self.text = "\n".join(lines[:MAX_LINES])
        if len(self.buttons) > MAX_BUTTONS:
            raise ValueError("more than 3 buttons — use a list message instead")
        for b in self.buttons:
            if len(b.title) > MAX_BUTTON_LEN:
                b.title = b.title[:MAX_BUTTON_LEN]
        if len(self.list_rows) > MAX_LIST_ROWS:
            self.list_rows = self.list_rows[:MAX_LIST_ROWS]
        return self


def reply(
    to_id: str,
    role: Role,
    text: str,
    *,
    buttons: list[tuple[str, str]] | None = None,
    list_rows: list[tuple[str, str]] | None = None,
    list_button: str = "Choose",
    template: str | None = None,
    media: list[Media] | None = None,
) -> OutboundMessage:
    """Build a compliant outbound message. buttons/list_rows are (id, title) tuples."""
    return OutboundMessage(
        to_id=to_id,
        role=role,
        text=text,
        buttons=[Button(i, t) for i, t in (buttons or [])],
        list_rows=[Button(i, t) for i, t in (list_rows or [])],
        list_button=list_button,
        template=template,
        media=media or [],
    ).validate()
