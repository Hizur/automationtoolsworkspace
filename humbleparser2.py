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
CHROMEDRIVER_PATH = ""
KEYS_PAGE_URL = "https://www.humblebundle.com/home/keys"
OUTPUT_CSV = "humble_keys.csv"
HEADLESS = False
MAX_KEYS = 2000

# --- XPath Selectors ---
KEY_CONTAINER_XPATH = "//td[contains(@class, 'js-redeemer-cell') and contains(@class, 'redeemer-cell')]"
TITLE_XPATH = "./preceding-sibling::td[@class='game-name']/h4"
LOAD_MORE_ELEMENT_XPATH = "//button[contains(text(),'Load More')] | //a[contains(., 'Show more keys')]"

# --- Cookie Handling ---
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

def extract_data(container):
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
        print("Warning: Could not find title element")

    # --- Extract Key ---
    try:
        key_element = WebDriverWait(container, 10).until(
            EC.presence_of_element_located((By.XPATH, ".//div[contains(@class, 'keyfield-value')]"))
        )
        data['key'] = key_element.text.strip().replace('"', '')
    except (TimeoutException, NoSuchElementException):
        data['key'] = "N/A"
        print("Warning: Could not find key element")

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

    return data

def main():
    try:
        # --- Set the Cookie ---
        driver.get("https://www.humblebundle.com/")
        driver.add_cookie({'name': '_simpleauth_sess', 'value': cookie_value, 'domain': '.humblebundle.com'})
        driver.get(KEYS_PAGE_URL)

        # Wait for at least one key container to be present
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, KEY_CONTAINER_XPATH))
        )

        # --- Pagination ---
        extracted_key_count = 0
        while extracted_key_count < MAX_KEYS:
            try:
                WebDriverWait(driver, 10).until(  #This wait is not needed anymore
                    EC.presence_of_element_located((By.XPATH, KEY_CONTAINER_XPATH))
                )
                key_containers = driver.find_elements(By.XPATH, KEY_CONTAINER_XPATH)
                num_containers = len(key_containers)
                print(f"Found {num_containers} key containers on the page.")

                if num_containers <= extracted_key_count:
                    print("No new key containers found.  Assuming end of list.")
                    break
                extracted_key_count = num_containers

                # "Load More" (handle button OR link)
                try:
                    load_more_element = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, LOAD_MORE_ELEMENT_XPATH))
                    )
                    load_more_element.click()
                    time.sleep(2)
                except TimeoutException:
                    try:
                        load_more_element = WebDriverWait(driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, "//a[contains(., 'Show more keys')]"))
                        )
                    except TimeoutException:
                        print("No 'Load More' button or link found. Assuming end of list.")
                        break

            except (TimeoutException, NoSuchElementException):
                print("Could not find key text elements or 'Load More' element.")
                break
            except Exception as e:
                print(f"Error during pagination: {e}")
                break

        # --- Extract and Write Data ---
        key_containers = driver.find_elements(By.XPATH, KEY_CONTAINER_XPATH)
        all_data = []
        for container in key_containers:
            key_data = extract_data(container)
            all_data.append(key_data)

        # --- Write to CSV ---
        with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['title', 'key', 'platform']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, quoting=csv.QUOTE_ALL, escapechar='\\')
            writer.writeheader()
            writer.writerows(all_data)

        print(f"Data saved to {OUTPUT_CSV}")

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        driver.quit()

if __name__ == "__main__":
    main()