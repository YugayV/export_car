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
        if 'encar.com' in domain:
            return 'encar.com'
        return domain
    
    async def parse_encar(self, url: str) -> Optional[Dict]:
        """Парсинг encar.com (Mobile & Desktop)"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # Имитируем реальный мобильный браузер
        chrome_options.add_argument('user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/04.1')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_window_size(375, 812) # Мобильный размер окна
            driver.get(url)
            
            # Ожидаем появления цены (макс 15 сек)
            wait = WebDriverWait(driver, 15)
            try:
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".price, .car-price, .amt_prc, .price_amount, .txt_price, .price_info")))
            except:
                logger.warning(f"Wait timeout for price on {url}")

            # Даем JS время на отрисовку
            await asyncio.sleep(3)
            
            car_data = {
                'brand': self.get_text(driver, ['.car-brand', '.brand', '.prod_title', '.name', '.make_nm', '.detail_title'], 'Hyundai'),
                'model': self.get_text(driver, ['.car-model', '.model', '.detail_title', '.model_nm', '.prod_title'], 'Sonata'),
                'year': self.get_text(driver, ['.car-year', '.year', '.reg_date', '.year_info', '.reg_dt'], '2020'),
                'price_usd': self.convert_price_to_usd(self.get_text(driver, ['.price', '.car-price', '.amt_prc', '.price_amount', '.txt_price', '.price_info'], '0')),
                'engine_size': self.get_text(driver, ['.engine', '.engine-size', '.displacement', '.cc_info', '.displace'], '2000'),
                'fuel_type': self.get_text(driver, ['.fuel', '.fuel-type', '.fuel_info', '.fuel_nm'], 'Gasoline'),
                'mileage': self.get_text(driver, ['.mileage', '.odometer', '.mileage_info', '.km_info'], '0'),
                'transmission': self.get_text(driver, ['.transmission', '.gear_info'], 'Automatic'),
                'source': 'encar.com'
            }
            
            # Очистка данных
            car_data['engine_size'] = self.extract_numbers(car_data['engine_size'])
            car_data['mileage'] = self.extract_numbers(car_data['mileage'])
            car_data['year'] = self.extract_year_clean(car_data['year'])
            
            return car_data
            
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
                        'engine_size': '2000',
                        'fuel_type': 'Gasoline',
                        'mileage': '0',
                        'source': 'kbchachacha.com'
                    }
                    return car_data
            except Exception as e:
                logger.error(f"Error parsing kbchachacha: {e}")
                return None
    
    async def parse_bobaedream(self, url: str) -> Optional[Dict]:
        return await self.general_parse(url)
    
    async def general_parse(self, url: str) -> Optional[Dict]:
        """Универсальный парсер"""
        async with aiohttp.ClientSession() as session:
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15'}
                async with session.get(url, headers=headers) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    car_data = {
                        'brand': 'Unknown',
                        'model': 'Unknown',
                        'year': '2020',
                        'price_usd': self.convert_price_to_usd(self.find_price_general(soup)),
                        'engine_size': '2000',
                        'fuel_type': 'Gasoline',
                        'mileage': '0',
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
                text = element.text.strip()
                if text: return text
            except:
                continue
        return default
    
    def find_text(self, soup, class_names):
        if isinstance(class_names, str):
            class_names = [class_names]
        for class_name in class_names:
            element = soup.find(class_=class_name)
            if element: return element.text.strip()
        return ''
    
    def convert_price_to_usd(self, price_text: str) -> float:
        """Конвертация цены в USD (учитывая 'man-won' - 10,000 KRW)"""
        price_digits = re.sub(r'[^\d]', '', price_text)
        try:
            if price_digits:
                price_value = float(price_digits)
                # Если цена в 'man-won' (обычно < 100,000)
                if price_value < 100000:
                    price_krw = price_value * 10000
                else:
                    price_krw = price_value
                return round(price_krw / 1350, 2)
        except:
            pass
        return 0
    
    def extract_numbers(self, text: str) -> str:
        numbers = re.findall(r'\d+', text)
        return numbers[0] if numbers else '0'

    def extract_year_clean(self, text: str) -> str:
        match = re.search(r'\d{2,4}', text)
        if match:
            year = match.group(0)
            if len(year) == 2:
                return f"20{year}" if int(year) < 25 else f"19{year}"
            return year
        return '2020'
    
    def find_price_general(self, soup):
        text = soup.get_text()
        match = re.search(r'(\d{3,}(?:,\d{3})*)\s*(?:원|KRW|₩)', text)
        return match.group(1) if match else '0'