README.txt

--------------------------------------------------------------------------------
\
**Script Name:** (whatever, You name it) humble_bundle_scraper.py

**Description:**

This Python script scrapes data about current bundles from the Humble Bundle website (www.humblebundle.com/bundles). It extracts information such as bundle titles, price ranges, the items included in each bundle, and saves this data into both a JSON file and an SQLite database.

**Purpose:**

The script is designed to automatically collect and store information about Humble Bundles for personal use, such as tracking available bundles, their contents, and prices.

**Requirements:**

Before running the script, you need to have the following installed:

1.  **Python 3.x:**  Ensure you have Python 3 or a later version installed on your system.

2.  **Python Libraries:** Install the necessary Python libraries using pip:
    ```
    pip install selenium
    ```

3.  **ChromeDriver:**
    *   This script uses Selenium with Chrome to scrape the website. You need to download ChromeDriver, which is the WebDriver for Chrome.
    *   Download the ChromeDriver executable that is compatible with your version of Chrome browser from: [https://chromedriver.chromium.org/downloads](https://chromedriver.chromium.org/downloads)
    *   Place the `chromedriver` executable in a directory that is in your system's PATH environment variable, or in the same directory as the script.

**Usage:**

1.  **Save the script:** Save the provided Python code as `humble_bundle_scraper.py` in your desired directory.

2.  **Run the script:** Open a terminal or command prompt, navigate to the directory where you saved the script, and execute it using:
    ```
    python humble_bundle_scraper.py
    ```

3.  **Wait for execution:** The script will open a Chrome browser instance (minimized and moved off-screen to run in the background). It will navigate to the Humble Bundle website, scrape the bundle data, and then close the browser. This process may take a few minutes depending on your internet connection and system speed.

**Output:**

After successful execution, the script will generate the following outputs:

1.  **JSON File:** A JSON file named `humble_bundles_YYYYMMDD_HHMMSS.json` (where YYYYMMDD\_HHMMSS is the timestamp of when the script was run) will be created in the same directory as the script. This file contains the scraped bundle data in JSON format, including:
    *   `scrape_date`: Date and time when the data was scraped.
    *   `bundles`: A list of bundle objects, each containing:
        *   `title`: Title of the bundle.
        *   `price_range`: Price range of the bundle.
        *   `contents`: A list of items included in the bundle.
        *   `url`: URL of the bundle page.

2.  **SQLite Database:** An SQLite database file named `humble_bundles.db` will be created (or updated if it already exists) in the same directory as the script. The database contains two tables:
    *   `bundles`: Stores general bundle information:
        *   `id`: Primary key, auto-incrementing integer.
        *   `title`: Bundle title (TEXT).
        *   `price_range`: Bundle price range (TEXT).
        *   `url`: Bundle URL (TEXT, UNIQUE).
        *   `date_added`: Timestamp of when the bundle was added to the database.
        *   `bundle_type`: Type of bundle (e.g., 'Książki', 'Gry', 'Oprogramowanie', 'Inny').
        *   `is_active`: Flag indicating if the bundle is currently active (1 for active, 0 for inactive).
    *   `bundle_contents`: Stores the items within each bundle:
        *   `id`: Primary key, auto-incrementing integer.
        *   `bundle_id`: Foreign key referencing the `bundles` table.
        *   `item_name`: Name of the item in the bundle (TEXT).
        *   `item_order`: Order of the item in the bundle (INTEGER).

3.  **Console Output:** During execution, the script will print information to the console, including:
    *   Status messages about the scraping process (starting, loading pages, finding bundles, saving data).
    *   Summary of found bundles (titles, prices, item counts).
    *   Statistics of active bundles in the database categorized by type.
    *   Any errors encountered during the process.

**Database Summary:**

After scraping and saving to the database, the script will also display a summary of the active bundles currently stored in the `humble_bundles.db` database in a readable format on the console. This summary includes the total number of active bundles, their distribution by type, and details for each bundle (title, price, date added, item count, and sample items).

**Important Notes:**

*   **Website Changes:** The Humble Bundle website structure may change in the future. If the script stops working, it might be due to changes in the website's HTML structure, requiring updates to the CSS selectors or XPath expressions used in the script.
*   **ChromeDriver Compatibility:** Ensure that the ChromeDriver version is compatible with your Chrome browser version. Incompatibility can cause the script to fail.
*   **Ethical Scraping:** This script is intended for personal use to gather publicly available information. Be mindful of website terms of service and robots.txt. Avoid excessive scraping that could overload the website's servers.
*   **Error Handling:** The script includes basic error handling, but web scraping can be inherently fragile. Review the console output for any error messages if the script does not run as expected.
*   **Database Location:** The SQLite database file `humble_bundles.db` will be created in the same directory where you run the script.

**Disclaimer:**

This script is provided as-is for informational and personal use only. The author didn't read code, author is not responsible for any misuse or consequences arising from the use of this script. Use it at your own risk and always respect website terms of service.

--------------------------------------------------------------------------------