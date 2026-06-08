from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def join_request(expected_index: int) -> InlineKeyboardMarkup:
    emojis = ['🛥️', '👾', '🏎️', '🌐', '🛩️', '⏳']
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=emoji,
                    callback_data='captcha:%i:%i' % (index, expected_index),
                )
                for index, emoji in enumerate(emojis[:3])
            ],
            [
                InlineKeyboardButton(
                    text=emoji,
                    callback_data='captcha:%i:%i' % (
                        index + 3,
                        expected_index,
                    ),
                )
                for index, emoji in enumerate(emojis[3:])
            ],
        ],
    )
