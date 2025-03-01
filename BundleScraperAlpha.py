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
            db_path = os.path.join(os.getcwd(), 'humble_bundles.db')
            print(f"Ścieżka do bazy danych: {db_path}")
            
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Tworzenie tabel z lepszą strukturą
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                price_range TEXT,
                url TEXT UNIQUE,
                date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                bundle_type TEXT,
                is_active INTEGER DEFAULT 1
            )
            ''')
            
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS bundle_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bundle_id INTEGER,
                item_name TEXT,
                item_order INTEGER,
                FOREIGN KEY (bundle_id) REFERENCES bundles(id)
            )
            ''')
            
            # Sprawdź czy istnieje stara tabela i przenieś dane jeśli potrzeba
            cursor.execute("PRAGMA table_info(bundle_contents)")
            columns = [column[1] for column in cursor.fetchall()]
            
            if 'content_item' in columns and 'item_name' not in columns:
                print("Migracja danych ze starej struktury...")
                # Dodaj nową kolumnę
                cursor.execute("ALTER TABLE bundle_contents ADD COLUMN item_name TEXT")
                cursor.execute("ALTER TABLE bundle_contents ADD COLUMN item_order INTEGER")
                
                # Przenieś dane
                cursor.execute("UPDATE bundle_contents SET item_name = content_item WHERE item_name IS NULL")
                conn.commit()
            
            # Dodaj indeksy dla szybszego wyszukiwania
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_title ON bundles(title)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_type ON bundles(bundle_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_active ON bundles(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_contents ON bundle_contents(bundle_id)")
            
            # Oznacz wszystkie istniejące bundle jako nieaktywne przed dodaniem nowych
            cursor.execute("UPDATE bundles SET is_active = 0")
            
            # Dodaj nowe dane
            for bundle in bundle_data:
                title = bundle.get('title', 'Nieznany Bundle')
                price = bundle.get('price_range', '€1')
                url = bundle.get('url', '')
                contents = bundle.get('contents', [])
                
                # Określ typ bundla na podstawie tytułu lub URL
                bundle_type = 'Inny'
                if 'Book Bundle' in title or 'books' in url:
                    bundle_type = 'Książki'
                elif 'Game Bundle' in title or 'games' in url:
                    bundle_type = 'Gry'
                elif 'Software Bundle' in title or 'software' in url:
                    bundle_type = 'Oprogramowanie'
                
                # Sprawdź czy bundle już istnieje
                cursor.execute("SELECT id FROM bundles WHERE url = ?", (url,))
                result = cursor.fetchone()
                
                if result:
                    # Bundle istnieje, aktualizuj dane
                    bundle_id = result[0]
                    cursor.execute('''
                    UPDATE bundles 
                    SET title = ?, price_range = ?, is_active = 1, bundle_type = ?
                    WHERE id = ?
                    ''', (title, price, bundle_type, bundle_id))
                    
                    # Usuń starą zawartość
                    cursor.execute("DELETE FROM bundle_contents WHERE bundle_id = ?", (bundle_id,))
                else:
                    # Dodaj nowy bundle
                    cursor.execute('''
                    INSERT INTO bundles (title, price_range, url, bundle_type, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    ''', (title, price, url, bundle_type))
                    bundle_id = cursor.lastrowid
                
                # Dodaj zawartość bundla
                for i, item in enumerate(contents):
                    cursor.execute('''
                    INSERT INTO bundle_contents (bundle_id, item_name, item_order)
                    VALUES (?, ?, ?)
                    ''', (bundle_id, item, i+1))
            
            conn.commit()
            print(f"Zapisano {len(bundle_data)} bundli do bazy danych")
            
            # Wyświetl statystyki
            cursor.execute("SELECT bundle_type, COUNT(*) FROM bundles WHERE is_active = 1 GROUP BY bundle_type")
            stats = cursor.fetchall()
            print("\nStatystyki aktywnych bundli:")
            for bundle_type, count in stats:
                print(f"- {bundle_type}: {count}")
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Błąd podczas zapisywania do bazy danych: {str(e)}")
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

    def display_database_summary(self):
        """Wyświetla podsumowanie zawartości bazy danych w czytelny sposób."""
        try:
            db_path = os.path.join(os.getcwd(), 'humble_bundles.db')
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            # Pobierz wszystkie aktywne bundle
            cursor.execute("""
            SELECT id, title, price_range, bundle_type, date_added 
            FROM bundles 
            WHERE is_active = 1
            ORDER BY bundle_type, title
            """)
            
            bundles = cursor.fetchall()
            
            if not bundles:
                print("Brak aktywnych bundli w bazie danych.")
                return
            
            # Statystyki według typu
            cursor.execute("""
            SELECT bundle_type, COUNT(*) as count 
            FROM bundles 
            WHERE is_active = 1 
            GROUP BY bundle_type
            ORDER BY count DESC
            """)
            
            stats = cursor.fetchall()
            
            print("\n===== PODSUMOWANIE BUNDLI W BAZIE DANYCH =====")
            print(f"Łączna liczba aktywnych bundli: {len(bundles)}")
            print("\nPodział według kategorii:")
            for bundle_type, count in stats:
                print(f"- {bundle_type}: {count} bundli")
            
            # Wyświetl szczegóły każdego bundla
            print("\n===== SZCZEGÓŁY BUNDLI =====")
            for bundle_id, title, price_range, bundle_type, date_added in bundles:
                # Pobierz liczbę elementów w bundlu
                cursor.execute("SELECT COUNT(*) FROM bundle_contents WHERE bundle_id = ?", (bundle_id,))
                item_count = cursor.fetchone()[0]
                
                # Pobierz przykładowe elementy (pierwsze 3)
                cursor.execute("""
                SELECT item_name FROM bundle_contents 
                WHERE bundle_id = ? 
                ORDER BY item_order 
                LIMIT 3
                """, (bundle_id,))
                
                sample_items = cursor.fetchall()
                sample_items = [item[0] for item in sample_items]
                
                # Formatuj wyświetlanie
                print(f"\n[{bundle_type}] {title}")
                print(f"Cena: {price_range}")
                print(f"Dodano: {date_added}")
                print(f"Liczba elementów: {item_count}")
                print("Przykładowe elementy:")
                for item in sample_items:
                    print(f"- {item}")
                if item_count > 3:
                    print(f"- ... i {item_count - 3} więcej")
                print("-" * 50)
            
            conn.close()
            return True
            
        except Exception as e:
            print(f"Błąd podczas wyświetlania podsumowania bazy danych: {str(e)}")
            import traceback
            traceback.print_exc()
            return False

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
