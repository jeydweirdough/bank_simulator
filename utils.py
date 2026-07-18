"""Utility functions for the Python Banking Management System.

This module provides common utilities such as clearing the screen, generating card
numbers and transaction IDs, validating input data, and prompting user inputs safely.
"""

import os
import random
import json
from datetime import datetime, timedelta
from typing import Collection


def clear_screen() -> None:
    """Clear the console screen depending on the operating system."""
    os.system("cls" if os.name == "nt" else "clear")


def pause_screen() -> None:
    """Pause execution until the user presses Enter."""
    input("\nPress Enter to continue...")


def generate_card_number(existing_cards: Collection[str]) -> str:
    """Generate a unique 16-digit card number.

    Args:
        existing_cards: A collection of already existing card numbers to ensure uniqueness.

    Returns:
        A unique 16-digit numeric string.
    """
    while True:
        # Generate 16 random digits
        card_num = "".join(str(random.randint(0, 9)) for _ in range(16))
        # Ensure it doesn't start with 0 (traditional for card numbers) and is unique
        if card_num[0] != "0" and card_num not in existing_cards:
            return card_num


def generate_transaction_id(existing_ids: Collection[int]) -> int:
    """Generate a unique transaction ID.

    Args:
        existing_ids: A collection of already used transaction IDs.

    Returns:
        A unique integer transaction ID.
    """
    while True:
        tx_id = random.randint(100000, 999999)
        if tx_id not in existing_ids:
            return tx_id


def generate_timestamp() -> str:
    """Generate the current timestamp formatted as YYYY-MM-DD HH:MM:SS.

    Returns:
        A formatted string of the current date and time.
    """
    return get_simulated_datetime().strftime("%Y-%m-%d %H:%M:%S")


def validate_pin(pin: str) -> bool:
    """Check if the PIN is exactly 6 digits.

    Args:
        pin: The PIN string to validate.

    Returns:
        True if valid, False otherwise.
    """
    return len(pin) == 6 and pin.isdigit()


def validate_name(name: str) -> bool:
    """Check if the name is non-empty and contains only letters and spaces.

    Args:
        name: The name string to validate.

    Returns:
        True if valid, False otherwise.
    """
    cleaned = name.strip()
    if not cleaned:
        return False
    # Check if name contains only alphabetic characters and spaces
    return all(char.isalpha() or char.isspace() for char in cleaned)


def prompt_string(prompt_text: str, allow_empty: bool = False) -> str:
    """Prompt the user for a string and optionally ensure it is not empty.

    Args:
        prompt_text: The message to show to the user.
        allow_empty: Whether empty string input is acceptable.

    Returns:
        The stripped string entered by the user.
    """
    while True:
        try:
            val = input(prompt_text).strip()
            if not allow_empty and not val:
                print("Error: Input cannot be empty. Please try again.")
                continue
            return val
        except (KeyboardInterrupt, SystemExit):
            print("\nOperation cancelled.")
            raise
        except Exception as e:
            print(f"Error reading input: {e}. Please try again.")


def prompt_int(prompt_text: str, min_val: int = None, max_val: int = None) -> int:
    """Prompt the user for an integer, validating constraints.

    Args:
        prompt_text: The message to show to the user.
        min_val: Optional minimum value (inclusive).
        max_val: Optional maximum value (inclusive).

    Returns:
        The validated integer.
    """
    while True:
        val_str = prompt_string(prompt_text)
        try:
            val = int(val_str)
            if min_val is not None and val < min_val:
                print(f"Error: Value must be at least {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"Error: Value cannot exceed {max_val}.")
                continue
            return val
        except ValueError:
            print("Error: Invalid integer. Please enter a whole number.")


def prompt_float(prompt_text: str, min_val: float = None, max_val: float = None) -> float:
    """Prompt the user for a float, validating constraints.

    Args:
        prompt_text: The message to show to the user.
        min_val: Optional minimum value (inclusive).
        max_val: Optional maximum value (inclusive).

    Returns:
        The validated float.
    """
    while True:
        val_str = prompt_string(prompt_text)
        try:
            # Handle decimals properly
            val = float(val_str)
            if min_val is not None and val < min_val:
                print(f"Error: Value must be at least {min_val}.")
                continue
            if max_val is not None and val > max_val:
                print(f"Error: Value cannot exceed {max_val}.")
                continue
            return val
        except ValueError:
            print("Error: Invalid decimal number. Please enter a valid float.")


def get_simulated_datetime() -> datetime:
    """Get the current datetime, adjusted by any simulated offset from sim_time.json."""
    base_dir = os.path.dirname(os.path.abspath(__file__))
    sim_path = os.path.join(base_dir, "sim_time.json")
    
    if os.path.exists(sim_path):
        try:
            with open(sim_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                days_offset = data.get("days_offset", 0)
                return datetime.now() + timedelta(days=days_offset)
        except Exception:
            pass
    return datetime.now()


def get_simulated_date_str() -> str:
    """Get the simulated date only, formatted as YYYY-MM-DD."""
    return get_simulated_datetime().strftime("%Y-%m-%d")
