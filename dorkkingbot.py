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
from selenium.common.exceptions import WebDriverException, NoSuchElementException, ElementClickInterceptedException
from selenium_stealth import stealth

# ----------------------------------------------------------------------------------
# LOGGING @Mod_By_Kamal
# ----------------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
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
CHROMEDRIVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chromedriver_files")
CHROMEDRIVER_PATH = os.path.join(CHROMEDRIVER_DIR, "chromedriver")

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
    Checks if wget and unzip are available.
    """
    # Check if chromedriver executable already exists and is executable
    if os.path.exists(CHROMEDRIVER_PATH) and os.access(CHROMEDRIVER_PATH, os.X_OK):
        logger.info(f"ChromeDriver already exists and is executable at: {CHROMEDRIVER_PATH}")
        return True

    # Check for required tools (wget, unzip)
    if not shutil.which("wget"):
        logger.error("`wget` command not found. Please install it.")
        return False
    if not shutil.which("unzip"):
        logger.error("`unzip` command not found. Please install it.")
        return False

    try:
        logger.info(f"Setting up ChromeDriver in {CHROMEDRIVER_DIR}...")

        # Ensure the target directory exists
        os.makedirs(CHROMEDRIVER_DIR, exist_ok=True)

        # URL for linux-arm64 (adjust version if needed, check https://googlechromelabs.github.io/chrome-for-testing/)
        # This version seems specific, ensure it matches a compatible Chrome version
        chromedriver_url = (
            "https://storage.googleapis.com/chrome-for-testing-public/131.0.6778.108/linux-arm64/chromedriver-linux-arm64.zip"
        )
        zip_filename = "chromedriver_linux_arm64.zip"
        zip_filepath = os.path.join(CHROMEDRIVER_DIR, zip_filename)

        # Download
        logger.info(f"Downloading ChromeDriver from {chromedriver_url}...")
        subprocess.run(['wget', chromedriver_url, '-O', zip_filepath], check=True, cwd=CHROMEDRIVER_DIR)

        # Unzip
        logger.info(f"Unzipping {zip_filename}...")
        unzip_dir = os.path.join(CHROMEDRIVER_DIR, "unzipped") # Unzip to a temp subfolder first
        os.makedirs(unzip_dir, exist_ok=True)
        with zipfile.ZipFile(zip_filepath, 'r') as zip_ref:
             zip_ref.extractall(unzip_dir)

        # Find the chromedriver executable within the extracted folder (it might be nested)
        extracted_chromedriver_path = None
        for root, dirs, files in os.walk(unzip_dir):
            if "chromedriver" in files:
                extracted_chromedriver_path = os.path.join(root, "chromedriver")
                break

        if not extracted_chromedriver_path:
             raise FileNotFoundError("Could not find 'chromedriver' executable in the extracted files.")

        # Move the executable to the final CHROMEDRIVER_PATH
        logger.info(f"Moving chromedriver to {CHROMEDRIVER_PATH}")
        shutil.move(extracted_chromedriver_path, CHROMEDRIVER_PATH)

        # Set executable permissions using Python's os.chmod
        logger.info(f"Setting executable permission for {CHROMEDRIVER_PATH}")
        current_permissions = os.stat(CHROMEDRIVER_PATH).st_mode
        os.chmod(CHROMEDRIVER_PATH, current_permissions | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH) # Add execute permission for user, group, others

        # Clean up zip file and temp unzip directory
        logger.info("Cleaning up downloaded zip file and temp directory...")
        os.remove(zip_filepath)
        shutil.rmtree(unzip_dir)

        logger.info("ChromeDriver setup completed successfully.")
        return True

    except FileNotFoundError as fnf_error:
        logger.error(f"Error during ChromeDriver setup: {fnf_error}")
        return False
    except subprocess.CalledProcessError as proc_error:
        logger.error(f"Error during ChromeDriver setup (wget/unzip command failed): {proc_error}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error setting up ChromeDriver: {e}")
        # Clean up potentially partially downloaded/extracted files
        if os.path.exists(zip_filepath):
             os.remove(zip_filepath)
        if os.path.exists(unzip_dir):
             shutil.rmtree(unzip_dir)
        return False

# ----------------------------------------------------------------------------------
# JSON UTILS => @Mod_By_Kamal
# (No changes needed here)
# ----------------------------------------------------------------------------------
def load_registered_users():
    if not os.path.exists(REGISTERED_USERS_FILE):
        return []
    try:
        with open(REGISTERED_USERS_FILE, "r") as f:
            data = json.load(f)
            # Ensure it's a list of integers (or convert if needed)
            if isinstance(data, list):
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
    """
    Save the list of registered user IDs to JSON.
    Ensures user_ids are integers.
    """
    # Ensure all IDs are integers before saving
    valid_user_ids = [int(uid) for uid in user_ids if isinstance(uid, (int, str)) and str(uid).isdigit()]
    try:
        with open(REGISTERED_USERS_FILE, "w") as f:
            json.dump(valid_user_ids, f, indent=4) # Add indent for readability
    except Exception as e:
        logger.error(f"Error saving registered users to {REGISTERED_USERS_FILE}: {e}")


def is_user_registered(user_id):
    registered = load_registered_users()
    return int(user_id) in registered # Ensure comparison is between integers

def register_user(user_id):
    registered = load_registered_users()
    int_user_id = int(user_id) # Ensure we're working with an integer
    if int_user_id not in registered:
        registered.append(int_user_id)
        save_registered_users(registered)

# ----------------------------------------------------------------------------------
# CREATE A NEW DRIVER FOR EACH PAGE => @Mod_By_Kamal
# ----------------------------------------------------------------------------------

def create_local_driver():
    """
    Create and return a new headless Chrome Selenium driver with stealth settings.
    Uses the locally managed ChromeDriver.
    Assumes Chrome browser binary is findable in PATH or installed in a standard user location.
    """
    # Ensure chromedriver is set up before creating a driver
    if not setup_chrome_driver():
         logger.error("ChromeDriver setup failed. Cannot create driver.")
         # Optionally raise an exception or return None to handle this upstream
         raise RuntimeError("ChromeDriver setup failed. Cannot proceed.")
         # return None


    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox") # Often needed in restricted/containerized environments
    chrome_options.add_argument("--disable-dev-shm-usage") # Overcomes limited resource problems
    chrome_options.add_argument("--disable-gpu") # Generally recommended for headless
    chrome_options.add_argument("--disable-extensions")
    # chrome_options.add_argument("--disable-logging") # Can sometimes hide useful errors
    # chrome_options.add_argument("--disable-dev-tools") # Dev tools not usually needed for headless
    chrome_options.add_argument("--disable-software-rasterizer")

    # Make the language explicitly English
    chrome_options.add_argument("--lang=en-US")
    chrome_options.add_experimental_option('prefs', {'intl.accept_languages': 'en-US,en'})

    # Prevent some automated detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")

    # --- REMOVED ---
    # chrome_options.binary_location = "/usr/bin/google-chrome"
    # Let Selenium try to find Chrome. If it fails, the user needs to:
    # 1. Install Chrome/Chromium for ARM64.
    # 2. Ensure its location is in the system PATH.
    # 3. OR, manually uncomment and set the binary_location below:
    # chrome_options.binary_location = "/path/to/your/chrome-arm64/chrome"
    # Example: chrome_options.binary_location = os.path.expanduser("~/chrome-linux/chrome")

    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    # Use the CHROMEDRIVER_PATH defined globally
    service = ChromeService(executable_path=CHROMEDRIVER_PATH)

    try:
        local_driver = webdriver.Chrome(service=service, options=chrome_options)
    except WebDriverException as e:
        logger.error(f"Failed to start Chrome WebDriver: {e}")
        logger.error("Ensure Chrome/Chromium (ARM64) is installed and accessible.")
        logger.error(f"Selenium is using ChromeDriver from: {CHROMEDRIVER_PATH}")
        # If Chrome binary location is the issue, you might see "cannot find Chrome binary" or similar.
        # Instruct user to potentially set `chrome_options.binary_location` manually in the code if needed.
        raise # Re-raise the exception to stop execution if driver fails

    # Apply stealth settings
    try:
        stealth(
            local_driver,
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/110.0.5481.105 Safari/537.36" # Consider updating UA if using a newer Chrome version
            ),
            languages=["en-US", "en"],
            vendor="Google Inc.",
            platform="Win32", # Stealth might mask the true platform
            webgl_vendor="Intel Inc.",
            renderer="Intel Iris OpenGL Engine",
            fix_hairline=True,
        )
    except Exception as e:
        logger.warning(f"Could not apply all stealth settings: {e}")


    local_driver.set_page_load_timeout(30) # Increased timeout slightly
    return local_driver

# (Rest of the functions: click_google_consent_if_needed, google_search, detect_tech_stack, check_site_details, extract_domain, extract_language, async wrappers, bot commands, main)
# --- NO CHANGES needed in the following functions based on the requirements ---

# ----------------------------------------------------------------------------------
# CLICK GOOGLE CONSENT (No Changes Needed)
# ----------------------------------------------------------------------------------
def click_google_consent_if_needed(driver, wait_seconds=3): # Slightly longer wait
    """
    Attempts to click 'Accept all', 'I agree', etc. on Google's consent screen.
    """
    time.sleep(wait_seconds)
    # More comprehensive selectors, trying common patterns
    possible_selectors = [
        "button#L2AGLb",                          # Common "I Agree" button
        "button#W0wltc",                          # Another variant
        "//button[.//div[contains(text(), 'Accept all')]]", # XPath for "Accept all" text
        "//button[.//div[contains(text(), 'I agree')]]",    # XPath for "I agree" text
        "div[role='dialog'] button:nth-of-type(2)", # Fallback pattern (often the second button)
        "form[action*='consent'] button",          # Button within a consent form
    ]
    for sel in possible_selectors:
        try:
            if sel.startswith("//"): # Handle XPath
                 btn = driver.find_element(By.XPATH, sel)
            else: # Handle CSS Selectors
                 btn = driver.find_element(By.CSS_SELECTOR, sel)

            # Try clicking with JavaScript if direct click is intercepted
            try:
                btn.click()
            except ElementClickInterceptedException:
                logger.warning(f"Direct click intercepted for selector {sel}, trying JavaScript click.")
                driver.execute_script("arguments[0].click();", btn)

            logger.info(f"Clicked Google consent button using selector: {sel}")
            time.sleep(2)  # Let the page react/reload
            return # Stop after successful click
        except (NoSuchElementException, ElementClickInterceptedException) as e:
             # Log only if it's an interception error we couldn't bypass
             if isinstance(e, ElementClickInterceptedException):
                 logger.warning(f"Could not click consent button ({sel}): {e}")
             pass # Try the next selector if this one fails
        except Exception as e_general:
            logger.error(f"Unexpected error finding/clicking consent button ({sel}): {e_general}")
            pass # Try next selector

    logger.info("Could not find or click any known Google consent button.")


# ----------------------------------------------------------------------------------
# GOOGLE SEARCH (Selector Updated, otherwise no changes needed for environment)
# ----------------------------------------------------------------------------------

def google_search(query: str, limit: int = 10, offset: int = 0):
    """
    Paginate Google search. Handles consent and uses updated selectors.
    """
    all_links = []
    seen = set()

    # Calculate pages based on 100 results per page, respecting the limit
    # Example: limit=150 -> need 2 pages (0-99, 100-199)
    # Example: limit=100 -> need 1 page (0-99)
    # Example: limit=50  -> need 1 page (0-99, but we stop early)
    pages_to_fetch = (limit + 99) // 100 # Integer division ceiling
    # Google realistically won't serve more than ~10 pages reliably
    max_google_pages = 10
    pages_needed = min(pages_to_fetch, max_google_pages)

    logger.info(f"[google_search] Query='{query}', limit={limit}, offset={offset}")
    logger.info(f"Aiming for {limit} results, will fetch up to {pages_needed} Google pages (max 100 results/page).")

    driver = None # Initialize driver variable

    for page_index in range(pages_needed):
        if len(all_links) >= limit:
            logger.info("Reached desired result limit. Stopping pagination.")
            break

        start_val = offset + (page_index * 100)
        driver = None # Ensure driver is reset for each attempt

        try:
            driver = create_local_driver() # Get a fresh driver instance
            if driver is None: # Handle case where driver creation failed
                logger.error("Failed to create WebDriver instance. Stopping search.")
                break

            # Add hl=en & gl=us to standardize results and interface language
            # Use safe URL encoding for the query
            from urllib.parse import quote_plus
            encoded_query = quote_plus(query)
            url = (
                f"https://www.google.com/search?q={encoded_query}"
                f"&num=100"          # Request 100 results
                f"&start={start_val}"  # Pagination offset
                f"&hl=en&gl=us"      # English language, US region
                f"&filter=0"         # Try to disable safe search filtering / duplicate removal
            )
            logger.info(f"Navigating to page {page_index + 1}: {url}")
            driver.get(url)

            click_google_consent_if_needed(driver)

            # Wait for results to potentially load after consent click or initial load
            time.sleep(2.5)

            # Updated selector for main organic result links
            # Targets the link (<a>) inside the div commonly holding the result URL block
            # This tends to be more stable than targeting specific classes that change often.
            result_elements = driver.find_elements(By.CSS_SELECTOR, "div.g a") # More general selector first
            # Fallback to a previously common selector if the above fails
            if not result_elements:
                result_elements = driver.find_elements(By.CSS_SELECTOR, "div.yuRUbf > a")

            if not result_elements:
                # Check for CAPTCHA or unusual page structure
                page_title = driver.title.lower()
                page_source_lower = driver.page_source.lower()
                if "captcha" in page_title or "recaptcha" in page_source_lower or "verify you are human" in page_source_lower:
                     logger.warning(f"CAPTCHA detected on page {page_index + 1}. Stopping search.")
                     break # Stop if we hit a CAPTCHA
                else:
                     logger.info(f"No results found using selectors on page {page_index + 1}. May be end of results or page change.")
                     break # Stop if no results found

            page_links = []
            for element in result_elements:
                try:
                     href = element.get_attribute("href")
                     # Filter out non-http links, internal Google links, etc.
                     if href and href.startswith("http") and "google.com/" not in href:
                         # Basic cleaning: remove tracking parameters if present (simple cases)
                         if "#:~:text=" in href:
                              href = href.split("#:~:text=")[0]
                         page_links.append(href)
                except Exception as link_err:
                     logger.warning(f"Error extracting href from an element: {link_err}")


            logger.info(f"Found {len(page_links)} potential links on page {page_index + 1}.")

            count_added_this_page = 0
            for link in page_links:
                if link not in seen:
                    seen.add(link)
                    all_links.append(link)
                    count_added_this_page += 1
                    if len(all_links) >= limit:
                        break # Stop adding if limit reached

            logger.info(f"Added {count_added_this_page} new unique links. Total unique links: {len(all_links)}.")

            if len(all_links) >= limit:
                logger.info("Reached desired result limit.")
                break # Exit outer loop if limit reached

        except WebDriverException as e:
            logger.error(f"WebDriver error occurred on page {page_index + 1}: {e}")
            # Check if it's a "target window closed" error, which might happen if browser crashes
            if "target window already closed" in str(e).lower():
                 logger.error("Browser window closed unexpectedly. Trying to continue if possible, but may lose results.")
            # We might want to break the loop on most WebDriver exceptions
            break
        except Exception as e_general:
             logger.error(f"An unexpected error occurred during scraping page {page_index + 1}: {e_general}")
             # Depending on the error, you might want to break or continue
             break # Safer to stop if something unexpected happens
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as quit_err:
                    logger.warning(f"Error quitting WebDriver instance: {quit_err}")
            # Add a delay between requests to avoid being blocked
            # Randomize delay slightly
            sleep_time = 3 + (os.urandom(1)[0] / 255.0 * 2) # Random float between 3.0 and 5.0
            logger.info(f"Sleeping for {sleep_time:.2f} seconds before next page or exit.")
            time.sleep(sleep_time)


    # Ensure we return only up to the requested limit
    return all_links[:limit]


# ----------------------------------------------------------------------------------
# DETECT TECH STACK (No Changes Needed)
# ----------------------------------------------------------------------------------
def detect_tech_stack(html_text: str):
    txt_lower = html_text.lower()
    # Use regex for better matching (word boundaries)
    import re

    front_found = []
    for fw in FRONTEND_FRAMEWORKS:
        # Look for framework names as whole words or common patterns
        # Example: \breact\b matches 'react' but not 'reactive'
        # Example: vue.js, node.js need special handling if dots are included
        pattern = r'\b' + re.escape(fw) + r'\b'
        if re.search(pattern, txt_lower):
            front_found.append(fw)
        # Add checks for specific markers if needed, e.g., <div id="app"> for Vue default
        elif fw == 'vue' and ('<div id="app">' in txt_lower or 'data-vue-meta' in txt_lower):
            front_found.append(fw)
        elif fw == 'angular' and ('ng-app' in txt_lower or 'ng-version' in txt_lower):
            front_found.append(fw)

    back_found = []
    for bw in BACKEND_FRAMEWORKS:
        pattern = r'\b' + re.escape(bw) + r'\b'
        # Special case for node.js, asp.net, etc.
        if bw == 'node.js' and ('node.js' in txt_lower or 'express' in txt_lower): # Express often implies Node
             pattern = r'\bnode\.js\b|\bexpress\b' # Adjust pattern
        elif bw == 'asp.net':
             pattern = r'\basp\.net\b'
        elif bw == 'ruby on rails':
             pattern = r'\bruby on rails\b|\brails\b' # Allow just 'rails'

        if re.search(pattern, txt_lower):
            back_found.append(bw)
        # Add checks for specific headers or meta tags
        elif bw == 'wordpress' and ('wp-content' in txt_lower or 'wp-json' in txt_lower or '/wp-includes/' in txt_lower):
             back_found.append(bw)
        elif bw == 'php' and ('.php' in txt_lower or 'x-powered-by: php' in txt_lower): # Simple check
             back_found.append(bw)
        elif bw == 'laravel' and ('laravel_session' in txt_lower or 'X-CSRF-TOKEN' in txt_lower): # Common Laravel markers
             back_found.append(bw)

    design_found = []
    for ds in DESIGN_LIBRARIES:
        pattern = r'\b' + re.escape(ds) + r'\b'
        if re.search(pattern, txt_lower):
            design_found.append(ds)
        # Check for common CSS class prefixes or file names
        elif ds == 'bootstrap' and ('class="container' in txt_lower or 'bootstrap.min.css' in txt_lower):
             design_found.append(ds)
        elif ds == 'tailwind' and ('class="w-' in txt_lower or 'class="h-' in txt_lower or 'tailwindcss' in txt_lower): # Tailwind utility classes
             design_found.append(ds)


    # Remove duplicates and format
    return {
        "front_end": ", ".join(sorted(list(set(front_found)))) if front_found else "N/A",
        "back_end": ", ".join(sorted(list(set(back_found)))) if back_found else "N/A",
        "design": ", ".join(sorted(list(set(design_found)))) if design_found else "N/A",
    }


# ----------------------------------------------------------------------------------
# SITE DETAILS CHECK (No Changes Needed for environment)
# ----------------------------------------------------------------------------------
def check_site_details(url: str):
    details = {
        "url": url,
        "dns": "N/A",
        "ssl": "N/A",
        "status_code": None, # Use None to indicate not checked yet
        "cloudflare": "Unknown",
        "captcha": "Unknown",
        "gateways": "N/A",
        "graphql": "Unknown",
        "language": "N/A",
        "front_end": "N/A",
        "back_end": "N/A",
        "design": "N/A",
        "error": None, # Add an error field
    }

    # --- DNS Check ---
    domain = extract_domain(url)
    if domain:
        try:
            socket.gethostbyname(domain)
            details["dns"] = "✅ Resolvable"
        except socket.gaierror:
            details["dns"] = "❌ Unresolvable"
            details["error"] = "DNS lookup failed"
            # If DNS fails, skip HTTP request
            return details
        except Exception as dns_e:
             details["dns"] = f"⚠️ Error ({type(dns_e).__name__})"
             logger.warning(f"DNS check error for {domain}: {dns_e}")
             # Proceed with HTTP check cautiously


    # --- HTTP Request ---
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36', # Standard UA
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    session = requests.Session() # Use session for potential cookie handling, keep-alive
    session.headers.update(headers)
    html_text = ""
    txt_lower = ""
    resp_headers = {}

    try:
        # Try with SSL verification first
        resp = session.get(url, timeout=15, verify=True, allow_redirects=True)
        details["ssl"] = "✅ Valid"
        details["status_code"] = resp.status_code
        html_text = resp.text
        txt_lower = html_text.lower()
        resp_headers = resp.headers

    except requests.exceptions.SSLError:
        details["ssl"] = "❌ Invalid/Self-Signed"
        logger.warning(f"SSL verification failed for {url}. Retrying without verification.")
        try:
            # Retry without SSL verification
            resp = session.get(url, timeout=15, verify=False, allow_redirects=True)
            # Suppress InsecureRequestWarning if using verify=False
            requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
            details["status_code"] = resp.status_code # Still record status code
            html_text = resp.text
            txt_lower = html_text.lower()
            resp_headers = resp.headers
            # Note: Stack detection might still work even with invalid SSL
        except Exception as e_noverify:
            logger.error(f"Error fetching {url} even without SSL verify: {e_noverify}")
            details["error"] = f"Fetch failed (NoVerify): {type(e_noverify).__name__}"
            details["status_code"] = "Error" # Indicate fetch error
            return details # Stop if fetch fails completely

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
            details["status_code"] = req_e.response.status_code # Get status code if available
        return details


    # --- Analysis based on response (if successful or SSL invalid) ---
    if html_text: # Proceed only if we got some HTML content
        # Cloudflare (Check headers primarily, then body)
        cf_detected = False
        # Common Cloudflare headers
        cf_headers = ['cf-ray', 'cf-cache-status', 'server']
        for h_key, h_val in resp_headers.items():
             if h_key.lower() in cf_headers and 'cloudflare' in h_val.lower():
                  cf_detected = True
                  break
             # Server header sometimes just says "cloudflare"
             if h_key.lower() == 'server' and h_val.lower() == 'cloudflare':
                 cf_detected = True
                 break
        # Fallback: Check body for common Cloudflare block/JS challenge patterns
        if not cf_detected and ('cloudflare' in txt_lower or 'cdn-cgi' in txt_lower or 'ray id' in txt_lower):
             # Be cautious, this might be false positive if 'cloudflare' is just mentioned
             if 'checking your browser before accessing' in txt_lower or 'enable javascript and refresh' in txt_lower:
                 cf_detected = True

        details["cloudflare"] = "✅ YES" if cf_detected else "🔥 NO"

        # Captcha (Check body)
        captcha_markers = ["captcha", "recaptcha", "hcaptcha", "turnstile", "are you a robot", "verify you are human"]
        if any(marker in txt_lower for marker in captcha_markers):
            details["captcha"] = "✅ YES"
        else:
            details["captcha"] = "🔥 NO"

        # GraphQL (Check body for common endpoint hints or keywords)
        # Look for "/graphql", "graphql.min.js", "apollo", "relay" etc.
        graphql_markers = ["/graphql", "graphql.js", "apollo", "relay", '"__typename"']
        if any(marker in txt_lower for marker in graphql_markers):
            details["graphql"] = "✅ YES"
        else:
            details["graphql"] = "🔥 NO"

        # Language (Extract from <html lang="..."> attribute)
        lang = extract_language(html_text)
        details["language"] = lang if lang else "N/A"

        # Payment Gateways (Check body)
        found_gw = []
        for gw in PAYMENT_GATEWAYS:
             # Use word boundaries for more accuracy where possible
             pattern = r'\b' + re.escape(gw) + r'\b'
             # Handle cases like authorize.net where '.' is part of the name
             if '.' in gw: pattern = re.escape(gw) # Simpler match if special chars involved

             if re.search(pattern, txt_lower, re.IGNORECASE):
                  found_gw.append(gw)

        # Deduplicate and join
        details["gateways"] = ", ".join(sorted(list(set(found_gw)))) if found_gw else "None"

        # Tech stack (Use dedicated function)
        stack = detect_tech_stack(html_text)
        details["front_end"] = stack["front_end"]
        details["back_end"] = stack["back_end"]
        details["design"] = stack["design"]

    # If status code indicates client/server error, reflect that if no specific error was caught
    if isinstance(details["status_code"], int) and details["status_code"] >= 400 and details["error"] is None:
         details["error"] = f"HTTP {details['status_code']}"


    return details

# ----------------------------------------------------------------------------------
# UTILITY FUNCTIONS (No Changes Needed)
# ----------------------------------------------------------------------------------
def extract_domain(url: str):
    from urllib.parse import urlparse
    try:
        parsed = urlparse(url)
        # Return hostname (which is preferred over netloc for DNS lookup)
        return parsed.hostname
    except ValueError:
        logger.warning(f"Could not parse URL to extract domain: {url}")
        return None

def extract_language(html: str):
    import re
    # Match <html lang="xx"> or <html lang="xx-YY"> case-insensitively
    match = re.search(r"<html[^>]*\slang\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    # Fallback: Look for <meta http-equiv="Content-Language" content="xx">
    meta_match = re.search(r"<meta[^>]*http-equiv\s*=\s*['\"]Content-Language['\"][^>]*content\s*=\s*['\"]([^'\"]+)['\"]", html, re.IGNORECASE)
    if meta_match:
        return meta_match.group(1).strip()
    return None


# ----------------------------------------------------------------------------------
# ASYNC WRAPPERS (No Changes Needed)
# ----------------------------------------------------------------------------------

executor = ThreadPoolExecutor(max_workers=5) # Keep worker count moderate

async def async_google_search(query: str, limit: int, offset: int):
    loop = asyncio.get_running_loop()
    # Add try-except block here to catch exceptions from the sync function
    try:
        return await loop.run_in_executor(
            executor, google_search, query, limit, offset
        )
    except Exception as e:
        logger.error(f"Error in async_google_search executor task: {e}")
        # Depending on desired behavior, you might return an empty list or re-raise
        return [] # Return empty list on error

async def async_check_site_details(url: str):
    loop = asyncio.get_running_loop()
    # Add try-except block here as well
    try:
        return await loop.run_in_executor(
            executor, check_site_details, url
        )
    except Exception as e:
        logger.error(f"Error in async_check_site_details executor task for {url}: {e}")
        # Return a dict indicating error for this specific URL
        return {
            "url": url,
            "error": f"Task execution failed: {type(e).__name__}",
            # Fill other keys with defaults or N/A
            "dns": "N/A", "ssl": "N/A", "status_code": "Error", "cloudflare": "Unknown",
            "captcha": "Unknown", "gateways": "N/A", "graphql": "Unknown", "language": "N/A",
            "front_end": "N/A", "back_end": "N/A", "design": "N/A",
        }

# ----------------------------------------------------------------------------------
# BOT COMMAND HANDLERS (Minor formatting improvements, core logic unchanged)
# ----------------------------------------------------------------------------------

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
        # Notify admin about new registration (optional)
        try:
             await context.bot.send_message(
                 chat_id=ADMIN_ID,
                 text=f"🔔 New user registered:\nUsername: @{username} (ID: {user_id})"
             )
        except Exception as e:
             logger.warning(f"Could not notify admin about new user {user_id}: {e}")


async def cmd_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Access Denied: You must /register before using commands.")
        return

    text = (
        "🤖 *Available Commands:*\n\n"
        "`/dork <query> <count>`\n"
        "  Searches Google for the specified query and returns up to `<count>` results (max 300).\n"
        "  *Example:*\n"
        '  `/dork intext:"powered by shopify" + "contact" 50`\n\n'
        "`/cmds`\n"
        "  Shows this help message.\n\n"
        # Admin only section
        f"{'*Admin Commands:*' if user_id == ADMIN_ID else ''}\n"
        f"{'`/bord <message>` - Broadcast a message to all registered users.' if user_id == ADMIN_ID else ''}\n"
        f"{'`/listusers` - List registered user IDs (Admin only).' if user_id == ADMIN_ID else ''}\n"
        f"{'`/unreg <user_id>` - Unregister a user (Admin only).' if user_id == ADMIN_ID else ''}\n"
    )
    await update.message.reply_text(text, parse_mode='Markdown')

# Add admin commands /listusers and /unreg
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
    # Handle potential message length limit for large user lists
    if len(user_list_text) > 4000: # Telegram limit is 4096
         # Send as a file or split message if needed
         with open("registered_users_list.txt", "w") as f:
              f.write("\n".join(map(str, registered_users)))
         await update.message.reply_document(
              document=open("registered_users_list.txt", "rb"),
              caption="Registered user list (too long for a message)."
         )
         os.remove("registered_users_list.txt")
    else:
         await update.message.reply_text(user_list_text, parse_mode='Markdown')


async def cmd_unreg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    args = context.args
    if len(args) != 1 or not args[0].isdigit():
        await update.message.reply_text("Usage: `/unreg <user_id>`")
        return

    user_id_to_unreg = int(args[0])
    registered_users = load_registered_users()

    if user_id_to_unreg not in registered_users:
        await update.message.reply_text(f"User ID `{user_id_to_unreg}` is not registered.")
        return

    registered_users.remove(user_id_to_unreg)
    save_registered_users(registered_users)
    logger.info(f"Admin {user_id} unregistered user {user_id_to_unreg}.")
    await update.message.reply_text(f"✅ User ID `{user_id_to_unreg}` has been unregistered.")
    # Optionally notify the unregistered user
    try:
        await context.bot.send_message(
            chat_id=user_id_to_unreg,
            text="Your registration for this bot has been removed by the admin."
        )
    except Exception as e:
        logger.warning(f"Could not notify user {user_id_to_unreg} about unregistration: {e}")


async def cmd_dork(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    username = update.effective_user.username or f"User_{user_id}"
    if not is_user_registered(user_id):
        await update.message.reply_text("❌ Access Denied: You must /register before using /dork.")
        return

    raw_text = update.message.text.strip()
    command_args = raw_text[len("/dork"):].strip()

    if not command_args:
        await update.message.reply_text("⚠️ Usage: `/dork <query> <count>`\nExample: `/dork site:example.com 10`", parse_mode='Markdown')
        return

    try:
        # Right-split once to separate query from count
        query_part, count_str = command_args.rsplit(" ", 1)
        query_part = query_part.strip()
        count_str = count_str.strip()

        if not query_part:
             raise ValueError("Query part is empty.")

        if not count_str.isdigit():
            await update.message.reply_text("⚠️ Invalid count. Please provide a number (e.g., 50).")
            return

        limit = int(count_str)
        if limit < 1:
            limit = 1
        elif limit > 300: # Enforce max limit
            limit = 300
            await update.message.reply_text("ℹ️ Maximum count is 300. Searching for 300 results.")

    except ValueError:
        # Handle cases where there's no space or count isn't last
        await update.message.reply_text("⚠️ Invalid format. Usage: `/dork <query> <count>`\nExample: `/dork site:example.com 10`", parse_mode='Markdown')
        return

    logger.info(f"User {username} ({user_id}) initiated dork: query='{query_part}', limit={limit}")
    processing_msg = await update.message.reply_text(
        f"🔍 Searching for up to *{limit}* results for:\n`{query_part}`\n\n"
        f"This may take a while, please wait...",
        parse_mode='Markdown'
    )

    start_time = time.time()
    try:
        results = await async_google_search(query_part, limit, 0)
    except RuntimeError as driver_err:
         # Catch the error raised if driver setup fails
         logger.error(f"Dork command failed due to WebDriver setup issue: {driver_err}")
         await processing_msg.edit_text(f"❌ Error: Could not initialize the web driver. {driver_err}")
         return
    except Exception as e:
        logger.error(f"Unhandled error during async_google_search for query '{query_part}': {e}")
        await processing_msg.edit_text(f"❌ An unexpected error occurred during Google search: {e}")
        return

    search_duration = time.time() - start_time
    logger.info(f"Google search for '{query_part}' completed in {search_duration:.2f}s, found {len(results)} URLs.")

    if not results:
        await processing_msg.edit_text(
             f"🚫 No results found for:\n`{query_part}`\n"
             f"(Search took {search_duration:.2f}s). Possible Google block or too specific query?",
             parse_mode='Markdown'
         )
        return

    await processing_msg.edit_text(
        f"✅ Found *{len(results)}* URLs.\n"
        f"Now analyzing site details (this might take time)...",
        parse_mode='Markdown'
    )

    # Check site details concurrently
    tasks = [async_check_site_details(url) for url in results]
    details_list = await asyncio.gather(*tasks)

    analysis_duration = time.time() - start_time - search_duration
    logger.info(f"Site analysis completed in {analysis_duration:.2f}s.")

    # Prepare a text file
    timestamp = int(time.time())
    # Sanitize query for filename (replace non-alphanumeric with underscore)
    safe_query_part = "".join(c if c.isalnum() else "_" for c in query_part[:30]) # Limit length
    filename = f"dork_{safe_query_part}_{timestamp}.txt"

    lines = []
    lines.append(f"--- Dork Results ---\n")
    lines.append(f"Query: {query_part}\n")
    lines.append(f"Requested Count: {limit}\n")
    lines.append(f"Found URLs: {len(results)}\n")
    lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(timestamp))}\n")
    lines.append(f"Search Duration: {search_duration:.2f}s\n")
    lines.append(f"Analysis Duration: {analysis_duration:.2f}s\n")
    lines.append("----------------------------------------\n\n")

    for d in details_list:
        lines.append(f"URL: {d.get('url', 'N/A')}")
        if d.get('error'):
             lines.append(f"\n  🚨 Error: {d['error']}")
        lines.append(f"\n  DNS: {d.get('dns', 'N/A')}")
        lines.append(f" | SSL: {d.get('ssl', 'N/A')}")
        lines.append(f" | Status: {d.get('status_code', 'N/A')}")
        lines.append(f"\n  Cloudflare: {d.get('cloudflare', 'Unknown')}")
        lines.append(f" | Captcha: {d.get('captcha', 'Unknown')}")
        lines.append(f" | GraphQL: {d.get('graphql', 'Unknown')}")
        lines.append(f"\n  Language: {d.get('language', 'N/A')}")
        lines.append(f"\n  Gateways: {d.get('gateways', 'N/A')}")
        lines.append(f"\n  Stack (Detected):")
        lines.append(f"\n    Frontend: {d.get('front_end', 'N/A')}")
        lines.append(f"\n    Backend: {d.get('back_end', 'N/A')}")
        lines.append(f"\n    Design: {d.get('design', 'N/A')}")
        lines.append(f"\n\n⚡ Bot by @iam_stillnobody | @dorkkingbot ⚡\n")
        lines.append("----------------------------------------\n")

    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename) # Save in script dir
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
        logger.info(f"Results saved to {filepath}")
    except Exception as e:
        logger.error(f"Error writing results file {filepath}: {e}")
        await processing_msg.edit_text("❌ Error writing results to file.")
        return


    # Send the file
    try:
        with open(filepath, "rb") as file_data:
            doc = InputFile(file_data, filename=filename)
            await update.message.reply_document(
                document=doc,
                caption=f"📄 Here are the {len(details_list)} results for your query:\n`{query_part}`",
                parse_mode='Markdown'
            )
        # Delete the temporary processing message
        await processing_msg.delete()
        logger.info(f"Results file {filename} sent successfully to user {user_id}.")

    except Exception as e:
        logger.error(f"Error sending file {filename}: {e}")
        # Edit the processing message instead of sending a new one
        await processing_msg.edit_text(f"❌ Error sending the results file: {e}\nThe file was generated but could not be sent.")

    # Clean up the file
    finally:
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted local results file: {filepath}")
        except Exception as e:
            logger.error(f"Error deleting file {filepath}: {e}")


async def cmd_bord(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ Unauthorized.")
        return

    text = update.message.text.strip()
    parts = text.split(" ", maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text("Usage: `/bord <message>`")
        return

    message_to_broadcast = parts[1].strip()
    registered_users = load_registered_users()

    if not registered_users:
         await update.message.reply_text("No registered users to broadcast to.")
         return

    logger.info(f"Admin {user_id} starting broadcast to {len(registered_users)} users.")
    await update.message.reply_text(f"📢 Starting broadcast to {len(registered_users)} users...")

    count_sent = 0
    count_failed = 0
    failed_users = []

    for uid in registered_users:
        # Avoid broadcasting to the admin themselves unless they are the only user
        # if uid == ADMIN_ID and len(registered_users) > 1: continue

        try:
            await context.bot.send_message(
                chat_id=uid,
                text=f"🔔 *Admin Broadcast:*\n\n{message_to_broadcast}",
                parse_mode='Markdown'
            )
            count_sent += 1
            logger.debug(f"Broadcast sent successfully to {uid}")
            # Sleep to avoid hitting rate limits
            await asyncio.sleep(0.1) # Sleep for 100ms between messages
        except Exception as e:
            count_failed += 1
            failed_users.append(uid)
            logger.error(f"Could not send broadcast to user {uid}: {e}")
            # Handle specific errors like 'Forbidden: bot was blocked by the user'
            if "bot was blocked" in str(e).lower():
                 logger.warning(f"User {uid} blocked the bot. Consider unregistering them.")
                 # Optionally unregister blocked users automatically here
                 # registered_users.remove(uid)
                 # save_registered_users(registered_users)


    final_message = f"Broadcast finished.\n✅ Sent: {count_sent}\n❌ Failed: {count_failed}"
    if failed_users:
        final_message += f"\nFailed User IDs: {failed_users}"
        logger.warning(f"Broadcast failed for users: {failed_users}")

    await update.message.reply_text(final_message)
    logger.info(f"Broadcast complete. Sent: {count_sent}, Failed: {count_failed}")

# ----------------------------------------------------------------------------------
# FALLBACK HANDLER
# ----------------------------------------------------------------------------------

async def fallback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles any message that isn't a command."""
    user_id = update.effective_user.id
    if not is_user_registered(user_id):
        await update.message.reply_text("Please /register first to use the bot.")
    else:
        # Optional: Provide a helpful message for registered users
        await update.message.reply_text(
            "I didn't recognize that command. 🤔\n"
            "Type /cmds to see the list of available commands."
        )
    logger.info(f"Received non-command message from user {user_id}: {update.message.text[:50]}...")


