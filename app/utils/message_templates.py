from __future__ import annotations

import copy
import html
from typing import Any

from aiogram import Bot, types
from aiogram.types import FSInputFile, InlineKeyboardMarkup
from aiogram.utils.text_decorations import html_decoration
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import MessageTemplate

TEMPLATE_GREETING = 'greeting'
TEMPLATE_MENU = 'menu'

TEXT_CAPABLE_CONTENT_TYPES = {
    types.ContentType.TEXT,
    types.ContentType.PHOTO,
    types.ContentType.VIDEO,
    types.ContentType.ANIMATION,
    types.ContentType.DOCUMENT,
    types.ContentType.AUDIO,
    types.ContentType.VOICE,
}
SUPPORTED_TEMPLATE_CONTENT_TYPES = TEXT_CAPABLE_CONTENT_TYPES | {
    types.ContentType.STICKER,
    types.ContentType.VIDEO_NOTE,
}
CONTENT_TYPE_TITLES = {
    types.ContentType.TEXT: 'текст',
    types.ContentType.PHOTO: 'фото',
    types.ContentType.VIDEO: 'видео',
    types.ContentType.ANIMATION: 'GIF / анимация',
    types.ContentType.DOCUMENT: 'документ',
    types.ContentType.AUDIO: 'аудио',
    types.ContentType.VOICE: 'голосовое',
    types.ContentType.STICKER: 'стикер',
    types.ContentType.VIDEO_NOTE: 'видеокружок',
}

DEFAULT_MESSAGE_TEMPLATES: dict[str, dict[str, Any]] = {
    TEMPLATE_GREETING: {
        'content_type': types.ContentType.TEXT,
        'html_text': '👋 Привет, <b>{name}</b>!',
        'file_id': None,
    },
    TEMPLATE_MENU: {
        'content_type': types.ContentType.PHOTO,
        'file_id': None,
        'file_path': './bot_media/welcome.jpg',
        'html_text': (
            '👀 Привет!\n'
            '💌 Я Бот <b>Анонимная валентинка!</b>\n\n'
            'Чтобы тебе отправили валентинку, поделись ссылкой:\n\n'
            '<code>{link}</code>'
        ),
    },
}


class UnsupportedTemplateContentType(ValueError):
    pass


def get_content_type_title(content_type: str | None) -> str:
    return CONTENT_TYPE_TITLES.get(content_type or '', content_type or 'неизвестно')


def _render_source_text(message: types.Message) -> str | None:
    if message.text is not None:
        return html_decoration.unparse(message.text, message.entities)

    if message.caption is not None:
        return html_decoration.unparse(
            message.caption,
            message.caption_entities,
        )

    return None


def _build_message_payload(message: types.Message) -> dict[str, Any]:
    html_text = _render_source_text(message)

    if message.text is not None:
        return {
            'content_type': types.ContentType.TEXT,
            'file_id': None,
            'html_text': html_text,
        }

    if message.photo:
        return {
            'content_type': types.ContentType.PHOTO,
            'file_id': message.photo[-1].file_id,
            'html_text': html_text,
        }

    if message.video:
        return {
            'content_type': types.ContentType.VIDEO,
            'file_id': message.video.file_id,
            'html_text': html_text,
        }

    if message.animation:
        return {
            'content_type': types.ContentType.ANIMATION,
            'file_id': message.animation.file_id,
            'html_text': html_text,
        }

    if message.document:
        return {
            'content_type': types.ContentType.DOCUMENT,
            'file_id': message.document.file_id,
            'html_text': html_text,
        }

    if message.audio:
        return {
            'content_type': types.ContentType.AUDIO,
            'file_id': message.audio.file_id,
            'html_text': html_text,
        }

    if message.voice:
        return {
            'content_type': types.ContentType.VOICE,
            'file_id': message.voice.file_id,
            'html_text': html_text,
        }

    if message.sticker:
        return {
            'content_type': types.ContentType.STICKER,
            'file_id': message.sticker.file_id,
            'html_text': None,
        }

    if message.video_note:
        return {
            'content_type': types.ContentType.VIDEO_NOTE,
            'file_id': message.video_note.file_id,
            'html_text': None,
        }

    raise UnsupportedTemplateContentType(message.content_type)


def extract_template_payload(message: types.Message) -> dict[str, Any]:
    if message.content_type not in SUPPORTED_TEMPLATE_CONTENT_TYPES:
        raise UnsupportedTemplateContentType(message.content_type)

    return _build_message_payload(message)


def _resolve_name(user: Any | None) -> str:
    if user is None:
        return ''

    first_name = (getattr(user, 'first_name', None) or '').strip()
    if first_name:
        return first_name

    username = (getattr(user, 'username', None) or '').strip()
    if username:
        return username

    return 'пользователь'


def _resolve_username(user: Any | None) -> str:
    if user is None:
        return ''

    return (getattr(user, 'username', None) or '').strip()


