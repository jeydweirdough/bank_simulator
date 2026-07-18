"""Persistence layer for the Python Banking Management System.

This module manages the saving, loading, backing up, and restoring of account data
to/from JSON files, handling file errors and parsing exceptions gracefully.
"""

import json
import os
import shutil
from typing import Any, Dict


class Storage:
    """Handles JSON storage operations including loading, saving, backup, and restore."""

    def __init__(self, file_path: str, backup_path: str) -> None:
        """Initialize Storage with database and backup file paths.

        Args:
            file_path: Path to the main database JSON file.
            backup_path: Path to the backup JSON file.
        """
        self.file_path = file_path
        self.backup_path = backup_path
        self._ensure_db_exists()

    def _ensure_db_exists(self) -> None:
        """Create the database file with default skeleton structure if it doesn't exist."""
        if not os.path.exists(self.file_path):
            self.save_data({"accounts": {}})

    def load_data(self) -> Dict[str, Any]:
        """Load account data from the JSON file.

        Handles cases where file is empty, missing, or corrupted.

        Returns:
            The parsed dictionary representation of the database.
        """
        if not os.path.exists(self.file_path):
            return {"accounts": {}}

        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    return {"accounts": {}}
                db = json.loads(content)
        except (FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            print(f"\n[Warning] Database read error or corruption detected: {e}.")
            print("Initializing clean/empty data structure.")
            # Return a default clean state
            db = {"accounts": {}}
            self.save_data(db)
            return db

        # Run blockchain audit & self-healing
        if self._heal_database(db):
            print("[Blockchain System] Saved self-healed/migrated database to disk.")
            self.save_data(db)

        return db

    def _heal_database(self, db: Dict[str, Any]) -> bool:
        """Audit the transaction history and self-heal any tampering using blockchain links.
        Also automatically migrates 4-digit PINs to 6-digit by appending '00'.
        """
        import hashlib
        import random
        repaired = False

        accounts_data = db.setdefault("accounts", {})

        # Phase 0: Migrate legacy 4-digit PINs to 6-digit PINs (append '00')
        for card_number, acc_data in accounts_data.items():
            pin = acc_data.get("pin", "")
            if len(pin) == 4:
                acc_data["pin"] = pin + "00"
                repaired = True

        # Phase 1: Ensure partner_card is set for existing transfer transactions
        for card_number, acc_data in accounts_data.items():
            for tx in acc_data.setdefault("transactions", []):
                if tx.get("type") in ["Transfer In", "Transfer Out"] and not tx.get("partner_card"):
                    # Search for matching transfer in other accounts
                    partner_type = "Transfer In" if tx["type"] == "Transfer Out" else "Transfer Out"
                    for other_card, other_acc in accounts_data.items():
                        if other_card == card_number:
                            continue
                        for other_tx in other_acc.get("transactions", []):
                            if (other_tx.get("type") == partner_type and
                                abs(float(other_tx.get("amount", 0)) - float(tx.get("amount", 0))) < 0.001 and
                                other_tx.get("timestamp") == tx.get("timestamp") and
                                not other_tx.get("partner_card")):
                                tx["partner_card"] = other_card
                                other_tx["partner_card"] = card_number
                                repaired = True
                                break

        # Helper to compute transaction hash
        def get_expected_hash(tx: dict) -> str:
            payload = f"{tx.get('id')}|{tx.get('type')}|{str(float(tx.get('amount', 0)))}|{str(float(tx.get('previous_balance', 0)))}|{str(float(tx.get('balance', 0)))}|{tx.get('timestamp')}|{tx.get('previous_hash', '')}|{tx.get('partner_card', '')}"
            return hashlib.sha256(payload.encode("utf-8")).hexdigest()

        # Helper to check if a transaction hash matches its contents
        def is_hash_valid(tx: dict) -> bool:
            if not tx.get("hash"):
                return False
            return tx.get("hash") == get_expected_hash(tx)

        # Phase 2: Detect tampered transactions and heal them from their counterparty partner's records
        for card_number, acc_data in accounts_data.items():
            transactions = acc_data.get("transactions", [])
            for i, tx in enumerate(transactions):
                tx_type = tx.get("type")
                # Check hash validity and chaining
                hash_valid = is_hash_valid(tx)
                chain_valid = (i == 0 and tx.get("previous_hash") == "0") or (i > 0 and tx.get("previous_hash") == transactions[i-1].get("hash"))
                
                if not hash_valid or not chain_valid:
                    # Tampering detected!
                    print(f"\n[Blockchain Audit] Tampering detected in card {card_number} at transaction ID {tx.get('id')}.")
                    
                    if tx_type in ["Transfer In", "Transfer Out"] and tx.get("partner_card"):
                        partner_card = tx["partner_card"]
                        partner_acc = accounts_data.get(partner_card)
                        if partner_acc:
                            partner_type = "Transfer In" if tx_type == "Transfer Out" else "Transfer Out"
                            # Find the matching partner transaction that is valid
                            found_partner = None
                            for p_tx in partner_acc.get("transactions", []):
                                if (p_tx.get("type") == partner_type and
                                    p_tx.get("partner_card") == card_number and
                                    abs(float(p_tx.get("amount", 0)) - float(tx.get("amount", 0))) < 0.001 and
                                    p_tx.get("timestamp") == tx.get("timestamp") and
                                    is_hash_valid(p_tx)):
                                    found_partner = p_tx
                                    break
                            
                            if found_partner:
                                print(f"[Blockchain Audit] Restoring transaction ID {tx.get('id')} from partner card {partner_card}.")
                                tx["amount"] = found_partner["amount"]
                                tx["timestamp"] = found_partner["timestamp"]
                                tx["partner_card"] = partner_card
                                tx["hash"] = "" # Will force recalculation of hashes
                                repaired = True

        # Phase 3: Detect deleted transaction records (exist in B but deleted in A)
        for card_number, acc_data in accounts_data.items():
            transactions = acc_data.get("transactions", [])
            for tx in transactions:
                tx_type = tx.get("type")
                if tx_type in ["Transfer In", "Transfer Out"] and tx.get("partner_card") and is_hash_valid(tx):
                    partner_card = tx["partner_card"]
                    partner_acc = accounts_data.get(partner_card)
                    if partner_acc:
                        partner_type = "Transfer In" if tx_type == "Transfer Out" else "Transfer Out"
                        # Look for corresponding transaction
                        has_partner = False
                        for p_tx in partner_acc.get("transactions", []):
                            if (p_tx.get("type") == partner_type and
                                p_tx.get("partner_card") == card_number and
                                abs(float(p_tx.get("amount", 0)) - float(tx.get("amount", 0))) < 0.001 and
                                p_tx.get("timestamp") == tx.get("timestamp")):
                                has_partner = True
                                break
                        
                        if not has_partner:
                            # Recreate the deleted transaction in partner's account
                            print(f"\n[Blockchain Audit] Transaction ID {tx.get('id')} was deleted from card {partner_card}. Re-creating from card {card_number}...")
                            all_tx_ids = []
                            for ac in accounts_data.values():
                                for t in ac.get("transactions", []):
                                    all_tx_ids.append(t.get("id"))
                            
                            new_id = random.randint(100000, 999999)
                            while new_id in all_tx_ids:
                                new_id = random.randint(100000, 999999)
                            
                            new_partner_tx = {
                                "id": new_id,
                                "type": partner_type,
                                "amount": tx["amount"],
                                "previous_balance": 0.0,
                                "balance": 0.0,
                                "timestamp": tx["timestamp"],
                                "hash": "",
                                "previous_hash": "",
                                "partner_card": card_number
                            }
                            partner_acc["transactions"].append(new_partner_tx)
                            repaired = True

        # Phase 4: If any repairs occurred or if new transactions have empty hashes, rebuild balance lists & sign hashes
        # We always verify the hash validation and sign them if empty to bootstrap database
        for card_number, acc_data in accounts_data.items():
            transactions = acc_data.get("transactions", [])
            needs_hash = any(not t.get("hash") for t in transactions)
            
            if repaired or needs_hash:
                # Sort chronologically by timestamp
                transactions.sort(key=lambda x: x.get("timestamp", ""))
                
                balance = 0.0
                prev_hash = "0"
                for tx in transactions:
                    tx["previous_balance"] = balance
                    tx_type = tx.get("type")
                    amount = float(tx.get("amount", 0))
                    
                    if tx_type in ["Deposit", "Transfer In", "Interest"]:
                        tx["balance"] = balance + amount
                    elif tx_type in ["Withdrawal", "Transfer Out", "Maintenance Fee"]:
                        tx["balance"] = balance - amount
                    elif tx_type == "Account Creation":
                        tx["balance"] = amount
                    
                    balance = tx["balance"]
                    tx["previous_hash"] = prev_hash
                    
                    # Generate hash
                    tx["hash"] = get_expected_hash(tx)
                    prev_hash = tx["hash"]
                
                acc_data["balance"] = balance
                acc_data["transactions"] = transactions

        return repaired

    def save_data(self, data: Dict[str, Any]) -> bool:
        """Atomically save account data to the JSON file.

        Writes to a temporary file first, then renames it to target file path.

        Args:
            data: The dictionary database to save.

        Returns:
            True if save was successful, False otherwise.
        """
        temp_file = f"{self.file_path}.tmp"
        try:
            # Ensure containing directory exists
            dir_name = os.path.dirname(self.file_path)
            if dir_name and not os.path.exists(dir_name):
                os.makedirs(dir_name, exist_ok=True)

            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            
            # Atomic rename/replace
            if os.path.exists(temp_file):
                if os.path.exists(self.file_path):
                    os.remove(self.file_path)
                os.rename(temp_file, self.file_path)
            return True
        except (IOError, OSError) as e:
            print(f"\n[Error] Failed to write database: {e}")
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except OSError:
                    pass
            return False

    def backup(self) -> bool:
        """Create a backup copy of the current database.

        Returns:
            True if backup succeeded, False otherwise.
        """
        try:
            if not os.path.exists(self.file_path):
                print("\n[Error] Main database file not found. Cannot perform backup.")
                return False
            shutil.copy2(self.file_path, self.backup_path)
            return True
        except (FileNotFoundError, IOError, OSError) as e:
            print(f"\n[Error] Backup operation failed: {e}")
            return False

    def restore(self) -> bool:
        """Restore the database from the backup copy.

        Returns:
            True if restore succeeded, False otherwise.
        """
        try:
            if not os.path.exists(self.backup_path):
                raise FileNotFoundError("Backup database file does not exist.")
            
            # Load backup to verify it is valid JSON before replacing active db
            with open(self.backup_path, "r", encoding="utf-8") as f:
                json.load(f)
                
            shutil.copy2(self.backup_path, self.file_path)
            return True
        except FileNotFoundError as e:
            print(f"\n[Error] Restore failed: {e}")
            return False
        except (json.JSONDecodeError, ValueError) as e:
            print(f"\n[Error] Restore failed because backup file is corrupted: {e}")
            return False
        except (IOError, OSError) as e:
            print(f"\n[Error] Restore failed due to system I/O error: {e}")
            return False
