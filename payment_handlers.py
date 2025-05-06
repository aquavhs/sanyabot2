import asyncio
import logging
import datetime
from aiogram import Bot, types
from aiogram import Dispatcher
from yoomoney import Client, Quickpay
from keyboards import get_payment_keyboard, get_subscription_keyboard, get_main_keyboard
from database import Database
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from subscription_manager import SubscriptionManager
from utils import is_admin
from aiogram.types import FSInputFile

# Словарь с ценами и названиями подписок
SUBSCRIPTION_PRICES = {
    "sub_basic": {
        "amount": 90,
        "name": "Подписка на день",
        "label": "basic_user",
        "duration": datetime.timedelta(days=1)
    },
    "sub_standard": {
        "amount": 440,
        "name": "Подписка на неделю",
        "label": "standard_user",
        "duration": datetime.timedelta(days=7)
    },
    "sub_premium": {
        "amount": 1620,
        "name": "Подписка на месяц",
        "label": "premium_user",
        "duration": datetime.timedelta(days=30)
    }
}

class PaymentHandler:
    def __init__(self, bot: Bot, yoomoney_client: Client, wallet_number: str, db: Database):
        self.bot = bot
        self.yoomoney_client = yoomoney_client
        self.wallet_number = wallet_number
        self.db = db
        self.subscription_manager = SubscriptionManager(bot, db.db_path)
        self._check_subscriptions_task = None

    async def start_background_tasks(self):
        """Запускает фоновые задачи"""
        self._check_subscriptions_task = asyncio.create_task(self._check_subscriptions_loop())

    async def stop_background_tasks(self):
        """Останавливает фоновые задачи"""
        if self._check_subscriptions_task:
            self._check_subscriptions_task.cancel()
            try:
                await self._check_subscriptions_task
            except asyncio.CancelledError:
                pass

    async def _check_subscriptions_loop(self):
        """Цикл проверки подписок"""
        while True:
            try:
                await self.subscription_manager.check_expiring_subscriptions()
                await asyncio.sleep(300)  # Проверяем каждые 5 минут
            except Exception as e:
                logging.error(f"Ошибка в цикле проверки подписок: {e}")
                await asyncio.sleep(60)

    async def assign_user_label(self, user_id: int, username: str, subscription_type: str) -> None:
        """
        Присваивает индивидуальный label пользователю после успешной оплаты
        
        Args:
            user_id (int): ID пользователя в Telegram
            username (str): Имя пользователя
            subscription_type (str): Тип подписки (sub_basic, sub_standard, sub_premium)
        """
        try:
            # Получаем информацию о подписке
            sub_info = SUBSCRIPTION_PRICES[subscription_type]
            user_label = sub_info["label"]
            
            # Рассчитываем время начала и окончания подписки
            start_time = datetime.datetime.now()
            end_time = start_time + sub_info["duration"]
            
            # Формируем username_at
            username_at = f"@{username}" if username and username != "Unknown" else None
            
            # Получаем информацию о пользователе
            user = await self.db.get_user(user_id)
            first_name = user["first_name"] if user else "Unknown"
            
            # Сохраняем информацию в базу данных
            await self.db.create_user(
                user_id=user_id,
                first_name=first_name,
                username=username,
                username_at=username_at,
                label=user_label,
                subscription_start=start_time,
                subscription_end=end_time
            )
            
            # Отправляем единое сообщение с информацией о подписке и кнопкой
            photo = FSInputFile("imgs/3.png")
            await self.bot.send_photo(
                chat_id=user_id,
                photo=photo,
                caption=(
                    "🎉 Поздравляем с успешной оплатой!\n\n"
                    f"📅 Подписка активна до: {end_time.strftime('%d.%m.%Y %H:%M')}\n\n"
                    "Нажмите кнопку ниже, чтобы присоединиться к нашему каналу:"
                ),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(
                            text="📢 Присоединиться к каналу",
                            url="https://t.me/+9dOYr5Z3XMk3YjQy"
                        )]
                    ]
                ),
                parse_mode="Markdown"
            )
            
            logging.info(f"Пользователю {user_id} присвоен label: {user_label}")
            
        except Exception as e:
            logging.error(f"Ошибка при присвоении label пользователю {user_id}: {e}")
            await self.bot.send_message(
                chat_id=user_id,
                text="Произошла ошибка при присвоении статуса. Пожалуйста, обратитесь в поддержку."
            )

    async def process_subscription_choice(self, callback_query: types.CallbackQuery, test_mode: bool = False):
        """Обработчик выбора подписки"""
        try:
            subscription_type = callback_query.data
            selected_sub = SUBSCRIPTION_PRICES.get(subscription_type)
            
            if not selected_sub:
                await callback_query.answer("❌ Неверный тип подписки", show_alert=True)
                return
            
            # Проверяем наличие активной подписки
            user_info = await self.subscription_manager.get_subscription_info(callback_query.from_user.id)
            if user_info and user_info.get("subscription_end"):
                end_time = datetime.datetime.strptime(
                    user_info["subscription_end"],
                    "%d.%m.%Y %H:%M:%S"
                )
                if end_time > datetime.datetime.now():
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="✅ Продлить",
                                    callback_data=f"extend_{subscription_type}"
                                ),
                                InlineKeyboardButton(
                                    text="❌ Отмена",
                                    callback_data="cancel_extend"
                                )
                            ]
                        ]
                    )
                    await callback_query.message.answer(
                        f"У вас уже есть активная подписка до: {end_time.strftime('%d.%m.%Y %H:%M')}\n"
                        "Хотите продлить?",
                        reply_markup=keyboard
                    )
                    return
            
            if test_mode:
                # Тестовый режим - симулируем успешную оплату
                await self.assign_user_label(
                    callback_query.from_user.id,
                    callback_query.from_user.username or "Unknown",
                    subscription_type
                )
                return
            
            # Создаем форму для оплаты через ЮMoney
            quickpay = Quickpay(
                receiver=self.wallet_number,
                quickpay_form="shop",
                targets=f"Оплата {selected_sub['name']}",
                paymentType="AC",
                sum=selected_sub['amount'],
                label=f"{callback_query.from_user.id}_{callback_query.data}"
            )
            
            await callback_query.message.answer(
                f"💳 Для оплаты {selected_sub['name']} на сумму {selected_sub['amount']}₽, "
                "нажмите кнопку 'Оплатить' ниже.\n\n"
                "⏳ После оплаты бот автоматически проверит статус платежа.\n"
                "Время ожидания: 10 минут",
                reply_markup=get_payment_keyboard(quickpay.redirected_url)
            )
            
            # Запускаем проверку оплаты
            asyncio.create_task(self.check_payment(
                label=f"{callback_query.from_user.id}_{callback_query.data}",
                chat_id=callback_query.message.chat.id
            ))
            
        except Exception as e:
            logging.error(f"Ошибка при создании формы оплаты: {e}")
            await callback_query.message.answer("Произошла ошибка при создании формы оплаты. Попробуйте позже.")

    async def process_extend_subscription(self, callback_query: types.CallbackQuery):
        """Обработчик продления подписки"""
        try:
            subscription_type = callback_query.data.replace("extend_", "")
            selected_sub = SUBSCRIPTION_PRICES.get(subscription_type)
            
            if not selected_sub:
                await callback_query.answer("❌ Неверный тип подписки", show_alert=True)
                return

            quickpay = Quickpay(
                receiver=self.wallet_number,
                quickpay_form="shop",
                targets=f"Продление {selected_sub['name']}",
                paymentType="AC",
                sum=selected_sub['amount'],
                label=f"{callback_query.from_user.id}_extend_{subscription_type}"
            )
            
            await callback_query.message.edit_text(
                f"💳 Для продления {selected_sub['name']} на сумму {selected_sub['amount']}₽, "
                "нажмите кнопку 'Оплатить' ниже.\n\n"
                "⏳ После оплаты бот автоматически проверит статус платежа.\n"
                "Время ожидания: 10 минут",
                reply_markup=get_payment_keyboard(quickpay.redirected_url)
            )
            
            asyncio.create_task(self.check_payment(
                label=f"{callback_query.from_user.id}_extend_{subscription_type}",
                chat_id=callback_query.message.chat.id,
                is_extension=True
            ))

        except Exception as e:
            logging.error(f"Ошибка при создании формы продления: {e}")
            await callback_query.message.answer("Произошла ошибка при создании формы продления. Попробуйте позже.")

    async def process_cancel_extend(self, callback_query: types.CallbackQuery):
        """Обработчик отмены продления подписки"""
        await callback_query.message.edit_text("❌ Продление подписки отменено.")
        # Открываем главное меню
        is_user_admin = is_admin(callback_query.from_user.id)
        await callback_query.message.answer(
            "📌 *Добро пожаловать.*\n"
            "_Ты зашёл в систему, которая работает._\n\n"
            "🔸 Без лишнего шума\n"
            "🔸 Без мотивационных соплей\n"
            "🔸 Только нужные инструменты и конкретные шаги\n\n"
            "*Выбери, с чего хочешь начать. Остальное пойдёт по накатанной.*",
            reply_markup=get_main_keyboard(is_user_admin),
            parse_mode="Markdown"
        )

    async def check_payment(self, label: str, chat_id: int, is_extension: bool = False) -> bool:
        """Проверяет статус платежа"""
        try:
            max_attempts = 30  # 30 попыток по 20 секунд
            attempts = 0
            
            while attempts < max_attempts:
                history = self.yoomoney_client.operation_history(
                    label=label,
                    from_date=datetime.datetime.now() - datetime.timedelta(minutes=10)
                )
                
                for operation in history.operations:
                    if operation.status == "success" and operation.label == label:
                        label_parts = label.split("_")
                        if len(label_parts) >= 2:
                            user_id = int(label_parts[0])
                            subscription_type = "_".join(label_parts[1:])
                            
                            if is_extension:
                                # Продлеваем подписку
                                await self.subscription_manager.extend_subscription(
                                    user_id,
                                    SUBSCRIPTION_PRICES[subscription_type]["duration"]
                                )
                            else:
                                # Создаем новую подписку
                                user_info = await self.subscription_manager.get_subscription_info(user_id)
                                await self.assign_user_label(
                                    user_id,
                                    user_info.get("username", "Unknown") if user_info else "Unknown",
                                    subscription_type
                                )
                            return True
                
                attempts += 1
                await asyncio.sleep(20)
            
            await self.bot.send_message(
                chat_id=chat_id,
                text="❌ Время ожидания оплаты истекло. Пожалуйста, попробуйте оплатить снова."
            )
            return False
            
        except Exception as e:
            logging.error(f"Ошибка при проверке платежа: {e}")
            await self.bot.send_message(
                chat_id=chat_id,
                text="Произошла ошибка при проверке оплаты. Попробуйте позже."
            )
            return False

    async def process_check_payment(self, callback_query: types.CallbackQuery):
        """Обработчик кнопки 'Я оплатил'"""
        try:
            # Получаем label из callback_data
            label = callback_query.data.replace("check_payment_", "")
            
            # Проверяем статус платежа
            history = self.yoomoney_client.operation_history(
                label=label,
                from_date=datetime.datetime.now() - datetime.timedelta(minutes=30)
            )
            
            # Проверяем каждую операцию
            for operation in history.operations:
                if operation.status == "success" and operation.label == label:
                    # Если найдена успешная операция, отправляем сообщение
                    await callback_query.message.edit_text(
                        "✅ Оплата успешно получена! Ваша подписка активирована.",
                        reply_markup=None
                    )
                    return
            
            # Если оплата не найдена
            await callback_query.answer(
                "❌ Оплата пока не поступила. Если вы уже оплатили, подождите немного и попробуйте снова.",
                show_alert=True
            )
                
        except Exception as e:
            logging.error(f"Ошибка при проверке оплаты: {e}")
            await callback_query.answer(
                "Произошла ошибка при проверке оплаты. Попробуйте позже.",
                show_alert=True
            )

    def register_handlers(self, dp: Dispatcher):
        """Регистрация обработчиков"""
        dp.register_callback_query_handler(
            self.process_subscription_choice,
            lambda c: c.data in SUBSCRIPTION_PRICES.keys()
        )
        dp.register_callback_query_handler(
            self.process_extend_subscription,
            lambda c: c.data.startswith("extend_")
        )
        dp.register_callback_query_handler(
            self.process_cancel_extend,
            lambda c: c.data == "cancel_extend"
        )
        dp.register_callback_query_handler(
            self.process_check_payment,
            lambda c: c.data == "check_payment"
        ) 