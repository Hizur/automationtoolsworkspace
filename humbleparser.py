import os
import time
import csv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.chrome.service import Service

# --- Configuration ---
CHROMEDRIVER_PATH = ""  # e.g., "/path/to/chromedriver" (leave empty if in PATH)
KEYS_PAGE_URL = "https://www.humblebundle.com/home/keys"  # VERIFY THIS IS THE CORRECT URL!
OUTPUT_CSV = "humble_keys.csv"
HEADLESS = False  # Set to True to run without a visible browser window
MAX_KEYS = 2000  # Maximum number of keys to extract

# --- XPath Selectors (ADAPT THESE!) ---
# 1. Load More Button (or similar element to trigger loading more keys)
LOAD_MORE_ELEMENT_XPATH = "//button[contains(text(),'Load More')] or //a[contains(., 'Show more keys')]"

# 2. Key Container (The element that contains all info for ONE game key)
KEY_CONTAINER_XPATH = "//td[contains(@class, 'js-redeemer-cell') and contains(@class, 'redeemer-cell')]"

# 3. Data Extraction Rules (TITLE LIKELY NEEDS ADJUSTMENT)
DATA_EXTRACTION_RULES = {
    'title': {'method': By.XPATH, 'selector': './preceding-sibling::td//h4', 'attribute': 'title'},
    'key': {'method': By.XPATH, 'selector': './/div[contains(@class, "keyfield-value")]', 'attribute': None},
    'platform': {'method': By.XPATH, 'selector': './/a[contains(@class, "steam-redeem-button")]', 'attribute': None},
}

# --- Cookie Handling (Environment Variable) ---
cookie_value = os.environ.get('HUMBLE_SESSION_COOKIE')
if not cookie_value:
    print("ERROR: HUMBLE_SESSION_COOKIE environment variable not set.")
    print("Please set it to your _simpleauth_sess cookie value.")
    exit(1)

# --- WebDriver Setup ---
options = webdriver.ChromeOptions()
if HEADLESS:
    options.add_argument("--headless")
if CHROMEDRIVER_PATH:
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
else:
    driver = webdriver.Chrome(options=options)

def extract_data(container, rules):
    """Extracts data from a single key container using explicit waits."""
    data = {}
    for key, rule in rules.items():
        try:
            element = WebDriverWait(container, 10).until(
                EC.presence_of_element_located((rule['method'], rule['selector']))
            )
            if rule['attribute']:
                data[key] = element.get_attribute(rule['attribute'])
            else:
                data[key] = element.text.strip()
        except (TimeoutException, NoSuchElementException):
            data[key] = "N/A"
            print(f"Warning: Could not find element for '{key}'")
    # Infer platform based on Steam button presence
    if 'platform' in data and data['platform'] != "N/A":
        data['platform'] = "Steam"
    elif 'platform' in data:
        data['platform'] = "Unknown"
    return data

def main():
    try:
        # --- Set the Cookie ---
        driver.get("https://www.humblebundle.com/")
        driver.add_cookie({'name': '_simpleauth_sess', 'value': cookie_value, 'domain': '.humblebundle.com'})
        driver.get(KEYS_PAGE_URL)

        # --- Handle Pagination/Infinite Scroll (Robust Approach) ---
        extracted_key_count = 0
        while extracted_key_count < MAX_KEYS:
            try:
                # Wait for at least one key container to be present
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, KEY_CONTAINER_XPATH))
                )

                # Find all key containers *currently* on the page
                key_containers = driver.find_elements(By.XPATH, KEY_CONTAINER_XPATH)
                num_containers = len(key_containers)
                print(f"Found {num_containers} key containers on the page.")

                # If we haven't extracted any new keys, we might be at the end
                if num_containers <= extracted_key_count:
                    print("No new key containers found.  Assuming end of list.")
                    break

                extracted_key_count = num_containers #update count

                # Click the "Load More" element (if it exists)
                load_more_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((By.XPATH, LOAD_MORE_ELEMENT_XPATH))
                )
                load_more_element.click()
                time.sleep(2)  # Wait for new content to load

            except TimeoutException:
                print("No more 'Load More' element found.  Assuming end of list.")
                break
            except NoSuchElementException:
                print("Could not find key containers or 'Load More' element.")
                break
            except Exception as e:
                print(f"Error during pagination: {e}")
                break

        # --- Extract Key Data (After Loading All Keys) ---
        key_containers = driver.find_elements(By.XPATH, KEY_CONTAINER_XPATH)
        all_keys_data = []
        for container in key_containers:
            key_data = extract_data(container, DATA_EXTRACTION_RULES)
            all_keys_data.append(key_data)

        # --- Save Data to CSV ---
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = list(DATA_EXTRACTION_RULES.keys())
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_keys_data)

        print(f"Data saved to {OUTPUT_CSV}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()