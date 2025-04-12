# @Mod_By_Kamal

import logging
import os
import time
import socket
import requests
import subprocess
import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
import shutil  # For moving files
import zipfile # For unzipping
import stat    # For chmod constants
import traceback
import html
from urllib.parse import urlparse, quote_plus
import re # For regex operations

from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    filters,
    MessageHandler,
)

# For Selenium / stealth: - @Mod_By_Kamal
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.common.exceptions import (
    WebDriverException, NoSuchElementException, ElementClickInterceptedException,
    TimeoutException as SeleniumTimeoutException # Alias to avoid confusion with requests.exceptions.Timeout
)
from selenium_stealth import stealth

# ----------------------------------------------------------------------------------
# LOGGING @Mod_By_Kamal
# ----------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s' # Added logger name
)
logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------------------
# GLOBALS @Mod_By_Kamal
# ----------------------------------------------------------------------------------

# IMPORTANT: Store your token securely (e.g., environment variable)
# BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "YOUR_FALLBACK_TOKEN_HERE")
BOT_TOKEN = "8161093765:AAFDEFktZmojS0W0WrVuCZodkqpZR7HUfCA" # Replace with your actual token securely

ADMIN_ID = 7069274296  # The admin's Telegram user ID - @Mod_By_Kamal
REGISTERED_USERS_FILE = "registered_users.json" # Stored in the script's directory

# Define the local directory for ChromeDriver relative to the script
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CHROMEDRIVER_DIR = os.path.join(SCRIPT_DIR, "chromedriver_files")
CHROMEDRIVER_PATH = os.path.join(CHROMEDRIVER_DIR, "chromedriver")

# --- ChromeDriver URL ---
# Using version 131.0.6778.108 as requested previously, which has linux-arm64.
# Official linux-arm64 builds for 114.0.5735.90 are not available from Google.
# Ensure your installed Chrome/Chromium browser is compatible with this ChromeDriver version.
CHROMEDRIVER_VERSION = "131.0.6778.108"
CHROMEDRIVER_PLATFORM = "linux-arm64"
CHROMEDRIVER_ZIP_FILENAME = f"chromedriver-{CHROMEDRIVER_PLATFORM}.zip"
CHROMEDRIVER_URL = (
    f"https://storage.googleapis.com/chrome-for-testing-public/"
    f"{CHROMEDRIVER_VERSION}/{CHROMEDRIVER_PLATFORM}/{CHROMEDRIVER_ZIP_FILENAME}"
)
# --- End ChromeDriver URL ---


PAYMENT_GATEWAYS = [
    "paypal", "stripe", "braintree", "square", "magento", "avs", "convergepay",
    "paysimple", "oceanpayments", "eprocessing", "hipay", "worldpay", "cybersource",
    "payjunction", "authorize.net", "2checkout", "adyen", "checkout.com", "payflow",
    "payeezy", "usaepay", "creo", "squareup", "authnet", "ebizcharge", "cpay",
    "moneris", "recurly", "cardknox", "chargify", "paytrace", "hostedpayments",
    "securepay", "eway", "blackbaud", "lawpay", "clover", "cardconnect", "bluepay",
    "fluidpay", "rocketgateway", "rocketgate", "shopify", "woocommerce",
    "bigcommerce", "opencart", "prestashop", "razorpay"
]
FRONTEND_FRAMEWORKS = ["react", "angular", "vue", "svelte"]
BACKEND_FRAMEWORKS = [
    "wordpress", "laravel", "django", "node.js", "express", "ruby on rails",
    "flask", "php", "asp.net", "spring"
]
DESIGN_LIBRARIES = ["bootstrap", "tailwind", "bulma", "foundation", "materialize"]

# ----------------------------------------------------------------------------------
# CHROMEDRIVER SETUP (ARM64, Local Directory) => @Mod_By_Kamal
# ----------------------------------------------------------------------------------

