from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from app.utils.reveal_sender import format_reveal_button_text


async def anon_share(url) -> InlineKeyboardMarkup:
    text = "Поделиться ссылкой"
    buttons = [
        [
            InlineKeyboardButton(text=text, url=url)
        ]
    ]
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    return keyboard


async def answer_button(
    user_id,
    valentine_id: int | None = None,
    reveal_price: int | None = None,
    revealed: bool = False,
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text="Ответить",
                callback_data=f"answer_{user_id}",
            )
        ]
    ]

    if valentine_id is not None:
        if revealed:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text="Отправитель раскрыт ✅",
                        callback_data=f"reveal_info:{valentine_id}",
                    )
                ]
            )
        elif reveal_price is not None and reveal_price > 0:
            buttons.append(
                [
                    InlineKeyboardButton(
                        text=format_reveal_button_text(reveal_price),
                        callback_data=(
                            f"reveal_pay:{valentine_id}:{reveal_price}"
                        ),
                    )
                ]
            )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)
    return keyboard
