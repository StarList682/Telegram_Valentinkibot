from contextlib import suppress
from datetime import datetime

from aiogram import Router, F, exceptions
from aiogram import types
from aiogram.enums import ContentType
from aiogram.filters import StateFilter, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from aiogram.utils.deep_linking import create_start_link, decode_payload
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import (
    Referral,
    Sponsor,
    User as SourceUser,
    ValentineMessage,
)
from app.templates.keyboards import user as sponsor_nav
from app.utils.message_templates import (
    TEMPLATE_GREETING,
    TEMPLATE_MENU,
    load_message_template,
    send_template_message,
)
from app.utils.mailing_buttons import parse_mail_stars_payload
from app.utils.pricing import get_reveal_sender_price
from app.utils.reveal_sender import (
    REVEAL_STARS_CURRENCY,
    build_reveal_payload,
    format_sender_reveal_text,
    parse_reveal_payload,
)
from app.utils.subscription import SubscriptionService, render_subscription_text
import keyboards.handlers_kb as kb
from States.States import LinkAnswer
from main import bot
import database as db

router = Router()


def _extract_receiver_id(start_args: str | None) -> int | None:
    if not start_args:
        return None

    try:
        decoded_payload = decode_payload(start_args)
    except Exception:
        return None

    if decoded_payload.lstrip("-").isdigit():
        return int(decoded_payload)

    return None


async def _load_valentine(
    session: AsyncSession,
    valentine_id: int,
) -> ValentineMessage | None:
    return await session.get(ValentineMessage, valentine_id)


async def _resolve_sender_identity(
    session: AsyncSession,
    valentine: ValentineMessage,
) -> tuple[str | None, str | None]:
    sender = await session.get(SourceUser, int(valentine.sender_id))
    sender_name = (
        getattr(sender, 'first_name', None)
        or valentine.sender_name
        or 'Пользователь'
    )
    sender_username = (
        getattr(sender, 'username', None)
        or valentine.sender_username
    )
    return sender_name, sender_username


async def _render_reveal_text(
    session: AsyncSession,
    valentine: ValentineMessage,
) -> str:
    sender_name, sender_username = await _resolve_sender_identity(
        session,
        valentine,
    )
    return format_sender_reveal_text(
        sender_id=int(valentine.sender_id),
        sender_name=sender_name,
        sender_username=sender_username,
    )


async def _mark_valentine_revealed(
    bot_instance,
    valentine: ValentineMessage,
) -> None:
    if not valentine.receiver_message_id:
        return

    with suppress(exceptions.TelegramAPIError):
        await bot_instance.edit_message_reply_markup(
            chat_id=int(valentine.receiver_chat_id),
            message_id=int(valentine.receiver_message_id),
            reply_markup=await kb.answer_button(
                str(valentine.sender_id),
                valentine_id=valentine.id,
                revealed=True,
            ),
        )


async def _track_utc_link(
    session: AsyncSession,
    start_args: str | None,
) -> None:
    if not start_args or _extract_receiver_id(start_args) is not None:
        return

    await session.execute(
        update(Referral)
        .where(Referral.ref == start_args)
        .values(total=Referral.total + 1)
    )
    await session.commit()


async def _show_start_screen(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: types.User,
    start_args: str | None = None,
) -> None:
    await state.clear()
    await state.set_state(None)
    await db.update(user.id, user.first_name or '')
    await _track_utc_link(session, start_args)

    link = await create_start_link(bot, str(user.id), encode=True)
    inline_share_text = "\nОтправь мне анонимную валентинку!💌"
    inline_link = f'https://t.me/share/url?url={link}&text={inline_share_text}'
    greeting_payload, _ = await load_message_template(session, TEMPLATE_GREETING)
    if greeting_payload is not None:
        await send_template_message(
            bot=message.bot,
            chat_id=message.chat.id,
            payload=greeting_payload,
            user=user,
        )

    menu_payload, _ = await load_message_template(session, TEMPLATE_MENU)
    if menu_payload is not None:
        await send_template_message(
            bot=message.bot,
            chat_id=message.chat.id,
            payload=menu_payload,
            user=user,
            link=link,
            reply_markup=await kb.anon_share(inline_link),
            append_menu_link=True,
        )

    receiver_id = _extract_receiver_id(start_args)
    if receiver_id is None:
        return

    del_message = await message.answer(text="💞 Напиши валентинку")
    await state.set_state(LinkAnswer.getAnswer)
    await state.update_data(
        receiver_id=receiver_id,
        del_message_id=del_message.message_id,
    )