def setup_chrome_driver():
    """
    Downloads and sets up ChromeDriver for linux-arm64 in a local directory.
    Uses the globally defined CHROMEDRIVER_URL.
    Checks if wget and unzip are available.
    """
    # Check if chromedriver executable already exists and is executable
    if os.path.exists(CHROMEDRIVER_PATH) and os.access(CHROMEDRIVER_PATH, os.X_OK):
        # Optional: Add version check here if needed in the future
        logger.info(f"ChromeDriver already exists and is executable at: {CHROMEDRIVER_PATH}")
        return True

    # Check for required tools (wget, unzip)
    if not shutil.which("wget"):
        logger.error("`wget` command not found. Please install it. ChromeDriver setup cannot proceed.")
        return False
    if not shutil.which("unzip"):
        logger.error("`unzip` command not found. Please install it. ChromeDriver setup cannot proceed.")
        return False

    logger.info(f"Setting up ChromeDriver version {CHROMEDRIVER_VERSION} for {CHROMEDRIVER_PLATFORM} in {CHROMEDRIVER_DIR}...")

    # Ensure the target directory exists
    os.makedirs(CHROMEDRIVER_DIR, exist_ok=True)

    zip_filename = CHROMEDRIVER_ZIP_FILENAME # Use global definition
    zip_filepath = os.path.join(CHROMEDRIVER_DIR, zip_filename)
    unzip_dir = os.path.join(CHROMEDRIVER_DIR, "unzipped") # Temp extraction folder

    # Clean up previous attempts if necessary
    if os.path.exists(zip_filepath):
        logger.warning(f"Removing existing zip file: {zip_filepath}")
        os.remove(zip_filepath)
    if os.path.exists(unzip_dir):
        logger.warning(f"Removing existing unzip directory: {unzip_dir}")
        shutil.rmtree(unzip_dir)
    if os.path.exists(CHROMEDRIVER_PATH):
         logger.warning(f"Removing existing (likely outdated/non-executable) driver: {CHROMEDRIVER_PATH}")
         os.remove(CHROMEDRIVER_PATH)


    try:
        # Download
        logger.info(f"Downloading ChromeDriver from {CHROMEDRIVER_URL}...")
        # Use --quiet for less verbose output, add timeout
        # Consider adding --tries=3 for basic retry
        process = subprocess.run(
            ['wget', '--timeout=60', '--tries=3', CHROMEDRIVER_URL, '-O', zip_filepath],
            check=True, cwd=CHROMEDRIVER_DIR, capture_output=True, text=True
        )
        logger.info("Download complete.")

        # Unzip
        logger.info(f"Unzipping {zip_filename}...")
        os.makedirs(unzip_dir, exist_ok=True)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
             zip_ref.extractall(unzip_dir)

        # Find the chromedriver executable within the extracted folder
        # The zip file from CfT usually has a top-level directory like 'chromedriver-linux-arm64'
        extracted_chromedriver_path = None
        possible_executable_path = os.path.join(unzip_dir, f"chromedriver-{CHROMEDRIVER_PLATFORM}", "chromedriver")

        if os.path.exists(possible_executable_path):
             extracted_chromedriver_path = possible_executable_path
        else:
             # Fallback search if structure is different
             logger.warning(f"Expected path not found ({possible_executable_path}), searching extracted files...")
             for root, dirs, files in os.walk(unzip_dir):
                 if "chromedriver" in files:
                     extracted_chromedriver_path = os.path.join(root, "chromedriver")
                     logger.info(f"Found chromedriver executable at: {extracted_chromedriver_path}")
                     break

        if not extracted_chromedriver_path:
             raise FileNotFoundError(f"Could not find 'chromedriver' executable within the extracted files in {unzip_dir}.")

        # Move the executable to the final CHROMEDRIVER_PATH
        logger.info(f"Moving chromedriver to {CHROMEDRIVER_PATH}")
        shutil.move(extracted_chromedriver_path, CHROMEDRIVER_PATH)

        # Set executable permissions using Python's os.chmod
        logger.info(f"Setting executable permission for {CHROMEDRIVER_PATH}")
        current_permissions = os.stat(CHROMEDRIVER_PATH).st_mode
        # Add execute for user, group, others (like chmod 755)
        os.chmod(CHROMEDRIVER_PATH, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        # Clean up zip file and temp unzip directory
        logger.info("Cleaning up downloaded zip file and temp directory...")
        os.remove(zip_filepath)
        shutil.rmtree(unzip_dir)

        logger.info(f"ChromeDriver version {CHROMEDRIVER_VERSION} setup completed successfully.")
        return True

    except FileNotFoundError as fnf_error:
        logger.error(f"Error during ChromeDriver setup: {fnf_error}")
        return False
    except subprocess.CalledProcessError as proc_error:
        logger.error(f"Error during ChromeDriver download (wget failed): {proc_error}")
        logger.error(f"wget stdout: {proc_error.stdout}")
        logger.error(f"wget stderr: {proc_error.stderr}")
        # Check common wget errors (404 Not Found, network issues)
        if "404 Not Found" in proc_error.stderr:
             logger.error(f"Download URL returned 404 Not Found: {CHROMEDRIVER_URL}")
             logger.error("Please verify the CHROMEDRIVER_VERSION and URL are correct for linux-arm64.")
        return False
    except zipfile.BadZipFile:
         logger.error(f"Error: Downloaded file '{zip_filepath}' is not a valid zip file or is corrupted.")
         return False
    except Exception as e:
        logger.error(f"Unexpected error setting up ChromeDriver: {e}", exc_info=True)
        # Clean up potentially partially downloaded/extracted files
        if os.path.exists(zip_filepath): os.remove(zip_filepath)
        if os.path.exists(unzip_dir): shutil.rmtree(unzip_dir)
        return False

# (The rest of the script remains the same as the previous version)
# ... (JSON Utils, create_local_driver, click_google_consent_if_needed, google_search, tech stack, site details, async wrappers, bot commands, error handler, main, entry point) ...


# --- MAKE SURE THE FOLLOWING SECTIONS ARE STILL PRESENT AND UNCHANGED ---

# ----------------------------------------------------------------------------------
# JSON UTILS => @Mod_By_Kamal
# ----------------------------------------------------------------------------------
def load_registered_users():
    # ... (implementation from previous version) ...
    if not os.path.exists(REGISTERED_USERS_FILE):
        return []
    try:
        with open(REGISTERED_USERS_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, list):
                 # Ensure all elements are integers
                 return [int(uid) for uid in data if isinstance(uid, (int, str)) and str(uid).isdigit()]
            else:
                logger.warning(f"Corrupted or invalid format in {REGISTERED_USERS_FILE}. Expected a list.")
                return []
    except json.JSONDecodeError:
        logger.error(f"Error decoding JSON from {REGISTERED_USERS_FILE}. Returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Error loading registered users from {REGISTERED_USERS_FILE}: {e}")
        return []

def save_registered_users(user_ids):
    # ... (implementation from previous version) ...
    valid_user_ids = [int(uid) for uid in user_ids if isinstance(uid, (int, str)) and str(uid).isdigit()]
    try:
        with open(REGISTERED_USERS_FILE, "w") as f:
            json.dump(valid_user_ids, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving registered users to {REGISTERED_USERS_FILE}: {e}")

def is_user_registered(user_id):
    # ... (implementation from previous version) ...
    registered = load_registered_users()
    return int(user_id) in registered

def register_user(user_id):
    # ... (implementation from previous version) ...
    registered = load_registered_users()
    int_user_id = int(user_id)
    if int_user_id not in registered:
        registered.append(int_user_id)
        save_registered_users(registered)


# ----------------------------------------------------------------------------------
# CREATE A NEW DRIVER FOR EACH PAGE => @Mod_By_Kamal
# ----------------------------------------------------------------------------------
def create_local_driver():
    # ... (implementation from previous version - crucial part is using CHROMEDRIVER_PATH and NO hardcoded binary_location unless needed) ...
    logger.debug("Attempting to create local WebDriver.")
    if not setup_chrome_driver():
         logger.critical("ChromeDriver setup failed. Cannot create driver.")
         raise RuntimeError("ChromeDriver setup failed. Cannot proceed with web scraping.")

    chrome_options = Options()
    # Common options for headless/server environments
    chrome_options.add_argument("--headless=new") # Use the new headless mode
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--window-size=1920,1080")

    # Language settings
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en-US,en'})

    # Stealth-related options
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # --- Chrome Binary Location ---
    # REMOVED: chrome_options.binary_location = "/usr/bin/google-chrome"
    # Let Selenium try to find Chrome automatically.
    # If Chrome/Chromium ARM64 is installed in a non-standard path,
    # uncomment and set the line below MANUALLY by the user:
    # chrome_options.binary_location = "/path/to/your/chrome-arm64/chrome"
    # Example: chrome_options.binary_location = os.path.expanduser("~/chrome-linux/chrome")
    # --- ---

    service = ChromeService(executable_path=CHROMEDRIVER_PATH)
    logger.debug(f"Initializing Chrome driver with service: {CHROMEDRIVER_PATH}")

    local_driver = None
    try:
        local_driver = webdriver.Chrome(service=service, options=chrome_options)
        logger.debug("WebDriver initialized.")
    except WebDriverException as e:
        logger.critical(f"Failed to start Chrome WebDriver: {e}")
        logger.critical("Ensure Google Chrome/Chromium (ARM64, compatible with ChromeDriver {CHROMEDRIVER_VERSION}) is installed.")
        if "cannot find chrome binary" in str(e).lower():
             logger.critical("Chrome binary not found in PATH. You may need to set 'chrome_options.binary_location' manually in the script.")
        else:
             logger.critical(f"Using ChromeDriver from: {CHROMEDRIVER_PATH}")
        raise # Re-raise the exception to stop execution

    # Apply stealth settings
    try:
        logger.debug("Applying stealth settings...")
        stealth(
            local_driver,
            user_agent=( # Use a plausible, relatively modern User-Agent
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                f"Chrome/{CHROMEDRIVER_VERSION.split('.')[0]}.0.0.0 Safari/537.36" # Match major Chrome version
            ),
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32", # Often used by stealth to mask OS
            webgl_vendor="Intel Inc.", # Generic values
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
        logger.debug("Stealth settings applied.")
    except Exception as e:
        logger.warning(f"Could not apply all stealth settings: {e}")

    # Set page load timeout
    page_load_timeout = 45 # Increased timeout
    local_driver.set_page_load_timeout(page_load_timeout)
    logger.debug(f"Page load timeout set to {page_load_timeout} seconds.")
    return local_driver


# ----------------------------------------------------------------------------------
# CLICK GOOGLE CONSENT (No Changes Needed)
# ----------------------------------------------------------------------------------
def click_google_consent_if_needed(driver, wait_seconds=3):
    # ... (implementation from previous version) ...
    time.sleep(wait_seconds)
    possible_selectors = [
        (By.CSS_SELECTOR, "button#L2AGLb"),
        (By.CSS_SELECTOR, "button#W0wltc"),
        (By.XPATH, "//button[.//div[contains(., 'Accept all')]]"), # Using . instead of text() for flexibility
        (By.XPATH, "//button[.//div[contains(., 'I agree')]]"),
        (By.XPATH, "//button[contains(., 'Reject all')]"), # Sometimes need to reject first
        (By.CSS_SELECTOR, "div[role='dialog'] button:not([jsaction*='close'])"), # Try any button in dialog not being close
        (By.CSS_SELECTOR, "form[action*='consent'] button[type='submit']"),
    ]
    clicked = False
    for by_type, sel in possible_selectors:
        if clicked: break # Stop if already clicked
        try:
            logger.debug(f"Trying to find consent button with: {by_type} / {sel}")
            btn = driver.find_element(by_type, sel)
            # Check if button is visible and interactable (basic check)
            if btn.is_displayed() and btn.is_enabled():
                logger.info(f"Attempting to click Google consent button: {sel}")
                try:
                    btn.click()
                    clicked = True
                except ElementClickInterceptedException:
                    logger.warning(f"Direct click intercepted for {sel}, trying JavaScript click.")
                    try:
                        driver.execute_script("arguments[0].click();", btn)
                        clicked = True
                    except Exception as js_e:
                        logger.warning(f"JavaScript click also failed for {sel}: {js_e}")

                if clicked:
                    logger.info(f"Clicked Google consent button using: {sel}")
                    time.sleep(2.5) # Wait for page reaction
                    return # Exit function after successful click
            else:
                 logger.debug(f"Consent button found but not interactable: {sel}")

        except NoSuchElementException:
            logger.debug(f"Consent button not found with: {sel}")
            pass # Try the next selector
        except ElementClickInterceptedException as e_int:
            # This case might be handled by the inner try-except, but log if it bubbles up
             logger.warning(f"Click intercepted for {sel} (outer handler): {e_int}")
        except Exception as e_general:
            logger.error(f"Unexpected error finding/clicking consent button ({sel}): {e_general}")
            pass

    if not clicked:
        logger.info("Could not find or click any known Google consent button.")


# ----------------------------------------------------------------------------------
# GOOGLE SEARCH (No Changes Needed)
# ----------------------------------------------------------------------------------
async def google_search(query: str, limit: int = 10, offset: int = 0):
    # ... (implementation from previous version) ...
    all_links = []
    seen = set()
    pages_to_fetch = (limit + 99) // 100
    max_google_pages = 10
    pages_needed = min(pages_to_fetch, max_google_pages)

    logger.info(f"[google_search] Query='{query}', limit={limit}, offset={offset}")
    logger.info(f"Aiming for {limit} results, will fetch up to {pages_needed} Google pages.")

    driver = None
    user_agent_for_requests = None # Store UA used by driver

    for page_index in range(pages_needed):
        if len(all_links) >= limit:
            logger.info("Reached desired result limit. Stopping pagination.")
            break

        start_val = offset + (page_index * 100)
        driver = None # Ensure driver is reset

        try:
            logger.info(f"--- Scraping Google Page {page_index + 1} ---")
            driver = create_local_driver()
            if driver is None:
                logger.error("Failed to create WebDriver instance. Stopping search.")
                break

            # Get the actual user agent being used by the driver for consistency in requests later if needed
            if user_agent_for_requests is None:
                 user_agent_for_requests = driver.execute_script("return navigator.userAgent;")
                 logger.info(f"Using User-Agent: {user_agent_for_requests}")


            encoded_query = quote_plus(query)
            url = (
                f"https://www.google.com/search?q={encoded_query}"
                f"&num=100"
                f"&start={start_val}"
                f"&hl=en&gl=us"
                f"&filter=0" # Attempt to disable filtering
                f"&safe=off" # Attempt to disable safe search
            )
            logger.info(f"Navigating to page {page_index + 1}: {url}")
            driver.get(url)

            click_google_consent_if_needed(driver)

            time.sleep(1) # Short wait for results to potentially render

            # --- Find Result Links ---
            # Primary target: Links directly within the main results block divs (often class 'g')
            # This is more robust than relying on specific nested classes like yuRUbf which change.
            result_elements = driver.find_elements(By.CSS_SELECTOR, "div.g div[data-ved] a[href]:not(:has(img))")

            # Fallback selectors if the primary one yields nothing
            if not result_elements:
                 logger.debug("Primary selector 'div.g div[data-ved] a[href]:not(:has(img))' failed, trying fallbacks...")
                 # Fallback 1: Simpler link within 'g'
                 result_elements = driver.find_elements(By.CSS_SELECTOR, "div.g a[href]:not(:has(img))")
            if not result_elements:
                 # Fallback 2: The older common selector
                 result_elements = driver.find_elements(By.CSS_SELECTOR, "div.yuRUbf > a[href]")
            if not result_elements:
                # Fallback 3: Even more general links that look like results
                 result_elements = driver.find_elements(By.XPATH, "//a[@href and @ping and not(ancestor::div[contains(@style,'display:none')]) and not(ancestor::div[contains(@class,'related')]) and not(ancestor::div[contains(@class,'ads')])]")


            if not result_elements:
                page_title = driver.title.lower()
                page_source_lower = driver.page_source.lower()
                if any(captcha_kw in page_source_lower for captcha_kw in ["recaptcha", "verify you are human", "before you continue"]):
                     logger.warning(f"CAPTCHA or interstitial detected on page {page_index + 1}. Stopping search.")
                     break
                else:
                     logger.info(f"No valid result links found using known selectors on page {page_index + 1}. End of results or Google layout change?")
                     # Optionally take a screenshot for debugging
                     # screenshot_path = os.path.join(SCRIPT_DIR, f"no_results_page_{page_index+1}.png")
                     # driver.save_screenshot(screenshot_path)
                     # logger.info(f"Screenshot saved to {screenshot_path}")
                     break

            page_links = []
            for element in result_elements:
                try:
                     href = element.get_attribute("href")
                     # Basic filtering
                     if href and href.startswith("http") and \
                        "google.com/" not in href and \
                        "google.co." not in href and \
                        "accounts.google" not in href and \
                        "support.google" not in href and \
                        "maps.google" not in href and \
                        not href.startswith("javascript:") and \
                        not href.startswith("/"):
                          # Clean common tracking parameters
                          parsed_link = urlparse(href)
                          cleaned_link = parsed_link._replace(query='', fragment='').geturl()
                          # Remove trailing slash for consistency before adding to set
                          if cleaned_link.endswith('/'):
                               cleaned_link = cleaned_link[:-1]
                          page_links.append(cleaned_link)
                except Exception as link_err:
                     logger.warning(f"Error extracting href from an element: {link_err}")

            logger.info(f"Found {len(page_links)} potential unique links on page {page_index + 1}.")

            count_added_this_page = 0
            for link in page_links:
                if link not in seen:
                    seen.add(link)
                    all_links.append(link)
                    count_added_this_page += 1
                    if len(all_links) >= limit:
                        break

            logger.info(f"Added {count_added_this_page} new unique links. Total unique links: {len(all_links)}.")

            if len(all_links) >= limit:
                logger.info("Reached desired result limit.")
                break

        except SeleniumTimeoutException:
             logger.error(f"Page load timeout occurred on page {page_index + 1} for URL: {url}")
             break # Stop if a page times out
        except WebDriverException as e:
            logger.error(f"WebDriver error occurred on page {page_index + 1}: {e}")
            if "ERR_CONNECTION_REFUSED" in str(e) or "ERR_NAME_NOT_RESOLVED" in str(e):
                 logger.error("Possible network issue or Google blocking.")
            # Check for "target window already closed" or session errors
            if "target window already closed" in str(e).lower() or "session deleted because of page crash" in str(e).lower():
                 logger.error("Browser window closed unexpectedly (crash?). Stopping search.")
                 break
            # Consider breaking on most WebDriver errors
            break
        except Exception as e_general:
             logger.error(f"An unexpected error occurred during scraping page {page_index + 1}: {e_general}", exc_info=True)
             break
        finally:
            if driver:
                try:
                    driver.quit()
                    logger.debug(f"WebDriver instance for page {page_index + 1} quit.")
                except Exception as quit_err:
                    logger.warning(f"Error quitting WebDriver instance: {quit_err}")
            # Dynamic sleep based on results found
            sleep_time = 3.0 + (2.0 * (1 - (count_added_this_page / 100.0))) # Longer sleep if fewer new results
            sleep_time = max(2.0, min(sleep_time, 5.0)) # Clamp between 2 and 5 seconds
            logger.info(f"Sleeping for {sleep_time:.2f}s before next page or exit.")
            await asyncio.sleep(sleep_time) # Use asyncio.sleep in async function

    return all_links[:limit]


# ----------------------------------------------------------------------------------
# DETECT TECH STACK (No Changes Needed)
# ----------------------------------------------------------------------------------
def detect_tech_stack(html_text: str, headers: dict = None):
    # ... (implementation from previous version, potentially enhanced) ...
    txt_lower = html_text.lower()
    headers_lower = {k.lower(): v.lower() for k, v in headers.items()} if headers else {}

    # More specific regex patterns and checks
    tech = {
        "front_end": set(),
        "back_end": set(),
        "design": set(),
        "server": headers_lower.get('server', 'N/A'),
        "cdn": set()
    }

    # Frontend Frameworks
    if re.search(r'\bdata-reactroot\b|\breact(\.min)?\.js\b', txt_lower): tech["front_end"].add("React")
    if re.search(r'\bng-version\b|\bangular(\.min)?\.js\b', txt_lower): tech["front_end"].add("Angular")
    if re.search(r'\bdata-vue-meta\b|<div id="app">', txt_lower): tech["front_end"].add("Vue.js") # Simple Vue markers
    if re.search(r'\bsvelte-\w+\b|<script[^>]+src[^>]+svelte', txt_lower): tech["front_end"].add("Svelte")

    # Backend Frameworks / Platforms
    if 'wp-content' in txt_lower or 'wp-json' in txt_lower or '/wp-includes/' in txt_lower or headers_lower.get('link', '').count('wp-json'): tech["back_end"].add("WordPress")
    if 'laravel_session' in headers_lower.get('set-cookie', '') or 'X-CSRF-TOKEN' in txt_lower: tech["back_end"].add("Laravel")
    if 'django' in txt_lower or headers_lower.get('x-powered-by', '') == 'django': tech["back_end"].add("Django")
    if headers_lower.get('x-powered-by', '') == 'express' or 'node.js' in headers_lower.get('server', ''): tech["back_end"].add("Node.js/Express")
    if '_rails_session' in headers_lower.get('set-cookie', '') or headers_lower.get('x-runtime', ''): tech["back_end"].add("Ruby on Rails")
    if headers_lower.get('x-powered-by', '') == 'flask' or 'flask' in headers_lower.get('server', ''): tech["back_end"].add("Flask")
    if '.php' in txt_lower or 'php' in headers_lower.get('x-powered-by', '') or 'php' in headers_lower.get('server', ''): tech["back_end"].add("PHP")
    if 'asp.net' in headers_lower.get('x-powered-by', '') or 'aspnet' in headers_lower.get('x-aspnet-version', '') or '.aspx' in txt_lower: tech["back_end"].add("ASP.NET")
    if 'jsessionid' in headers_lower.get('set-cookie', '') or headers_lower.get('x-powered-by', '') == 'jsp' or 'spring' in headers_lower.get('x-application-context',''): tech["back_end"].add("Java/Spring") # Common Java markers

    # Design Libraries
    if re.search(r'class="[^"]*\b(container|row|col-|btn-|modal)\b', txt_lower) or 'bootstrap(\.min)?\.css' in txt_lower: tech["design"].add("Bootstrap")
    if re.search(r'class="[^"]*\b(w-|h-|p-|m-|text-|bg-|border-)\w+', txt_lower) or 'tailwind(\.min)?\.css' in txt_lower: tech["design"].add("Tailwind CSS")
    if 'bulma(\.min)?\.css' in txt_lower or 'class="[^"]*\b(hero|title|subtitle|button)\b' in txt_lower: tech["design"].add("Bulma") # Bulma specific classes
    if 'foundation(\.min)?\.css' in txt_lower or 'class="[^"]*\b(grid-container|cell|orbit)\b' in txt_lower: tech["design"].add("Foundation")
    if 'materialize(\.min)?\.css' in txt_lower or 'class="[^"]*\b(material-|waves-|card-panel)\b' in txt_lower: tech["design"].add("Materialize")

    # CDN Detection from Headers
    server = headers_lower.get('server', '')
    if 'cloudflare' in server: tech["cdn"].add("Cloudflare")
    if 'aws' in server or 'cloudfront' in server: tech["cdn"].add("AWS CloudFront")
    if 'google' in server: tech["cdn"].add("Google Cloud CDN") # Generic Google
    if 'akamai' in server: tech["cdn"].add("Akamai")
    if 'fastly' in server: tech["cdn"].add("Fastly")
    # Check specific CDN headers
    if 'cf-ray' in headers_lower: tech["cdn"].add("Cloudflare")
    if 'x-cache' in headers_lower and ('cloudfront' in headers_lower['x-cache'] or 'Hit from cloudfront' in headers_lower['x-cache']): tech["cdn"].add("AWS CloudFront")
    if 'x-fastly' in headers_lower: tech["cdn"].add("Fastly")


    return {
        "front_end": ", ".join(sorted(list(tech["front_end"]))) if tech["front_end"] else "N/A",
        "back_end": ", ".join(sorted(list(tech["back_end"]))) if tech["back_end"] else "N/A",
        "design": ", ".join(sorted(list(tech["design"]))) if tech["design"] else "N/A",
        "server": tech["server"],
        "cdn": ", ".join(sorted(list(tech["cdn"]))) if tech["cdn"] else "N/A",
    }


# ----------------------------------------------------------------------------------
# SITE DETAILS CHECK (No Changes Needed)
# ----------------------------------------------------------------------------------
def check_site_details(url: str):
    # ... (implementation from previous version, enhanced formatting and tech stack) ...
    details = {
        "url": url,
        "dns": "N/A",
        "ssl": "N/A",
        "status_code": None,
        "cloudflare": "Unknown", # Now derived from CDN check
        "captcha": "Unknown",
        "gateways": "N/A",
        "graphql": "Unknown",
        "language": "N/A",
        "front_end": "N/A",
        "back_end": "N/A",
        "design": "N/A",
        "server": "N/A",
        "cdn": "N/A",
        "final_url": url, # Track final URL after redirects
        "error": None,
    }
    user_agent_for_requests = ( # Use a consistent, common UA
         "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
         f"Chrome/{CHROMEDRIVER_VERSION.split('.')[0]}.0.0.0 Safari/537.36"
     )

    # --- DNS Check ---
    domain = extract_domain(url)
    if domain:
        try:
            ip_address = socket.gethostbyname(domain)
            details["dns"] = f"✅ Resolvable ({ip_address})"
        except socket.gaierror:
            details["dns"] = "❌ Unresolvable"
            details["error"] = "DNS lookup failed"
            return details
        except Exception as dns_e:
             details["dns"] = f"⚠️ Error ({type(dns_e).__name__})"
             logger.warning(f"DNS check error for {domain}: {dns_e}")
    else:
        details["dns"] = "⚠️ Invalid URL (No Domain)"
        details["error"] = "Invalid URL format"
        return details


    # --- HTTP Request ---
    headers = {
        'User-Agent': user_agent_for_requests,
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7', # More modern accept header
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br', # Accept compression
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Sec-Ch-Ua': f'"Google Chrome";v="{CHROMEDRIVER_VERSION.split('.')[0]}", "Not(A:Brand";v="8", "Chromium";v="{CHROMEDRIVER_VERSION.split('.')[0]}"', # Client hints
        'Sec-Ch-Ua-Mobile': '?0',
        'Sec-Ch-Ua-Platform': '"Windows"', # Common platform hint
    }
    session = requests.Session()
    session.headers.update(headers)
    html_text = ""
    txt_lower = ""
    resp_headers = {}
    final_url = url

    # Disable SSL warnings globally for this function if verify=False is used
    original_warnings_filter = requests.packages.urllib3.exceptions.SecurityWarning
    requests.packages.urllib3.disable_warnings(original_warnings_filter)

    try:
        resp = session.get(url, timeout=20, verify=True, allow_redirects=True, stream=False) # Increased timeout, disable stream initially
        resp.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        details["ssl"] = "✅ Valid"
        details["status_code"] = resp.status_code
        details["final_url"] = resp.url # Store the final URL after redirects
        # Decode content carefully
        try:
             html_text = resp.content.decode(resp.apparent_encoding or 'utf-8', errors='replace')
        except Exception as decode_err:
             logger.warning(f"Could not decode content for {resp.url}: {decode_err}. Trying raw text.")
             html_text = resp.text # Fallback to requests' default decoding
        txt_lower = html_text.lower()
        resp_headers = resp.headers

    except requests.exceptions.SSLError:
        details["ssl"] = "❌ Invalid/Self-Signed"
        logger.warning(f"SSL verification failed for {url}. Retrying without verification.")
        try:
            resp = session.get(url, timeout=20, verify=False, allow_redirects=True, stream=False)
            resp.raise_for_status()
            details["status_code"] = resp.status_code
            details["final_url"] = resp.url
            try:
                 html_text = resp.content.decode(resp.apparent_encoding or 'utf-8', errors='replace')
            except Exception: html_text = resp.text
            txt_lower = html_text.lower()
            resp_headers = resp.headers
        except requests.exceptions.HTTPError as http_err_noverify:
             details["status_code"] = http_err_noverify.response.status_code
             details["error"] = f"HTTP {details['status_code']} (NoVerify)"
             logger.error(f"HTTP error fetching {url} (NoVerify): {http_err_noverify}")
             return details # Stop if fetch fails with HTTP error
        except Exception as e_noverify:
            logger.error(f"Error fetching {url} even without SSL verify: {e_noverify}", exc_info=True)
            details["error"] = f"Fetch failed (NoVerify): {type(e_noverify).__name__}"
            details["status_code"] = "Error"
            return details

    except requests.exceptions.HTTPError as http_err:
         details["status_code"] = http_err.response.status_code
         details["final_url"] = http_err.response.url
         details["error"] = f"HTTP {details['status_code']}"
         logger.error(f"HTTP error fetching {url}: {http_err}")
         # Try to get headers even on error if possible
         resp_headers = http_err.response.headers
         # Still attempt analysis based on headers if available
    except requests.exceptions.Timeout:
        logger.error(f"Timeout fetching {url}")
        details["error"] = "Timeout"
        details["status_code"] = "Timeout"
        return details
    except requests.exceptions.ConnectionError as conn_err:
        logger.error(f"Connection error fetching {url}: {conn_err}")
        details["error"] = f"Connection Error: {type(conn_err).__name__}"
        details["status_code"] = "ConnError"
        return details
    except requests.exceptions.RequestException as req_e:
        logger.error(f"Request error fetching {url}: {req_e}")
        details["error"] = f"Request Error: {type(req_e).__name__}"
        details["status_code"] = "ReqError"
        if hasattr(req_e, 'response') and req_e.response is not None:
            details["status_code"] = req_e.response.status_code
            resp_headers = req_e.response.headers # Try to get headers
        return details
    finally:
        # Restore warnings filter if needed, though disabling globally might be fine for script context
         pass # requests.packages.urllib3.enable_warnings(original_warnings_filter)


    # --- Analysis based on response ---
    # Tech Stack (Pass headers too)
    stack_info = detect_tech_stack(html_text, resp_headers)
    details.update(stack_info) # Update details with detected stack, server, cdn

    # Cloudflare (Now derived from CDN check)
    details["cloudflare"] = "✅ YES" if "Cloudflare" in details["cdn"] else "🔥 NO"

    # Captcha (Check body)
    captcha_markers = ["captcha", "recaptcha", "hcaptcha", "turnstile", "are you a robot", "verify you are human", "challenge-platform"]
    if any(marker in txt_lower for marker in captcha_markers):
        details["captcha"] = "✅ YES"
    else:
        details["captcha"] = "🔥 NO"

    # GraphQL
    graphql_markers = ["/graphql", "graphql.js", "apollo", "relay", '"__typename"']
    if any(marker in txt_lower for marker in graphql_markers):
        details["graphql"] = "✅ YES"
    else:
        details["graphql"] = "🔥 NO"

    # Language
    lang = extract_language(html_text)
    details["language"] = lang if lang else "N/A"

    # Payment Gateways
    found_gw = set()
    for gw in PAYMENT_GATEWAYS:
         pattern = r'\b' + re.escape(gw).replace(r'\.', r'[\.\s\-]?') + r'\b' # Allow dot, space, or hyphen in names like authorize.net
         if '.' in gw: pattern = re.escape(gw) # Keep simple match for names with dots if regex fails

         try:
             if re.search(pattern, txt_lower, re.IGNORECASE):
                  found_gw.add(gw)
         except re.error: # Fallback for complex patterns
              if gw.lower() in txt_lower:
                   found_gw.add(gw)

    details["gateways"] = ", ".join(sorted(list(found_gw))) if found_gw else "None"

    return details


# ----------------------------------------------------------------------------------
# UTILITY FUNCTIONS (No Changes Needed)
# ----------------------------------------------------------------------------------
def extract_domain(url: str):
    # ... (implementation from previous version) ...
    try:
        parsed = urlparse(url)
        # Ensure scheme is present for proper parsing, default to http if missing
        if not parsed.scheme:
             url = "http://" + url
             parsed = urlparse(url)

        # Return hostname (which is preferred over netloc for DNS lookup)
        # Convert to lowercase for consistency
        return parsed.hostname.lower() if parsed.hostname else None
    except ValueError:
        logger.warning(f"Could not parse URL to extract domain: {url}")
        return None

def extract_language(html: str):
    # ... (implementation from previous version) ...
    import re
    match = re.search(r"<html[^>]*\slang\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    meta_match = re.search(r"<meta[^>]*http-equiv\s*=\s*['\"]Content-Language['\"][^>]*content\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1).strip()
    return None


# ----------------------------------------------------------------------------------
# ASYNC WRAPPERS (No Changes Needed)
# ----------------------------------------------------------------------------------
executor = ThreadPoolExecutor(max_workers=8) # Increased worker count slightly

async def async_google_search_wrapper(query: str, limit: int, offset: int): # Renamed slightly for clarity
    loop = asyncio.get_running_loop()
    try:
        # Run the potentially long-running sync function in the executor
        return await loop.run_in_executor(
            executor, google_search, query, limit, offset
        )
    except RuntimeError as driver_err:
         logger.error(f"RuntimeError in async_google_search task (likely driver setup): {driver_err}")
         raise # Re-raise driver errors to be caught by the command handler
    except Exception as e:
        logger.error(f"Exception in async_google_search executor task: {e}", exc_info=True)
        return [] # Return empty list on other errors

async def async_check_site_details_wrapper(url: str): # Renamed slightly for clarity
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            executor, check_site_details, url
        )
    except Exception as e:
        logger.error(f"Exception in async_check_site_details executor task for {url}: {e}", exc_info=True)
        # Return a dict indicating error for this specific URL
        return {
            "url": url, "final_url": url, "error": f"Task execution failed: {type(e).__name__}",
            "dns": "N/A", "ssl": "N/A", "status_code": "Error", "cloudflare": "Unknown",
            "captcha": "Unknown", "gateways": "N/A", "graphql": "Unknown", "language": "N/A",
            "front_end": "N/A", "back_end": "N/A", "design": "N/A", "server": "N/A", "cdn": "N/A",
        }

# ----------------------------------------------------------------------------------
# BOT COMMAND HANDLERS (Enhanced Formatting, /dork output)
# ----------------------------------------------------------------------------------

# ... (cmd_start, cmd_register, cmd_cmds, cmd_listusers, cmd_unreg - Implementations from previous version) ...
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    logger.info(f"Received /start command from user {username} ({user_id})")

    if not is_user_registered(user_id):
        await update.message.reply_text(
            "👋 Welcome!\n"
            "You are not registered yet. Please use the /register command to gain access."
        )
    else:
        await update.message.reply_text(
            f"Welcome back, {username}!\n"
            "You are already registered. Use /cmds to see available commands."
        )

async def cmd_register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"

    if is_user_registered(user_id):
        logger.info(f"User {username} ({user_id}) tried to /register again.")
        await update.message.reply_text("✅ You are already registered!")
    else:
        register_user(user_id)
        logger.info(f"User {username} ({user_id}) successfully registered.")
        await update.message.reply_text(
            "🎉 Registration successful!\n"
            "You can now use the bot commands. Type /cmds for instructions."
        )
        # Notify admin about new registration
        if ADMIN_ID and ADMIN_ID != user_id: # Don't notify if admin registers themself
            try:
                 await context.bot.send_message(
                     chat_id=ADMIN_ID,
                     text=f"🔔 New user registered:\nUsername: @{username} (ID: `{user_id}`)",
                     parse_mode='Markdown'
                 )
            except Exception as e:
                 logger.warning(f"Could not notify admin about new user {user_id}: {e}")


async def cmd_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Access Denied: You must /register before using commands.")
        return

    is_admin = (user_id == ADMIN_ID)

    text = (
        "🤖 *Available Commands:*\n\n"
        "`/dork <query> <count>`\n"
        "  Searches Google for the specified query and returns up to `<count>` results (max 300), analyzing each site.\n"
        "  *Example:*\n"
        '  `/dork inurl:cart.php intext:"add to cart" 50`\n\n'
        "`/cmds`\n"
        "  Shows this help message.\n\n"
    )
    if is_admin:
         text += (
             "*Admin Commands:*\n"
             "`/bord <message>`\n"
             "  Broadcast a message to all registered users.\n"
             "`/listusers`\n"
             "  List registered user IDs.\n"
             "`/unreg <user_id>`\n"
             "  Unregister a user by their ID.\n\n"
         )
    text += "⚡ Bot by @iam_stillnobody | @dorkkingbot ⚡"

    await update.message.reply_text(text, parse_mode='Markdown')

async def cmd_listusers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
         await update.message.reply_text("❌ Unauthorized.")
         return

    registered_users = load_registered_users()
    if not registered_users:
         await update.message.reply_text("No users are currently registered.")
         return

    user_list_text = "👥 *Registered Users:*\n" + "\n".join(f"- `{uid}`" for uid in registered_users)

    if len(user_list_text.encode('utf-8')) > 4000: # Check byte length for safety
         tmp_filename = f"registered_users_{int(time.time())}.txt"
         tmp_filepath = os.path.join(SCRIPT_DIR, tmp_filename)
         try:
             with open(tmp_filepath, "w") as f:
                 f.write("\n".join(map(str, registered_users)))
             await update.message.reply_document(
                 document=open(tmp_filepath, "rb"),
                 caption="Registered user list (too long for a message)."
             )
         except Exception as e:
              logger.error(f"Failed to send user list as file: {e}")
              await update.message.reply_text("Error sending user list as file.")
         finally:
              if os.path.exists(tmp_filepath): os.remove(tmp_filepath)
    else:
         await update.message.reply_text(user_list_text, parse_mode='Markdown')

async def cmd_unreg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: `/unreg <user_id>`", parse_mode='Markdown')
        return

    user_id_to_unreg = int(args[0])
    registered_users = load_registered_users()

    if user_id_to_unreg not in registered_users:
        await update.message.reply_text(f"User ID `{user_id_to_unreg}` is not registered.", parse_mode='Markdown')
        return
    if user_id_to_unreg == ADMIN_ID:
         await update.message.reply_text("Cannot unregister the admin.")
         return

    registered_users.remove(user_id_to_unreg)
    save_registered_users(registered_users)
    logger.info(f"Admin {user_id} unregistered user {user_id_to_unreg}.")
    await update.message.reply_text(f"✅ User ID `{user_id_to_unreg}` has been unregistered.", parse_mode='Markdown')

    try:
        await context.bot.send_message(
            chat_id=user_id_to_unreg,
            text="Your registration for this bot has been removed by the admin."
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id_to_unreg} about unregistration: {e}")


# --- cmd_dork (Main function) ---
async def cmd_dork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Access Denied: You must /register before using /dork.")
        return

    command_args = " ".join(context.args) if context.args else ""

    if not command_args:
        await update.message.reply_text("⚠️ Usage: `/dork <query> <count>`\nExample: `/dork site:example.com 10`", parse_mode='Markdown')
        return

    try:
        # Allow query to contain spaces, count must be last argument
        if " " in command_args:
             query_part, count_str = command_args.rsplit(" ", 1)
             query_part = query_part.strip()
             count_str = count_str.strip()
             if not query_part: raise ValueError("Query cannot be empty.")
        else:
             # Assume input is just the query if no space and is not a number, default count? Or error?
             # Let's require both query and count for clarity.
             raise ValueError("Invalid format. Missing count?")

        if not count_str.isdigit():
             # Maybe the last part wasn't the count, treat whole thing as query? No, stick to format.
             raise ValueError("Count must be a number.")

        limit = int(count_str)
        limit = max(1, min(limit, 300)) # Clamp limit between 1 and 300

    except ValueError as e:
        await update.message.reply_text(f"⚠️ Invalid format: {e}. Usage: `/dork <query> <count>`", parse_mode='Markdown')
        return

    logger.info(f"User {username} ({user_id}) initiated dork: query='{query_part}', limit={limit}")
    processing_msg = await update.message.reply_text(
        f"🔍 Searching Google for up to *{limit}* results...\n"
        f"Query: `{query_part}`\n\n"
        f"This may take a few minutes, please wait...",
        parse_mode='Markdown'
    )

    start_time = time.time()
    results = []
    try:
        # Use the async wrapper which runs the sync google_search in executor
        results = await async_google_search_wrapper(query_part, limit, 0)
    except RuntimeError as driver_err:
         logger.error(f"Dork command failed for user {user_id} due to WebDriver setup issue: {driver_err}")
         await processing_msg.edit_text(f"❌ Error: Could not initialize the web driver.\n`{driver_err}`\nPlease check bot logs or contact admin.", parse_mode='Markdown')
         return
    except Exception as e:
        logger.error(f"Unhandled error during async_google_search_wrapper for query '{query_part}': {e}", exc_info=True)
        await processing_msg.edit_text(f"❌ An unexpected error occurred during Google search: `{e}`", parse_mode='Markdown')
        return

    search_duration = time.time() - start_time
    logger.info(f"Google search for '{query_part}' completed in {search_duration:.2f}s, found {len(results)} URLs.")

    if not results:
        await processing_msg.edit_text(
             f"🚫 No results found for:\n`{query_part}`\n"
             f"(Search took {search_duration:.2f}s). Try broadening your query?",
             parse_mode='Markdown'
         )
        return

    await processing_msg.edit_text(
        f"✅ Found *{len(results)}* URLs in {search_duration:.2f}s.\n"
        f"🕵️ Now analyzing site details (using {executor._max_workers} workers)...",
        parse_mode='Markdown'
    )

    # Check site details concurrently using the async wrapper
    analysis_start_time = time.time()
    tasks = [async_check_site_details_wrapper(url) for url in results]
    details_list = await asyncio.gather(*tasks)
    analysis_duration = time.time() - analysis_start_time
    total_duration = time.time() - start_time
    logger.info(f"Site analysis for {len(details_list)} URLs completed in {analysis_duration:.2f}s.")

    # Prepare a text file
    timestamp = int(time.time())
    safe_query_part = "".join(c if c.isalnum() or c in ['_','-'] else "_" for c in query_part[:40]).rstrip('_')
    filename = f"dork_{safe_query_part}_{timestamp}.txt"
    filepath = os.path.join(SCRIPT_DIR, filename)

    # --- Format Output File ---
    lines = []
    lines.append(f"--- ⚙️ Sitedorker Results ⚙️ ---\n")
    lines.append(f"Query: {query_part}\n")
    lines.append(f"Requested Limit: {limit}\n")
    lines.append(f"URLs Found (Google): {len(results)}\n")
    lines.append(f"URLs Analyzed: {len(details_list)}\n")
    lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(timestamp))}\n")
    lines.append(f"Durations: Search={search_duration:.2f}s | Analysis={analysis_duration:.2f}s | Total={total_duration:.2f}s\n")
    lines.append("----------------------------------------\n\n")

    successful_checks = 0
    errors_encountered = 0
    for d in details_list:
        if d.get('error'):
             errors_encountered += 1
             lines.append(f"URL: {d.get('url', 'N/A')}")
             lines.append(f"\n  🚨 Error: {d['error']}")
             lines.append(f" | Final URL: {d.get('final_url', 'N/A')}")
             lines.append(f"\n  DNS: {d.get('dns', 'N/A')}")
             lines.append(f" | Status: {d.get('status_code', 'N/A')}")
        else:
             successful_checks +=1
             lines.append(f"URL: {d.get('url', 'N/A')}")
             if d.get('url') != d.get('final_url'):
                  lines.append(f"\n  ↪️ Final URL: {d.get('final_url', 'N/A')}")
             lines.append(f"\n  ℹ️ Status: {d.get('status_code', 'N/A')}")
             lines.append(f" | DNS: {d.get('dns', 'N/A')}")
             lines.append(f" | SSL: {d.get('ssl', 'N/A')}")
             lines.append(f"\n  🛡️ Cloudflare: {d.get('cloudflare', 'Unknown')}")
             lines.append(f" | Captcha: {d.get('captcha', 'Unknown')}")
             lines.append(f" | CDN: {d.get('cdn', 'N/A')}")
             lines.append(f"\n  🌐 Language: {d.get('language', 'N/A')}")
             lines.append(f" | GraphQL: {d.get('graphql', 'Unknown')}")
             lines.append(f"\n  💳 Gateways: {d.get('gateways', 'None')}")
             lines.append(f"\n  💻 Stack:")
             lines.append(f"\n    Server: {d.get('server', 'N/A')}")
             lines.append(f"\n    Backend: {d.get('back_end', 'N/A')}")
             lines.append(f"\n    Frontend: {d.get('front_end', 'N/A')}")
             lines.append(f"\n    Design: {d.get('design', 'N/A')}")

        lines.append(f"\n\n⚡ Bot by @iam_stillnobody | @dorkkingbot ⚡\n")
        lines.append("----------------------------------------\n")

    # --- Write and Send File ---
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info(f"Results saved to {filepath}")
    except Exception as e:
        logger.error(f"Error writing results file {filepath}: {e}")
        await processing_msg.edit_text("❌ Error writing results to file.")
        return

    try:
        caption = (
             f"📄 Dork results for: `{query_part}`\n"
             f"Found: {len(results)}, Analyzed: {len(details_list)} ({successful_checks}✓, {errors_encountered}✗)\n"
             f"Total Time: {total_duration:.2f}s"
        )
        with open(filepath, "rb") as file_data:
            await update.message.reply_document(
                document=InputFile(file_data, filename=filename),
                caption=caption,
                parse_mode='Markdown',
                reply_to_message_id=update.message.message_id # Reply to original request
            )
        await processing_msg.delete() # Delete the "processing..." message
        logger.info(f"Results file {filename} sent successfully to user {user_id}.")

    except Exception as e:
        logger.error(f"Error sending file {filename}: {e}")
        await processing_msg.edit_text(
            f"❌ Error sending the results file: `{e}`\n"
            f"The file was generated (`{filename}`) but could not be sent.",
            parse_mode='Markdown'
        )

    finally:
        # Clean up the file
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted local results file: {filepath}")
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")


async def cmd_bord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (implementation from previous version) ...
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    message_to_broadcast = " ".join(context.args) if context.args else ""
    if not message_to_broadcast:
        await update.message.reply_text("Usage: `/bord <message>`", parse_mode='Markdown')
        return

    registered_users = load_registered_users()
    if not registered_users:
         await update.message.reply_text("No registered users to broadcast to.")
         return

    logger.info(f"Admin {user_id} starting broadcast to {len(registered_users)} users.")
    await update.message.reply_text(f"📢 Starting broadcast to {len(registered_users)} users...")

    count_sent = 0
    count_failed = 0
    failed_users = []
    users_to_remove = [] # Users who blocked the bot

    broadcast_text = f"🔔 *Admin Broadcast:*\n\n{message_to_broadcast}"

    for uid in registered_users:
        if uid == ADMIN_ID: continue # Don't broadcast to admin

        try:
            await context.bot.send_message(
                chat_id=uid,
                text=broadcast_text,
                parse_mode='Markdown'
            )
            count_sent += 1
            logger.debug(f"Broadcast sent successfully to {uid}")
            # Sleep to avoid hitting rate limits (Telegram limits ~30 messages/sec globally, 1/sec to same chat)
            await asyncio.sleep(0.05) # 50ms sleep should be safe for different users
        except Exception as e:
            count_failed += 1
            failed_users.append(uid)
            logger.error(f"Could not send broadcast to user {uid}: {e}")
            # Check for specific errors indicating the user blocked the bot or was deactivated
            error_str = str(e).lower()
            if "forbidden: bot was blocked by the user" in error_str or \
               "forbidden: user is deactivated" in error_str or \
               "chat not found" in error_str:
                logger.warning(f"User {uid} blocked the bot or is inactive. Marking for removal.")
                users_to_remove.append(uid)

    # Unregister users who blocked the bot
    if users_to_remove:
         current_registered = load_registered_users()
         updated_registered = [uid for uid in current_registered if uid not in users_to_remove]
         if len(updated_registered) < len(current_registered):
              save_registered_users(updated_registered)
              logger.info(f"Automatically unregistered {len(users_to_remove)} users: {users_to_remove}")


    final_message = f"Broadcast finished.\n✅ Sent: {count_sent}\n❌ Failed: {count_failed}"
    if users_to_remove:
        final_message += f"\n🗑️ Unregistered due to block/inactive: {len(users_to_remove)}"
    if failed_users and count_failed > len(users_to_remove): # Show other failures if any
         other_failed = [uid for uid in failed_users if uid not in users_to_remove]
         if other_failed:
             final_message += f"\n⚠️ Other failed User IDs: {other_failed}"

    await update.message.reply_text(final_message)
    logger.info(f"Broadcast complete. Sent: {count_sent}, Failed: {count_failed}, Unregistered: {len(users_to_remove)}")


# ----------------------------------------------------------------------------------
# FALLBACK HANDLER
# ----------------------------------------------------------------------------------
async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (implementation from previous version) ...
    user_id = update.effective_user.id
    if not is_user_registered(user_id):
        await update.message.reply_text("Please /register first to use the bot.")
    else:
        await update.message.reply_text(
            "I didn't recognize that command. 🤔\n"
            "Type /cmds to see the list of available commands."
        )
    logger.debug(f"Received non-command message from user {user_id}: {update.message.text[:50]}...")


# ----------------------------------------------------------------------------------
# ERROR HANDLER
# ----------------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (implementation from previous version) ...
    logger.error(f"Exception while handling an update:", exc_info=context.error)

    if ADMIN_ID:
        try:
            # Format the error message for HTML
            tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
            tb_string = "".join(tb_list)

            update_str = ""
            if isinstance(update, Update):
                 update_str = update.to_json(indent=2)
            elif update:
                 update_str = str(update)


            # Limit traceback length
            max_tb_len = 2000
            truncated_tb = tb_string[-max_tb_len:]
            if len(tb_string) > max_tb_len:
                 truncated_tb = "(...)\n" + truncated_tb


            error_message = (
                 f"⚠️ <b>Bot Error Occurred</b> ⚠️\n\n"
                 f"<b>Error:</b> <pre>{html.escape(str(context.error))}</pre>\n\n"
                 # f"<b>Update:</b>\n<pre>{html.escape(update_str)}</pre>\n\n" # Update object can be huge
                 f"<b>Traceback (last {max_tb_len} chars):</b>\n<pre>{html.escape(truncated_tb)}</pre>"
            )

            # Split the message if too long
            max_len = 4096
            for i in range(0, len(error_message), max_len):
                await context.bot.send_message(
                    chat_id=ADMIN_ID,
                    text=error_message[i:i + max_len],
                    parse_mode='HTML'
                )
        except Exception as e_notify:
             logger.error(f"CRITICAL: Failed to notify admin about error: {e_notify}")
             # Also log the original error again in case notification fails completely
             logger.error(f"Original error details (logging again due to notify failure): {context.error}", exc_info=context.error)


# ----------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------
def main():
    # ... (Prerequisite checks from previous version) ...
    logger.info("Checking prerequisites...")
    if not shutil.which("wget"):
         logger.critical("CRITICAL: `wget` not found. ChromeDriver setup requires it. Please install wget.")
         # return # Exit if essential tools are missing? Or let setup fail? Let setup fail for now.
    if not shutil.which("unzip"):
         logger.critical("CRITICAL: `unzip` not found. ChromeDriver setup requires it. Please install unzip.")

    logger.info("Running initial check/setup for ChromeDriver...")
    if not setup_chrome_driver():
         logger.warning("Initial ChromeDriver setup failed. The /dork command will likely fail until dependencies (wget, unzip, network access) are met or setup succeeds.")
         # Allow bot to start for other commands

    # Build the application
    app_builder = ApplicationBuilder().token(BOT_TOKEN)
    # Increase default timeouts slightly
    app_builder.connect_timeout(30)
    app_builder.read_timeout(30)
    app_builder.write_timeout(30)

    app = app_builder.build()

    # --- Register Handlers ---
    app.add_handler(CommandHandler("start", cmd_start, block=False)) # Run non-blocking
    app.add_handler(CommandHandler("register", cmd_register, block=False))
    app.add_handler(CommandHandler("cmds", cmd_cmds, block=False))
    app.add_handler(CommandHandler("dork", cmd_dork)) # Keep dork blocking within its handler scope
    # Admin commands
    app.add_handler(CommandHandler("bord", cmd_bord, block=False))
    app.add_handler(CommandHandler("listusers", cmd_listusers, block=False))
    app.add_handler(CommandHandler("unreg", cmd_unreg, block=False))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler, block=False))
    app.add_error_handler(error_handler)


    logger.info("Bot is starting... Press Ctrl+C to stop.")
    try:
        # Start polling
        app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True) # Drop old updates on restart
    finally:
        # Cleanup executor on shutdown
        logger.info("Shutting down thread pool executor...")
        executor.shutdown(wait=True)
        logger.info("Bot has stopped.")

