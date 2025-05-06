import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
import os
from yoomoney import Client
import datetime

from keyboards import get_main_keyboard, get_subscription_keyboard, get_admin_keyboard, get_subscription_management_keyboard
from payment_handlers import PaymentHandler
from handlers import MessageHandler
from database import Database
from functions import check_user_channel_subscription, remove_user_from_channel, check_and_remove_expired_users, ChannelManager
from utils import is_admin

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Загрузка переменных окружения
env_path = os.path.join(os.path.dirname(__file__), '.env')
logging.info(f"Путь к файлу .env: {env_path}")
logging.info(f"Файл .env существует: {os.path.exists(env_path)}")

# Читаем и выводим содержимое файла .env (без значений)
try:
    with open(env_path, 'r', encoding='utf-8') as f:
        env_content = f.read()
        logging.info("Содержимое файла .env (только имена переменных):")
        for line in env_content.splitlines():
            if line.strip() and not line.strip().startswith('#'):
                var_name = line.split('=')[0].strip()
                logging.info(f"- {var_name}")
except Exception as e:
    logging.error(f"Ошибка при чтении файла .env: {e}")

load_dotenv(env_path)

# Получение токенов из переменных окружения
BOT_TOKEN = os.getenv('BOT_TOKEN')
YOOMONEY_TOKEN = os.getenv('YOOMONEY_ACCESS_TOKEN')
WALLET_NUMBER = os.getenv('YOOMONEY_RECEIVER')
ADMIN_IDS = list(map(int, os.getenv('ADMIN_IDS', '').split(',')))  # Список ID администраторов
CHANNEL_ID = os.getenv('CHANNEL_ID')

# Отладочная информация
logging.info(f"BOT_TOKEN найден: {'Да' if BOT_TOKEN else 'Нет'}")
logging.info(f"YOOMONEY_TOKEN найден: {'Да' if YOOMONEY_TOKEN else 'Нет'}")
logging.info(f"WALLET_NUMBER найден: {'Да' if WALLET_NUMBER else 'Нет'}")
logging.info(f"CHANNEL_ID найден: {'Да' if CHANNEL_ID else 'Нет'}")

# Проверка наличия необходимых токенов
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения")
if not YOOMONEY_TOKEN:
    raise ValueError("YOOMONEY_TOKEN не найден в переменных окружения")
if not WALLET_NUMBER:
    raise ValueError("YOOMONEY_RECEIVER не найден в переменных окружения")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Инициализация клиента ЮMoney
yoomoney_client = Client(YOOMONEY_TOKEN)

# Инициализация базы данных
db = Database()

# Словарь для хранения режимов работы для админов
admin_test_modes = {}

# Инициализация обработчиков
message_handler = MessageHandler(bot, yoomoney_client)
payment_handler = PaymentHandler(bot, yoomoney_client, WALLET_NUMBER, db)

# Инициализация менеджеров
channel_manager = ChannelManager(bot, CHANNEL_ID)