# ----------------------------------------------------------------------------------
# ERROR HANDLER
# ----------------------------------------------------------------------------------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)

    # Optionally notify the admin about the error
    if ADMIN_ID:
         try:
             # Format the error message
             tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
             tb_string = "".join(tb_list)
             error_message = (
                 f"An exception was raised while handling an update\n"
                 f"<pre>update = {html.escape(json.dumps(update.to_dict(), indent=2, ensure_ascii=False))}</pre>\n"
                 f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n"
                 f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n"
                 f"<pre>{html.escape(tb_string)}</pre>"
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
              logger.error(f"Failed to notify admin about error: {e_notify}")


# ----------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------
import traceback
import html

def main():
    # Check essential prerequisites before starting the bot
    # 1. Check if chromedriver setup can run (at least find wget/unzip)
    if not shutil.which("wget") or not shutil.which("unzip"):
         logger.critical("CRITICAL: `wget` or `unzip` not found. ChromeDriver setup will fail. Please install them.")
         # Decide whether to exit or try to continue (setup will fail later)
         # return # Exit if essential tools are missing

    # 2. Attempt initial ChromeDriver setup (or check if exists)
    #    This happens within create_local_driver now, but an early check is good.
    logger.info("Running initial check/setup for ChromeDriver...")
    if not setup_chrome_driver():
         logger.warning("Initial ChromeDriver setup failed. The /dork command might not work until dependencies are met or setup succeeds.")
         # Bot can still run for /register, /cmds, etc.

    # Build the application
    app_builder = ApplicationBuilder().token(BOT_TOKEN)
    # Optional: Configure connection pool size if expecting high concurrency
    # app_builder.pool_timeout(30)
    # app_builder.connect_timeout(30)
    # app_builder.read_timeout(30)
    # app_builder.write_timeout(30)

    app = app_builder.build()


    # --- Register Handlers ---
    # Command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("register", cmd_register))
    app.add_handler(CommandHandler("cmds", cmd_cmds))
    app.add_handler(CommandHandler("dork", cmd_dork))
    # Admin commands
    app.add_handler(CommandHandler("bord", cmd_bord))
    app.add_handler(CommandHandler("listusers", cmd_listusers))
    app.add_handler(CommandHandler("unreg", cmd_unreg))


    # Message handler for non-command text (must be after command handlers)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, fallback_handler))

    # Error handler
    app.add_error_handler(error_handler)


    logger.info("Bot is starting... Press Ctrl+C to stop.")
    # Start polling
    app.run_polling(allowed_updates=Update.ALL_TYPES) # Process all update types

    # Cleanup executor on shutdown (optional, but good practice)
    executor.shutdown(wait=True)
    logger.info("Bot has stopped.")

# ----------------------------------------------------------------------------------
# ENTRY POINT
# ----------------------------------------------------------------------------------

if __name__ == "__main__":
    # --- User Instructions ---
    print("--- Sitedorker Bot ---")
    print("Starting up...")
    print("\n[Prerequisites]")
    print("1. Python 3.7+ installed.")
    print("2. Required Python packages. Install using:")
    print("   pip install --user python-telegram-bot selenium selenium-stealth requests")
    print("   (Consider using a virtual environment: python -m venv venv; source venv/bin/activate; pip install ...)")
    print("3. `wget` and `unzip` command-line tools must be installed and in your PATH.")
    print("4. Google Chrome or Chromium browser (ARM64 version) must be installed.")
    print("   - If it's in your system PATH, the script should find it automatically.")
    print("   - If not, you *must* edit the `create_local_driver` function in the script")
    print("     and set the `chrome_options.binary_location` to the correct path of the executable.")
    print("-" * 20)

    # Check BOT_TOKEN is set
    if BOT_TOKEN == "YOUR_FALLBACK_TOKEN_HERE" or not BOT_TOKEN:
         logger.critical("FATAL: Telegram Bot Token is not set! Please edit the BOT_TOKEN variable in the script or set the TELEGRAM_BOT_TOKEN environment variable.")
         exit(1) # Exit if token is missing

    main()