# ----------------------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------------------
if __name__ == "__main__":
    # ... (User instructions from previous version) ...
    print("--- Sitedorker Bot ---")
    print("Starting up...")
    print("\n[Prerequisites]")
    print("1. Python 3.7+ installed.")
    print("2. Required Python packages. Install using:")
    print("   pip install --user python-telegram-bot selenium selenium-stealth requests")
    print("   (Recommended: Use a virtual environment: python3 -m venv venv; source venv/bin/activate; pip install ...)")
    print("3. `wget` and `unzip` command-line tools must be installed and in your PATH.")
    print(f"4. Google Chrome or Chromium browser (ARM64, compatible with ChromeDriver {CHROMEDRIVER_VERSION}) must be installed.")
    print("   - If it's in your system PATH, the script should find it automatically.")
    print("   - If not, you *MUST* edit the `create_local_driver` function in the script")
    print("     and set the `chrome_options.binary_location` to the correct path of the executable.")
    print("-" * 20)


    # Check BOT_TOKEN is set
    if BOT_TOKEN == "YOUR_FALLBACK_TOKEN_HERE" or not BOT_TOKEN or len(BOT_TOKEN.split(':')) != 2:
         logger.critical("FATAL: Telegram Bot Token is missing or invalid! Please edit the BOT_TOKEN variable in the script.")
         exit(1)

    main()