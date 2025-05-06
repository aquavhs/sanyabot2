from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Главное меню
def get_main_keyboard(is_admin: bool = False) -> InlineKeyboardMarkup:
    """
    Создает основную клавиатуру
    
    Args:
        is_admin (bool): Является ли пользователь администратором
    """
    keyboard = []
    if is_admin:
        keyboard = [
            [InlineKeyboardButton(text="📱 Подписки", callback_data="subscribe")],
            [InlineKeyboardButton(text="👨‍💼 Админ-панель", callback_data="admin_panel")]
        ]
    else:
        keyboard = [
            [InlineKeyboardButton(text="📱 Подписки", callback_data="subscribe")]
        ]
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

# Клавиатура выбора подписки
def get_subscription_keyboard() -> InlineKeyboardMarkup:
    """Создает клавиатуру с тарифами подписок"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔹 День - 90₽", callback_data="sub_basic")],
            [InlineKeyboardButton(text="🔹 Неделя - 440₽", callback_data="sub_standard")],
            [InlineKeyboardButton(text="🔹 Месяц - 1620₽", callback_data="sub_premium")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
        ]
    )

# Клавиатура оплаты
def get_payment_keyboard(payment_url: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для оплаты"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", url=payment_url)],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_payment")]
        ]
    )

def get_admin_keyboard(is_test_mode: bool = False) -> InlineKeyboardMarkup:
    """Создает клавиатуру админ-панели"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text="🔄 Тестовый режим: " + ("✅ Вкл." if is_test_mode else "❌ Выкл."),
                callback_data="toggle_test_mode"
            )],
            [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton(text="👥 Управление подписками", callback_data="admin_subscriptions")],
            [InlineKeyboardButton(text="📢 Управление каналом", callback_data="admin_channel")],
            [InlineKeyboardButton(text="💰 Баланс", callback_data="admin_balance")],
            [InlineKeyboardButton(text="⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")]
        ]
    )

def get_subscription_management_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Возвращает клавиатуру для управления подпиской пользователя"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Продлить на день",
                    callback_data=f"admin_extend_{user_id}_day"
                ),
                InlineKeyboardButton(
                    text="❌ Отменить подписку",
                    callback_data=f"admin_cancel_{user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Продлить на неделю",
                    callback_data=f"admin_extend_{user_id}_week"
                )
            ],
            [
                InlineKeyboardButton(
                    text="➕ Продлить на месяц",
                    callback_data=f"admin_extend_{user_id}_month"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Назад",
                    callback_data="admin_panel"
                )
            ]
        ]
    ) 