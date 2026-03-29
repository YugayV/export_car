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
        """Парсинг encar.com (Mobile & Desktop) с интеллектуальным поиском цены и названия"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('user-agent=Mozilla/5.0 (iPhone; CPU iPhone OS 14_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0.3 Mobile/15E148 Safari/04.1')
        
        driver = None
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_window_size(375, 812)
            driver.get(url)
            
            # Ожидаем загрузки страницы
            await asyncio.sleep(5)
            
            page_source = driver.page_source
            
            # 1. Попытка вытащить данные через JavaScript (самый точный метод для Encar)
            script_data = driver.execute_script("""
                let res = {brand: 'Unknown', model: 'Unknown', price: 0, year: '2020'};
                try {
                    // 1. Поиск в глобальных переменных Encar (часто есть на мобильной версии)
                    if (window.carDetail) {
                        res.brand = window.carDetail.makeNm || res.brand;
                        res.model = window.carDetail.modelNm || res.model;
                        res.price = window.carDetail.price || res.price;
                        res.year = window.carDetail.modelYear || res.year;
                    }
                    // 2. Поиск в JSON-LD
                    let jsonLd = document.querySelector('script[type="application/ld+json"]');
                    if (jsonLd) {
                        let data = JSON.parse(jsonLd.innerText);
                        if (data.brand) res.brand = data.brand.name || res.brand;
                        if (data.name) res.model = data.name || res.model;
                        if (data.offers && data.offers.price) res.price = data.offers.price || res.price;
                    }
                } catch(e) {}
                return res;
            """)
            
            brand = script_data.get('brand', 'Unknown')
            model = script_data.get('model', 'Unknown')
            raw_price = str(script_data.get('price', '0'))
            year = str(script_data.get('year', '2020'))

            # 2. Если через JS не вышло, ищем в meta-тегах (og:title, og:description)
            if brand == 'Unknown' or model == 'Unknown':
                og_title = driver.execute_script("return document.querySelector('meta[property=\"og:title\"]')?.content")
                if og_title and 'Encar' in og_title:
                    # Формат обычно: "Hyundai Sonata - Encar"
                    clean_title = og_title.split('-')[0].strip()
                    parts = clean_title.split()
                    if len(parts) >= 2:
                        brand = parts[0]
                        model = " ".join(parts[1:])

            # 3. Если все еще Unknown, ищем через регулярные выражения в исходном коде
            if brand == 'Unknown':
                brand_match = re.search(r'"(?:makeNm|brandName)":"([^"]+)"', page_source)
                if brand_match: brand = brand_match.group(1)
            
            if model == 'Unknown':
                model_match = re.search(r'"(?:modelNm|modelName)":"([^"]+)"', page_source)
                if model_match: model = model_match.group(1)

            # 4. Поиск цены в тексте (резервный вариант)
            if raw_price == '0':
                og_desc = driver.execute_script("return document.querySelector('meta[property=\"og:description\"]')?.content")
                if og_desc:
                    price_match = re.search(r'([\d,]+)\s*만원', og_desc)
                    if price_match: raw_price = price_match.group(1).replace(',', '')

            # 5. Ищем цену в innerText страницы, если все еще 0
            final_price_krw = self.extract_price_krw(raw_price)
            if final_price_krw < 1000000:
                page_text = driver.execute_script("return document.body.innerText")
                prices = re.findall(r'([\d,]+)\s*만원', page_text)
                if prices:
                    valid_prices = [int(p.replace(',', '')) for p in prices if p.replace(',', '').isdigit()]
                    logical = [p for p in valid_prices if p >= 100] # Машины дешевле 1 млн вон редкость
                    if logical:
                        final_price_krw = max(logical) * 10000

            car_data = {
                'brand': brand,
                'model': model,
                'year': self.extract_year_clean(year),
                'price_krw': final_price_krw,
                'engine_size': self.get_text(driver, ['.engine', '.cc_info', '.displace'], '2000'),
                'fuel_type': self.get_text(driver, ['.fuel', '.fuel_info', '.fuel_nm'], 'Gasoline'),
                'mileage': self.get_text(driver, ['.mileage', '.km_info', '.mile'], '0'),
                'transmission': self.get_text(driver, ['.transmission', '.gear_info'], 'Automatic'),
                'source': 'encar.com'
            }
            
            # Чистка числовых данных
            car_data['engine_size'] = self.extract_numbers(car_data['engine_size'])
            car_data['mileage'] = self.extract_numbers(car_data['mileage'])
            
            return car_data
            
        except Exception as e:
            logger.error(f"Error parsing encar: {e}")
            return None
        finally:
            if driver:
                driver.quit()
            
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