# Регистрация обработчиков команд
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Обработчик команды /start"""
    try:
        is_user_admin = is_admin(message.from_user.id, ADMIN_IDS)
        
        # Проверяем, существует ли пользователь
        user = await db.get_user(message.from_user.id)
        
        if not user:
            # Создаем нового пользователя только если его нет в базе
            username_at = f"@{message.from_user.username}" if message.from_user.username else None
            await db.create_user(
                user_id=message.from_user.id,
                first_name=message.from_user.first_name,
                username=message.from_user.username or "Unknown",
                username_at=username_at,
                label="basic_user",
                subscription_start=datetime.datetime.now(),
                subscription_end=datetime.datetime.now()
            )
        else:
            # Если пользователь существует, обновляем только его имя и username
            username_at = f"@{message.from_user.username}" if message.from_user.username else None
            await db.update_user_info(
                user_id=message.from_user.id,
                first_name=message.from_user.first_name,
                username=message.from_user.username or "Unknown",
                username_at=username_at
            )
        
        # Отправляем приветственное сообщение с фото
        photo = FSInputFile("imgs/1.png")
        await message.answer_photo(
            photo=photo,
            caption=(
                "📌 *Добро пожаловать.*\n"
                "_Ты зашёл в систему, которая работает._\n\n"
                "🔸 Без лишнего шума\n"
                "🔸 Без мотивационных соплей\n"
                "🔸 Только нужные инструменты и конкретные шаги\n\n"
                "*Выбери, с чего хочешь начать. Остальное пойдёт по накатанной.*"
            ),
            reply_markup=get_main_keyboard(is_user_admin),
            parse_mode="Markdown"
        )
    except Exception as e:
        logging.error(f"Ошибка в обработчике /start: {e}")
        await message.answer("Произошла ошибка при обработке команды. Пожалуйста, попробуйте позже.")

@dp.callback_query(lambda c: c.data == "admin_panel")
async def process_admin_panel(callback_query: types.CallbackQuery):
    """Обработчик входа в админ-панель"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к админ-панели.", show_alert=True)
        return
    
    # Получаем текущий режим для админа
    is_test_mode = admin_test_modes.get(callback_query.from_user.id, False)
    
    # Удаляем предыдущее сообщение
    try:
        await callback_query.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # Отправляем новое сообщение вместо редактирования
    await callback_query.message.answer(
        "👨‍💼 Панель администратора\n"
        "Выберите действие:",
        reply_markup=get_admin_keyboard(is_test_mode)
    )

