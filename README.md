# Python Playwright Account Registration Bot

A Python automation script for activating phone numbers via registration, for educational purposes only.

![Python Version](https://img.shields.io/badge/python-3.9%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

> **⚠️ Disclaimer: For Educational Use Only**
>
> This script is provided strictly for educational purposes and as a proof-of-concept for browser automation. The author is not responsible for any misuse of this code. Using this script for spam, malicious activities, or any action that violates the terms of service of any website is strictly prohibited. **You are solely responsible for your actions.**

---

## 🚀 Features

* **Automated Signup:** Fully automates the account registration workflow.
* **Playwright Driven:** Uses modern Playwright for robust and reliable browser control.
* **Auto-Dependency Install:** A setup script checks and installs required `pip` packages (like `playwright`, `faker`) and browser binaries on first run.
* **Dynamic Data:** Uses `faker` to generate realistic user data (names, emails, strong passwords) for each run.
* **Batch Processing:** Reads a list of phone numbers from `numbers.txt` and processes them sequentially.
* **CSV Output:** Saves detailed results of every attempt (success or failure) to `created_accounts_with_phone.csv`.
* **Performance Optimized:** Blocks heavy, non-essential resources (images, fonts, trackers) to speed up page loads.
* **Clean Architecture:** Built using OOP principles, a Page Object Model (POM), and Dependency Injection for easy maintenance and scalability.

---

## 🏗️ Architecture Overview

This script is not just a simple linear script; it's structured using professional design patterns:

* **`BotConfig`:** A dataclass holding all static configuration (URLs, filenames, timeouts).
* **`Page Object Model (POM)`:**
    * `BasePage`: Contains common utilities like `robust_goto` and popup closing.
    * `SignUpPage`: Manages all locators and actions for the main registration form.
    * `PhoneVerificationPage`: Manages locators and actions for the phone verification step.
* **`DataGenerator`:** A dedicated class for creating fake `AccountData`.
* **`IOutputWriter`:** An abstract interface for writing results, making it easy to swap (e.g., from `CsvOutputWriter` to a database writer).
* **`AccountCreator`:** The main orchestrator that injects and coordinates all the other services.



---

## 🔧 Setup & Installation

1.  **Clone the repository:**
    ```bash
    git clone [https://github.com/YOUR_USERNAME/YOUR_REPONAME.git](https://github.com/YOUR_USERNAME/YOUR_REPONAME.git)
    cd YOUR_REPONAME
    ```

2.  **Ensure Python 3.9+ is installed.**

3.  **Run the script:**
    The script handles its own setup. The first time you run it, it will automatically:
    * Install `playwright`, `faker`, and `requests` using `pip`.
    * Run `playwright install --with-deps` to download the required browser binaries.

---

## ⚙️ How to Use

1.  **Create `numbers.txt`:**
    Create a file named `numbers.txt` in the same directory. Add the phone numbers you want to process, with **one number per line**.

    ```
    +1234567890
    +1234567891
    +1234567892
    ```

2.  **(Optional) Tweak Configuration:**
    Open the Python script and modify the `BotConfig` class at the top of the file to change settings like `HEADLESS`, timeouts, or file paths.

    ```python
    @dataclass
    class BotConfig:
        SIGNUP_URL: str = "[https://app.calebandbrown.com/signup](https://app.calebandbrown.com/signup)"
        NUMBERS_FILE: str = "numbers.txt"
        OUTPUT_CSV: str = "created_accounts_with_phone.csv"
        LOG_FILE: str = "caleb_playwright_pro_final.log"
        
        HEADLESS: bool = False # Set to True for background running
        ...
    ```

3.  **Run the Bot:**
    ```bash
    python your_script_name.py
    ```

4.  **Check Results:**
    All results, including generated data and success/failure notes, will be saved in `created_accounts_with_phone.csv`.

---

## 📄 License

This project is licensed under the MIT License. See the `LICENSE` file for details.
