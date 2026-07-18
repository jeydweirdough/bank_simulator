"""Account entity representation for the Python Banking Management System.

This module models a bank account, maintaining attributes like card numbers, owners,
balances, failed attempts, and the history of transactions.
"""

from typing import Any, Dict, List
from transactions import Transaction
from utils import generate_timestamp


class Account:
    """Represents a bank account with CRUD mapping utilities."""

    def __init__(
        self,
        account_id: int,
        card_number: str,
        owner: str,
        pin: str,
        balance: float,
        interest_rate: float = 0.03,
        created_at: str = None,
        updated_at: str = None,
        failed_attempts: int = 0,
        locked: bool = False,
        locked_until: str = None,
        transactions: List[Transaction] = None,
    ) -> None:
        """Initialize an Account instance.

        Args:
            account_id: Unique database ID for the account.
            card_number: Unique 16-digit card number.
            owner: Account owner's name.
            pin: 6-digit PIN string.
            balance: Initial deposit or current balance.
            interest_rate: Default interest rate.
            created_at: ISO timestamp of account creation.
            updated_at: ISO timestamp of last update.
            failed_attempts: Sequential failed login count.
            locked: Lock status of the account.
            locked_until: Timestamp when lockout expires.
            transactions: History of Transaction objects.
        """
        now = generate_timestamp()
        self.id = account_id
        self.card_number = card_number
        self.owner = owner
        self.pin = pin
        self.balance = float(balance)
        self.interest_rate = float(interest_rate)
        self.created_at = created_at if created_at else now
        self.updated_at = updated_at if updated_at else now
        self.failed_attempts = failed_attempts
        self.locked = locked
        self.locked_until = locked_until
        self.transactions = transactions if transactions is not None else []

    def to_dict(self) -> Dict[str, Any]:
        """Serialize Account details for database storage.

        Returns:
            A dictionary representation of the account.
        """
        return {
            "id": self.id,
            "owner": self.owner,
            "pin": self.pin,
            "balance": self.balance,
            "interest_rate": self.interest_rate,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "failed_attempts": self.failed_attempts,
            "locked": self.locked,
            "locked_until": self.locked_until,
            "transactions": [tx.to_dict() for tx in self.transactions],
        }

    @classmethod
    def from_dict(cls, card_number: str, data: Dict[str, Any]) -> "Account":
        """Deserialize an Account dictionary to an Account instance.

        Args:
            card_number: The 16-digit card number associated with the account.
            data: The deserialized JSON object for the account.

        Returns:
            A populated Account object.
        """
        transactions_list = []
        for tx_data in data.get("transactions", []):
            transactions_list.append(Transaction.from_dict(tx_data))

        return cls(
            account_id=int(data["id"]),
            card_number=str(card_number),
            owner=str(data["owner"]),
            pin=str(data["pin"]),
            balance=float(data["balance"]),
            interest_rate=float(data.get("interest_rate", 0.03)),
            created_at=str(data["created_at"]),
            updated_at=str(data["updated_at"]),
            failed_attempts=int(data.get("failed_attempts", 0)),
            locked=bool(data.get("locked", False)),
            locked_until=data.get("locked_until"),
            transactions=transactions_list,
        )

    def add_transaction(self, tx: Transaction) -> None:
        """Append a transaction to the history and update the account balance.

        Args:
            tx: The transaction entry to add.
        """
        import hashlib
        if not tx.previous_hash:
            if self.transactions:
                tx.previous_hash = self.transactions[-1].hash
            else:
                tx.previous_hash = "0"

        if not tx.hash:
            payload = f"{tx.id}|{tx.type}|{str(float(tx.amount))}|{str(float(tx.previous_balance))}|{str(float(tx.balance))}|{tx.timestamp}|{tx.previous_hash}|{tx.partner_card}"
            tx.hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

        self.transactions.append(tx)
        self.balance = tx.balance
        self.updated_at = generate_timestamp()

    def increment_failed_attempts(self, max_attempts: int) -> None:
        """Increment failed attempts and lock the account if threshold is met.

        Args:
            max_attempts: Number of allowed attempts before locking.
        """
        from utils import get_simulated_datetime
        from datetime import timedelta
        self.failed_attempts += 1
        if self.failed_attempts >= max_attempts:
            self.locked = True
            self.locked_until = (get_simulated_datetime() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
        self.updated_at = generate_timestamp()

    def reset_failed_attempts(self) -> None:
        """Reset failed attempts count (upon successful login)."""
        self.failed_attempts = 0
        self.updated_at = generate_timestamp()

    def unlock(self) -> None:
        """Unlock the account and reset failed login attempts."""
        self.locked = False
        self.locked_until = None
        self.failed_attempts = 0
        self.updated_at = generate_timestamp()
