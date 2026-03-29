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
        # Создаем папку для логов если её нет
        if not os.path.exists('logs'):
            os.makedirs('logs')
            
        self.parser = CarParser()
        self.calculator = CustomsCalculator()
        self.db = Database()
        self.user_sessions = {}
        logger.info("Bot initialized")
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /start command"""
        user = update.effective_user
        welcome_message = (
            f"🚗 *Welcome to Car Import Bot, {user.first_name}!*\n\n"
            "I can help you calculate the full cost of importing a car from Korea.\n\n"
            "1️⃣ Send me an encar.com link\n"
            "2️⃣ Or use the buttons below for info.\n\n"
            "Use /help for more instructions."
        )
        keyboard = [
            [InlineKeyboardButton("💰 Calculate Car", callback_data="new_calculation")],
            [InlineKeyboardButton("📞 Contact Manager", callback_data="contact")],
            [InlineKeyboardButton("ℹ️ About Us", callback_data="about")]
        ]
        await update.message.reply_text(
            welcome_message, 
            parse_mode='Markdown', 
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handler for /help command"""
        help_text = (
            "📖 *How to use this bot:*\n\n"
            "1. Go to [encar.com](https://www.encar.com)\n"
            "2. Find a car you like\n"
            "3. Copy the URL and paste it here\n"
            "4. I will calculate the total cost including customs and shipping."
        )
        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Process incoming text messages"""
        text = update.message.text
        # Регулярное выражение для Encar или Daum (часто ссылки в Kakao приходят через daum)
        if re.search(r'encar\.com|daumcdn\.net', text):
            await self.process_url(update, context, text)
        else:
            await update.message.reply_text("Please send a valid encar.com link.")

    async def process_url(self, update, context, url):
        """Analyze Encar link and ask for destination country"""
        user_id = update.effective_user.id
        await update.message.reply_text("🔍 Analyzing link... Please wait.")
        
        try:
            car_data = await self.parser.parse_from_url(url)
            if car_data and car_data.get('price_usd', 0) > 0:
                # Сохраняем данные в сессию пользователя
                self.user_sessions[user_id] = {'car_data': car_data}
                
                # Показываем инфо об авто и спрашиваем страну
                msg = (
                    f"✅ *Car Found:* {car_data['brand']} {car_data['model']}\n"
                    f"📅 *Year:* {car_data['year']}\n"
                    f"💰 *Price in Korea:* ${car_data['price_usd']:,.0f}\n\n"
                    "🌍 *Select Destination Country:* "
                )
                
                keyboard = [
                    [InlineKeyboardButton("🇷🇺 Russia", callback_data="dest_russia")],
                    [InlineKeyboardButton("🇺🇿 Uzbekistan", callback_data="dest_uzbekistan")],
                    [InlineKeyboardButton("🇰🇿 Kazakhstan", callback_data="dest_kazakhstan")]
                ]
                await update.message.reply_text(
                    msg, 
                    parse_mode='Markdown', 
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await update.message.reply_text(
                    "❌ *Could not extract car price.*\n"
                    "The link might be invalid or car is sold. Please try another Encar link.",
                    parse_mode='Markdown'
                )
        except Exception as e:
            logger.error(f"Error processing URL: {e}")
            await update.message.reply_text("❌ Error processing link. Please try again.")

    async def button_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle button clicks and calculate final price"""
        query = update.callback_query
        user_id = update.effective_user.id
        await query.answer()
        
        data = query.data
        
        if data.startswith("dest_"):
            country_code = data.replace("dest_", "")
            session = self.user_sessions.get(user_id)
            
            if not session or 'car_data' not in session:
                await query.edit_message_text("❌ Session expired. Please send the link again.")
                return
            
            car_data = session['car_data']
            
            # Расчет стоимости для выбранной страны
            result = await self.calculator.calculate_total_cost(car_data, destination=country_code)
            
            # Получаем рекомендацию от DeepSeek
            ai_recommendation = await self.calculator.get_ai_recommendation(car_data, result, country_code)
            
            country_name = "Russia" if country_code == "russia" else "Uzbekistan" if country_code == "uzbekistan" else "Kazakhstan"
            
            final_msg = (
                f"📊 *Full Import Cost to {country_name}:*\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"🚗 *Car Price:* ${car_data['price_usd']:,.0f}\n"
                f"⚓ *Shipping:* ${result['shipping_cost']:,.0f}\n"
                f"🛡️ *Customs Duty:* ${result['customs_duty']:,.0f}\n"
                f"♻️ *Recycling Fee:* ${result['recycling_fee']:,.0f}\n"
                f"📦 *Other Fees:* ${result['broker_fee'] + result['customs_fee'] + result['insurance']:,.0f}\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"💰 *TOTAL:* `${result['total']:,.0f}`\n\n"
                f"🤖 *AI Recommendation:* \n_{ai_recommendation}_\n\n"
                f"📞 Contact manager to order: {COMPANY_INFO['telegram']}"
            )
            
            await query.edit_message_text(final_msg, parse_mode='Markdown')
            
        elif data == "contact":
            await query.message.reply_text(f"📞 Contact our manager: {COMPANY_INFO['telegram']}")
        elif data == "about":
            await query.message.reply_text(f"ℹ️ {COMPANY_INFO['address']}")
        elif data == "new_calculation":
            await query.message.reply_text("Please send me an encar.com car link.")

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        sys.exit(1)
    
    try:
        bot = CarImportBot()
        
        async def post_init(application: Application):
            await bot.calculator.update_exchange_rate()
            logger.info("Exchange rate updated")

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
        
        print("🚀 Bot is starting on Railway...")
        application.run_polling(drop_pending_updates=True)
        
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()