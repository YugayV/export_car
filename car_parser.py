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
        """Парсинг encar.com (Mobile & Desktop) с интеллектуальным поиском цены"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        # Имитируем реальный мобильный браузер (iPhone)
        chrome_options.add_argument('user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/04.1')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_window_size(375, 812) # Мобильный размер окна
            driver.get(url)
            
            # Ожидаем появления любого элемента (макс 15 сек)
            wait = WebDriverWait(driver, 15)
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            except:
                logger.warning(f"Wait timeout for body on {url}")

            # Даем JS время на полную отрисовку всех данных
            await asyncio.sleep(5)
            
            # 1. Интеллектуальный поиск цены и данных
            raw_price = '0'
            brand = 'Unknown'
            model = 'Unknown'
            year = '2020'
            
            # А. Попытка вытащить данные из мета-тегов и заголовка (самый точный способ)
            try:
                # 1. Проверяем og:title - там обычно "Марка Модель - Encar"
                og_title = driver.execute_script("return document.querySelector('meta[property=\"og:title\"]')?.content")
                if og_title and 'Encar' in og_title:
                    clean_title = og_title.split('-')[0].strip()
                    title_parts = clean_title.split()
                    if len(title_parts) >= 2:
                        brand = title_parts[0]
                        model = " ".join(title_parts[1:])
                
                # 2. Если все еще Unknown, пробуем вытащить из JSON-LD или скриптов Encar
                if brand == 'Unknown':
                    script_data = driver.execute_script("""
                        let data = {};
                        // Попытка найти данные в глобальных переменных Encar
                        if (window.carDetail) {
                            data.brand = window.carDetail.makeNm;
                            data.model = window.carDetail.modelNm;
                        }
                        return data;
                    """)
                    if script_data.get('brand'):
                        brand = script_data['brand']
                        model = script_data.get('model', 'Unknown')

                # 3. Если все еще Unknown, пробуем заголовок страницы
                if brand == 'Unknown':
                    page_title = driver.title
                    if page_title and '-' in page_title:
                        clean_title = page_title.split('-')[0].strip()
                        title_parts = clean_title.split()
                        if len(title_parts) >= 2:
                            brand = title_parts[0]
                            model = " ".join(title_parts[1:])

                # 3. Пытаемся найти год и цену в og:description
                og_desc = driver.execute_script("return document.querySelector('meta[property=\"og:description\"]').content")
                # Цена
                price_match = re.search(r'([\d,]+)\s*만원', og_desc)
                if price_match:
                    raw_price = price_match.group(1).replace(',', '')
                # Год
                year_match = re.search(r'(\d{2,4})년', og_desc)
                if year_match:
                    year = year_match.group(1)
            except Exception as e:
                logger.warning(f"Meta extraction failed: {e}")

            # Б. Если в мета-тегах нет, ищем по специфическим селекторам
            if brand == 'Unknown':
                brand = self.get_text(driver, [
                    '.car-brand', '.brand', '.make_nm', 
                    '.prod_title .make', '.detail_title .brand',
                    'span.make'
                ], 'Unknown')
            
            if model == 'Unknown':
                model = self.get_text(driver, [
                    '.car-model', '.model', '.model_nm', 
                    '.prod_title .model', '.detail_title .model',
                    'span.model'
                ], 'Unknown')
            if year == '2020':
                year = self.get_text(driver, ['.car-year', '.year', '.reg_date', '.year_info', '.reg_dt'], '2020')

            clean_raw = raw_price.replace(',', '')
            if raw_price == '0' or (clean_raw.isdigit() and int(clean_raw) < 50):
                raw_price = self.get_text(driver, [
                    '.price_amount .num', 
                    '.amt_prc .num', 
                    '.txt_price .num',
                    '.price_info .num', 
                    '.amt',
                    '.price'
                ], '0')
            
            # В. Валидация и финальный поиск в тексте
            final_price_krw = self.extract_price_krw(raw_price)
            
            # Если цена все еще нереально низкая (меньше 1 млн вон), ищем в innerText
            if final_price_krw < 1000000:
                page_text = driver.execute_script("return document.body.innerText")
                # Ищем все вхождения "число + 만원"
                all_prices = re.findall(r'([\d,]+)\s*만원', page_text)
                if all_prices:
                    clean_prices = [int(p.replace(',', '')) for p in all_prices if p.replace(',', '').isdigit()]
                    logical_prices = [p for p in clean_prices if p >= 100]
                    if logical_prices:
                        raw_price = str(max(logical_prices))
                        final_price_krw = self.extract_price_krw(raw_price)
                        logger.info(f"Price corrected via text scan: {final_price_krw}")

            car_data = {
                'brand': brand,
                'model': model,
                'year': year,
                'price_krw': final_price_krw,
                'engine_size': self.get_text(driver, ['.engine', '.engine-size', '.displacement', '.cc_info', '.displace', '.capacity'], '2000'),
                'fuel_type': self.get_text(driver, ['.fuel', '.fuel-type', '.fuel_info', '.fuel_nm'], 'Gasoline'),
                'mileage': self.get_text(driver, ['.mileage', '.odometer', '.mileage_info', '.km_info', '.mile'], '0'),
                'transmission': self.get_text(driver, ['.transmission', '.gear_info', '.gear_nm'], 'Automatic'),
                'source': 'encar.com'
            }
            
            # Очистка и валидация данных
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
                        'price_krw': self.extract_price_krw(self.find_text(soup, ['price', 'car_price'])),
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
                        'price_krw': self.extract_price_krw(self.find_price_general(soup)),
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
    
    def extract_price_krw(self, price_text: str) -> float:
        """Извлечение чистой цены в вонах (KRW)"""
        # Очищаем текст от лишних символов
        price_digits = re.sub(r'[^\d]', '', str(price_text))
        try:
            if price_digits:
                val = float(price_digits)
                # На Encar цены обычно в 'man-won' (десятитысячных вонах). 
                # Если число в пределах 10-100,000 - это точно man-won.
                # Машины стоят от 100 манов (1.3 млн вон) до 50,000 манов (650 млн вон).
                if val < 100000:
                    return val * 10000
                return val
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