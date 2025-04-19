import sys

# ANSI color codes
GREEN = '\033[0;32m'
RED = '\033[0;31m'
YELLOW = '\033[0;33m'
BLUE = '\033[0;34m'
NC = '\033[0m'  # No Color


def print_status(message):
    print(f"{GREEN}[INFO]{NC} {message}")


def print_error(message):
    print(f"{RED}[ERROR]{NC} {message}", file=sys.stderr)


def print_warning(message):
    print(f"{YELLOW}[WARNING]{NC} {message}")


def print_info(message):
    print(f"{BLUE}[INFO]{NC} {message}") 