import re
from datetime import datetime
import json

def validate_car_data(car_data: dict) -> bool:
    """Проверка валидности данных автомобиля"""
    required_fields = ['brand', 'model', 'year']
    
    for field in required_fields:
        if not car_data.get(field):
            return False
    
    # Проверка года
    try:
        year = int(car_data['year'])
        current_year = datetime.now().year
        if year < 1980 or year > current_year:
            return False
    except:
        return False
    
    return True

def extract_car_info_from_text(text: str) -> dict:
    """Извлечение информации об авто из текста"""
    # Паттерны для разных форматов
    patterns = [
        r'(\w+)\s+(\w+)\s+(\d{4})',  # Hyundai Sonata 2022
        r'(\w+)\s+(\w+)\s+(\d{2}년)', # Hyundai Sonata 22년
        r'(\w+)\s+(\w+)\s+(\d{2})'     # Hyundai Sonata 22
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            year = match.group(3)
            # Конвертируем 2-значный год в 4-значный
            if len(year) == 2:
                year = f"20{year}" if int(year) < 24 else f"19{year}"
            
            return {
                'brand': match.group(1),
                'model': match.group(2),
                'year': year
            }
    
    return None

def format_price(price: float) -> str:
    """Форматирование цены"""
    return f"${price:,.2f}"

def calculate_commission(price: float, commission_percent: float = 3) -> float:
    """Расчет комиссии"""
    return price * commission_percent / 100

def save_to_json(data: dict, filename: str):
    """Сохранение данных в JSON"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_from_json(filename: str) -> dict:
    """Загрузка данных из JSON"""
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return {}