"""Transaction representation for the Python Banking Management System.

This module defines the Transaction dataclass which represents a single financial
log item in the account history, supporting serialization and deserialization.
"""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class Transaction:
    """Represents a banking transaction ledger entry."""

    id: int
    type: str  # e.g., "Deposit", "Withdrawal", "Transfer In", "Transfer Out", etc.
    amount: float
    previous_balance: float
    balance: float  # Serves as the new balance after the transaction
    timestamp: str
    hash: str = ""
    previous_hash: str = ""
    partner_card: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert the transaction instance to a dictionary for JSON serialization.

        Returns:
            A dictionary of transaction attributes.
        """
        return {
            "id": self.id,
            "type": self.type,
            "amount": float(self.amount),
            "previous_balance": float(self.previous_balance),
            "balance": float(self.balance),
            "timestamp": self.timestamp,
            "hash": self.hash,
            "previous_hash": self.previous_hash,
            "partner_card": self.partner_card,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Transaction":
        """Reconstruct a Transaction instance from a dictionary.

        Args:
            data: A dictionary containing transaction fields.

        Returns:
            A new instance of Transaction.
        """
        return cls(
            id=int(data["id"]),
            type=str(data["type"]),
            amount=float(data["amount"]),
            previous_balance=float(data.get("previous_balance", 0.0)),
            balance=float(data["balance"]),
            timestamp=str(data["timestamp"]),
            hash=str(data.get("hash", "")),
            previous_hash=str(data.get("previous_hash", "")),
            partner_card=str(data.get("partner_card", "")),
        )
