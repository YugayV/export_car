import sqlite3
import json
from datetime import datetime
import aiosqlite
import logging
import os
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path='data/bot_database.db'):
        self.db_path = db_path
        # Создаем директорию если её нет
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_db()
    
    def init_db(self):
        """Инициализация базы данных"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Таблица пользователей
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    phone TEXT,
                    email TEXT,
                    country TEXT DEFAULT 'russia',
                    language TEXT DEFAULT 'ru',
                    registration_date TIMESTAMP,
                    last_activity TIMESTAMP,
                    is_active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Таблица расчетов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS calculations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    car_data TEXT,
                    calculation_result TEXT,
                    created_at TIMESTAMP,
                    status TEXT DEFAULT 'new',
                    is_favorite BOOLEAN DEFAULT 0,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица запросов на связь
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS contact_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    request_text TEXT,
                    contact_phone TEXT,
                    contact_email TEXT,
                    created_at TIMESTAMP,
                    processed BOOLEAN DEFAULT 0,
                    processed_at TIMESTAMP,
                    manager_comment TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Таблица статистики
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS statistics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE,
                    total_users INTEGER,
                    active_users INTEGER,
                    total_calculations INTEGER,
                    conversion_rate FLOAT,
                    UNIQUE(date)
                )
            ''')
            
            # Таблица настроек
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TIMESTAMP
                )
            ''')
            
            conn.commit()
            logger.info(f"Database initialized successfully at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
        finally:
            conn.close()
    
    # ... остальные методы остаются без изменений ...