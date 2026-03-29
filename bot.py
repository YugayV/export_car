import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
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
        # Создаем папку для логов если её нет
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        self.parser = CarParser()
        self.calculator = CustomsCalculator()
        self.db = Database()
        self.user_sessions = {}
        logger.info("Bot initialized")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /start"""
        user = update.effective_user
        welcome_message = (
            f"🚗 *Добро пожаловать в Car Import Bot, {user.first_name}!*\n\n"
            "Я помогу вам рассчитать полную стоимость импорта автомобиля из Кореи.\n\n"
            "1️⃣ Пришлите мне ссылку на [encar.com](https://www.encar.com)\n"
            "2️⃣ Или воспользуйтесь меню ниже."
        )
        
        # Инлайн кнопки для приветственного сообщения
        inline_keyboard = [
            [InlineKeyboardButton("💰 Рассчитать авто", callback_data="new_calculation")],
            [InlineKeyboardButton("📞 Связаться", callback_data="contact")]
        ]
        
        # Постоянные кнопки внизу экрана (Reply Keyboard)
        reply_keyboard = [
            [KeyboardButton("🚗 Рассчитать авто"), KeyboardButton("📈 Анализ рынка")],
            [KeyboardButton("📞 Контакты"), KeyboardButton("ℹ️ О нас")]
        ]
        
        await update.message.reply_text(
            welcome_message, 
            parse_mode='Markdown', 
            reply_markup=InlineKeyboardMarkup(inline_keyboard)
        )
        
        # Отправляем отдельное сообщение с постоянным меню
        await update.message.reply_text(
            "Используйте кнопки меню для навигации:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, resize_keyboard=True, persistent=True)
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработчик команды /help"""
        help_text = (
            "📖 *Как пользоваться ботом:*\n\n"
            "1. Зайдите на [encar.com](https://www.encar.com)\n"
            "2. Найдите интересующий вас автомобиль\n"
            "3. Скопируйте ссылку и вставьте её сюда\n"
            "4. Я рассчитаю полную стоимость, включая таможню и доставку."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка входящих текстовых сообщений и кнопок меню"""
        text = update.message.text
        
        # Обработка кнопок Reply Keyboard
        if text == "🚗 Рассчитать авто":
            await update.message.reply_text("Пожалуйста, пришлите ссылку на автомобиль с encar.com.")
            return
        elif text == "📈 Анализ рынка":
            await update.message.reply_text("Функция анализа рынка временно недоступна.")
            return
        elif text == "📞 Контакты":
            await update.message.reply_text(f"📧 Email для заказа: {COMPANY_INFO['email']}\n📱 Тел: {COMPANY_INFO['phone']}")
            return
        elif text == "ℹ️ О нас":
            await update.message.reply_text(f"ℹ️ Адрес: {COMPANY_INFO['address']}")
            return

        # Регулярное выражение для Encar или Daum
        if re.search(r'encar\.com|daumcdn\.net', text):
            await self.process_url(update, context, text)
        else:
            await update.message.reply_text("Пожалуйста, выберите действие в меню или пришлите ссылку на encar.com.")

    async def process_url(self, update, context, url):
        """Анализ ссылки Encar и запрос страны назначения"""
        user_id = update.effective_user.id
        await update.message.reply_text("🔍 Анализирую ссылку... Пожалуйста, подождите.")
        
        try:
            car_data = await self.parser.parse_from_url(url)
            if car_data and (car_data.get('price_krw', 0) > 0 or car_data.get('price_usd', 0) > 0):
                # Сохраняем данные в сессию пользователя
                self.user_sessions[user_id] = {'car_data': car_data}
                
                # Считаем примерную цену в USD для превью
                price_krw = car_data.get('price_krw', 0)
                if price_krw > 0:
                    rate = self.calculator.exchange_rate if self.calculator.exchange_rate > 0 else 1350
                    price_usd = price_krw / rate
                else:
                    price_usd = car_data.get('price_usd', 0)
                
                # Показываем инфо об авто и спрашиваем страну
                msg = (
                    f"✅ *Автомобиль найден:* {car_data['brand']} {car_data['model']}\n"
                    f"📅 *Год:* {car_data['year']}\n"
                    f"💰 *Цена в Корее:* {price_krw:,.0f} KRW (~${price_usd:,.0f})\n\n"
                    "🌍 *Выберите страну назначения:* "
                )
                
                keyboard = [
                    [InlineKeyboardButton("🇷🇺 Россия", callback_data="dest_russia")],
                    [InlineKeyboardButton("🇺🇿 Узбекистан", callback_data="dest_uzbekistan")],
                    [InlineKeyboardButton("🇰🇿 Казахстан", callback_data="dest_kazakhstan")]
                ]
                await update.message.reply_text(
                    msg, 
                    parse_mode='Markdown', 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    "❌ *Не удалось извлечь цену автомобиля.*\n"
                    "Ссылка может быть неверной или автомобиль уже продан. Попробуйте другую ссылку с Encar.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text("❌ Ошибка при обработке ссылки. Пожалуйста, попробуйте еще раз.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Обработка нажатий на кнопки и финальный расчет"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        data = query.data
        
        if data.startswith("dest_"):
            country_code = data.replace("dest_", "")
            session = self.user_sessions.get(user_id)
            
            if not session or 'car_data' not in session:
                await query.edit_message_text("❌ Сессия истекла. Пожалуйста, пришлите ссылку снова.")
                return
            
            car_data = session['car_data']
            
            # Расчет стоимости для выбранной страны
            result = await self.calculator.calculate_total_cost(car_data, destination=country_code)
            
            # Получаем рекомендацию от DeepSeek
            ai_recommendation = await self.calculator.get_ai_recommendation(car_data, result, country_code)
            
            country_map = {"russia": "Россию", "uzbekistan": "Узбекистан", "kazakhstan": "Казахстан"}
            country_name = country_map.get(country_code, country_code)
            
            # Формируем доп. инфо от ИИ если есть
            ai_details = f"\n\nℹ️ *Актуально на 2026:* \n_{result['ai_info']}_" if result.get('ai_info') else ""

            final_msg = (
                f"📊 *Полная стоимость импорта в {country_name}:*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🚗 *Авто:* {car_data['brand']} {car_data['model']}\n"
                f"📅 *Год:* {car_data['year']}\n"
                f"💵 *Цена авто:* ${result['car_price']:,.0f}\n"
                f"⚓ *Доставка:* ${result['shipping_cost']:,.0f}\n"
                f"🛡️ *Таможенная пошлина:* ${result['customs_duty']:,.0f}\n"
                f"♻️ *Утильсбор:* ${result['recycling_fee']:,.0f}\n"
                f"📦 *Прочие расходы:* ${result['broker_fee'] + result['customs_fee'] + result['insurance']:,.0f}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *ИТОГО:* `{result['total']:,.0f} USD`{ai_details}\n\n"
                f"🤖 *Рекомендация ИИ:* \n_{ai_recommendation}_\n\n"
                f"📧 *Email для заказа:* {COMPANY_INFO['email']}\n"
                f"📱 *WhatsApp/Tel:* {COMPANY_INFO['phone']}"
            )
            
            await query.edit_message_text(final_msg, parse_mode='Markdown')
            
        elif data == "contact":
            await query.message.reply_text(f"📞 Связаться с нашим менеджером: {COMPANY_INFO['telegram']}")
        elif data == "about":
            await query.message.reply_text(f"ℹ️ {COMPANY_INFO['address']}")
        elif data == "new_calculation":
            await query.message.reply_text("Пожалуйста, пришлите мне ссылку на автомобиль с encar.com.")

def main():
    """Основная функция запуска бота (синхронная точка входа)"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)
    
    try:
        bot = CarImportBot()
        
        async def post_init(application: Application):
            await bot.calculator.update_exchange_rate()
            # Устанавливаем список команд в меню кнопки "Menu"
            await application.bot.set_my_commands([
                BotCommand("start", "Запустить бота"),
                BotCommand("help", "Инструкция"),
                BotCommand("about", "О компании")
            ])
            logger.info("Bot initialized and commands set")

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .post_init(post_init)
            .build()
        )
        
        application.add_handler(CommandHandler("start", bot.start))
        application.add_handler(CommandHandler("help", bot.help_command))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_message))
        application.add_handler(CallbackQueryHandler(bot.button_callback))
        
        print("🚀 Bot is running on Railway!")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()