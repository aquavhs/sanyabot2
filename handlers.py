import logging
from aiogram import Bot, types
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from yoomoney import Client

from keyboards import get_main_keyboard, get_subscription_keyboard

class MessageHandler:
    def __init__(self, bot: Bot, yoomoney_client: Client):
        self.bot = bot
        self.yoomoney_client = yoomoney_client

    async def process_subscribe_button(self, callback_query: types.CallbackQuery):
        """Обработчик нажатия кнопки 'Подписки'"""
        # Удаляем сообщение с кнопкой
        await callback_query.message.delete()
        
        # Отправляем сообщение с описанием и кнопками
        photo = FSInputFile("imgs/2.png")
        await callback_query.message.answer_photo(
            photo=photo,
            caption=(
                "*Подписка - это не доступ. Это выбор стороны.* 🔓\n\n"
                "Либо ты как все - тыкаешь наугад, сливаешь, ищешь виноватых.\n"
                "Либо ты заходишь внутрь. Туда, где:\n\n"
                "⚔️ _Работают готовые алгоритмы, которые другим даже не покажут_\n\n"
                "🧠 _Всё структурировано — тебе не надо гадать, ты просто берёшь и бьёшь точно_\n\n"
                "📈 _Есть рост, результат и контроль — ты не зависишь от эмоций и паники_\n\n"
                "🎯 _Это уже не \"тест\", это переход в режим: я играю на победу_\n\n"
                "💡 *Условия простые:*\n"
                "▪️ День - 90₽. Для тех, кто не верит, но хочет проверить.\n"
                "▪️ Неделя - 440₽. Для тех, кто готов рискнуть и забрать своё.\n"
                "▪️ Месяц - 1620₽. Для тех, кто решил идти до конца.\n\n"
                "❌ *Остаться снаружи - тоже выбор. Но потом не говори, что не знал.*"
            ),
            reply_markup=get_subscription_keyboard(),
            parse_mode="Markdown"
        )

    async def cancel_payment(self, callback_query: types.CallbackQuery):
        """Обработчик отмены оплаты"""
        await callback_query.message.delete()
        await callback_query.message.answer("Оплата отменена. Вы можете начать сначала, отправив команду /start")

    async def cmd_balance(self, message: Message):
        """Обработчик команды /balance"""
        try:
            user = self.yoomoney_client.account_info()
            await message.answer(f"Ваш баланс: {user.balance} {user.currency}")
        except Exception as e:
            logging.error(f"Ошибка при получении баланса: {e}")
            await message.answer("Произошла ошибка при получении баланса") 