import aiohttp
import json
from datetime import datetime
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class CustomsCalculator:
    def __init__(self):
        # Курсы валют
        self.exchange_rate = 1300  # KRW/USD
        
        # Коэффициенты для разных стран
        self.country_coeff = {
            'russia': {
                'name': 'Россия',
                'duty_rate_new': 0.48,      # 48% для авто до 3 лет
                'duty_rate_old': 0.25,       # 25% для авто старше 3 лет
                'vat_rate': 0.20,            # НДС 20%
                'recycling_base': 200,       # Базовый утильсбор в USD
                'customs_fee': 50,           # Таможенный сбор
                'currency': 'USD'
            },
            'kazakhstan': {
                'name': 'Казахстан',
                'duty_rate_new': 0.15,
                'duty_rate_old': 0.10,
                'vat_rate': 0.12,
                'recycling_base': 150,
                'customs_fee': 40,
                'currency': 'USD'
            },
            'belarus': {
                'name': 'Беларусь',
                'duty_rate_new': 0.25,
                'duty_rate_old': 0.20,
                'vat_rate': 0.20,
                'recycling_base': 180,
                'customs_fee': 45,
                'currency': 'USD'
            },
            'uzbekistan': {
                'name': 'Узбекистан',
                'duty_rate_new': 0.30,
                'duty_rate_old': 0.20,
                'vat_rate': 0.15,
                'recycling_base': 220,
                'customs_fee': 50,
                'currency': 'USD'
            }
        }
        
        # Стоимость доставки
        self.shipping_options = {
            'sea_busan_vladivostok': {'price': 800, 'days': 12, 'name': 'Море: Пусан → Владивосток'},
            'sea_busan_novorossiysk': {'price': 2500, 'days': 35, 'name': 'Море: Пусан → Новороссийск'},
            'sea_busan_st_petersburg': {'price': 3000, 'days': 45, 'name': 'Море: Пусан → Санкт-Петербург'},
            'rail_busan_astana': {'price': 2000, 'days': 25, 'name': 'ЖД: Пусан → Астана'},
            'air_busan_moscow': {'price': 5000, 'days': 5, 'name': 'Авиа: Пусан → Москва'}
        }
    
    async def calculate_total_cost(self, car_data: Dict, destination: str = 'russia', 
                                   shipping_method: str = 'sea_busan_vladivostok') -> Dict:
        """Расчет полной стоимости импорта"""
        
        country = self.country_coeff.get(destination, self.country_coeff['russia'])
        
        # Получаем данные авто
        car_price = float(car_data.get('price_usd', 0))
        engine_size = float(self.extract_engine_size(car_data.get('engine_size', '2000')))
        year = int(self.extract_year(car_data.get('year', '2020')))
        
        # Расчет возраста авто
        current_year = datetime.now().year
        car_age = current_year - year
        is_new_car = car_age <= 3
        
        # Расчет стоимости доставки
        shipping = self.shipping_options.get(shipping_method, self.shipping_options['sea_busan_vladivostok'])
        shipping_cost = shipping['price']
        
        # Страховка (2% от стоимости авто)
        insurance = car_price * 0.02
        
        # Таможенная пошлина
        if is_new_car:
            customs_duty = car_price * country['duty_rate_new']
        else:
            # Для старых авто - по объему двигателя
            duty_per_cc = self.get_duty_per_cc(engine_size, car_age)
            customs_duty = (engine_size * duty_per_cc) / self.exchange_rate
        
        # Акциз (для некоторых стран)
        excise_tax = self.calculate_excise_tax(engine_size, car_price, destination)
        
        # НДС
        vat_base = car_price + shipping_cost + insurance + customs_duty + excise_tax
        vat = vat_base * country['vat_rate']
        
        # Утильсбор
        recycling_fee = country['recycling_base'] * self.get_recycling_coefficient(engine_size)
        
        # Таможенный сбор
        customs_fee = country['customs_fee']
        
        # Услуги брокера
        broker_fee = 300
        
        # Сертификация (если нужно)
        certification_fee = self.calculate_certification_fee(car_age, engine_size)
        
        # Итоговая стоимость
        total = (car_price + shipping_cost + insurance + customs_duty + 
                excise_tax + vat + recycling_fee + customs_fee + 
                broker_fee + certification_fee)
        
        # Расчет экономии
        local_price = await self.get_local_market_price(car_data, destination)
        savings = local_price - total if local_price > 0 else 0
        
        return {
            'car_price': car_price,
            'shipping_cost': shipping_cost,
            'shipping_days': shipping['days'],
            'shipping_method': shipping['name'],
            'insurance': round(insurance, 2),
            'customs_duty': round(customs_duty, 2),
            'excise_tax': round(excise_tax, 2),
            'vat': round(vat, 2),
            'recycling_fee': round(recycling_fee, 2),
            'customs_fee': customs_fee,
            'broker_fee': broker_fee,
            'certification_fee': round(certification_fee, 2),
            'total': round(total, 2),
            'savings': round(savings, 2),
            'local_price': round(local_price, 2),
            'delivery_time': shipping['days'],
            'customs_time': 5,
            'car_age': car_age,
            'is_new_car': is_new_car
        }
    
    def extract_engine_size(self, engine_text: str) -> float:
        """Извлечение объема двигателя из текста"""
        # Убираем все символы кроме цифр
        numbers = ''.join(filter(str.isdigit, str(engine_text)))
        if numbers:
            size = float(numbers)
            # Если число маленькое (1-9), это литры, конвертируем в см³
            if size < 100:
                size = size * 1000
            return size
        return 2000
    
    def extract_year(self, year_text: str) -> str:
        """Извлечение года из текста"""
        numbers = ''.join(filter(str.isdigit, str(year_text)))
        if len(numbers) == 2:
            year = f"20{numbers}" if int(numbers) < 24 else f"19{numbers}"
            return year
        return numbers if numbers else '2020'
    
    def get_duty_per_cc(self, engine_size: float, car_age: int) -> float:
        """Получение ставки пошлины за см³ (для авто старше 3 лет)"""
        # Ставки в евро за см³
        if engine_size <= 1000:
            rate = 1.5
        elif engine_size <= 1500:
            rate = 1.7
        elif engine_size <= 1800:
            rate = 2.0
        elif engine_size <= 2300:
            rate = 2.5
        elif engine_size <= 3000:
            rate = 3.0
        else:
            rate = 3.5
        
        # Увеличение для очень старых авто
        if car_age > 7:
            rate *= 1.2
        
        return rate
    
    def get_recycling_coefficient(self, engine_size: float) -> float:
        """Коэффициент утильсбора в зависимости от объема"""
        if engine_size <= 1000:
            return 1.0
        elif engine_size <= 2000:
            return 1.5
        elif engine_size <= 3000:
            return 2.0
        else:
            return 2.5
    
    def calculate_excise_tax(self, engine_size: float, car_price: float, destination: str) -> float:
        """Расчет акциза"""
        # Акциз рассчитывается только для некоторых стран
        excise_rates = {
            'russia': 0,
            'kazakhstan': 0,
            'belarus': 0,
            'uzbekistan': 0.05  # 5% в Узбекистане
        }
        
        rate = excise_rates.get(destination, 0)
        return car_price * rate
    
    def calculate_certification_fee(self, car_age: int, engine_size: float) -> float:
        """Расчет стоимости сертификации"""
        if car_age <= 3:
            return 500  # Для новых авто
        else:
            return 300  # Для старых авто
    
    async def get_local_market_price(self, car_data: Dict, destination: str) -> float:
        """Получение цены на аналогичный автомобиль на местном рынке"""
        # Здесь можно интегрироваться с API местных площадок
        # Пока возвращаем примерную цену (+30% к стоимости)
        car_price = float(car_data.get('price_usd', 0))
        
        local_markup = {
            'russia': 1.35,
            'kazakhstan': 1.25,
            'belarus': 1.30,
            'uzbekistan': 1.40
        }
        
        markup = local_markup.get(destination, 1.30)
        return car_price * markup
    
    async def update_exchange_rate(self):
        """Обновление курса валют"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get('https://api.exchangerate-api.com/v4/latest/USD') as response:
                    data = await response.json()
                    # Обновляем курс KRW
                    if 'KRW' in data.get('rates', {}):
                        self.exchange_rate = data['rates']['KRW']
                        logger.info(f"Exchange rate updated: 1 USD = {self.exchange_rate} KRW")
        except Exception as e:
            logger.error(f"Error updating exchange rate: {e}")