async def _resume_after_subscription_success(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: types.User,
) -> None:
    state_data = await state.get_data()
    pending_start_args = state_data.get("pending_start_args")
    pending_callback_data = state_data.get("pending_callback_data")

    if (
        isinstance(pending_callback_data, str)
        and pending_callback_data.startswith("answer_")
    ):
        receiver_id = pending_callback_data.split("_", 1)[1]
        await state.clear()
        del_message = await message.answer(text="💛 Напиши ответ")
        await state.set_state(LinkAnswer.getAnswer)
        await state.update_data(
            receiver_id=receiver_id,
            del_message_id=del_message.message_id,
        )
        return

    await _show_start_screen(
        message=message,
        state=state,
        session=session,
        user=user,
        start_args=(
            pending_start_args
            if isinstance(pending_start_args, str)
            else None
        ),
    )


@router.message(Command('start'), StateFilter("*"))
async def process_start_command(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    command: CommandObject | None = None,
):
    await _show_start_screen(
        message=message,
        state=state,
        session=session,
        user=message.from_user,
        start_args=(command.args if command else None),
    )


@router.callback_query(F.data == "checksub", StateFilter("*"))
async def check_subscription(
    callback: types.CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: SourceUser,
    subscription_service: SubscriptionService,
):
    if await subscription_service.has_active_op_access(session, user.id):
        with suppress(exceptions.TelegramAPIError):
            await callback.message.delete()

        user.subbed = True
        await _resume_after_subscription_success(
            message=callback.message,
            state=state,
            session=session,
            user=callback.from_user,
        )
        await session.commit()
        return

    state_data = await state.get_data()
    shown_sponsor_ids = [
        int(sponsor_id)
        for sponsor_id in state_data.get("op_sponsor_ids", [])
    ]
    flyer_signatures = list(
        dict.fromkeys(state_data.get("op_flyer_signatures", []))
    )

    if flyer_signatures:
        await subscription_service.complete_flyer_signatures(
            session=session,
            user_id=user.id,
            signatures=flyer_signatures,
        )

    sponsors, required_sponsors, sponsor_ids, new_flyer_signatures = (
        await subscription_service.resolve_items(session, user, bot)
    )
    await state.update_data(
        op_sponsor_ids=sponsor_ids,
        op_flyer_signatures=new_flyer_signatures,
    )

    if required_sponsors:
        await callback.answer(
            "Проверка не пройдена. Подпишитесь на недостающие каналы.",
            True,
        )
        updated = False
        with suppress(exceptions.TelegramAPIError):
            await callback.message.edit_text(
                render_subscription_text(sponsors, failed_check=True),
                reply_markup=sponsor_nav.inline.subscription(sponsors),
            )
            updated = True

        if not updated:
            with suppress(exceptions.TelegramAPIError):
                await callback.message.answer(
                    render_subscription_text(sponsors, failed_check=True),
                    reply_markup=sponsor_nav.inline.subscription(sponsors),
                )

        if user.subbed:
            user.subbed = False
            await session.commit()
        return

    with suppress(exceptions.TelegramAPIError):
        await callback.message.delete()

    user.subbed = True
    if not user.subbed_before:
        user.subbed_before = True

    new_sponsor_ids = await subscription_service.complete_sponsors(
        session=session,
        user_id=user.id,
        sponsor_ids=shown_sponsor_ids,
    )
    if new_sponsor_ids:
        await session.execute(
            update(Sponsor)
            .where(Sponsor.id.in_(new_sponsor_ids))
            .values(visits=Sponsor.visits + 1)
        )
        await session.execute(
            update(Sponsor)
            .where(
                Sponsor.id.in_(new_sponsor_ids),
                Sponsor.limit != 0,
                Sponsor.visits >= Sponsor.limit,
            )
            .values(is_active=False)
        )

    await subscription_service.grant_op_access(session, user.id)
    await _resume_after_subscription_success(
        message=callback.message,
        state=state,
        session=session,
        user=callback.from_user,
    )
    await session.commit()


