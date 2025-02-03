from datetime import datetime
from colorama import Fore, Style

# Logging functions

def log_info(message):
    """Log essential informational messages."""
    print(f"ℹ️ {datetime.now()} - {message}")

def log_warning(message):
    """Log warning messages."""
    print(f"⚠️ {datetime.now()} - {message}")

def log_error(message):
    """Log error messages."""
    print(f"❌ {datetime.now()} - {message}")

def log_debug(message):
    """Log debug messages."""
    print(f"🔍 {datetime.now()} - {message}")


# Logging functions for Main.py

def log_action_main(action: str, detail: str = "", request_id: str = ""):
    print(f"✅ {Fore.GREEN}[{datetime.now()}] [ACTION] [RequestID: {request_id}] {action}{Style.RESET_ALL} - {detail}")

def log_error_main(error: str, detail: str = "", request_id: str = ""):
    print(f"❗ {Fore.RED}[{datetime.now()}] [ERROR] [RequestID: {request_id}] {error}{Style.RESET_ALL} - {detail}")

def log_info_main(info: str, detail: str = "", request_id: str = ""):
    print(f"ℹ️ {Fore.CYAN}[{datetime.now()}] [INFO] [RequestID: {request_id}] {info}{Style.RESET_ALL} - {detail}")

def log_divider_main(title: str):
    print(f"\n{'=' * 10} {title} {'=' * 10}\n")


