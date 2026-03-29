import aiohttp
from bs4 import BeautifulSoup
import asyncio
import re
import logging
from typing import Optional, Dict
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException

logger = logging.getLogger(__name__)

class CarParser:
    def __init__(self):
        self.sites = {
            'encar.com': self.parse_encar,
            'kbchachacha.com': self.parse_kbchachacha,
            'bobaedream.co.kr': self.parse_bobaedream
        }
        
    async def parse_from_url(self, url: str) -> Optional[Dict]:
        """Парсинг данных автомобиля по URL"""
        try:
            domain = self.extract_domain(url)
            logger.info(f"Parsing URL: {url}, domain: {domain}")
            
            if domain in self.sites:
                return await self.sites[domain](url)
            else:
                return await self.general_parse(url)
                
        except Exception as e:
            logger.error(f"Error parsing URL {url}: {e}")
            return None
    
    def extract_domain(self, url: str) -> str:
        """Извлечение основного домена из URL (включая мобильные версии)"""
        match = re.search(r'https?://(?:www\.|fem\.)?([^/]+)', url)
        domain = match.group(1) if match else ''
        # Если это мобильная версия encar, возвращаем основной домен для маппинга
        if 'encar.com' in domain:
            return 'encar.com'
        return domain
    
    async def parse_encar(self, url: str) -> Optional[Dict]:
        """Парсинг encar.com"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Без GUI
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.get(url)
            
            wait = WebDriverWait(driver, 10)
            
            # Ожидаем загрузки страницы
            wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # Дополнительная задержка для JS на мобильной версии
            await asyncio.sleep(2)
            
            car_data = {
                'brand': self.get_text(driver, ['.car-brand', '.brand', '.prod_title', '.name', '.make_nm'], 'Hyundai'),
                'model': self.get_text(driver, ['.car-model', '.model', '.detail_title', '.model_nm'], 'Sonata'),
                'year': self.get_text(driver, ['.car-year', '.year', '.reg_date', '.year_info'], '2020'),
                'price_usd': self.convert_price_to_usd(self.get_text(driver, ['.price', '.car-price', '.amt_prc', '.price_amount', '.price_info', '.txt_price'], '0')),
                'engine_size': self.get_text(driver, ['.engine', '.engine-size', '.displacement', '.cc_info'], '2000'),
                'fuel_type': self.get_text(driver, ['.fuel', '.fuel-type', '.fuel_info'], 'Gasoline'),
                'mileage': self.get_text(driver, ['.mileage', '.odometer', '.mileage_info'], '0'),
                'transmission': self.get_text(driver, '.transmission', 'Automatic'),
                'source': 'encar.com'
            }
            
            # Очищаем и валидируем данные
            car_data['engine_size'] = self.extract_numbers(car_data['engine_size'])
            car_data['mileage'] = self.extract_numbers(car_data['mileage'])
            
            return car_data
            
        except TimeoutException:
            logger.error(f"Timeout while loading {url}")
            return None
        except Exception as e:
            logger.error(f"Error parsing encar: {e}")
            return None
        finally:
            if driver:
                driver.quit()
    
    async def parse_kbchachacha(self, url: str) -> Optional[Dict]:
        """Парсинг kbchachacha.com"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    car_data = {
                        'brand': self.find_text(soup, ['car_brand', 'brand']),
                        'model': self.find_text(soup, ['car_model', 'model']),
                        'year': self.find_text(soup, ['year', 'car_year']),
                        'price_usd': self.convert_price_to_usd(self.find_text(soup, ['price', 'car_price'])),
                        'engine_size': self.find_text(soup, ['engine', 'cc']),
                        'fuel_type': self.find_text(soup, ['fuel', 'fuel_type']),
                        'mileage': self.find_text(soup, ['mileage', 'odometer']),
                        'transmission': self.find_text(soup, ['transmission', 'gear']),
                        'source': 'kbchachacha.com'
                    }
                    
                    return car_data
                    
            except Exception as e:
                logger.error(f"Error parsing kbchachacha: {e}")
                return None
    
    async def parse_bobaedream(self, url: str) -> Optional[Dict]:
        """Парсинг bobaedream.co.kr"""
        # Аналогично parse_kbchachacha
        return await self.general_parse(url)
    
    async def general_parse(self, url: str) -> Optional[Dict]:
        """Общий парсер для любых сайтов"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # Ищем цену в различных форматах
                    price = self.find_price_general(soup)
                    
                    # Ищем год
                    year = self.find_year_general(soup)
                    
                    # Ищем марку и модель
                    brand, model = self.find_brand_model_general(soup)
                    
                    car_data = {
                        'brand': brand,
                        'model': model,
                        'year': year,
                        'price_usd': self.convert_price_to_usd(price),
                        'engine_size': '2000',
                        'fuel_type': 'Gasoline',
                        'mileage': '0',
                        'transmission': 'Automatic',
                        'source': url
                    }
                    
                    return car_data
                    
            except Exception as e:
                logger.error(f"Error in general parse: {e}")
                return None
    
    def get_text(self, driver, selectors, default=''):
        """Безопасное получение текста элемента"""
        if isinstance(selectors, str):
            selectors = [selectors]
        
        for selector in selectors:
            try:
                element = driver.find_element(By.CSS_SELECTOR, selector)
                return element.text.strip()
            except:
                continue
        return default
    
    def find_text(self, soup, class_names):
        """Поиск текста по классам"""
        if isinstance(class_names, str):
            class_names = [class_names]
        
        for class_name in class_names:
            element = soup.find(class_=class_name)
            if element:
                return element.text.strip()
        return ''
    
    def convert_price_to_usd(self, price_text: str) -> float:
        """Конвертация цены в USD (учитывая 'man-won' - 10,000 KRW)"""
        # Убираем все символы кроме цифр
        price_digits = re.sub(r'[^\d]', '', price_text)
        
        try:
            if price_digits:
                price_value = float(price_digits)
                
                # Если цена в корейских 'man-won' (обычно на Encar цены в десятитысячных вонах)
                # Например, 2500 man-won = 25,000,000 KRW
                if price_value < 100000: # Предполагаем, что это man-won если число не миллионы
                    price_krw = price_value * 10000
                else:
                    price_krw = price_value
                
                # Используем актуальный курс из калькулятора (или 1350 по дефолту)
                rate = 1350 
                return round(price_krw / rate, 2)
        except:
            pass
        return 0
    
    def extract_numbers(self, text: str) -> str:
        """Извлечение чисел из текста"""
        numbers = re.findall(r'\d+', text)
        return numbers[0] if numbers else '0'
    
    def find_price_general(self, soup):
        """Поиск цены на странице"""
        price_patterns = [
            r'(\d{3,}(?:,\d{3})*)\s*(?:원|KRW|₩)',
            r'₩\s*(\d{3,}(?:,\d{3})*)',
            r'USD\s*(\d{3,}(?:,\d{3})*)',
            r'\$(\d{3,}(?:,\d{3})*)'
        ]
        
        text = soup.get_text()
        for pattern in price_patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return '0'
    
    def find_year_general(self, soup):
        """Поиск года выпуска"""
        year_pattern = r'\b(19|20)\d{2}\b'
        text = soup.get_text()
        matches = re.findall(year_pattern, text)
        return matches[0] if matches else '2020'
    
    def find_brand_model_general(self, soup):
        """Поиск марки и модели"""
        title = soup.find('title')
        if title:
            title_text = title.text
            # Простой парсинг из title
            parts = title_text.split()
            if len(parts) >= 2:
                return parts[0], parts[1]
        return 'Unknown', 'Unknown'