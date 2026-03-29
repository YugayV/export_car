#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    ContextTypes, CallbackQueryHandler, filters
)
import asyncio
import re
import os
import sys
from datetime import datetime

# Импортируем наши модули
from car_parser import CarParser
from customs_calculator import CustomsCalculator
from database import Database
from config import BOT_TOKEN, COMPANY_INFO, DEBUG, LOG_LEVEL
from utils.logger import setup_logger

# Настройка логирования
logger = setup_logger(__name__, 'logs/bot.log', level=LOG_LEVEL)

class CarImportBot:
    def __init__(self):
        self.parser = CarParser()
        self.calculator = CustomsCalculator()
        self.db = Database()
        self.user_sessions = {}
        logger.info("Bot initialized")
    
    # ... все методы остаются без изменений ...

async def main():
    """Основная функция запуска бота"""
    
    # Проверка токена
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        print("❌ ERROR: BOT_TOKEN is not set in environment variables!")
        print("Please set BOT_TOKEN in Railway variables or .env file")
        sys.exit(1)
    
    try:
        # Создаем экземпляр бота
        bot = CarImportBot()
        
        # Создаем приложение
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Добавляем обработчики команд
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(CommandHandler("price", bot.price_command))
        application.add_handler(CommandHandler("history", bot.history_command))
        application.add_handler(CommandHandler("contact", bot.contact_command))
        application.add_handler(CommandHandler("currency", bot.currency_command))
        application.add_handler(CommandHandler("about", bot.about_command))
        
        # Обработчик текстовых сообщений
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND, 
            bot.handle_message
        ))
        
        # Обработчик колбэков от кнопок
        application.add_handler(CallbackQueryHandler(bot.button_callback))
        
        # Запускаем бота
        logger.info("Starting bot on Railway...")
        print("🚀 Bot is running on Railway!")
        print(f"Bot token: {BOT_TOKEN[:10]}...")
        
        # Запускаем polling с обработкой ошибок
        await application.run_polling()
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())