cmd/PowerShell/?linux?, ustawiamy środowisko z ciasteczkiem autoryzacji naszego konta komendą: $envHUMBLE_SESSION_COOKIE = '_simpleauth_sess'
Można zrobić to chyba także w pliku .env po ewentualnych drobnych modyfikacjach, ale to raczej niezbyt bezpieczne.


ENG:

# Humble Bundle Key Extractor

This Python script extracts data from your Humble Bundle keys page and saves it to a CSV file. It is designed to be robust, handle pagination, and avoid accidental key redemption.

## Features

*   **Authentication:** Uses your Humble Bundle session cookie (`_simpleauth_sess`) for authentication, avoiding the need to store your username and password.
*   **Data Extraction:** Extracts the following information for each key:
    *   Game Title
    *   Key
    *   Platform (inferred, e.g., Steam, GOG, Origin)
    *   Page Number (on the Humble Bundle keys page)
    *   Item Number (position of the key on its page)
*   **Pagination:**  Handles multiple pages of keys by automatically clicking the "Next Page" button.
*   **CSV Output:** Saves the extracted data to a properly formatted CSV file (`humble_keys.csv` by default), with columns for title, key, platform, page number, and item number.  Uses quoting to handle commas and special characters within titles.
*   **Randomized Wait Times:**  Includes randomized wait times between actions to mimic human behavior and reduce the risk of being detected as a bot.
*   **Error Handling:**  Includes comprehensive error handling and logging to make debugging easier.  Catches `TimeoutException`, `NoSuchElementException`, `WebDriverException`, and `StaleElementReferenceException`.  Provides informative error messages.
*   **Stale Element Handling:**  Includes logic to handle `StaleElementReferenceException` errors, which can occur when the page is dynamically updated.
*   **No Accidental Redemption:** The script is carefully designed *not* to interact with any "Redeem" buttons or links. It *only* extracts data from the key *listing* page.
* **Configurable**: Settings are located at the top of the script.

## Requirements

*   **Python 3.6+:**  This script requires Python 3.6 or later.
*   **Selenium:**  You need to install the Selenium WebDriver:
    ```bash
    pip install selenium
    ```
*   **ChromeDriver:** You need to download the ChromeDriver executable that is compatible with your Chrome/Brave browser version.  You can download it from:
    [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads)

    Place the `chromedriver` executable in a location that is in your system's `PATH` environment variable, *or* specify the full path to the executable in the `CHROMEDRIVER_PATH` variable within the script.

## Usage

1.  **Install Dependencies:**  Make sure you have Python 3.6+ and Selenium installed. Download ChromeDriver.
2.  **Obtain Session Cookie:**
    *   Log in to your Humble Bundle account in your Chrome or Brave browser.
    *   Open the developer tools (usually by pressing F12).
    *   Go to the "Application" tab (Chrome) or "Storage" tab (Firefox).  In Brave, it's under "Application".
    *   Expand "Cookies" in the left sidebar and click on `https://www.humblebundle.com`.
    *   Find the cookie named `_simpleauth_sess` and copy its *entire* value.
3.  **Set Environment Variable:**  Set the `HUMBLE_SESSION_COOKIE` environment variable to the value of your `_simpleauth_sess` cookie.  The *recommended* way to do this is *temporarily* in your terminal/command prompt *before* running the script. This avoids storing the cookie directly in the script.

    *   **Windows (PowerShell):**
        ```powershell
        $env:HUMBLE_SESSION_COOKIE = 'your_cookie_value'
        ```
    *   **Windows (Command Prompt):**
        ```
        set HUMBLE_SESSION_COOKIE=your_cookie_value
        ```
    *    **Linux/macOS (Bash/Zsh):**
        ```bash
        export HUMBLE_SESSION_COOKIE="your_cookie_value"
        ```
     **Important:** Replace `"your_cookie_value"` with your *actual* cookie value. Make sure to use single quotes in powershell to avoid interpretation of special characters inside cookie.
