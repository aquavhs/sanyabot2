import asyncio
import logging
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest
import datetime

# Функции для работы с каналом
async def check_user_channel_subscription(bot: Bot, channel_id: str, user_id: int) -> bool:
    """Проверяет, подписан ли пользователь на канал"""
    try:
        member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        return member.status not in ['left', 'kicked', 'banned']
    except TelegramBadRequest:
        return False

async def remove_user_from_channel(bot: Bot, channel_id: str, user_id: int) -> bool:
    """Удаляет пользователя из канала"""
    try:
        await bot.ban_chat_member(chat_id=channel_id, user_id=user_id)
        await bot.unban_chat_member(chat_id=channel_id, user_id=user_id)  # Разбаниваем, чтобы пользователь мог вернуться
        return True
    except Exception as e:
        logging.error(f"Ошибка при удалении пользователя {user_id} из канала: {e}")
        return False

async def check_and_remove_expired_users(bot: Bot, channel_id: str, db):
    """Проверяет и удаляет пользователей с истекшей подпиской из канала"""
    while True:
        try:
            # Получаем пользователей с истекшей подпиской
            expired_users = await db.get_expired_subscriptions()
            
            for user in expired_users:
                # Проверяем, есть ли пользователь в канале
                if await check_user_channel_subscription(bot, channel_id, user['user_id']):
                    # Удаляем пользователя из канала
                    if await remove_user_from_channel(bot, channel_id, user['user_id']):
                        logging.info(f"Пользователь {user['user_id']} удален из канала (истекла подписка)")
                        try:
                            # Уведомляем пользователя
                            await bot.send_message(
                                user['user_id'],
                                "❌ Ваша подписка истекла. Вы были удалены из канала. "
                                "Для возобновления доступа, пожалуйста, продлите подписку."
                            )
                        except Exception as e:
                            logging.error(f"Не удалось отправить уведомление пользователю {user['user_id']}: {e}")
        
        except Exception as e:
            logging.error(f"Ошибка при проверке истекших подписок: {e}")
        
        # Проверяем каждый час
        await asyncio.sleep(3600)

# Класс для управления каналом
class ChannelManager:
    def __init__(self, bot: Bot, channel_id: str):
        self.bot = bot
        self.channel_id = channel_id

    async def check_user_subscription(self, user_id: int) -> bool:
        """Проверяет, подписан ли пользователь на канал"""
        try:
            member = await self.bot.get_chat_member(chat_id=self.channel_id, user_id=user_id)
            return member.status not in ['left', 'kicked', 'banned']
        except TelegramBadRequest:
            return False

    async def remove_user(self, user_id: int) -> bool:
        """Удаляет пользователя из канала"""
        try:
            await self.bot.ban_chat_member(chat_id=self.channel_id, user_id=user_id)
            await self.bot.unban_chat_member(chat_id=self.channel_id, user_id=user_id)  # Разбаниваем, чтобы пользователь мог вернуться
            return True
        except Exception as e:
            logging.error(f"Ошибка при удалении пользователя {user_id} из канала: {e}")
            return False 