@router.message(StateFilter(LinkAnswer.getAnswer))
async def handler(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
):
    if not message.text:
        await message.answer("Только текстом еще раз напиши 🤗")
        return
    await message.reply("Отправлено")
    link = await create_start_link(bot, str(message.from_user.id), encode=True)
    user_anon = link.split('=')[1]
    user_data = await state.get_data()
    receiver_id = user_data["receiver_id"]
    receiver_id_int = int(receiver_id)
    del_message_id = user_data["del_message_id"]
    await bot.delete_message(message.chat.id, del_message_id)
    text = f"🎁 Валентинка от <b>{user_anon}</b>:\n\n{message.html_text}"
    user_id = str(message.from_user.id)
    reveal_price = await get_reveal_sender_price(session)
    valentine = ValentineMessage(
        sender_id=int(message.from_user.id),
        receiver_id=receiver_id_int,
        receiver_chat_id=receiver_id_int,
        receiver_message_id=None,
        sender_name=message.from_user.first_name,
        sender_username=message.from_user.username,
    )
    session.add(valentine)
    await session.flush()
    inline_kb = await kb.answer_button(
        user_id,
        valentine_id=valentine.id,
        reveal_price=reveal_price,
    )
    photo = types.FSInputFile("./bot_media/notification.png")
    delivered = await bot.send_photo(
        photo=photo,
        chat_id=receiver_id_int,
        caption=text,
        reply_markup=inline_kb,
    )
    valentine.receiver_chat_id = int(delivered.chat.id)
    valentine.receiver_message_id = int(delivered.message_id)
    await session.commit()
    await state.clear()
    await state.set_state(None)


@router.callback_query(F.data.split("_")[0] == "answer", StateFilter(None))
async def send_random_value(callback: types.CallbackQuery, state: FSMContext):
    receiver_id = callback.data.split("_")[1]
    del_message = await callback.message.reply(text="💛 Напиши ответ")
    await state.set_state(LinkAnswer.getAnswer)
    await state.update_data(receiver_id=receiver_id)
    await state.update_data(del_message_id=del_message.message_id)


@router.callback_query(F.data.startswith("reveal_pay:"), StateFilter("*"))
async def reveal_sender_payment(
    callback: types.CallbackQuery,
    session: AsyncSession,
):
    parts = callback.data.split(":")
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        return await callback.answer("Некорректные параметры оплаты.", True)

    valentine_id = int(parts[1])
    amount_stars = int(parts[2])
    if amount_stars < 1:
        return await callback.answer("Цена сейчас недоступна.", True)

    valentine = await _load_valentine(session, valentine_id)
    if valentine is None:
        return await callback.answer("Валентинка не найдена.", True)

    if int(valentine.receiver_id) != int(callback.from_user.id):
        return await callback.answer(
            "Эта покупка доступна только получателю валентинки.",
            True,
        )

    if valentine.revealed_at is not None:
        await callback.answer("Отправитель уже раскрыт.", True)
        await callback.message.answer(
            await _render_reveal_text(session, valentine),
        )
        return

    await callback.bot.send_invoice(
        chat_id=callback.message.chat.id,
        title="Узнать кто отправил",
        description=(
            "Раскрытие отправителя этой валентинки.\n"
            "Стоимость: %i ⭐"
        ) % amount_stars,
        payload=build_reveal_payload(valentine_id, amount_stars),
        provider_token="",
        currency=REVEAL_STARS_CURRENCY,
        prices=[
            types.LabeledPrice(
                label="Раскрытие отправителя",
                amount=amount_stars,
            )
        ],
    )
    await callback.answer("Инвойс отправлен.")


