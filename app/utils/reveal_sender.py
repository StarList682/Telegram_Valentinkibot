from __future__ import annotations

import html
from dataclasses import dataclass


REVEAL_STARS_CURRENCY = 'XTR'
DEFAULT_REVEAL_SENDER_PRICE = 25


@dataclass
class RevealPaymentPayload:
    valentine_id: int
    amount_stars: int


def build_reveal_payload(
    valentine_id: int,
    amount_stars: int,
) -> str:
    return 'reveal:%i:%i' % (valentine_id, amount_stars)


def parse_reveal_payload(
    payload: str,
) -> RevealPaymentPayload | None:
    if not payload.startswith('reveal:'):
        return None

    parts = payload.split(':', 2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return None

    valentine_id = int(parts[1])
    amount_stars = int(parts[2])
    if valentine_id < 1 or amount_stars < 1:
        return None

    return RevealPaymentPayload(
        valentine_id=valentine_id,
        amount_stars=amount_stars,
    )


def format_reveal_button_text(amount_stars: int) -> str:
    return 'Узнать кто отправил - %i⭐' % amount_stars


def format_sender_reveal_text(
    sender_id: int,
    sender_name: str | None,
    sender_username: str | None,
) -> str:
    safe_name = html.escape((sender_name or 'Пользователь').strip() or 'Пользователь')
    lines = [
        '💘 Эту валентинку отправил: '
        '<a href="tg://user?id=%i">%s</a>' % (sender_id, safe_name),
    ]

    username = (sender_username or '').strip().lstrip('@')
    if username:
        lines.append('👤 Username: @%s' % html.escape(username))

    lines.append('🆔 ID: <code>%i</code>' % sender_id)
    return '\n'.join(lines)
