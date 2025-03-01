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
        self.db_path = os.path.join(os.getcwd(), 'humble_bundles.db')
        self.setup_database()
    
    def setup_database(self):
        """Inicjalizacja bazy danych SQLite"""
        try:
            print(f"Inicjalizuję bazę danych: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Sprawdź czy tabela istnieje
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bundles'")
            table_exists = cursor.fetchone()
            
            if not table_exists:
                print("Tworzę nową tabelę bundles")
                # Tworzenie tabeli od podstaw
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS bundles (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        price_range TEXT,
                        url TEXT UNIQUE,
                        date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        bundle_type TEXT,
                        is_active INTEGER DEFAULT 1,
                        expiration_date TEXT
                    )
                ''')
            else:
                print("Tabela bundles już istnieje, sprawdzam strukturę")
                # Sprawdź czy kolumny istnieją
                cursor.execute("PRAGMA table_info(bundles)")
                columns = [column[1] for column in cursor.fetchall()]
                
                # Dodaj kolumnę bundle_type jeśli nie istnieje
                if 'bundle_type' not in columns:
                    cursor.execute("ALTER TABLE bundles ADD COLUMN bundle_type TEXT")
                    print("Dodano kolumnę bundle_type do istniejącej tabeli")
                
                # Dodaj kolumnę expiration_date jeśli nie istnieje
                if 'expiration_date' not in columns:
                    cursor.execute("ALTER TABLE bundles ADD COLUMN expiration_date TEXT")
                    print("Dodano kolumnę expiration_date do istniejącej tabeli")
            
            # Tworzenie tabeli zawartości bundle
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS bundle_contents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bundle_id INTEGER,
                    item_name TEXT,
                    item_order INTEGER,
                    FOREIGN KEY (bundle_id) REFERENCES bundles (id)
                )
            ''')
            
            # Sprawdź strukturę kolumn przed dodaniem indeksów
            cursor.execute("PRAGMA table_info(bundles)")
            columns = [column[1] for column in cursor.fetchall()]
            
            # Dodaj indeksy dla istniejących kolumn
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_title ON bundles(title)")
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_bundle_url ON bundles(url)")  # Unikalne URL
            
            if 'bundle_type' in columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_type ON bundles(bundle_type)")
            
            if 'is_active' in columns:
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_active ON bundles(is_active)")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_bundle_contents ON bundle_contents(bundle_id)")
            
            # Usuń potencjalne duplikaty
            self.deduplicate_database()
            
            conn.commit()
            print("Inicjalizacja bazy danych zakończona pomyślnie")
            conn.close()
        except Exception as e:
            print(f"Błąd podczas inicjalizacji bazy danych: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def deduplicate_database(self):
        """Usuwa duplikaty z bazy danych"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            print("Sprawdzam duplikaty w bazie danych...")
            
            # Znajdź duplikaty URL
            cursor.execute("""
            SELECT url, COUNT(*) as count
            FROM bundles
            GROUP BY url
            HAVING COUNT(*) > 1
            """)
            
            duplicates = cursor.fetchall()
            if duplicates:
                print(f"Znaleziono {len(duplicates)} URL z duplikatami")
                
                for url, count in duplicates:
                    print(f"URL {url} ma {count} duplikatów")
                    
                    # Znajdź wszystkie rekordy z tym URL
                    cursor.execute("SELECT id FROM bundles WHERE url = ? ORDER BY id DESC", (url,))
                    record_ids = [row[0] for row in cursor.fetchall()]
                    
                    # Zachowaj najnowszy rekord, usuń pozostałe
                    keep_id = record_ids[0]
                    delete_ids = record_ids[1:]
                    
                    print(f"Zachowuję rekord ID={keep_id}, usuwam ID: {delete_ids}")
                    
                    # Zaktualizuj zawartość bundla - przenieś wszystkie elementy do zachowanego rekordu
                    for delete_id in delete_ids:
                        cursor.execute("""
                        UPDATE bundle_contents 
                        SET bundle_id = ?
                        WHERE bundle_id = ?
                        """, (keep_id, delete_id))
                        
                        # Usuń zduplikowany rekord
                        cursor.execute("DELETE FROM bundles WHERE id = ?", (delete_id,))
                    
                print(f"Usunięto duplikaty. Zatwierdzam zmiany...")
                conn.commit()
            else:
                print("Nie znaleziono duplikatów URL w bazie danych.")
            
            # Sprawdź duplikaty w zawartości bundli
            cursor.execute("""
            SELECT bundle_id, item_name, COUNT(*) as count
            FROM bundle_contents
            GROUP BY bundle_id, item_name
            HAVING COUNT(*) > 1
            """)
            
            content_duplicates = cursor.fetchall()
            if content_duplicates:
                print(f"Znaleziono {len(content_duplicates)} zduplikowanych elementów w bundle_contents")
                
                for bundle_id, item_name, count in content_duplicates:
                    print(f"Bundle ID={bundle_id}, Element '{item_name}' ma {count} duplikatów")
                    
                    # Znajdź wszystkie zduplikowane rekordy
                    cursor.execute("""
                    SELECT id FROM bundle_contents 
                    WHERE bundle_id = ? AND item_name = ?
                    ORDER BY id
                    """, (bundle_id, item_name))
                    
                    record_ids = [row[0] for row in cursor.fetchall()]
                    
                    # Zachowaj pierwszy rekord, usuń pozostałe
                    keep_id = record_ids[0]
                    delete_ids = record_ids[1:]
                    
                    for delete_id in delete_ids:
                        cursor.execute("DELETE FROM bundle_contents WHERE id = ?", (delete_id,))
                
                print(f"Usunięto duplikaty zawartości. Zatwierdzam zmiany...")
                conn.commit()
            else:
                print("Nie znaleziono duplikatów w zawartości bundli.")
            
            conn.close()
            return True
        except Exception as e:
            print(f"Błąd podczas usuwania duplikatów: {str(e)}")
            return False

    def save_to_database(self, bundle_data):
        """Zapisuje dane do bazy danych SQLite"""
        if not bundle_data:
            print("Brak danych do zapisania")
            return False
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            conn = None
            try:
                print(f"Zapisuję dane do bazy danych: {self.db_path} (próba {retry_count + 1}/{max_retries})")
                
                # Upewnij się, że katalog istnieje
                db_dir = os.path.dirname(self.db_path)
                if not os.path.exists(db_dir) and db_dir:
                    os.makedirs(db_dir)
                
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                # Włącz obsługę kluczy obcych
                cursor.execute("PRAGMA foreign_keys = ON")
                
                # Rozpocznij transakcję
                cursor.execute("BEGIN TRANSACTION")
                
                # Najpierw oznacz wszystkie jako nieaktywne
                cursor.execute("UPDATE bundles SET is_active = 0")
                
                # Lista URL przetworzonych bundli do śledzenia duplikatów
                processed_urls = set()
                
                # Dodaj nowe dane
                for bundle in bundle_data:
                    title = bundle.get('title', 'Nieznany Bundle')
                    price = bundle.get('price_range', '€1')
                    url = bundle.get('url', '')
                    contents = bundle.get('contents', [])
                    expiration_date = bundle.get('expiration_date')
                    
                    # Pomijaj duplikaty URL w aktualnym zbiorze danych
                    if url in processed_urls:
                        print(f"Pomijam duplikat URL: {url}")
                        continue
                    
                    processed_urls.add(url)
                    
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
                        SET title = ?, price_range = ?, is_active = 1, bundle_type = ?, expiration_date = ?
                        WHERE id = ?
                        ''', (title, price, bundle_type, expiration_date, bundle_id))
                    else:
                        # Dodaj nowy bundle
                        cursor.execute('''
                        INSERT INTO bundles (title, price_range, url, bundle_type, is_active, expiration_date)
                        VALUES (?, ?, ?, ?, 1, ?)
                        ''', (title, price, url, bundle_type, expiration_date))
                        bundle_id = cursor.lastrowid
                    
                    # Dodaj zawartość bundla
                    for i, item in enumerate(contents):
                        cursor.execute('''
                        INSERT INTO bundle_contents (bundle_id, item_name, item_order)
                        VALUES (?, ?, ?)
                        ''', (bundle_id, item, i+1))
                
                # Zatwierdź zmiany
                conn.commit()
                print("Zapisywanie zakończone pomyślnie")
                
                # Usuń potencjalne duplikaty
                self.deduplicate_database()
                
                return True
            
            except sqlite3.IntegrityError as e:
                if "UNIQUE constraint failed: bundles.url" in str(e):
                    print(f"Błąd duplikatu URL: {str(e)}")
                    print("Próba naprawy duplikatów...")
                    
                    # Spróbuj naprawić duplikaty i kontynuuj
                    self.deduplicate_database()
                    retry_count += 1
                    continue
                else:
                    print(f"Błąd integralności bazy danych: {str(e)}")
                    retry_count += 1
            
            except Exception as e:
                print(f"BŁĄD podczas zapisywania do bazy danych: {str(e)}")
                import traceback
                traceback.print_exc()
                
                # Próba wycofania transakcji w przypadku błędu
                if conn:
                    try:
                        conn.rollback()
                        print("Transakcja została wycofana")
                    except:
                        print("Nie udało się wycofać transakcji")
                
                # Spróbuj ponownie
                retry_count += 1
                print(f"Ponawiam próbę zapisu ({retry_count}/{max_retries})...")
                time.sleep(1)  # Odczekaj chwilę przed ponowną próbą
            
            finally:
                # Upewnij się, że połączenie zostanie zamknięte
                if conn:
                    try:
                        conn.close()
                        print("Połączenie z bazą danych zostało zamknięte")
                    except:
                        print("Nie udało się zamknąć połączenia z bazą danych")
        
        # Jeśli wszystkie próby zakończyły się niepowodzeniem
        if retry_count >= max_retries:
            print(f"⚠️ Wszystkie {max_retries} prób zapisu do bazy danych zakończyły się niepowodzeniem.")
            # Ostatnia próba - zapisz do pliku awaryjnego
            self.save_to_emergency_file(bundle_data)
        
        return False

    def verify_database_consistency(self, bundle_data):
        """Sprawdza czy dane w bazie danych są zgodne z danymi JSON"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Sprawdź czy liczba bundli się zgadza
            cursor.execute("SELECT COUNT(*) FROM bundles WHERE is_active = 1")
            db_bundle_count = cursor.fetchone()[0]
            if db_bundle_count != len(bundle_data):
                print(f"Niezgodność: W bazie danych jest {db_bundle_count} bundli, a w danych JSON {len(bundle_data)}")
                return False
            
            # Sprawdź zawartość każdego bundla
            for bundle in bundle_data:
                url = bundle.get('url', '')
                contents = bundle.get('contents', [])
                
                # Znajdź bundle w bazie danych
                cursor.execute("SELECT id FROM bundles WHERE url = ? AND is_active = 1", (url,))
                result = cursor.fetchone()
                if not result:
                    print(f"Niezgodność: Bundle z URL {url} nie został znaleziony w bazie danych")
                    return False
                
                bundle_id = result[0]
                
                # Sprawdź liczbę elementów w bundlu
                cursor.execute("SELECT COUNT(*) FROM bundle_contents WHERE bundle_id = ?", (bundle_id,))
                db_content_count = cursor.fetchone()[0]
                if db_content_count != len(contents):
                    print(f"Niezgodność: Bundle {url} ma {db_content_count} elementów w bazie danych, a {len(contents)} w danych JSON")
                    return False
            
            conn.close()
            return True
        except Exception as e:
            print(f"Błąd podczas weryfikacji bazy danych: {str(e)}")
            return False

    def save_to_emergency_file(self, bundle_data):
        """Zapisuje dane do pliku awaryjnego w przypadku problemów z bazą danych"""
        try:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'emergency_bundle_data_{timestamp}.json'
            
            emergency_data = {
                'scrape_date': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'error_note': 'Ten plik został utworzony awaryjnie z powodu problemów z zapisem do bazy danych',
                'bundles': bundle_data
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(emergency_data, f, ensure_ascii=False, indent=4)
            
            print(f"⚠️ Dane zostały awaryjnie zapisane do pliku: {filename}")
            print("Możesz wykorzystać te dane do ręcznego załadowania do bazy danych później.")
            return filename
        except Exception as e:
            print(f"Błąd podczas zapisywania pliku awaryjnego: {str(e)}")
            return None

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
            expiration_dates = {}  # Słownik do przechowywania dat wygaśnięcia
            
            # Najpierw zbierz wszystkie linki i daty wygaśnięcia na stronie głównej
            for tile in bundle_tiles:
                try:
                    link = tile.find_element(By.TAG_NAME, "a")
                    url = link.get_attribute('href')
                    
                    # Pobierz datę wygaśnięcia
                    try:
                        # Próbuj różnych selektorów do znalezienia licznika
                        countdown_selectors = [
                            ".js-countdown-timer", 
                            ".timer-wrapper",
                            ".js-countdown-timer.is-hidden",
                            "[aria-label*='days']"
                        ]
                        
                        countdown_element = None
                        for selector in countdown_selectors:
                            try:
                                elements = tile.find_elements(By.CSS_SELECTOR, selector)
                                if elements:
                                    countdown_element = elements[0]
                                    break
                            except:
                                continue
                        
                        if countdown_element:
                            # Podejście 1: Pobieranie z elementów span
                            try:
                                days_element = countdown_element.find_element(By.CSS_SELECTOR, ".js-days")
                                hours_element = countdown_element.find_element(By.CSS_SELECTOR, ".js-hours")
                                minutes_element = countdown_element.find_element(By.CSS_SELECTOR, ".js-minutes")
                                
                                days_text = days_element.text
                                hours_text = hours_element.text
                                minutes_text = minutes_element.text
                                
                                # Wyczyść tekst i wyodrębnij liczby
                                days = int(days_text.replace("Days Left", "").replace("Day Left", "").strip()) if "Day" in days_text else 0
                                hours = int(hours_text.strip())
                                minutes = int(minutes_text.strip())
                            except Exception as e:
                                print(f"Nie udało się pobrać czasu metodą spans: {e}")
                                
                                # Podejście 2: Pobieranie z atrybutu aria-label
                                try:
                                    aria_label = countdown_element.get_attribute("aria-label")
                                    if aria_label:
                                        print(f"Znaleziono aria-label: {aria_label}")
                                        # Przetwarzanie tekstu aria-label
                                        # Format: "X days, Y hours, Z minutes, and W seconds left"
                                        parts = aria_label.split(",")
                                        
                                        days = 0
                                        hours = 0
                                        minutes = 0
                                        
                                        for part in parts:
                                            part = part.strip().lower()
                                            if "day" in part:
                                                days = int(part.split()[0])
                                            elif "hour" in part:
                                                hours = int(part.split()[0])
                                            elif "minute" in part and "and" not in part:
                                                minutes = int(part.split()[0])
                                except Exception as ex:
                                    print(f"Nie udało się pobrać czasu z aria-label: {ex}")
                                    # Ustawmy domyślne wartości
                                    days = 14  # Typowy czas trwania bundla
                                    hours = 0
                                    minutes = 0
                            
                            # Oblicz datę wygaśnięcia na podstawie obecnej daty
                            from datetime import datetime, timedelta
                            expiration_date = datetime.now() + timedelta(days=days, hours=hours, minutes=minutes)
                            expiration_date_str = expiration_date.strftime('%Y-%m-%d %H:%M:%S')
                            
                            expiration_dates[url] = expiration_date_str
                            print(f"Bundle {url} wygasa: {expiration_date_str} (za {days}d {hours}h {minutes}m)")
                        else:
                            print(f"Nie znaleziono elementu odliczania dla {url}")
                            expiration_dates[url] = None
                    except Exception as e:
                        print(f"Nie udało się pobrać daty wygaśnięcia dla {url}: {e}")
                        expiration_dates[url] = None
                    
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
                        'url': url,
                        'expiration_date': expiration_dates.get(url)
                    }
                    
                    bundle_data.append(bundle_info)
                    print(f"Dodano bundle: {title}")
                    if expiration_dates.get(url):
                        print(f"Data wygaśnięcia: {expiration_dates.get(url)}")
                    
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
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Pobierz wszystkie aktywne bundle
            cursor.execute("""
            SELECT id, title, price_range, bundle_type, date_added, expiration_date 
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
            for bundle_id, title, price_range, bundle_type, date_added, expiration_date in bundles:
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
                if expiration_date:
                    print(f"Wygasa: {expiration_date}")
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
        if bundle.get('expiration_date'):
            print(f"Wygasa: {bundle['expiration_date']}")
        print("Zawartość:")
        for item in bundle['contents']:
            print(f"- {item}")
        print("-" * 50)
    
    print(f"\nDane zostały zapisane do bazy SQLite: {scraper.db_path}")
    print(f"Dane zostały zapisane do pliku JSON: {json_filename}")

if __name__ == "__main__":
    main()