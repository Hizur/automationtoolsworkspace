from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import json
import sqlite3
from datetime import datetime
import time
import os

class HumbleBundleScraper:
    def __init__(self):
        # Konfiguracja opcji Chrome
        chrome_options = Options()
        
        # Opcje zapewniające, że Chrome pozostanie zminimalizowany
        chrome_options.add_argument("--start-minimized")
        chrome_options.add_argument("--window-position=-32000,-32000")  # Przesuń okno poza ekran
        
        # Opcje wydajnościowe i zapobiegające wyskakiwaniu okien
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-notifications")
        chrome_options.add_argument("--disable-popup-blocking")
        
        # Opcjonalnie możemy użyć trybu headless, ale może to wpłynąć na działanie niektórych stron
        # chrome_options.add_argument("--headless=new")
        
        # Inicjalizacja WebDrivera z opcjami
        self.driver = webdriver.Chrome(options=chrome_options)
        
        # Ustaw timeout dla operacji WebDrivera
        self.driver.set_page_load_timeout(30)
        
        # Dodatkowe ustawienie rozmiaru okna na minimalny
        self.driver.set_window_size(1, 1)
        
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        self.db_name = 'humble_bundles.db'
        self.setup_database()
    
    def setup_database(self):
        """Inicjalizacja bazy danych SQLite"""
        conn = sqlite3.connect(self.db_name)
        cursor = conn.cursor()
        
        # Tworzenie tabel jeśli nie istnieją
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT,
                price_range TEXT,
                url TEXT,
                scrape_date TEXT
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundle_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bundle_id INTEGER,
                content_item TEXT,
                FOREIGN KEY (bundle_id) REFERENCES bundles (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def save_to_database(self, bundle_data):
        try:
            print("Zapisuję dane do bazy danych...")
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'humble_bundles.db')
            print(f"Ścieżka do bazy danych: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Tworzenie tabeli, jeśli nie istnieje
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price_range TEXT,
                url TEXT UNIQUE,
                scrape_date TEXT
            )
            ''')
            
            # Tworzenie tabeli dla zawartości bundli
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundle_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bundle_id INTEGER,
                item_name TEXT,
                FOREIGN KEY (bundle_id) REFERENCES bundles (id)
            )
            ''')
            
            # Zapisywanie danych
            current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for bundle in bundle_data:
                try:
                    # Dodawanie bundle
                    cursor.execute('''
                    INSERT OR REPLACE INTO bundles (title, price_range, url, scrape_date)
                    VALUES (?, ?, ?, ?)
                    ''', (bundle['title'], bundle['price_range'], bundle['url'], current_date))
                    
                    # Pobieranie ID dodanego bundle
                    bundle_id = cursor.lastrowid
                    
                    # Usuwanie starych zawartości dla tego bundle
                    cursor.execute('DELETE FROM bundle_contents WHERE bundle_id = ?', (bundle_id,))
                    
                    # Dodawanie zawartości
                    for item in bundle['contents']:
                        cursor.execute('''
                        INSERT INTO bundle_contents (bundle_id, item_name)
                        VALUES (?, ?)
                        ''', (bundle_id, item))
                    
                    print(f"Zapisano bundle: {bundle['title']}")
                except Exception as e:
                    print(f"Błąd podczas zapisywania bundle {bundle['title']}: {e}")
            
            # Zatwierdzanie zmian
            conn.commit()
            print(f"Pomyślnie zapisano {len(bundle_data)} bundli do bazy danych")
            
            # Sprawdzanie, czy dane zostały zapisane
            cursor.execute('SELECT COUNT(*) FROM bundles')
            bundle_count = cursor.fetchone()[0]
            cursor.execute('SELECT COUNT(*) FROM bundle_contents')
            content_count = cursor.fetchone()[0]
            print(f"W bazie danych znajduje się {bundle_count} bundli i {content_count} elementów zawartości")
            
            conn.close()
            return True
        except Exception as e:
            print(f"Wystąpił błąd podczas zapisywania do bazy danych: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def save_to_json(self, bundle_data):
        """Zapisywanie danych do pliku JSON"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'humble_bundles_{timestamp}.json'
        
        # Dodanie timestamp do danych
        data_with_timestamp = {
            'scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'bundles': bundle_data
        }
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data_with_timestamp, f, ensure_ascii=False, indent=4)
        
        return filename

    def get_bundle_title(self, driver):
        try:
            # Próbujemy różnych selektorów dla tytułu
            selectors = [
                ".bundle-title", 
                ".hero-title", 
                "h1.heading-medium",
                "h1",
                ".title-container h1"
            ]
            
            for selector in selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    if elements and elements[0].text.strip():
                        return elements[0].text.strip()
                except:
                    continue
            
            # Jeśli nie znaleziono tytułu, spróbuj pobrać z URL
            url = driver.current_url
            if 'books' in url:
                return "Book Bundle"
            elif 'games' in url:
                return "Game Bundle"
            elif 'software' in url:
                return "Software Bundle"
            elif 'bundle' in url:
                parts = url.split('/')
                if len(parts) > 4:
                    title_part = parts[4].split('?')[0]
                    return title_part.replace('-', ' ').title()
            
            return "Nieznany Bundle"
        except:
            return "Nieznany Bundle"

    def get_bundle_contents(self, driver):
        try:
            # Czekaj na załadowanie zawartości
            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".tier-item-content, .dd-game-row, .tier-content"))
                )
            except:
                print("Timeout podczas ładowania zawartości, próbuję kontynuować...")
            
            # Próbuj różne selektory dla zawartości
            selectors = [
                ".tier-item-content .dd-image-box-caption", 
                ".tier-item-content .dd-image-box-white-text",
                ".dd-game-row .dd-image-box-caption",
                ".dd-game-title",
                ".tier-content .dd-name",
                ".content-list li"
            ]
            
            for selector in selectors:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                contents = [elem.text.strip() for elem in elements if elem.text.strip()]
                if contents:
                    return contents
            
            # Jeśli nie znaleziono zawartości, sprawdź czy to nie jest strona informacyjna
            if any(x in driver.current_url for x in ['blog', 'support', 'jobs', 'membership', 'affiliates', 'facebook', 'instagram']):
                return ["Strona informacyjna - brak zawartości bundle"]
            
            return []
        except Exception as e:
            print(f"Błąd podczas pobierania zawartości: {str(e)}")
            return []

    def scrape_bundles(self):
        try:
            print("Rozpoczynam scrapowanie...")
            self.driver.get('https://www.humblebundle.com/bundles')
            print("Czekam na załadowanie strony...")
            time.sleep(10)
            
            # Poczekaj na załadowanie bundli
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".tile-holder"))
            )
            
            bundle_tiles = self.driver.find_elements(By.CSS_SELECTOR, ".tile-holder")
            print(f"Znaleziono {len(bundle_tiles)} bundli")
            
            # Zbierz wszystkie linki do bundli
            bundle_links = []
            for tile in bundle_tiles:
                try:
                    link = tile.find_element(By.TAG_NAME, "a")
                    url = link.get_attribute('href')
                    bundle_links.append(url)
                except Exception as e:
                    print(f"Nie udało się pobrać linku: {e}")
            
            print(f"Zebrano {len(bundle_links)} linków do bundli")
            
            # Usuń duplikaty
            bundle_links = list(set(bundle_links))
            print(f"Po usunięciu duplikatów: {len(bundle_links)} unikalnych bundli")
            
            # Otwórz każdy bundle w nowej karcie
            original_window = self.driver.current_window_handle
            tabs = [original_window]  # Lista otwartych kart
            
            print("Otwieram bundle w nowych kartach...")
            for i, url in enumerate(bundle_links):
                # Otwórz nową kartę
                self.driver.execute_script("window.open('', '_blank');")
                tabs.append(self.driver.window_handles[-1])
                self.driver.switch_to.window(tabs[-1])
                
                # Przejdź do URL bundle
                print(f"Otwieram bundle {i+1}/{len(bundle_links)}: {url}")
                self.driver.get(url)
                time.sleep(1)  # Krótka pauza między otwieraniem kart
            
            # Przełącz z powrotem na pierwszą kartę
            self.driver.switch_to.window(original_window)
            
            # Przetwarzaj każdą kartę po kolei
            bundle_data = []
            
            print("\nPrzetwarzam otwarte karty...")
            for i, tab in enumerate(tabs[1:], 1):  # Pomijamy pierwszą kartę (strona główna)
                try:
                    print(f"\nPrzetwarzam bundle {i}/{len(tabs)-1}")
                    self.driver.switch_to.window(tab)
                    
                    url = self.driver.current_url
                    print(f"URL: {url}")
                    
                    # Pobierz tytuł z URL
                    try:
                        bundle_name = url.split('/')[-1].split('?')[0]
                        title = bundle_name.replace('-', ' ').replace('_', ' ').title()
                        print(f"Tytuł: {title}")
                    except:
                        title = "Nieznany tytuł"
                    
                    # Pobierz cenę - NOWA METODA
                    try:
                        # Szukamy etykiety z ceną
                        price_labels = self.driver.find_elements(By.CSS_SELECTOR, "label.preset-price")
                        if price_labels:
                            # Bierzemy pierwszą (najniższą) cenę
                            price_range = price_labels[0].text.strip()
                            print(f"Znaleziona cena: {price_range}")
                        else:
                            # Alternatywne metody pobierania ceny
                            price_element = self.driver.find_element(By.CSS_SELECTOR, ".price-info, .fine-print, .price-text")
                            price_range = price_element.text.strip().split('\n')[0]
                            print(f"Alternatywna cena: {price_range}")
                    except Exception as e:
                        print(f"Błąd podczas pobierania ceny: {e}")
                        price_range = "Cena nieznana"
                    
                    # Pobierz zawartość (gry)
                    try:
                        game_titles = WebDriverWait(self.driver, 10).until(
                            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "span.item-title"))
                        )
                        contents = [title.text.strip() for title in game_titles if title.text.strip()]
                        print(f"Znaleziono {len(contents)} elementów")
                    except Exception as e:
                        print(f"Błąd podczas pobierania zawartości: {e}")
                        contents = ["Nie udało się pobrać zawartości"]
                    
                    bundle_info = {
                        'title': title,
                        'price_range': price_range,
                        'contents': contents,
                        'url': url
                    }
                    
                    bundle_data.append(bundle_info)
                    print(f"Dodano bundle: {title}")
                    
                except Exception as e:
                    print(f"Błąd podczas przetwarzania karty: {str(e)}")
            
            # Zamknij wszystkie karty oprócz pierwszej
            for tab in tabs[1:]:
                self.driver.switch_to.window(tab)
                self.driver.close()
            
            # Wróć do pierwszej karty
            self.driver.switch_to.window(original_window)
            
            if not bundle_data:
                print("\nNie znaleziono żadnych bundli!")
            else:
                print(f"\nPomyślnie zebrano dane o {len(bundle_data)} bundlach")
                
                # Wyświetl zebrane dane
                print("\nZnalezione bundle:")
                for bundle in bundle_data:
                    print(f"\nTytuł: {bundle['title']}")
                    print(f"Cena: {bundle['price_range']}")
                    print(f"Liczba elementów: {len(bundle['contents'])}")
                    print("-" * 50)
            
            # Zapisz dane do bazy danych i JSON
            json_path = self.save_to_json(bundle_data)
            db_success = self.save_to_database(bundle_data)
            
            return bundle_data, json_path, db_success
            
        except Exception as e:
            print(f"Wystąpił błąd główny: {str(e)}")
            import traceback
            traceback.print_exc()
            return [], None, False
            
        finally:
            self.driver.quit()

    def get_bundle_price(self, driver):
        try:
            # Próbuj wszystkie selektory w jednym bloku try
            selectors = [
                ("css", "label.preset-price"),
                ("xpath", "/html/body/div[1]/div[1]/div[5]/div[2]/div/div[1]/div[2]/div/div[3]/div/form/div[1]/label[2]"),
                ("css", ".dd-price-row label"),
                ("css", "span.dd-price")
            ]
            
            for selector_type, selector in selectors:
                try:
                    if selector_type == "css":
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if elements:
                            return elements[0].text.strip()
                    else:  # xpath
                        element = driver.find_element(By.XPATH, selector)
                        return element.text.strip()
                except:
                    continue
                
            # Jeśli wszystkie metody zawiodą
            return "€1"
        except:
            return "€1"

def main():
    scraper = HumbleBundleScraper()
    bundles, json_filename, db_success = scraper.scrape_bundles()
    
    # Wyświetlenie wyników
    print("\nZnalezione bundle:")
    for bundle in bundles:
        print(f"\nTytuł: {bundle['title']}")
        print(f"Zakres cen: {bundle['price_range']}")
        print(f"URL: {bundle['url']}")
        print("Zawartość:")
        for item in bundle['contents']:
            print(f"- {item}")
        print("-" * 50)
    
    print(f"\nDane zostały zapisane do bazy SQLite: {scraper.db_name}")
    print(f"Dane zostały zapisane do pliku JSON: {json_filename}")

if __name__ == "__main__":
    main()
