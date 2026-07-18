"""Core banking services for the Python Banking Management System.

This module implements transactions, account creations, deposits, withdrawals,
transfers, interest accumulation, fee charging, and database searches.
"""

from typing import Any, Dict, List, Optional, Tuple
from accounts import Account
from storage import Storage
from transactions import Transaction
from utils import (
    generate_card_number,
    generate_transaction_id,
    generate_timestamp,
)


class BankService:
    """Contains business logic for accounts, transfers, interest, fees, and statistics."""

    def __init__(self, storage: Storage) -> None:
        """Initialize BankService with storage.

        Args:
            storage: Storage instances for persistence.
        """
        self.storage = storage

    def _get_all_card_numbers(self, db_data: Dict[str, Any]) -> List[str]:
        """Collect all existing card numbers to ensure uniqueness."""
        return list(db_data.get("accounts", {}).keys())

    def _get_all_transaction_ids(self, db_data: Dict[str, Any]) -> List[int]:
        """Collect all transaction IDs across all accounts to ensure global uniqueness."""
        tx_ids = []
        for account_data in db_data.get("accounts", {}).values():
            for tx in account_data.get("transactions", []):
                tx_ids.append(tx["id"])
        return tx_ids

    def _get_next_account_id(self, db_data: Dict[str, Any]) -> int:
        """Calculate the next incremental account ID."""
        max_id = 0
        for account_data in db_data.get("accounts", {}).values():
            max_id = max(max_id, account_data.get("id", 0))
        return max_id + 1

    def create_account(self, owner: str, pin: str, initial_deposit: float) -> Tuple[Account, str]:
        """Create a new bank account with an initial deposit.

        Args:
            owner: The full name of the account holder.
            pin: A validated 4-digit PIN string.
            initial_deposit: Initial balance to seed the account.

        Returns:
            A tuple of (created_account, message).
        """
        db = self.storage.load_data()
        accounts_data = db.setdefault("accounts", {})

        # Generate unique card number and account ID
        existing_cards = self._get_all_card_numbers(db)
        card_number = generate_card_number(existing_cards)
        account_id = self._get_next_account_id(db)

        # Create account instance
        account = Account(
            account_id=account_id,
            card_number=card_number,
            owner=owner,
            pin=pin,
            balance=0.0,  # Starts at 0, updated via transaction
        )

        # Record account creation transaction
        existing_tx_ids = self._get_all_transaction_ids(db)
        tx_id = generate_transaction_id(existing_tx_ids)
        timestamp = generate_timestamp()

        creation_tx = Transaction(
            id=tx_id,
            type="Account Creation",
            amount=initial_deposit,
            previous_balance=0.0,
            balance=initial_deposit,
            timestamp=timestamp,
        )
        account.add_transaction(creation_tx)

        # Save to database
        accounts_data[card_number] = account.to_dict()
        self.storage.save_data(db)

        return account, f"Account successfully created!\nCard Number: {card_number}\nPIN: {pin}"

    def deposit(self, card_number: str, amount: float) -> Tuple[bool, str]:
        """Deposit money into a user's account.

        Args:
            card_number: The account's card number.
            amount: Non-negative amount to deposit.

        Returns:
            A tuple of (success_status, message).
        """
        if amount <= 0:
            return False, "Deposit amount must be a positive number."

        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number not in accounts_data:
            return False, "Account not found."

        account = Account.from_dict(card_number, accounts_data[card_number])
        previous_balance = account.balance

        # Generate transaction
        existing_tx_ids = self._get_all_transaction_ids(db)
        tx_id = generate_transaction_id(existing_tx_ids)
        new_balance = previous_balance + amount

        tx = Transaction(
            id=tx_id,
            type="Deposit",
            amount=amount,
            previous_balance=previous_balance,
            balance=new_balance,
            timestamp=generate_timestamp(),
        )
        account.add_transaction(tx)

        accounts_data[card_number] = account.to_dict()
        self.storage.save_data(db)

        return True, f"Successfully deposited ${amount:.2f}. New Balance: ${new_balance:.2f}"

    def withdraw(self, card_number: str, amount: float) -> Tuple[bool, str]:
        """Withdraw money from a user's account with overdraft protection.

        Args:
            card_number: The account's card number.
            amount: Non-negative amount to withdraw.

        Returns:
            A tuple of (success_status, message).
        """
        if amount <= 0:
            return False, "Withdrawal amount must be a positive number."

        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number not in accounts_data:
            return False, "Account not found."

        account = Account.from_dict(card_number, accounts_data[card_number])
        if account.locked:
            return False, "Account is locked. Cannot withdraw."

        previous_balance = account.balance
        if previous_balance < amount:
            return False, f"Insufficient funds. Current Balance: ${previous_balance:.2f}"

        # Generate transaction
        existing_tx_ids = self._get_all_transaction_ids(db)
        tx_id = generate_transaction_id(existing_tx_ids)
        new_balance = previous_balance - amount

        tx = Transaction(
            id=tx_id,
            type="Withdrawal",
            amount=amount,
            previous_balance=previous_balance,
            balance=new_balance,
            timestamp=generate_timestamp(),
        )
        account.add_transaction(tx)

        accounts_data[card_number] = account.to_dict()
        self.storage.save_data(db)

        return True, f"Successfully withdrew ${amount:.2f}. New Balance: ${new_balance:.2f}"

    def transfer(self, sender_card: str, receiver_card: str, amount: float) -> Tuple[bool, str]:
        """Transfer money between two accounts.

        Args:
            sender_card: The card number of the sender.
            receiver_card: The card number of the recipient.
            amount: Positive amount to transfer.

        Returns:
            A tuple of (success_status, message).
        """
        if amount <= 0:
            return False, "Transfer amount must be a positive number."

        if sender_card == receiver_card:
            return False, "You cannot transfer money to your own account."

        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if sender_card not in accounts_data:
            return False, "Sender account not found."
        if receiver_card not in accounts_data:
            return False, "Recipient account not found."

        sender = Account.from_dict(sender_card, accounts_data[sender_card])
        receiver = Account.from_dict(receiver_card, accounts_data[receiver_card])

        if sender.locked:
            return False, "Sender account is locked. Operation cancelled."
        if receiver.locked:
            return False, "Recipient account is locked. Operation cancelled."

        if sender.balance < amount:
            return False, f"Insufficient funds for transfer. Current Balance: ${sender.balance:.2f}"

        # Deduct from Sender
        sender_prev = sender.balance
        sender_new = sender_prev - amount

        # Deposit to Receiver
        receiver_prev = receiver.balance
        receiver_new = receiver_prev + amount

        # Create unique transactions
        existing_tx_ids = self._get_all_transaction_ids(db)
        tx_id_sender = generate_transaction_id(existing_tx_ids)
        # Add sender ID to existing list to prevent duplicate in recipient transaction
        existing_tx_ids.append(tx_id_sender)
        tx_id_receiver = generate_transaction_id(existing_tx_ids)

        timestamp = generate_timestamp()

        sender_tx = Transaction(
            id=tx_id_sender,
            type="Transfer Out",
            amount=amount,
            previous_balance=sender_prev,
            balance=sender_new,
            timestamp=timestamp,
            partner_card=receiver_card,
        )
        sender.add_transaction(sender_tx)

        receiver_tx = Transaction(
            id=tx_id_receiver,
            type="Transfer In",
            amount=amount,
            previous_balance=receiver_prev,
            balance=receiver_new,
            timestamp=timestamp,
            partner_card=sender_card,
        )
        receiver.add_transaction(receiver_tx)

        # Update DB
        accounts_data[sender_card] = sender.to_dict()
        accounts_data[receiver_card] = receiver.to_dict()
        self.storage.save_data(db)

        return True, f"Successfully transferred ${amount:.2f} to {receiver.owner}."

    def apply_interest(self, custom_rate: Optional[float] = None, card_number: Optional[str] = None) -> Tuple[bool, str]:
        """Apply interest based on a rate (balance * rate).

        Can be applied to a specific account or to all accounts in the database.

        Args:
            custom_rate: Optional decimal interest rate (e.g. 0.03 for 3%). If omitted, uses stored account rate.
            card_number: Optional card number to restrict application to a single account.

        Returns:
            A tuple of (success_status, message).
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if not accounts_data:
            return False, "No accounts found in database."

        existing_tx_ids = self._get_all_transaction_ids(db)
        timestamp = generate_timestamp()

        # If a single account is targeted
        if card_number is not None:
            if card_number not in accounts_data:
                return False, "Target account not found."
            
            account = Account.from_dict(card_number, accounts_data[card_number])
            rate = custom_rate if custom_rate is not None else account.interest_rate
            interest_earned = account.balance * rate

            prev_balance = account.balance
            new_balance = prev_balance + interest_earned

            tx_id = generate_transaction_id(existing_tx_ids)
            interest_tx = Transaction(
                id=tx_id,
                type="Interest",
                amount=interest_earned,
                previous_balance=prev_balance,
                balance=new_balance,
                timestamp=timestamp,
            )
            account.add_transaction(interest_tx)
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)
            return True, f"Applied interest of ${interest_earned:.2f} ({rate*100:.1f}%) to {account.owner}."

        # Apply to all accounts
        count = 0
        total_interest = 0.0
        for c_num, data in accounts_data.items():
            account = Account.from_dict(c_num, data)
            rate = custom_rate if custom_rate is not None else account.interest_rate
            interest_earned = account.balance * rate
            
            prev_balance = account.balance
            new_balance = prev_balance + interest_earned

            tx_id = generate_transaction_id(existing_tx_ids)
            existing_tx_ids.append(tx_id)  # prevent duplication within the loop

            interest_tx = Transaction(
                id=tx_id,
                type="Interest",
                amount=interest_earned,
                previous_balance=prev_balance,
                balance=new_balance,
                timestamp=timestamp,
            )
            account.add_transaction(interest_tx)
            accounts_data[c_num] = account.to_dict()
            total_interest += interest_earned
            count += 1

        self.storage.save_data(db)
        return True, f"Applied interest to {count} accounts. Total paid out: ${total_interest:.2f}"

    def apply_monthly_fee(self, amount: float) -> Tuple[bool, str]:
        """Apply a monthly maintenance fee to all accounts, preventing negative balances.

        Args:
            amount: The fee amount to charge.

        Returns:
            A tuple of (success_status, message).
        """
        if amount <= 0:
            return False, "Monthly fee must be a positive number."

        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if not accounts_data:
            return False, "No accounts found in database."

        existing_tx_ids = self._get_all_transaction_ids(db)
        timestamp = generate_timestamp()

        applied_count = 0
        skipped_count = 0
        total_charged = 0.0

        for c_num, data in accounts_data.items():
            account = Account.from_dict(c_num, data)
            prev_balance = account.balance

            # If account has no money, skip it entirely
            if prev_balance <= 0.0:
                skipped_count += 1
                continue

            # Deduct fee, ensuring balance does not drop below 0
            charge_amount = min(amount, prev_balance)
            new_balance = prev_balance - charge_amount

            tx_id = generate_transaction_id(existing_tx_ids)
            existing_tx_ids.append(tx_id)

            fee_tx = Transaction(
                id=tx_id,
                type="Maintenance Fee",
                amount=charge_amount,
                previous_balance=prev_balance,
                balance=new_balance,
                timestamp=timestamp,
            )
            account.add_transaction(fee_tx)
            accounts_data[c_num] = account.to_dict()
            total_charged += charge_amount
            applied_count += 1

        self.storage.save_data(db)
        return True, f"Fee charged: {applied_count} accounts. Skipped: {skipped_count}. Total collected: ${total_charged:.2f}."

    def delete_account(self, card_number: str) -> bool:
        """Permanently delete an account from the database.

        Args:
            card_number: The account's unique card number.

        Returns:
            True if deletion was successful, False otherwise.
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number in accounts_data:
            del accounts_data[card_number]
            self.storage.save_data(db)
            return True
        return False

    def unlock_account(self, card_number: str) -> bool:
        """Unlock an account and reset login attempts.

        Args:
            card_number: The card number to unlock.

        Returns:
            True if successfully unlocked, False otherwise.
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number in accounts_data:
            account = Account.from_dict(card_number, accounts_data[card_number])
            account.unlock()
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)
            return True
        return False

    def change_name(self, card_number: str, new_name: str) -> Tuple[bool, str]:
        """Update account owner's name.

        Args:
            card_number: User's card number.
            new_name: Valid name string.

        Returns:
            A tuple of (success_status, message).
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number in accounts_data:
            account = Account.from_dict(card_number, accounts_data[card_number])
            account.owner = new_name
            account.updated_at = generate_timestamp()
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)
            return True, "Name changed successfully."
        return False, "Account not found."

    def change_pin(self, card_number: str, new_pin: str) -> Tuple[bool, str]:
        """Update account PIN.

        Args:
            card_number: User's card number.
            new_pin: Validated 4-digit PIN string.

        Returns:
            A tuple of (success_status, message).
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if card_number in accounts_data:
            account = Account.from_dict(card_number, accounts_data[card_number])
            account.pin = new_pin
            account.updated_at = generate_timestamp()
            accounts_data[card_number] = account.to_dict()
            self.storage.save_data(db)
            return True, "PIN changed successfully."
        return False, "Account not found."

    def get_purchasing_power(self, balance: float, inflation_rate: float) -> float:
        """Calculate real purchasing power given an inflation rate (educational only).

        Args:
            balance: Current account balance.
            inflation_rate: Inflation rate percentage (e.g. 5 for 5%).

        Returns:
            The calculated purchasing power.
        """
        # Formula: balance / (1 + inflation_rate / 100)
        return balance / (1.0 + (inflation_rate / 100.0))

    def search_account(self, query: str) -> List[Account]:
        """Search accounts by owner name (case-insensitive substring) or card number (exact match).

        Args:
            query: The search term.

        Returns:
            A list of matching Account objects.
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})
        results = []

        for card_number, data in accounts_data.items():
            # Match card number exactly or owner case-insensitive substring
            if query == card_number or query.lower() in data.get("owner", "").lower():
                results.append(Account.from_dict(card_number, data))
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """Calculate banking statistics for admin review.

        Returns:
            A dictionary containing banking metrics.
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        total_users = len(accounts_data)
        total_money = sum(float(acc.get("balance", 0.0)) for acc in accounts_data.values())
        locked_accounts = sum(1 for acc in accounts_data.values() if acc.get("locked", False))

        return {
            "total_users": total_users,
            "total_money": total_money,
            "locked_accounts": locked_accounts,
        }

    def get_all_transactions(self) -> List[Dict[str, Any]]:
        """Collect all transactions from all accounts in the database.

        Returns:
            A list of all transactions with owner names and card numbers attached.
        """
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})
        all_txs = []

        for card_number, data in accounts_data.items():
            owner = data.get("owner", "Unknown")
            for tx_dict in data.get("transactions", []):
                # Copy transaction data and append owner info for readability
                tx_info = dict(tx_dict)
                tx_info["owner"] = owner
                tx_info["card_number"] = card_number
                all_txs.append(tx_info)

        # Sort transactions by timestamp (latest first) or transaction ID
        all_txs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return all_txs
