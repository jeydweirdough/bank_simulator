"""Authentication and session management for the Python Banking Management System.

This module handles session tracking for both standard accounts and admin logins,
managing failed attempt counters and locking mechanisms.
"""

from typing import Dict, Optional, Tuple
from accounts import Account
from constants import ADMIN_PASSWORD, ADMIN_USERNAME, MAX_FAILED_ATTEMPTS
from storage import Storage


class SessionManager:
    """Manages active login sessions and coordinates authentication attempts."""

    def __init__(self, storage: Storage) -> None:
        """Initialize the SessionManager with a reference to the storage layer.

        Args:
            storage: Reference to storage manager.
        """
        self.storage = storage
        self.current_user: Optional[Account] = None
        self.admin_logged_in: bool = False

    def login_user(self, card_number: str, pin: str) -> Tuple[bool, str]:
        """Authenticate a user using card number and PIN.

        Handles account locking on consecutive failed attempts.

        Args:
            card_number: The 16-digit card number.
            pin: The 4-digit PIN string.

        Returns:
            A tuple of (success_status, message).
        """
        # Always fetch fresh data to avoid concurrency/stale state issues
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number not in accounts_data:
            return False, "Account with this card number does not exist."

        account_data = accounts_data[card_number]
        # Deserialize into Account object
        account = Account.from_dict(card_number, account_data)

        if account.locked:
            if account.locked_until:
                from utils import get_simulated_datetime
                from datetime import datetime
                try:
                    locked_until_dt = datetime.strptime(account.locked_until, "%Y-%m-%d %H:%M:%S")
                    current_dt = get_simulated_datetime()
                    if current_dt >= locked_until_dt:
                        # Auto-unlock!
                        account.unlock()
                        accounts_data[card_number] = account.to_dict()
                        self.storage.save_data(db)
                    else:
                        remaining = locked_until_dt - current_dt
                        days = remaining.days
                        hours, remainder = divmod(remaining.seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        # Build formatted countdown string
                        parts = []
                        if days > 0:
                            parts.append(f"{days} day(s)")
                        if hours > 0:
                            parts.append(f"{hours} hour(s)")
                        if minutes > 0:
                            parts.append(f"{minutes} minute(s)")
                        if not parts:
                            parts.append(f"{seconds} second(s)")
                        time_str = ", ".join(parts)
                        return False, f"This account is locked due to 3 wrong retries. Please try again in {time_str}."
                except Exception:
                    pass

            if account.locked:
                return False, "This account is locked. Please contact an Administrator."

        if account.pin == pin:
            account.reset_failed_attempts()
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)
            self.current_user = account
            return True, f"Successfully logged in. Welcome, {account.owner}!"
        else:
            account.increment_failed_attempts(MAX_FAILED_ATTEMPTS)
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)

            if account.locked:
                return False, "Incorrect PIN. This account has now been locked due to 3 failed attempts."
            
            remaining = MAX_FAILED_ATTEMPTS - account.failed_attempts
            return False, f"Incorrect PIN. You have {remaining} attempts remaining before lock."

    def login_admin(self, username: str, password: str) -> bool:
        """Authenticate as administrator.

        Args:
            username: Admin username.
            password: Admin password.

        Returns:
            True if credentials match, False otherwise.
        """
        if username == ADMIN_USERNAME and password == ADMIN_PASSWORD:
            self.admin_logged_in = True
            return True
        return False

    def logout(self) -> None:
        """Clear active user and admin login states."""
        self.current_user = None
        self.admin_logged_in = False

    def is_user_logged_in(self) -> bool:
        """Check if a standard user is currently authenticated.

        Returns:
            True if a user is logged in, False otherwise.
        """
        return self.current_user is not None

    def is_admin_logged_in(self) -> bool:
        """Check if an administrator is currently authenticated.

        Returns:
            True if the admin is logged in, False otherwise.
        """
        return self.admin_logged_in
