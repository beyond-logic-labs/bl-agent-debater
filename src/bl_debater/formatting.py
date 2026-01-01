"""Terminal formatting utilities."""

# ANSI colors
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

def print_header(text: str):
    """Print a header."""
    print(f"\n{YELLOW}{'='*50}{RESET}")
    print(f"{YELLOW}{BOLD}  {text}{RESET}")
    print(f"{YELLOW}{'='*50}{RESET}\n")

def print_success(text: str):
    """Print success message."""
    print(f"{GREEN}{BOLD}{text}{RESET}")

def print_error(text: str):
    """Print error message."""
    print(f"{RED}{BOLD}Error: {text}{RESET}")

def print_info(text: str):
    """Print info message."""
    print(f"{CYAN}{text}{RESET}")

def print_warning(text: str):
    """Print warning message."""
    print(f"{YELLOW}{BOLD}Warning: {text}{RESET}")

def print_waiting(text: str):
    """Print waiting message."""
    print(f"{DIM}{text}{RESET}", end="\r")
