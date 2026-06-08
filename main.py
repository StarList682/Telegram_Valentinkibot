import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from admin_source import setup_source_admin
from app.utils.config import load_config
import database as db

settings = load_config()
bot = Bot(token=settings.bot.token, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())


async def main():
    from handlers import handler
    from app.utils.subscription import SubscriptionService

    await db.db_connect()
    admin_config, admin_sessionmaker = await setup_source_admin(dp)
    from app.utils.set_commands import set_commands
    subscription_service = SubscriptionService(
        flyer_key=admin_config.flyer.key,
        flyer_base_url=admin_config.flyer.base_url,
        shared_user_id=(
            admin_config.bot.admins[0]
            if admin_config.bot.admins
            else None
        ),
    )

    try:
        await set_commands(bot, admin_config, sessionmaker=admin_sessionmaker)
        if admin_config.bot.admins:
            await bot.send_message(
                chat_id=admin_config.bot.admins[0],
                text="Started bot",
            )

        dp.include_routers(handler.router)

        await bot.delete_webhook(drop_pending_updates=False)
        await dp.start_polling(
            bot,
            config=admin_config,
            subscription_service=subscription_service,
        )
    finally:
        await subscription_service.close()


if __name__ == "__main__":
    asyncio.run(main())
