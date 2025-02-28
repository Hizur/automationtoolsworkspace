import os
import time
import csv
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from selenium.webdriver.chrome.service import Service

# --- Configuration ---
CHROMEDRIVER_PATH = ""
KEYS_PAGE_URL = "https://www.humblebundle.com/home/keys"
OUTPUT_CSV = "humble_keys.csv"
HEADLESS = False
MAX_KEYS = 2000

# --- Latency/Wait Time Configuration (Randomization) ---
MIN_WAIT_TIME = 0.1
MAX_WAIT_TIME = 0.5

# --- XPath Selectors ---
KEY_CONTAINER_XPATH = "//td[contains(@class, 'js-redeemer-cell') and contains(@class, 'redeemer-cell')]"
TITLE_XPATH = "./preceding-sibling::td[@class='game-name']/h4"
LOAD_MORE_ELEMENT_XPATH = ".js-pagination-holder.pagination-holder > div.pagination > div.jump-to-page:not(.current) > i.hb.hb-chevron-right"
LOAD_MORE_ELEMENT_XPATH_TYPE = By.CSS_SELECTOR

# --- Cookie Handling (skopiuj ciasteczko _simpleauth_sess i ustaw je komendą $envHUMBLE_SESSION_COOKIE = )---
cookie_value = os.environ.get('HUMBLE_SESSION_COOKIE')
if not cookie_value:
    print("ERROR: HUMBLE_SESSION_COOKIE environment variable not set.")
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

def extract_data(container, page_number, item_number): # Added item_number
    """Extracts data from a single key container."""
    data = {}

    # --- Extract Title ---
    try:
        title_element = WebDriverWait(container, 10).until(
            EC.presence_of_element_located((By.XPATH, TITLE_XPATH))
        )
        data['title'] = title_element.text.strip().replace('"', '')
    except (TimeoutException, NoSuchElementException):
        data['title'] = "N/A"
        print(f"Warning (extract_data): Could not find title element")

    # --- Extract Key ---
    try:
        key_element = WebDriverWait(container, 10).until(
            EC.presence_of_element_located((By.XPATH, ".//div[contains(@class, 'keyfield-value')]"))
        )
        data['key'] = key_element.text.strip().replace('"', '')
    except (TimeoutException, NoSuchElementException):
        data['key'] = "N/A"
        print(f"Warning (extract_data): Could not find key element")

    # --- Platform Inference ---
    platform_keywords = {
        "steam": "Steam",
        "gog": "GOG",
        "origin": "Origin",
        "uplay": "Uplay",
        "epic": "Epic Games Store",
        "microsoft": "Microsoft Store",
    }
    container_html = container.get_attribute('outerHTML')
    found_platform = False
    for keyword, platform_name in platform_keywords.items():
        if keyword in container_html.lower():
            data['platform'] = platform_name
            found_platform = True
            break
    if not found_platform:
        data['platform'] = "Unknown"

    data['page_number'] = page_number
    data['item_number'] = item_number  # Add item number

    return data

def main():
    try:
        # --- Set the Cookie and Initial Load ---
        driver.get("https://www.humblebundle.com/")
        driver.add_cookie({'name': '_simpleauth_sess', 'value': cookie_value, 'domain': '.humblebundle.com'})
        wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
        time.sleep(wait_time)
        print(f"Waiting for {wait_time:.2f} seconds after setting cookie...")

        driver.get(KEYS_PAGE_URL)
        wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
        time.sleep(wait_time)
        print(f"Waiting for {wait_time:.2f} seconds after navigating to keys page...")

        # Wait for initial page load
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.XPATH, KEY_CONTAINER_XPATH))
            )
        except TimeoutException:
            print(f"ERROR: TimeoutException - Initial page load failed.")
            return

        all_data = []
        page_number = 1
        extracted_key_count = 0

        while extracted_key_count < MAX_KEYS:
            # --- Find Key Containers on the *CURRENT* Page ---
            key_containers = driver.find_elements(By.XPATH, KEY_CONTAINER_XPATH)
            num_containers = len(key_containers)
            print(f"Found {num_containers} key containers on page {page_number}.")

            # --- Extract Data from Current Page ---
            item_number = 1  # Initialize item number for each page
            for container in key_containers:
                try:
                    key_data = extract_data(container, page_number, item_number)  # Pass page_number and item_number
                    if key_data:
                        all_data.append(key_data)
                    item_number += 1  # Increment item number *after* processing each key
                except Exception as e:
                    print(f"Error during data extraction (page {page_number}): {e}. Skipping this key.")
                wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
                time.sleep(wait_time)
                print(f"Waiting for {wait_time:.2f} seconds after key extraction (page {page_number})...")

            extracted_key_count = len(all_data)

            # --- Click "Next Page" Button ---
            try:
                load_more_element = WebDriverWait(driver, 5).until(
                    EC.element_to_be_clickable((LOAD_MORE_ELEMENT_XPATH_TYPE, LOAD_MORE_ELEMENT_XPATH))
                )
                load_more_element.click()
                page_number += 1  # Increment page number *after* clicking
                # Wait for the next page to start loading (key containers)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, KEY_CONTAINER_XPATH))
                )
                wait_time = random.uniform(MIN_WAIT_TIME, MAX_WAIT_TIME)
                time.sleep(wait_time)
                print(f"Waiting for {wait_time:.2f} seconds after clicking and waiting for new containers...")

            except TimeoutException:
                print("No more 'Next Page' button found. Assuming end of list.")
                break
            except NoSuchElementException:
                print(f"Could not find 'Next Page' button. Selector: {LOAD_MORE_ELEMENT_XPATH}")
                break
            except WebDriverException as e:
                print(f"WebDriverError during pagination: {e}")
                break
            except Exception as e:
                print(f"Unexpected error during pagination: {e}")
                break

            if extracted_key_count >= MAX_KEYS:
                print(f"Maximum key limit ({MAX_KEYS}) reached.")
                break

        print("Pagination completed or maximum keys reached.")

        # --- Write to CSV ---
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'key', 'platform', 'page_number', 'item_number']  # Added 'item_number'
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar='\\')
            writer.writeheader()
            writer.writerows(all_data)

        print(f"Data saved to {OUTPUT_CSV}")

    except WebDriverException as e:
         print(f"WebDriverError: {e}. Please ensure ChromeDriver is correctly installed and compatible with your Chrome/Brave version.")
    except Exception as e:
        print(f"An unexpected error occurred in main(): {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()