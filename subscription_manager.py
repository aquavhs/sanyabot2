import logging
import datetime
import aiosqlite
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from keyboards import get_subscription_keyboard

class SubscriptionManager:
    def __init__(self, bot: Bot, db_path: str):
        self.bot = bot
        self.db_path = db_path
        
    async def extend_subscription(self, user_id: int, duration: datetime.timedelta) -> None:
        """Продлевает подписку пользователя на указанный срок"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем текущую дату окончания подписки
                query = "SELECT subscription_end FROM users WHERE user_id = ?"
                async with db.execute(query, (user_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        return
                    
                    current_end = datetime.datetime.strptime(
                        row[0],
                        "%d.%m.%Y %H:%M:%S"
                    )
                    
                    # Если подписка истекла, начинаем с текущего момента
                    if current_end < datetime.datetime.now():
                        current_end = datetime.datetime.now()
                    
                    # Рассчитываем новую дату окончания
                    new_end = current_end + duration
                    
                    # Обновляем дату окончания подписки
                    await db.execute(
                        "UPDATE users SET subscription_end = ? WHERE user_id = ?",
                        (new_end.strftime("%d.%m.%Y %H:%M:%S"), user_id)
                    )
                    await db.commit()
                    
                    # Отправляем уведомление пользователю
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=f"✅ Ваша подписка продлена!\n"
                             f"Новая дата окончания: {new_end.strftime('%d.%m.%Y %H:%M')}"
                    )
                    
        except Exception as e:
            logging.error(f"Ошибка при продлении подписки для пользователя {user_id}: {e}")
            
    async def debug_subscription_dates(self, user_id: int) -> None:
        """Метод для диагностики дат подписки"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    user = await cursor.fetchone()
                    if user:
                        now = datetime.datetime.now()
                        user_dict = dict(user)
                        logging.info(f"\n=== Диагностика подписки для пользователя {user_id} ===")
                        logging.info(f"Текущее время: {now}")
                        logging.info(f"Текущее время (строка): {now.strftime('%d.%m.%Y %H:%M:%S')}")
                        logging.info(f"Статус: {user_dict['label']}")
                        logging.info(f"Дата начала в БД: {user_dict['subscription_start']}")
                        logging.info(f"Дата окончания в БД: {user_dict['subscription_end']}")
                        
                        try:
                            end_time = datetime.datetime.strptime(
                                user_dict["subscription_end"],
                                "%d.%m.%Y %H:%M:%S"
                            )
                            time_left = end_time - now
                            seconds_left = time_left.total_seconds()
                            logging.info(f"Распарсенная дата окончания: {end_time}")
                            logging.info(f"Разница в секундах: {seconds_left}")
                            logging.info(f"Подписка {'активна' if seconds_left > 0 else 'истекла'}")
                        except ValueError as e:
                            logging.error(f"Ошибка при парсинге даты: {e}")
                        
                        logging.info("=" * 50)
                    else:
                        logging.info(f"Пользователь {user_id} не найден в базе данных")
        except Exception as e:
            logging.error(f"Ошибка при диагностике: {e}")

    async def update_user_subscription(self, user_id: int, label: str, 
                                     subscription_end: datetime.datetime) -> None:
        """Обновляет информацию о подписке пользователя"""
        try:
            now = datetime.datetime.now()
            # Форматируем даты в строки
            now_str = now.strftime("%d.%m.%Y %H:%M:%S")
            end_str = subscription_end.strftime("%d.%m.%Y %H:%M:%S")
            
            async with aiosqlite.connect(self.db_path) as db:
                # Обновляем информацию о подписке
                await db.execute("""
                    UPDATE users 
                    SET label = ?, 
                        subscription_start = ?,
                        subscription_end = ?, 
                        updated_at = ?
                    WHERE user_id = ?
                """, (
                    label,
                    now_str,
                    end_str,
                    now_str,
                    user_id
                ))
                await db.commit()
                
                # Запускаем диагностику после обновления
                await self.debug_subscription_dates(user_id)
                
        except Exception as e:
            logging.error(f"Ошибка при обновлении подписки пользователя {user_id}: {e}")
            
    async def check_expiring_subscriptions(self) -> None:
        """Проверяет истекающие подписки и отправляет уведомления"""
        try:
            now = datetime.datetime.now()
            
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                # Получаем всех пользователей для проверки
                query = "SELECT * FROM users WHERE label != 'basic_user'"
                async with db.execute(query) as cursor:
                    users = await cursor.fetchall()
                    
                # Проверяем каждого пользователя
                for user in users:
                    user_dict = dict(user)
                    # Запускаем диагностику для каждого пользователя
                    await self.debug_subscription_dates(user_dict['user_id'])
                    
                    try:
                        end_time = datetime.datetime.strptime(
                            user_dict["subscription_end"],
                            "%d.%m.%Y %H:%M:%S"
                        )
                        
                        # Проверяем статус подписки
                        time_left = end_time - now
                        seconds_left = time_left.total_seconds()
                        
                        if seconds_left <= 0:
                            # Подписка истекла
                            logging.info(f"Подписка истекла для пользователя {user_dict['user_id']}")
                            await db.execute("""
                                UPDATE users 
                                SET label = 'basic_user'
                                WHERE user_id = ?
                            """, (user_dict['user_id'],))
                            await db.commit()
                        elif seconds_left <= 3600:  # Остался час или меньше
                            minutes_left = int(seconds_left // 60)
                            logging.info(
                                f"Отправляем уведомление пользователю {user_dict['user_id']} "
                                f"(осталось {minutes_left} минут)"
                            )
                            
                            await self.bot.send_message(
                                chat_id=user_dict["user_id"],
                                text=f"⚠️ Внимание! Ваша подписка истекает через {minutes_left} минут.\n"
                                     "Чтобы продлить подписку, нажмите кнопку ниже:",
                                reply_markup=get_subscription_keyboard()
                            )
                        else:
                            logging.info(
                                f"Подписка активна для пользователя {user_dict['user_id']}, "
                                f"осталось {int(seconds_left // 3600)} часов"
                            )
                            
                    except (ValueError, TypeError) as e:
                        logging.error(
                            f"Ошибка при обработке даты подписки пользователя {user_dict['user_id']}: {e}"
                        )
                
        except Exception as e:
            logging.error(f"Ошибка при проверке истекающих подписок: {e}")
            
    async def get_subscription_info(self, user_id: int) -> dict:
        """Получает информацию о подписке пользователя"""
        try:
            async with aiosqlite.connect(self.db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        return dict(row)
            return None
            
        except Exception as e:
            logging.error(f"Ошибка при получении информации о подписке пользователя {user_id}: {e}")
            return None

    async def cancel_subscription(self, user_id: int) -> bool:
        """Отменяет подписку пользователя"""
        try:
            now = datetime.datetime.now()
            async with aiosqlite.connect(self.db_path) as db:
                # Получаем текущую информацию о пользователе
                db.row_factory = aiosqlite.Row
                async with db.execute(
                    "SELECT * FROM users WHERE user_id = ?",
                    (user_id,)
                ) as cursor:
                    user = await cursor.fetchone()
                    if not user:
                        return False
                    
                    # Обновляем информацию о пользователе
                    await db.execute("""
                        UPDATE users 
                        SET label = 'basic_user',
                            subscription_end = ?,
                            updated_at = ?
                        WHERE user_id = ?
                    """, (
                        now.strftime("%d.%m.%Y %H:%M:%S"),
                        now.strftime("%d.%m.%Y %H:%M:%S"),
                        user_id
                    ))
                    await db.commit()
                    
                    # Отправляем уведомление пользователю
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ Ваша подписка была отменена администратором."
                    )
                    
                    logging.info(f"Отменена подписка пользователя {user_id}")
                    return True
                    
        except Exception as e:
            logging.error(f"Ошибка при отмене подписки пользователя {user_id}: {e}")
            return False 