@router.callback_query(F.data.startswith("reveal_info:"), StateFilter("*"))
async def reveal_sender_info(
    callback: types.CallbackQuery,
    session: AsyncSession,
):
    raw_id = callback.data.split(":", 1)[1]
    if not raw_id.isdigit():
        return await callback.answer("Валентинка не найдена.", True)

    valentine = await _load_valentine(session, int(raw_id))
    if valentine is None:
        return await callback.answer("Валентинка не найдена.", True)

    if int(valentine.receiver_id) != int(callback.from_user.id):
        return await callback.answer(
            "Эта информация доступна только получателю валентинки.",
            True,
        )

    if valentine.revealed_at is None:
        return await callback.answer(
            "Сначала оплатите раскрытие отправителя.",
            True,
        )

    await callback.answer()
    await callback.message.answer(
        await _render_reveal_text(session, valentine),
    )


@router.pre_checkout_query(F.invoice_payload.startswith("reveal:"))
async def reveal_pre_checkout_query(
    query: types.PreCheckoutQuery,
    session: AsyncSession,
):
    payload = parse_reveal_payload(query.invoice_payload)
    if payload is None:
        return

    valentine = await _load_valentine(session, payload.valentine_id)
    is_valid = bool(
        query.currency == REVEAL_STARS_CURRENCY
        and valentine is not None
        and int(valentine.receiver_id) == int(query.from_user.id)
        and valentine.revealed_at is None
        and query.total_amount == payload.amount_stars
    )

    await query.answer(
        ok=is_valid,
        error_message=(
            None if is_valid
            else "Не удалось проверить оплату раскрытия. Попробуйте снова."
        ),
    )


@router.pre_checkout_query(F.invoice_payload.startswith("mailstars:"))
async def mail_stars_pre_checkout_query(
    query: types.PreCheckoutQuery,
) -> None:
    amount_stars = parse_mail_stars_payload(query.invoice_payload)
    is_valid = bool(
        amount_stars is not None
        and query.currency == REVEAL_STARS_CURRENCY
        and query.total_amount == amount_stars
    )

    await query.answer(
        ok=is_valid,
        error_message=(
            None if is_valid
            else "Не удалось проверить оплату по рассылке. Попробуйте снова."
        ),
    )


@router.message(
    F.content_type == ContentType.SUCCESSFUL_PAYMENT,
    F.successful_payment.invoice_payload.startswith("reveal:"),
)
async def reveal_successful_payment(
    message: Message,
    session: AsyncSession,
):
    payment = message.successful_payment
    if payment is None or payment.currency != REVEAL_STARS_CURRENCY:
        return

    payload = parse_reveal_payload(payment.invoice_payload)
    if payload is None:
        return

    valentine = await _load_valentine(session, payload.valentine_id)
    if valentine is None:
        return await message.answer(
            "Оплата прошла, но валентинка не найдена.",
        )

    if int(valentine.receiver_id) != int(message.from_user.id):
        return

    if payment.total_amount != payload.amount_stars:
        return await message.answer(
            "Сумма оплаты не совпала. Попробуйте еще раз.",
        )

    if valentine.revealed_at is None:
        valentine.revealed_at = datetime.now()
        valentine.reveal_charge_id = payment.telegram_payment_charge_id
        valentine.reveal_stars_paid = payment.total_amount
        await session.commit()
        await _mark_valentine_revealed(message.bot, valentine)

    await message.answer(
        '✅ Оплата прошла.\n\n%s' % (
            await _render_reveal_text(session, valentine)
        ),
    )


@router.message(
    F.content_type == ContentType.SUCCESSFUL_PAYMENT,
    F.successful_payment.invoice_payload.startswith("mailstars:"),
)
async def mail_stars_successful_payment(
    message: Message,
) -> None:
    payment = message.successful_payment
    if payment is None or payment.currency != REVEAL_STARS_CURRENCY:
        return

    amount_stars = parse_mail_stars_payload(payment.invoice_payload)
    if amount_stars is None or payment.total_amount != amount_stars:
        return

    await message.answer(
        "✅ Оплата получена.\nСпасибо за покупку %i ⭐" % amount_stars
    )


@router.message(F.text, StateFilter(None))
async def handler(message: Message):
    await message.answer(
        text=f"""Вы перешли не по ссылке.\nНажмите /start чтобы вернуться 😉""")


@router.message(StateFilter(None))
async def handler(message: Message):
    await message.answer(
        text=f"""Я вас не понимаю 😥""")
