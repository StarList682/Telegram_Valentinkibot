import time
import asyncio

from typing import Any, Optional
from contextlib import suppress

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter

from app.utils.message_templates import send_template_message


class MailerSingleton(object):
    DEFAULT_DELAY = 1 / 25
    MAX_IN_FLIGHT = 32
    __instance = None

    def __init__(self, delay: int | float = None) -> None:
        if MailerSingleton.__instance is not None:
            raise Exception('MailingSingleton is a singleton!')

        self.delay = delay or self.DEFAULT_DELAY
        self.TIME_STARTED = 0
        self.last_update = 0
        self._resume_at = 0
        self._next_send_at = 0
        self._send_lock = asyncio.Lock()
        MailerSingleton.__instance = self

    @staticmethod
    def get_instance() -> 'MailerSingleton':
        if MailerSingleton.__instance is None:
            MailerSingleton()
        return MailerSingleton.__instance

    @staticmethod
    def pretty_time(seconds: float) -> str:
        seconds = int(seconds)
        return '%0d:%0d:%0d' % (
            seconds // 3600,
            seconds % 3600 // 60,
            seconds % 60
        )

    @classmethod
    def get_text(cls, scope: list[Any], sent: int, delay: float) -> str:
        total = max(len(scope), 1)
        progress = int(sent / total * 25)
        progress_bar = ('=' * progress) + (' ' * (25 - progress))

        return "<code>[%s]</code> %s/%s (ETA: %s)" % (
            progress_bar,
            sent,
            len(scope),
            cls.pretty_time(max(len(scope) - sent, 0) * delay)
        )

    async def _wait_for_send_slot(self, time_started: float) -> bool:
        async with self._send_lock:
            while self.TIME_STARTED == time_started:
                resume_at = max(self._resume_at, self._next_send_at)
                remaining = resume_at - time.monotonic()
                if remaining > 0:
                    await asyncio.sleep(min(remaining, 0.5))
                    continue

                self._next_send_at = time.monotonic() + self.delay
                return True
        return False

    async def _deliver(
        self,
        template_payload: dict,
        reply_markup: Optional[dict],
        bot: Bot,
        user: Any,
        time_started: float,
    ) -> bool | None:
        while await self._wait_for_send_slot(time_started):
            try:
                await send_template_message(
                    bot=bot,
                    chat_id=int(user.id),
                    payload=template_payload,
                    user=user,
                    reply_markup=reply_markup,
                    link=None,
                    append_menu_link=False,
                )
                return True
            except TelegramRetryAfter as exc:
                self._resume_at = max(
                    self._resume_at,
                    time.monotonic() + exc.retry_after,
                )
            except TelegramAPIError:
                return False
        return None

    async def start_mailing(
        self,
        template_payload: dict,
        reply_markup: Optional[dict],
        chat_id: int,
        bot: Bot,
        scope: list[Any],
        cancel_keyboard: dict
    ) -> None:
        self.TIME_STARTED = time.monotonic()

        time_started = self.TIME_STARTED
        delay = self.delay
        sent = 0
        failed = 0
        processed = 0
        tasks = set()
        self._resume_at = 0
        self._next_send_at = 0

        message = await bot.send_message(
            chat_id,
            self.get_text(scope, 0, delay),
            reply_markup=cancel_keyboard,
        )
        self.last_update = time.monotonic()

        async def update_progress() -> None:
            if time.monotonic() - self.last_update > 2:
                self.last_update = time.monotonic()
                with suppress(TelegramAPIError):
                    await message.edit_text(
                        self.get_text(scope, processed, delay),
                        reply_markup=cancel_keyboard,
                    )

        def collect(done: set[asyncio.Task]) -> None:
            nonlocal sent, failed, processed
            for task in done:
                result = task.result()
                if result is None:
                    continue
                processed += 1
                if result:
                    sent += 1
                else:
                    failed += 1

        for user in scope:
            if self.TIME_STARTED != time_started:
                break

            if len(tasks) >= self.MAX_IN_FLIGHT:
                done, tasks = await asyncio.wait(
                    tasks,
                    return_when=asyncio.FIRST_COMPLETED,
                )
                collect(done)
                await update_progress()

            tasks.add(asyncio.create_task(
                self._deliver(
                    template_payload,
                    reply_markup,
                    bot,
                    user,
                    time_started,
                )
            ))

        while tasks:
            done, tasks = await asyncio.wait(
                tasks,
                return_when=asyncio.FIRST_COMPLETED,
            )
            collect(done)
            await update_progress()

        stopped = self.TIME_STARTED != time_started

        with suppress(TelegramAPIError):
            await message.edit_text(
                self.get_text(scope, processed, delay),
            )

        await message.answer(
            '%s Успешно: %s. Ошибок доставки: %s' % (
                (
                    'Рассылка остановлена.'
                    if stopped
                    else 'Рассылка завершена.'
                ),
                sent,
                failed,
            ),
        )
        if self.TIME_STARTED == time_started:
            self.TIME_STARTED = 0

    def stop_mailing(self) -> bool:
        if self.TIME_STARTED == 0:
            return False

        self.TIME_STARTED = 0
        return True

    @property
    def is_mailing(self) -> bool:
        return self.TIME_STARTED != 0
