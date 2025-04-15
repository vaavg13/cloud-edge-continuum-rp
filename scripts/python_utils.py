#!/usr/bin/env python3

"""
Utility functions for Python scripts
"""

import sys
import shutil
import subprocess


def print_status(message):
    """Print a status message"""
    print(f"\033[1;34m[INFO]\033[0m {message}")


def print_error(message):
    """Print an error message"""
    print(f"\033[1;31m[ERROR]\033[0m {message}", file=sys.stderr)


def print_warning(message):
    """Print a warning message"""
    print(f"\033[1;33m[WARNING]\033[0m {message}")


def print_success(message):
    """Print a success message"""
    print(f"\033[1;32m[SUCCESS]\033[0m {message}")


def check_command(command):
    """Check if a command is available in the system"""
    if shutil.which(command) is None:
        print_error(f"Command '{command}' not found. Please install it and try again.")
        return False
    return True


def run_command(command, shell=False, check=True, capture_output=False, text=True):
    """Run a command and return the result"""
    try:
        result = subprocess.run(
            command,
            shell=shell,
            check=check,
            capture_output=capture_output,
            text=text
        )
        return result
    except subprocess.CalledProcessError as e:
        print_error(f"Command failed with error code {e.returncode}")
        if e.stdout:
            print(f"Command output: {e.stdout}")
        if e.stderr:
            print(f"Command error: {e.stderr}")
        return e
    except Exception as e:
        print_error(f"Failed to execute command: {e}")
        return None 