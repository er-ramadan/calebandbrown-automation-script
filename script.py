# --- Dependencies ---
import importlib.util
import subprocess
import sys
import os

def ensure_package(pkg_name, install_name=None):
    """Check if a package is installed; if not, install it."""
    if install_name is None:
        install_name = pkg_name
    if importlib.util.find_spec(pkg_name) is None:
        print(f"🔧 Installing missing package: {install_name} ...")
        subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", install_name], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

# Required packages
required_packages = {
    "playwright": "playwright",
    "faker": "faker",
    "requests": "requests",
}

print("Verifying dependencies...")
for pkg, install_name in required_packages.items():
    ensure_package(pkg, install_name)

# Install Playwright browsers if not already installed
try:
    # Check if browsers are installed by trying a dry-run
    check_path = subprocess.run([sys.executable, "-m", "playwright", "install", "--dry-run"], check=True, capture_output=True, text=True)
    if "chromium" not in check_path.stdout:
        raise Exception("Browsers not found")
except Exception:
    print("⚙️ Installing Playwright browsers (chromium, firefox, webkit)...")
    subprocess.run([sys.executable, "-m", "playwright", "install", "--with-deps"], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

print("✅ All dependencies verified and ready.")

# --- Core Imports ---
import random
import secrets
import string
import time
import csv
import logging
import traceback
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any

from playwright.sync_api import (
    sync_playwright,
    Playwright,
    Browser,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
    Route,
    Request
)
from faker import Faker

# --- Config ---
@dataclass
class BotConfig:
    """Bot config - tweak settings here."""
    SIGNUP_URL: str = "https://app.calebandbrown.com/signup"
    NUMBERS_FILE: str = "numbers.txt"
    OUTPUT_CSV: str = "created_accounts_with_phone.csv"
    LOG_FILE: str = "caleb_playwright_pro_final.log"
    
    HEADLESS: bool = False
    MAX_NAV_RETRIES: int = 3
    GOTO_TIMEOUT_MS: int = 45_000
    ACTION_TIMEOUT_MS: int = 20_000
    
    COUNTRIES: List[str] = [
        "Egypt", "Saudi Arabia", "Singapore",
        "France", "Germany", "Italy", "Spain", "Netherlands", "Sweden", "Switzerland", "Poland"
    ]
    
    MIN_DELAY_ACTION: float = 0.05
    MAX_DELAY_ACTION: float = 0.25
    
    KEEP_BROWSER_OPEN_ON_SUCCESS: bool = False
    
    CSV_FIELDS: List[str] = [
        "timestamp", "phone_used", "email", "password", 
        "first_name", "last_name", "country", "notes"
    ]

@dataclass
class AccountData:
    first_name: str
    last_name: str
    email: str
    password: str
    country: str
    phone: Optional[str] = None
    timestamp: str = ""

# --- Helper Functions ---

def setup_logging(log_file: str) -> logging.Logger:
    """Sets up the global rotating file + console logger."""
    logger = logging.getLogger("AccountCreatorBot")
    if logger.hasHandlers():
        return logger # Already set up
        
    logger.setLevel(logging.INFO)
    # File handler
    handler = RotatingFileHandler(log_file, maxBytes=8*1024*1024, backupCount=6, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s"))
    logger.addHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(console_handler)
    
    return logger

def read_numbers_file(file_path: str) -> List[str]:
    """Reads a list of phone numbers from a file."""
    log = logging.getLogger("AccountCreatorBot") # Use main logger
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            numbers = [line.strip() for line in f if line.strip()]
        log.info("Loaded %d phone numbers from %s", len(numbers), file_path)
        return numbers
    except FileNotFoundError:
        log.warning("Numbers file not found: %s. Will run 1x without phone.", file_path)
        return []
    except Exception as e:
        log.exception("Error reading numbers file: %s", e)
        return []

def jitter_sleep(min_s: float, max_s: float):
    """Sleeps for a random duration."""
    time.sleep(random.uniform(min_s, max_s))

# --- Data Generation ---

class DataGenerator:
    """Generates fake user data for signups."""
    def __init__(self, countries: List[str]):
        self.fake = Faker()
        self.countries = countries
        self.log = logging.getLogger(f"{self.__class__.__name__}")

    def _generate_strong_password(self) -> str:
        """Generates a complex, randomized password."""
        specials = "!@#$%&*()_+-=<>?@!$!"
        base_len = random.randint(8, 11)
        base = ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(base_len))

        # Ensure complexity
        if not any(c.isupper() for c in base): base = 'S' + base[1:]
        if not any(c.islower() for c in base): base = base[:-1] + 'a'
        if not any(c.isdigit() for c in base): base = base + str(random.randint(1,9))

        num_specials = random.randint(3, 6)
        specials_part = ''.join(secrets.choice(specials) for _ in range(num_specials))
        
        insert_pos = random.randint(1, max(1, len(base)-1))
        password = base[:insert_pos] + specials_part + base[insert_pos:]
        
        return password[:18] # Cap length

    def _generate_realistic_email(self, first: str, last: str) -> str:
        """Generates a realistic-looking email."""
        f = first.lower().replace(" ", "")
        l = last.lower().replace(" ", "")
        patterns = [
            f"{f}.{l}{random.randint(10,99)}", f"{f}{l}{random.randint(1,9999)}",
            f"{f}_{l}{random.randint(1,99)}", f"{f}{random.randint(100,999)}",
        ]
        pattern = random.choice(patterns)
        domain = random.choice(["gmail.com", "outlook.com", "hotmail.com", "yahoo.com"])
        return f"{pattern}@{domain}"

    def generate_account_data(self, phone_number: Optional[str]) -> AccountData:
        """Generates a complete set of data for a new account."""
        first = self.fake.first_name()
        last = self.fake.last_name()
        email = self._generate_realistic_email(first, last)
        password = self._generate_strong_password()
        country = random.choice(self.countries)
        timestamp = datetime.utcnow().isoformat() + "Z"
        
        self.log.debug("Generated data for: %s", email)
        return AccountData(
            first_name=first, last_name=last, email=email,
            password=password, country=country, phone=phone_number,
            timestamp=timestamp
        )

# --- Output Writers ---

class IOutputWriter(ABC):
    """Abstract interface for output writers (e.g., CSV, DB)."""
    @abstractmethod
    def write_row(self, data: Dict[str, Any]):
        pass

class CsvOutputWriter(IOutputWriter):
    """CSV file implementation of IOutputWriter."""
    def __init__(self, filename: str, fieldnames: List[str]):
        self.filename = Path(filename)
        self.fieldnames = fieldnames
        self.log = logging.getLogger(f"{self.__class__.__name__}")
        self._initialize_file()

    def _initialize_file(self):
        """Creates the CSV and writes the header if it doesn't exist."""
        if not self.filename.exists():
            self.log.info("Creating new output CSV: %s", self.filename)
            try:
                with open(self.filename, "w", newline="", encoding="utf-8") as fh:
                    writer = csv.DictWriter(fh, fieldnames=self.fieldnames)
                    writer.writeheader()
            except IOError as e:
                self.log.exception("Failed to initialize CSV file: %s", e)
                raise

    def write_row(self, data: Dict[str, Any]):
        """Appends a single row to the CSV."""
        try:
            with open(self.filename, "a", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=self.fieldnames)
                writer.writerow(data)
        except IOError as e:
            self.log.exception("Failed to write row to CSV: %s", data.get("email"))
        except Exception as e:
            self.log.exception("Unhandled error writing CSV row: %s", e)

# --- Browser Management ---

class BrowserManager:
    """Handles browser launch, context creation, and cleanup."""
    def __init__(self, playwright: Playwright, config: BotConfig):
        self.playwright = playwright
        self.config = config
        self.browser: Optional[Browser] = None
        self.log = logging.getLogger(f"{self.__class__.__name__}")

    def launch(self):
        """Launches the Chromium browser."""
        if self.browser:
            return # Already launched
        try:
            self.log.info("Launching browser (Headless: %s)...", self.config.HEADLESS)
            self.browser = self.playwright.chromium.launch(
                headless=self.config.HEADLESS,
                slow_mo=0
            )
        except Exception as e:
            self.log.exception("Failed to launch browser: %s", e)
            raise

    def _setup_request_blocking(self, context: BrowserContext):
        """Block heavy/tracker resources to speed up page loads."""
        blocked_resource_types = ["image", "media", "font"]
        blocked_hosts = [
            "google-analytics.com", "googletagmanager.com", "hotjar.com",
            "facebook.net", "doubleclick.net", "bing.com", "quantserve.com"
        ]
        
        def route_handler(route: Route, request: Request):
            try:
                if request.resource_type in blocked_resource_types:
                    return route.abort()
                if any(host in request.url.lower() for host in blocked_hosts):
                    return route.abort()
                return route.continue_()
            except Exception:
                try: route.continue_() # Failsafe
                except Exception: pass

        try:
            context.route("**/*", route_handler)
            self.log.debug("Request blocking configured.")
        except Exception as e:
            self.log.exception("Failed to setup request blocking: %s", e)

    def new_context(self) -> BrowserContext:
        """Creates a new, isolated browser context with optimizations."""
        if not self.browser:
            self.log.error("Browser not launched. Call launch() first.")
            raise Exception("BrowserNotLaunched")
            
        try:
            context = self.browser.new_context(
                viewport={"width": 1200, "height": 820},
                java_script_enabled=True,
                user_agent=self.playwright.devices['Desktop Chrome']['user_agent']
            )
            self._setup_request_blocking(context)
            return context
        except Exception as e:
            self.log.exception("Failed to create new context: %s", e)
            self.log.warning("Attempting to relaunch browser...")
            self.shutdown()
            self.launch()
            # Retry once
            context = self.browser.new_context(
                viewport={"width": 1200, "height": 820}
            )
            self._setup_request_blocking(context)
            self.log.info("Successfully created context after relaunch.")
            return context
    
    def close_context(self, context: BrowserContext):
        """Safely closes a browser context."""
        try:
            context.close()
        except Exception as e:
            self.log.warning("Exception while closing context: %s", e)

    def shutdown(self):
        """Closes the browser."""
        if self.browser:
            try:
                self.browser.close()
                self.log.info("Browser shut down.")
            except Exception as e:
                self.log.warning("Exception while closing browser: %s", e)
            self.browser = None

# --- Page Objects ---

class BasePage:
    """Base Page Object with common helpers (goto, popups, etc)."""
    def __init__(self, page: Page, config: BotConfig):
        self.page = page
        self.config = config
        self.log = logging.getLogger(f"{self.__class__.__name__}")
        self.page.set_default_timeout(self.config.ACTION_TIMEOUT_MS)
        self.min_delay = self.config.MIN_DELAY_ACTION
        self.max_delay = self.config.MAX_DELAY_ACTION
    
    def robust_goto(self, url: str) -> bool:
        """Wrapper for page.goto() with retries and backoff."""
        last_exc = None
        for attempt in range(1, self.config.MAX_NAV_RETRIES + 1):
            try:
                self.page.goto(url, timeout=self.config.GOTO_TIMEOUT_MS, wait_until="load")
                try:
                    self.page.wait_for_load_state("networkidle", timeout=2000)
                except PlaywrightTimeoutError:
                    pass # 'load' is good enough
                self._optimize_loaded_page()
                return True
            except PlaywrightTimeoutError as te:
                last_exc = te
                backoff = min(2 * attempt, 8)
                self.log.warning("Goto attempt %d timed out; backing off %ds", attempt, backoff)
                time.sleep(backoff + random.uniform(0, 0.5))
            except Exception as e:
                last_exc = e
                self.log.exception("Goto attempt %d error: %s", attempt, str(e))
                time.sleep(1.0 + random.uniform(0,0.5))
        
        self.log.error("Navigation failed after %d attempts. Last error: %s", self.config.MAX_NAV_RETRIES, repr(last_exc))
        return False

    def _optimize_loaded_page(self):
        """Run JS to kill videos, iframes, animations, and overlays."""
        try:
            script = """
            (() => {
                try {
                    document.querySelectorAll('video, audio, iframe').forEach(el => el.remove());
                    const css = `* { animation: none !important; transition: none !imporant; }`;
                    const style = document.createElement('style');
                    style.innerText = css;
                    document.head && document.head.appendChild(style);
                    document.querySelectorAll('.chat-widget, .chatbot, .cookie-banner').forEach(el => el.remove());
                    return true;
                } catch(e) { return false; }
            })();
            """
            self.page.evaluate(script)
            jitter_sleep(0.05, 0.12)
            self.log.debug("Page optimizations applied.")
        except Exception as e:
            self.log.warning("Failed to apply page optimizations: %s", e)

    def close_common_popups(self):
        """Best-effort attempt to click common close/dismiss buttons."""
        selectors = [
            "button[aria-label='Close']", "button:has-text('Close')",
            "button:has-text('Dismiss')", "button:has-text('Not now')",
            "div[role='dialog'] button:has-text('Close')"
        ]
        for sel in selectors:
            try:
                loc = self.page.locator(sel)
                if loc.count() > 0:
                    loc.first.click(timeout=1200)
                    jitter_sleep(0.03, 0.08)
            except Exception:
                pass # Ignore errors


class SignUpPage(BasePage):
    """Page Object for the main /signup form."""
    
    def __init__(self, page: Page, config: BotConfig):
        super().__init__(page, config)
        self.country_input = page.locator("input[placeholder='Select country']").first
        self.first_name_input = page.locator("input[placeholder='Legal first name']").first
        self.last_name_input = page.locator("input[placeholder='Legal last name']").first
        self.email_input = page.locator("input[placeholder='Email address']").first
        self.password_input = page.locator("input[placeholder='Password']").first
        self.confirm_pass_input = page.locator("input[placeholder='Confirm password']").first
        self.create_button = page.locator("button:has-text('Create account')")

    def navigate(self) -> bool:
        self.log.info("Navigating to signup URL...")
        return self.robust_goto(self.config.SIGNUP_URL)

    def _select_country_by_typing(self, country: str) -> bool:
        """Strategy 1: Type and click exact match."""
        try:
            self.country_input.click(timeout=2000)
            jitter_sleep(0.02, 0.06)
            self.country_input.fill("", timeout=800)
            for ch in country:
                self.country_input.type(ch, delay=random.randint(6, 18))
            jitter_sleep(0.02, 0.06)
            
            option_selector = f"div[role='option']:has-text('{country}'), .css-54kpfw:has-text('{country}')"
            option = self.page.locator(option_selector).first
            option.wait_for(state="visible", timeout=3000)
            option.click()
            jitter_sleep(0.02, 0.06)
            return True
        except Exception:
            return False
            
    def _select_country_by_js(self, country: str) -> bool:
        """Strategy 2: Use JavaScript to find and click the element."""
        try:
            self.country_input.click(timeout=1200)
            jitter_sleep(0.02, 0.05)
            script = f"""
            (() => {{
                const name = "{country}".toLowerCase();
                const options = Array.from(document.querySelectorAll('div[role="option"], .css-54kpfw'));
                for (const el of options) {{
                    const txt = (el.innerText || '').trim().toLowerCase();
                    if (txt === name) {{
                        el.click();
                        return true;
                    }}
                }}
                return false;
            }})();
            """
            if self.page.evaluate(script):
                jitter_sleep(0.02, 0.05)
                return True
            return False
        except Exception:
            return False

    def select_country(self, country: str) -> bool:
        """Tries multiple strategies to select a country."""
        self.log.debug("Selecting country: %s", country)
        
        if self._select_country_by_typing(country):
            self.log.info("Country select OK (typing): %s", country)
            return True
            
        if self._select_country_by_js(country):
            self.log.info("Country select OK (JS): %s", country)
            return True
            
        self.log.warning("Country select FAILED: %s", country)
        return False

    def fill_form(self, data: AccountData) -> bool:
        """Fills the entire signup form."""
        try:
            self.close_common_popups()
            jitter_sleep(0.05, 0.12)
            
            if not self.select_country(data.country):
                self.log.warning("Country selection failed, proceeding anyway...")
            
            jitter_sleep(0.04, 0.12)
            self.first_name_input.fill(data.first_name, timeout=3000)
            jitter_sleep(0.02, 0.06)
            self.last_name_input.fill(data.last_name, timeout=3000)
            jitter_sleep(0.02, 0.06)
            self.email_input.fill(data.email, timeout=3000)
            jitter_sleep(0.02, 0.06)
            self.password_input.fill(data.password, timeout=3000)
            jitter_sleep(0.02, 0.04)
            self.confirm_pass_input.fill(data.password, timeout=3000)
            jitter_sleep(0.05, 0.12)
            return True
        except Exception as e:
            self.log.exception("Failed to fill signup form: %s", e)
            return False

    def submit_form(self) -> bool:
        """Submits the form."""
        try:
            self.create_button.click(timeout=5000)
            self.log.info("Clicked 'Create account' button.")
            return True
        except Exception as e:
            self.log.exception("Error clicking Create account: %s", e)
            return False


class PhoneVerificationPage(BasePage):
    """Page Object for the phone verification modal/page."""
    
    def __init__(self, page: Page, config: BotConfig):
        super().__init__(page, config)
        self.phone_input = page.locator("input[placeholder='Phone number']").first
        self.send_code_button = page.locator("button:has-text('Send code')")

    def wait_for_page(self, timeout_ms: int = 8000) -> bool:
        """Waits for the phone verification input to appear."""
        try:
            self.phone_input.wait_for(state="visible", timeout=timeout_ms)
            self.log.info("Phone verification page loaded.")
            return True
        except PlaywrightTimeoutError:
            self.log.warning("Phone verification input not found.")
            return False

    def submit_phone(self, phone_number: str) -> str:
        """Enters the phone number and clicks 'Send code'."""
        try:
            self.phone_input.click(timeout=1200)
            self.phone_input.fill("", timeout=1200)
            jitter_sleep(0.02, 0.06)
            
            for ch in phone_number:
                self.phone_input.type(ch, delay=random.randint(6, 18))
            jitter_sleep(0.04, 0.08)

            self.send_code_button.first.click(timeout=3000)
            
            self.log.info("Clicked 'Send code' for phone %s. Waiting 10s...", phone_number)
            # Wait for 10s as per original logic
            time.sleep(10)
            return "send_code_clicked_waited_10s"
            
        except Exception as e:
            self.log.exception("Error during phone verification step: %s", e)
            return f"phone_step_exception:{type(e).__name__}"

# --- Main Worker ---

class AccountCreator:
    """Main worker class. Orchestrates the full signup flow."""
    
    def __init__(self, 
                 browser_manager: BrowserManager, 
                 data_generator: DataGenerator, 
                 output_writer: IOutputWriter, 
                 config: BotConfig):
        
        self.browser_manager = browser_manager
        self.data_generator = data_generator
        self.output_writer = output_writer
        self.config = config
        self.log = logging.getLogger(f"{self.__class__.__name__}")
        self.account_index = 0

    def run_single_account(self, phone_number: Optional[str]) -> bool:
        """Runs the full E2E workflow for one account."""
        self.account_index += 1
        account_id = f"[#{self.account_index}]"
        
        data = self.data_generator.generate_account_data(phone_number)
        notes = "init"
        context: Optional[BrowserContext] = None
        
        self.log.info("%s Starting signup for %s (Phone: %s)", account_id, data.email, data.phone or "<none>")

        try:
            context = self.browser_manager.new_context()
            page = context.new_page()
            
            signup_page = SignUpPage(page, self.config)
            
            if not signup_page.navigate():
                notes = "nav_failed"
                raise Exception("NavigationFailed")
            
            if not signup_page.fill_form(data):
                notes = "form_fill_failed"
                raise Exception("FormFillFailed")
            
            if not signup_page.submit_form():
                notes = "submit_failed"
                raise Exception("SubmitFailed")
            
            # Handle post-submit logic
            if data.phone:
                phone_page = PhoneVerificationPage(page, self.config)
                if not phone_page.wait_for_page():
                    notes = "phone_input_not_found"
                else:
                    notes = phone_page.submit_phone(data.phone)
            else:
                # No phone, check for other outcomes
                try: page.wait_for_load_state("networkidle", timeout=2000)
                except Exception: pass
                
                if "verify" in page.content().lower() or "check your email" in page.content().lower():
                    notes = "verification_prompt_detected_no_phone"
                elif page.url != self.config.SIGNUP_URL:
                     notes = f"navigated_to:{page.url.split('?')[0]}" # Clean URL
                else:
                    notes = "unknown_post_submit_state_no_phone"
            
            self.log.info("%s Finished signup for %s — Notes: %s", account_id, data.email, notes)
            
            if self.config.KEEP_BROWSER_OPEN_ON_SUCCESS and not self.config.HEADLESS:
                self.log.warning("%s KEEP_BROWSER_OPEN is True. Pausing execution.", account_id)
                print(f"--- Paused for {data.email}. Press Enter in console to continue... ---")
                input() # Pause
                return False # Signal to stop loop

            return True # Success, continue loop

        except Exception as e:
            if "Target closed" in str(e) or "Browser has been closed" in str(e):
                self.log.error("%s Critical Playwright error: %s. Relaunching browser.", account_id, e)
                self.browser_manager.shutdown()
                self.browser_manager.launch()
            else:
                self.log.exception("%s Unhandled exception in flow for %s: %s", account_id, data.email, e)
            
            if notes == "init": # Ensure 'notes' reflects the error
                 notes = f"flow_exception:{type(e).__name__}"

        finally:
            # This block *always* runs
            self.output_writer.write_row({
                "timestamp": data.timestamp, "phone_used": data.phone or "",
                "email": data.email, "password": data.password,
                "first_name": data.first_name, "last_name": data.last_name,
                "country": data.country, "notes": notes
            })
            
            if context and not (self.config.KEEP_BROWSER_OPEN_ON_SUCCESS and not self.config.HEADLESS):
                self.browser_manager.close_context(context)

        return True # Continue loop even on failure

    def run(self, phone_numbers: List[str]):
        """Runs the creation loop for all provided phone numbers."""
        if not phone_numbers:
            self.log.info("No phone numbers loaded. Running one account without a phone number.")
            self.run_single_account(phone_number=None)
        else:
            self.log.info("Starting batch job for %d phone numbers.", len(phone_numbers))
            for phone in phone_numbers:
                continue_loop = self.run_single_account(phone_number=phone)
                if not continue_loop:
                    self.log.info("Stopping loop (KEEP_BROWSER_OPEN).")
                    break
                jitter_sleep(0.2, 0.6) # Delay between accounts

# --- Main Execution ---

def main():
    """Entry point: wires up dependencies and runs the bot."""
    
    config = BotConfig()
    logger = setup_logging(config.LOG_FILE)
    logger.info("--- Bot session started ---")

    phone_numbers = read_numbers_file(config.NUMBERS_FILE)

    try:
        with sync_playwright() as pw:
            
            # Init dependencies
            data_generator = DataGenerator(config.COUNTRIES)
            output_writer = CsvOutputWriter(config.OUTPUT_CSV, config.CSV_FIELDS)
            browser_manager = BrowserManager(pw, config)
            
            browser_manager.launch()

            # Create the main worker and inject dependencies
            creator = AccountCreator(
                browser_manager=browser_manager,
                data_generator=data_generator,
                output_writer=output_writer,
                config=config
            )

            # Run the workflow
            creator.run(phone_numbers)

            logger.info("--- Bot session finished successfully ---")

    except Exception as e:
        logger.exception("A fatal error occurred in main: %s", e)
        traceback.print_exc()
        sys.exit(1)
    finally:
        logger.info("--- Bot session ended ---")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n🚫 Interrupted by user. Exiting.")
        sys.exit(0)