def render_template_html(
    template_html: str | None,
    user: Any | None = None,
    *,
    link: str | None = None,
) -> str | None:
    if template_html is None:
        return None

    rendered = template_html
    placeholders = {
        '{name}': _resolve_name(user),
        '{username}': _resolve_username(user),
        '{link}': link or '',
    }
    for placeholder, value in placeholders.items():
        rendered = rendered.replace(placeholder, html.escape(value))

    return rendered


def _attach_menu_link(
    source_html: str | None,
    rendered_html: str | None,
    payload: dict[str, Any],
    *,
    link: str | None,
    append_menu_link: bool,
) -> str | None:
    if not append_menu_link or not link:
        return rendered_html

    if payload.get('content_type') not in TEXT_CAPABLE_CONTENT_TYPES:
        return rendered_html

    source_html = source_html or ''
    if '{link}' in source_html:
        return rendered_html

    link_html = '<code>%s</code>' % html.escape(link)
    if rendered_html:
        return '%s\n\n%s' % (rendered_html, link_html)
    return link_html


def personalize_template_payload(
    payload: dict[str, Any],
    user: Any | None = None,
    *,
    link: str | None = None,
    append_menu_link: bool = False,
) -> dict[str, Any]:
    personalized = dict(payload)
    source_html = personalized.get('html_text')
    rendered_html = render_template_html(source_html, user, link=link)
    personalized['html_text'] = _attach_menu_link(
        source_html,
        rendered_html,
        personalized,
        link=link,
        append_menu_link=append_menu_link,
    )
    return personalized


def normalize_reply_markup(
    reply_markup: InlineKeyboardMarkup | dict[str, Any] | None,
) -> InlineKeyboardMarkup | None:
    if reply_markup is None:
        return None

    if isinstance(reply_markup, InlineKeyboardMarkup):
        return reply_markup

    return InlineKeyboardMarkup.model_validate(reply_markup)


async def send_template_message(
    bot: Bot,
    chat_id: int,
    payload: dict[str, Any],
    *,
    user: Any | None = None,
    link: str | None = None,
    reply_markup: InlineKeyboardMarkup | dict[str, Any] | None = None,
    append_menu_link: bool = False,
) -> types.Message:
    rendered = personalize_template_payload(
        payload,
        user,
        link=link,
        append_menu_link=append_menu_link,
    )
    markup = normalize_reply_markup(reply_markup)
    content_type = rendered['content_type']
    file_id = rendered.get('file_id')
    html_text = rendered.get('html_text')

    if content_type == types.ContentType.TEXT:
        return await bot.send_message(
            chat_id=chat_id,
            text=html_text or '',
            reply_markup=markup,
        )

    media: str | FSInputFile | None = file_id
    if media is None and rendered.get('file_path'):
        media = FSInputFile(rendered['file_path'])

    if media is None:
        raise ValueError('Template media source is missing.')

    if content_type == types.ContentType.PHOTO:
        return await bot.send_photo(
            chat_id=chat_id,
            photo=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.VIDEO:
        return await bot.send_video(
            chat_id=chat_id,
            video=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.ANIMATION:
        return await bot.send_animation(
            chat_id=chat_id,
            animation=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.DOCUMENT:
        return await bot.send_document(
            chat_id=chat_id,
            document=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.AUDIO:
        return await bot.send_audio(
            chat_id=chat_id,
            audio=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.VOICE:
        return await bot.send_voice(
            chat_id=chat_id,
            voice=media,
            caption=html_text,
            reply_markup=markup,
        )

    if content_type == types.ContentType.STICKER:
        return await bot.send_sticker(
            chat_id=chat_id,
            sticker=media,
            reply_markup=markup,
        )

    if content_type == types.ContentType.VIDEO_NOTE:
        return await bot.send_video_note(
            chat_id=chat_id,
            video_note=media,
            reply_markup=markup,
        )

    raise UnsupportedTemplateContentType(content_type)


def template_to_payload(template: MessageTemplate) -> dict[str, Any]:
    return {
        'content_type': template.content_type,
        'file_id': template.file_id,
        'html_text': template.html_text,
    }


async def load_message_template(
    session: AsyncSession,
    key: str,
) -> tuple[dict[str, Any] | None, bool]:
    template = await session.get(MessageTemplate, key)
    if template is not None:
        return template_to_payload(template), True

    default_payload = DEFAULT_MESSAGE_TEMPLATES.get(key)
    if default_payload is None:
        return None, False

    return copy.deepcopy(default_payload), False


async def save_message_template(
    session: AsyncSession,
    key: str,
    payload: dict[str, Any],
) -> MessageTemplate:
    template = await session.get(MessageTemplate, key)
    if template is None:
        template = MessageTemplate(key=key)
        session.add(template)

    template.content_type = payload['content_type']
    template.file_id = payload.get('file_id')
    template.html_text = payload.get('html_text')
    await session.commit()
    return template


async def reset_message_template(
    session: AsyncSession,
    key: str,
) -> None:
    template = await session.get(MessageTemplate, key)
    if template is None:
        return

    await session.delete(template)
    await session.commit()
