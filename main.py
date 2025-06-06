import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from handlers import setup_handlers
import logging
from middlewares import SpamDetector
from config import BOT_TOKEN, LOG

if LOG:
    logging.basicConfig(level=logging.INFO)

async def main():
    logging.info("Начало инициалиызации бота")
    bot = Bot(token=BOT_TOKEN)
    logging.info("Bot создан")
    storage = MemoryStorage()
    logging.info("Storage создан")
    await bot.delete_webhook(drop_pending_updates=True)
    dp = Dispatcher(bot=bot, storage=storage)
    dp.message.middleware.register(SpamDetector())
    logging.info("Dispatcher создан")
    setup_handlers(dp)
    logging.info("Handlers настроены")
    await dp.start_polling(bot)
    logging.info("Polling начат")

if __name__ == '__main__':
    asyncio.run(main())