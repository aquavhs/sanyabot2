import sqlite3
import logging
import datetime
import aiosqlite
import os
from typing import Optional, List, Dict

class Database:
    def __init__(self, db_path: str = "bot_database.db"):
        """
        Инициализация подключения к базе данных SQLite
        
        Args:
            db_path (str): Путь к файлу базы данных
        """
        self.db_path = db_path
        self._create_tables()

    def _create_tables(self):
        """Создает необходимые таблицы в базе данных"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Создаем таблицу, если она не существует
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    first_name TEXT,
                    username TEXT,
                    username_at TEXT,
                    label TEXT,
                    subscription_start TEXT,
                    subscription_end TEXT,
                    updated_at TEXT
                )
            """)
            
            # Проверяем существующие колонки
            cursor.execute("PRAGMA table_info(users)")
            existing_columns = {column[1] for column in cursor.fetchall()}
            required_columns = {
                'user_id', 'first_name', 'username', 'username_at', 'label', 
                'subscription_start', 'subscription_end', 'updated_at'
            }
            
            # Добавляем недостающие колонки
            for column in required_columns - existing_columns:
                if column == 'user_id':
                    continue  # Пропускаем PRIMARY KEY
                cursor.execute(f"ALTER TABLE users ADD COLUMN {column} TEXT")
            
            conn.commit()
            logging.info("Структура базы данных успешно обновлена")

    def _format_datetime(self, dt: datetime.datetime) -> str:
        """
        Форматирует datetime в строку формата Д.М.Г Ч:M:C
        
        Args:
            dt (datetime): Объект datetime для форматирования
            
        Returns:
            str: Отформатированная дата и время
        """
        return dt.strftime("%d.%m.%Y %H:%M:%S")

    async def create_user(self, user_id: int, first_name: str, username: str, username_at: str, label: str, 
                         subscription_start: datetime.datetime, 
                         subscription_end: datetime.datetime) -> None:
        """Создает нового пользователя или обновляет существующего"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                INSERT OR REPLACE INTO users 
                (user_id, first_name, username, username_at, label, subscription_start, subscription_end, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id,
                first_name,
                username,
                username_at,
                label,
                subscription_start.strftime("%d.%m.%Y %H:%M:%S"),
                subscription_end.strftime("%d.%m.%Y %H:%M:%S"),
                datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
            ))
            await db.commit()

    async def get_user(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о пользователе"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute(
                "SELECT * FROM users WHERE user_id = ?",
                (user_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)
                return None

    async def get_all_users(self) -> List[Dict]:
        """Получает список всех пользователей"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute("SELECT * FROM users") as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]

    async def update_user_label(self, user_id: int, label: str, username_at: str = None) -> None:
        """Обновляет label пользователя и username_at если указан"""
        async with aiosqlite.connect(self.db_path) as db:
            if username_at is not None:
                await db.execute("""
                    UPDATE users 
                    SET label = ?, username_at = ?, updated_at = ?
                    WHERE user_id = ?
                """, (
                    label,
                    username_at,
                    datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                    user_id
                ))
            else:
                await db.execute("""
                    UPDATE users 
                    SET label = ?, updated_at = ?
                    WHERE user_id = ?
                """, (
                    label,
                    datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                    user_id
                ))
            await db.commit()

    async def get_user_subscription_info(self, user_id: int) -> Optional[Dict]:
        """Получает информацию о подписке пользователя"""
        user = await self.get_user(user_id)
        if not user:
            return None
            
        return {
            "label": user["label"],
            "subscription_start": user["subscription_start"],
            "subscription_end": user["subscription_end"]
        }

    async def update_user_subscription(self, user_id: int, subscription_end: datetime.datetime) -> None:
        """Обновляет дату окончания подписки пользователя"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET subscription_end = ?, updated_at = ?
                WHERE user_id = ?
            """, (
                subscription_end.strftime("%d.%m.%Y %H:%M:%S"),
                datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                user_id
            ))
            await db.commit()

    async def update_user_info(self, user_id: int, first_name: str, username: str, username_at: str) -> None:
        """Обновляет базовую информацию о пользователе, не трогая данные подписки"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                UPDATE users 
                SET first_name = ?,
                    username = ?,
                    username_at = ?,
                    updated_at = ?
                WHERE user_id = ?
            """, (
                first_name,
                username,
                username_at,
                datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
                user_id
            ))
            await db.commit()
            logging.info(f"Обновлена информация пользователя {user_id} (first_name: {first_name}, username: {username})")

    async def get_expired_subscriptions(self) -> List[Dict]:
        """Получает список пользователей с истекшей подпиской"""
        current_time = datetime.datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = sqlite3.Row
            async with db.execute("""
                SELECT * FROM users 
                WHERE subscription_end < ? 
                AND label != 'basic_user'
            """, (current_time,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows] 