4.  **Configure the Script (Optional):** Open the `humble_keys_final_randomized.py` file in a text editor.  You can adjust the following configuration variables at the top of the script:

    *   `CHROMEDRIVER_PATH`:  Set this to the full path to your `chromedriver` executable *if* it's not in your system's `PATH`.  If `chromedriver` *is* in your `PATH`, you can leave this variable empty.
    *   `KEYS_PAGE_URL`:  This should be the correct URL for your Humble Bundle keys page (usually `https://www.humblebundle.com/home/keys`), but double-check it.
    *   `OUTPUT_CSV`:  The name of the CSV file to which the data will be saved (default: `humble_keys.csv`).
    *   `HEADLESS`:  Set this to `True` to run the script without a visible browser window (recommended for normal use).  Set it to `False` for debugging.
    *   `MAX_KEYS`:  The maximum number of keys to extract (default: 2000).
    *   `MIN_WAIT_TIME` and `MAX_WAIT_TIME`:  These control the randomized wait times (in seconds) between actions.  You can adjust these, but be careful not to make them too short.

5.  **Run the Script:** Open a terminal or command prompt in the directory where you saved the script and run:

    ```bash
    python humble_keys_final_randomized.py
    ```

6.  **Output:** The script will extract the data and save it to the `humble_keys.csv` file (or whatever filename you specified in `OUTPUT_CSV`). You can then open this file in a spreadsheet program like LibreOffice Calc, Microsoft Excel, or Google Sheets.  **Make sure to configure your spreadsheet program to use commas as delimiters when importing the CSV.**

## Important Notes and Warnings:

*   **Terms of Service:**  Always review and respect Humble Bundle's terms of service regarding automated access to your account data.
*   **Website Changes:**  This script relies on the HTML structure of the Humble Bundle keys page.  If Humble Bundle changes the website, the script might break, and you'll likely need to update the XPath and CSS selectors.  The selectors are located at the top of the script for easy updating.
* **Security**: Your `_simpleauth_sess` cookie is sensitive information. Do *not* share it with anyone. Do *not* commit it to version control (e.g., Git).  Using environment variables is a safer way to handle the cookie than hardcoding it into the script.
* **Error Handling**: While this script has error handling, unexpected issues can still occur. If you encounter problems, check the console output for detailed error messages.

## Troubleshooting

*   **Script doesn't run/ChromeDriver error:** Make sure ChromeDriver is installed correctly and its path is configured properly.
*   **No keys extracted:** Double-check that your `_simpleauth_sess` cookie is correct and has not expired.  Make sure you are setting the `HUMBLE_SESSION_COOKIE` environment variable correctly.
*   **Only some keys extracted:**  The script might be encountering an issue with pagination.  Try increasing the wait times (`MIN_WAIT_TIME`, `MAX_WAIT_TIME`).  Check the console output for error messages.
*   **CSV data all in one column:** Your spreadsheet program is not using the correct delimiter (comma).  See the instructions above for your specific spreadsheet program (especially LibreOffice Calc and Excel) to configure the CSV import settings correctly.
*   **`StaleElementReferenceException`:** While the script has handling for this, it's *possible* it might still occur in some cases. If this happens, try slightly increasing the wait times, check for console messages.
* **Website has changed structure:** Check XPATHs.

## How to update XPATHs if Humble Bundle changes

1.  **Open Keys Page and Developer Tools:** Go to your Humble Bundle keys page and open the developer tools (F12).
2.  **Select Key Container:** Right-click on the area where a game *key* is displayed (not the title) and select "Inspect". This should highlight the `<div>` with class `keyfield-value` inside the `<td>` with classes `js-redeemer-cell` and `redeemer-cell`. Keep this in mind.
3.  **Find Parent `<tr>`:** In the developer tools, click on the parent elements of the highlighted `<td>` until you find the `<tr>` (table row) element that contains it.
4.  **Locate Title Element:**  Look at the *same* `<tr>` element.  Is the title element a *sibling* `<td>` within this same row?  If so, what are its classes?  Is it an `<h4>`? Right click on it and select copy -> xpath.
5. **Update the script:** Copy the new XPATH for the title, replace the value for the `TITLE_XPATH` variable.

## Disclaimer

This script is provided as-is, for educational and personal use only.  The author is not responsible for any issues arising from its use.  Use at your own risk, and always respect Humble Bundle's terms of service. The script author has absolute no idea what he's doing and he's a total maniac, rushing at the sun with a hoe.