@dp.callback_query(lambda c: c.data == "toggle_test_mode")
async def process_admin_test_mode(callback_query: types.CallbackQuery):
    """Обработчик переключения тестового режима"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # Переключаем режим для админа
    admin_test_modes[callback_query.from_user.id] = not admin_test_modes.get(callback_query.from_user.id, False)
    current_mode = "тестовый" if admin_test_modes[callback_query.from_user.id] else "реальный"
    
    # Удаляем предыдущее сообщение
    try:
        await callback_query.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # Отправляем новое сообщение
    await callback_query.message.answer(
        f"👨‍💼 Панель администратора\n"
        f"Режим работы: {current_mode}\n"
        f"Выберите действие:",
        reply_markup=get_admin_keyboard(admin_test_modes[callback_query.from_user.id])
    )

@dp.callback_query(lambda c: c.data == "main_menu")
async def process_main_menu(callback_query: types.CallbackQuery):
    """Обработчик возврата в главное меню"""
    is_user_admin = is_admin(callback_query.from_user.id, ADMIN_IDS)
    
    # Удаляем предыдущее сообщение
    try:
        await callback_query.message.delete()
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # Отправляем новое сообщение
    await callback_query.message.answer(
        "👋 Главное меню\n"
        "Выберите действие:",
        reply_markup=get_main_keyboard(is_user_admin)
    )

# Добавляем заглушки для новых функций админ-панели
@dp.callback_query(lambda c: c.data == "admin_stats")
async def process_admin_stats(callback_query: types.CallbackQuery):
    """Обработчик просмотра статистики"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # TODO: Добавить реальную статистику
    await callback_query.answer("📊 Функция статистики в разработке", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_users")
async def process_admin_users(callback_query: types.CallbackQuery):
    """Обработчик просмотра пользователей"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # TODO: Добавить список пользователей
    await callback_query.answer("👥 Функция просмотра пользователей в разработке", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_balance")
async def process_admin_balance(callback_query: types.CallbackQuery):
    """Обработчик просмотра баланса"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    try:
        user = yoomoney_client.account_info()
        
        # Удаляем предыдущее сообщение
        try:
            await callback_query.message.delete()
        except Exception as e:
            logging.error(f"Ошибка при удалении сообщения: {e}")
        
        # Отправляем новое сообщение
        await callback_query.message.answer(
            f"💰 Баланс кошелька: {user.balance} {user.currency}\n\n"
            "👨‍💼 Панель администратора\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )
    except Exception as e:
        logging.error(f"Ошибка при получении баланса: {e}")
        await callback_query.answer("❌ Ошибка при получении баланса", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_settings")
async def process_admin_settings(callback_query: types.CallbackQuery):
    """Обработчик настроек"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    # TODO: Добавить настройки
    await callback_query.answer("⚙️ Функция настроек в разработке", show_alert=True)

@dp.callback_query(lambda c: c.data == "subscribe")
async def process_subscribe_button(callback_query: types.CallbackQuery):
    await message_handler.process_subscribe_button(callback_query)

@dp.callback_query(lambda c: c.data.startswith("sub_"))
async def process_subscription_choice(callback_query: types.CallbackQuery):
    # Проверяем, является ли пользователь админом и включен ли для него тестовый режим
    is_test_mode = is_admin(callback_query.from_user.id, ADMIN_IDS) and admin_test_modes.get(callback_query.from_user.id, False)
    
    # Удаляем сообщение с выбором тарифа
    await callback_query.message.delete()
    
    # Обрабатываем выбор подписки
    await payment_handler.process_subscription_choice(callback_query, test_mode=is_test_mode)

@dp.callback_query(lambda c: c.data.startswith("extend_"))
async def process_extend_subscription(callback_query: types.CallbackQuery):
    """Обработчик продления подписки"""
    await payment_handler.process_extend_subscription(callback_query)

@dp.callback_query(lambda c: c.data == "cancel_extend")
async def process_cancel_extend(callback_query: types.CallbackQuery):
    """Обработчик отмены продления подписки"""
    await payment_handler.process_cancel_extend(callback_query)

@dp.callback_query(lambda c: c.data == "cancel_payment")
async def cancel_payment(callback_query: types.CallbackQuery):
    await message_handler.cancel_payment(callback_query)

@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    await message_handler.cmd_balance(message)

@dp.callback_query(lambda c: c.data == "admin_subscriptions")
async def process_admin_subscriptions(callback_query: types.CallbackQuery):
    """Обработчик просмотра списка подписчиков"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    try:
        # Получаем список всех пользователей
        users = await db.get_all_users()
        
        if not users:
            await callback_query.message.edit_text(
                "📝 Список пользователей пуст\n\n"
                "👨‍💼 Панель администратора\n"
                "Выберите действие:",
                reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
            )
            return
        
        # Формируем текст со списком пользователей
        current_time = datetime.datetime.now()
        text = "📋 Список пользователей и их подписок:\n\n"
        
        for user in users:
            # Получаем информацию о подписке
            subscription_end = datetime.datetime.strptime(
                user["subscription_end"],
                "%d.%m.%Y %H:%M:%S"
            ) if user["subscription_end"] else None
            
            # Определяем статус подписки
            status = "❌ Неактивна"
            remaining = ""
            if subscription_end:
                if subscription_end > current_time:
                    status = "✅ Активна"
                    time_left = subscription_end - current_time
                    days = time_left.days
                    hours = time_left.seconds // 3600
                    remaining = f"(осталось: {days}д {hours}ч)"
                else:
                    status = "⚠️ Истекла"
            
            # Добавляем информацию о пользователе
            text += (
                f"👤 {user['first_name'] or 'Без имени'} {user['username_at'] or ''} (ID: {user['user_id']})\n"
                f"📝 Статус: {user['label']}\n"
                f"🔄 Подписка: {status} {remaining}\n"
                f"⚡️ Действия: /extend_{user['user_id']}\n"
                "➖➖➖➖➖➖➖➖➖➖\n"
            )
        
        # Добавляем инструкцию по использованию
        text += "\n🔍 Для управления подпиской пользователя, нажмите на соответствующую команду /extend_ID"
        
        # Отправляем сообщение с информацией
        await callback_query.message.edit_text(
            text,
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )
        
    except Exception as e:
        logging.error(f"Ошибка при получении списка пользователей: {e}")
        await callback_query.message.edit_text(
            "❌ Произошла ошибка при получении списка пользователей\n\n"
            "👨‍💼 Панель администратора\n"
            "Выберите действие:",
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )

@dp.message(lambda message: message.text and message.text.startswith("/extend_"))
async def process_extend_command(message: types.Message):
    """Обработчик команды продления подписки"""
    if not is_admin(message.from_user.id, ADMIN_IDS):
        await message.answer("⛔ У вас нет доступа к этой функции.")
        return
    
    try:
        # Получаем ID пользователя из команды
        user_id = int(message.text.split("_")[1])
        
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        if not user:
            await message.answer("❌ Пользователь не найден.")
            return
        
        # Отправляем сообщение с клавиатурой для управления подпиской
        subscription_end = datetime.datetime.strptime(
            user["subscription_end"],
            "%d.%m.%Y %H:%M:%S"
        ) if user["subscription_end"] else "не активна"
        
        await message.answer(
            f"👤 Управление подпиской пользователя:\n"
            f"ID: {user['user_id']}\n"
            f"Имя: {user['first_name'] or 'Без имени'}\n"
            f"Статус: {user['label']}\n"
            f"Подписка до: {subscription_end}\n\n"
            f"Выберите действие:",
            reply_markup=get_subscription_management_keyboard(user_id)
        )
        
    except (ValueError, IndexError):
        await message.answer("❌ Неверный формат команды. Используйте /extend_ID")
    except Exception as e:
        logging.error(f"Ошибка при обработке команды продления: {e}")
        await message.answer("❌ Произошла ошибка при обработке команды.")

@dp.callback_query(lambda c: c.data.startswith("admin_extend_"))
async def process_admin_extend(callback_query: types.CallbackQuery):
    """Обработчик продления подписки администратором"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    try:
        # Разбираем callback_data
        _, _, user_id, period = callback_query.data.split("_")
        user_id = int(user_id)
        
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        if not user:
            await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        # Определяем длительность продления
        duration_map = {
            "day": datetime.timedelta(days=1),
            "week": datetime.timedelta(days=7),
            "month": datetime.timedelta(days=30)
        }
        duration = duration_map.get(period)
        if not duration:
            await callback_query.answer("❌ Неверный период продления.", show_alert=True)
            return
        
        # Определяем новую дату окончания подписки
        current_end = datetime.datetime.strptime(
            user["subscription_end"],
            "%d.%m.%Y %H:%M:%S"
        ) if user["subscription_end"] else datetime.datetime.now()
        
        # Если подписка истекла, начинаем с текущего момента
        if current_end < datetime.datetime.now():
            current_end = datetime.datetime.now()
        
        new_end = current_end + duration
        
        # Обновляем дату окончания подписки
        await db.update_user_subscription(
            user_id=user_id,
            subscription_end=new_end
        )
        
        # Получаем ссылку на канал
        try:
            chat = await bot.get_chat(CHANNEL_ID)
            invite_link = chat.invite_link
            if not invite_link:
                invite_link = await bot.create_chat_invite_link(CHANNEL_ID)
                invite_link = invite_link.invite_link
        except Exception as e:
            logging.error(f"Ошибка при получении ссылки на канал: {e}")
            invite_link = None
        
        # Отправляем уведомление пользователю
        try:
            message_text = (
                f"🎉 Ваша подписка была продлена администратором!\n"
                f"Новая дата окончания: {new_end.strftime('%d.%m.%Y %H:%M')}"
            )
            
            if invite_link:
                message_text += f"\n\n🔗 Ссылка на канал: {invite_link}"
            
            await bot.send_message(
                chat_id=user_id,
                text=message_text
            )
        except Exception as e:
            logging.error(f"Не удалось отправить уведомление пользователю {user_id}: {e}")
        
        # Отправляем подтверждение администратору
        await callback_query.message.edit_text(
            f"✅ Подписка пользователя {user['first_name'] or user_id} успешно продлена!\n"
            f"Новая дата окончания: {new_end.strftime('%d.%m.%Y %H:%M')}\n\n"
            f"Выберите действие:",
            reply_markup=get_subscription_management_keyboard(user_id)
        )
        
    except Exception as e:
        logging.error(f"Ошибка при продлении подписки: {e}")
        await callback_query.answer("❌ Произошла ошибка при продлении подписки.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("admin_cancel_"))
async def process_admin_cancel(callback_query: types.CallbackQuery):
    """Обработчик отмены подписки администратором"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔ У вас нет доступа к этой функции.", show_alert=True)
        return
    
    try:
        # Получаем ID пользователя из callback_data
        user_id = int(callback_query.data.replace("admin_cancel_", ""))
        
        # Получаем информацию о пользователе
        user = await db.get_user(user_id)
        if not user:
            await callback_query.answer("❌ Пользователь не найден.", show_alert=True)
            return
        
        # Проверяем, есть ли пользователь в канале
        if await channel_manager.check_user_subscription(user_id):
            # Удаляем пользователя из канала
            if await channel_manager.remove_user(user_id):
                logging.info(f"Пользователь {user_id} удален из канала (отмена подписки администратором)")
            else:
                logging.error(f"Не удалось удалить пользователя {user_id} из канала")
        
        # Отменяем подписку
        if await payment_handler.subscription_manager.cancel_subscription(user_id):
            await callback_query.message.edit_text(
                f"✅ Подписка пользователя {user['first_name']} успешно отменена.\n"
                f"Пользователь удален из канала.\n\n"
                f"Выберите действие:",
                reply_markup=get_subscription_management_keyboard(user_id)
            )
        else:
            await callback_query.answer("❌ Произошла ошибка при отмене подписки.", show_alert=True)
        
    except Exception as e:
        logging.error(f"Ошибка при отмене подписки: {e}")
        await callback_query.answer("❌ Произошла ошибка при отмене подписки.", show_alert=True)

@dp.callback_query(lambda c: c.data == "admin_channel")
async def admin_channel_handler(callback_query: types.CallbackQuery):
    """Обработчик управления каналом"""
    if not is_admin(callback_query.from_user.id, ADMIN_IDS):
        await callback_query.answer("⛔️ У вас нет прав администратора", show_alert=True)
        return

    if not CHANNEL_ID:
        await callback_query.message.edit_text(
            "⚠️ Канал не настроен!\n\n"
            "Для настройки:\n"
            "1. Добавьте бота в канал как администратора\n"
            "2. Установите переменную CHANNEL_ID в файле .env\n"
            "Пример: CHANNEL_ID=-100123456789",
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )
        return

    try:
        chat = await bot.get_chat(CHANNEL_ID)
        members_count = await bot.get_chat_member_count(CHANNEL_ID)
        
        expired_users = await db.get_expired_subscriptions()
        expired_count = 0
        
        for user in expired_users:
            if await check_user_channel_subscription(bot, CHANNEL_ID, user['user_id']):
                expired_count += 1
        
        message = (
            f"📢 Информация о канале\n\n"
            f"Название: {chat.title}\n"
            f"ID: {CHANNEL_ID}\n"
            f"Участников: {members_count}\n"
            f"Пользователей с истекшей подпиской: {expired_count}\n\n"
            f"🤖 Статус бота: ✅ Администратор\n"
            f"Автоудаление: ✅ Активно"
        )
        
        await callback_query.message.edit_text(
            message,
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )
    except Exception as e:
        logging.error(f"Ошибка при получении информации о канале: {e}")
        await callback_query.message.edit_text(
            "❌ Ошибка при получении информации о канале. "
            "Проверьте права бота и ID канала.",
            reply_markup=get_admin_keyboard(admin_test_modes.get(callback_query.from_user.id, False))
        )

# Добавляем запуск проверки при старте бота
async def on_startup(dp):
    asyncio.create_task(check_and_remove_expired_users(bot, CHANNEL_ID, db))

# Функция запуска бота
async def main():
    try:
        # Запускаем фоновые задачи
        await payment_handler.start_background_tasks()
        
        # Запуск задачи проверки подписок при старте
        await on_startup(dp)
        
        # Запуск бота
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка при запуске бота: {e}")
    finally:
        # Останавливаем фоновые задачи при завершении работы
        await payment_handler.stop_background_tasks()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main()) 