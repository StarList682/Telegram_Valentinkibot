from __future__ import annotations

import html
import re
from hashlib import blake2b
from urllib.parse import urlparse

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LabeledPrice


STARS_BUTTON_PREFIXES = ('stars:', 'xtr:')
MAIL_STARS_DEFAULT_DESCRIPTION = 'Оплата по предложению из рассылки.'


def split_button(raw_button: str) -> tuple[str, str]:
    for separator in (' - ', ' — ', ' – '):
        if separator in raw_button:
            text, target = raw_button.split(separator, 1)
            return text.strip(), target.strip()

    raise ValueError(
        'Неверный формат кнопки. Используйте: '
        '<code>Текст кнопки - https://example.com</code>'
    )


def is_valid_button_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in ('http', 'https') and parsed.netloc:
        return True

    if parsed.scheme == 'tg' and (parsed.netloc or parsed.path):
        return True

    return False


def build_mail_stars_payload(amount_stars: int, button_text: str) -> str:
    digest = blake2b(
        ('%s:%s' % (amount_stars, button_text)).encode('utf-8'),
        digest_size=4,
    ).hexdigest()
    return 'mailstars:%i:%s' % (amount_stars, digest)


def parse_mail_stars_payload(payload: str) -> int | None:
    if not payload.startswith('mailstars:'):
        return None

    parts = payload.split(':', 2)
    if len(parts) < 2 or not parts[1].isdigit():
        return None

    amount_stars = int(parts[1])
    if amount_stars < 1:
        return None

    return amount_stars


def _strip_html(html_text: str | None) -> str:
    if not html_text:
        return ''

    normalized_placeholders = (
        html_text
        .replace('{name}', 'пользователь')
        .replace('{username}', 'username')
        .replace('{link}', 'ссылка')
    )
    without_tags = re.sub(r'<[^>]+>', '', normalized_placeholders)
    normalized = html.unescape(without_tags)
    return ' '.join(normalized.split())


def _truncate(value: str, limit: int, fallback: str) -> str:
    value = (value or '').strip()
    if not value:
        value = fallback
    return value[:limit]


def parse_mailing_buttons(raw_text: str) -> list[list[dict[str, str | int]]]:
    rows: list[list[dict[str, str | int]]] = []

    for raw_row in raw_text.splitlines():
        raw_row = raw_row.strip()
        if not raw_row:
            continue

        row: list[dict[str, str | int]] = []
        for raw_button in raw_row.split('|'):
            raw_button = raw_button.strip()
            if not raw_button:
                continue

            button_text, button_target = split_button(raw_button)
            if not button_text or not button_target:
                raise ValueError(
                    'У каждой кнопки должны быть текст и ссылка.'
                )

            if len(button_text) > 64:
                raise ValueError(
                    'Текст кнопки не должен быть длиннее 64 символов.'
                )

            low_target = button_target.lower()
            if low_target.startswith(STARS_BUTTON_PREFIXES):
                _, raw_amount = button_target.split(':', 1)
                if not raw_amount.isdigit() or int(raw_amount) < 1:
                    raise ValueError(
                        'Для Stars используйте формат '
                        '<code>stars:25</code> или <code>xtr:25</code>.'
                    )

                row.append(
                    {
                        'type': 'stars',
                        'text': button_text,
                        'amount_stars': int(raw_amount),
                    }
                )
                continue

            if not is_valid_button_url(button_target):
                raise ValueError(
                    'Ссылка кнопки должна начинаться с '
                    '<code>https://</code>, <code>http://</code>, '
                    '<code>tg://</code> или быть формата '
                    '<code>stars:25</code>.'
                )

            row.append(
                {
                    'type': 'url',
                    'text': button_text,
                    'url': button_target,
                }
            )

        if row:
            rows.append(row)

    if not rows:
        raise ValueError(
            'Не удалось собрать кнопки. Отправьте хотя бы одну строку.'
        )

    return rows


async def build_mailing_reply_markup(
    bot: Bot,
    template_payload: dict,
    button_specs: list[list[dict[str, str | int]]] | None,
) -> InlineKeyboardMarkup | None:
    if not button_specs:
        return None

    source_text = _strip_html(template_payload.get('html_text'))
    rows: list[list[InlineKeyboardButton]] = []

    for spec_row in button_specs:
        row: list[InlineKeyboardButton] = []
        for button in spec_row:
            button_type = str(button.get('type'))
            button_text = str(button.get('text') or '').strip()

            if button_type == 'stars':
                amount_stars = int(button['amount_stars'])
                invoice_title = _truncate(
                    button_text,
                    32,
                    'Оплата звездами',
                )
                invoice_description = _truncate(
                    source_text,
                    255,
                    MAIL_STARS_DEFAULT_DESCRIPTION,
                )
                invoice_link = await bot.create_invoice_link(
                    title=invoice_title,
                    description=invoice_description,
                    payload=build_mail_stars_payload(
                        amount_stars,
                        button_text,
                    ),
                    provider_token='',
                    currency='XTR',
                    prices=[
                        LabeledPrice(
                            label=invoice_title,
                            amount=amount_stars,
                        )
                    ],
                )
                row.append(
                    InlineKeyboardButton(
                        text=button_text,
                        url=invoice_link,
                    )
                )
                continue

            row.append(
                InlineKeyboardButton(
                    text=button_text,
                    url=str(button['url']),
                )
            )

        if row:
            rows.append(row)

    if not rows:
        return None

    return InlineKeyboardMarkup(inline_keyboard=rows)
