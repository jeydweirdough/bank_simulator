"""Main runner and CLI view controller for the Python Banking Management System.

This module sets up dependencies, routes CLI commands to corresponding backend services,
and manages screen transitions and formatted print layouts.
"""

import sys
import os
import socket
import threading
import json
from datetime import datetime, timedelta
from typing import Optional
from constants import DEFAULT_DB_PATH, DEFAULT_BACKUP_PATH
from storage import Storage
from auth import SessionManager
from banking import BankService
from utils import (
    clear_screen,
    pause_screen,
    validate_pin,
    validate_name,
    prompt_string,
    prompt_int,
    prompt_float,
    get_simulated_date_str,
)


class BankCLI:
    """Controls the console interface and input loop routing."""

    def __init__(self) -> None:
        """Initialize backend services and session manager."""
        self.storage = Storage(DEFAULT_DB_PATH, DEFAULT_BACKUP_PATH)
        self.session = SessionManager(self.storage)
        self.banking = BankService(self.storage)
        self.db_lock = threading.Lock()
        self.server_thread = None
        self.server_running = False

    def start_server(self) -> None:
        """Start the background TCP server thread."""
        self.server_running = True
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()

    def _run_server(self) -> None:
        """Main socket listening loop running in background thread."""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_socket.bind(("127.0.0.1", 65432))
            server_socket.listen(5)
        except Exception:
            # Fail silently if socket is already in use
            return

        while self.server_running:
            try:
                server_socket.settimeout(1.0)
                try:
                    conn, addr = server_socket.accept()
                except socket.timeout:
                    continue
                
                # Delegate handling to another thread
                threading.Thread(
                    target=self._handle_client,
                    args=(conn,),
                    daemon=True
                ).start()
            except Exception:
                break
        server_socket.close()

    def _handle_client(self, conn: socket.socket) -> None:
        """Handle incoming command payload from robot client and execute services."""
        try:
            data_bytes = conn.recv(4096)
            if not data_bytes:
                return
            
            request = json.loads(data_bytes.decode("utf-8"))
            action = request.get("action")
            response = {"status": "error", "message": "Unknown action"}

            # Concurrency protection around database changes
            with self.db_lock:
                if action == "create":
                    owner = request["owner"]
                    pin = request["pin"]
                    deposit_amt = float(request["initial_deposit"])
                    account, msg = self.banking.create_account(owner, pin, deposit_amt)
                    
                    sys.stdout.write(f"\n[Robot Activity] Registered User '{owner}'. Card: {account.card_number}\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()
                    
                    response = {"status": "success", "card_number": account.card_number}

                elif action == "deposit":
                    card = request["card_number"]
                    amount = float(request["amount"])
                    success, msg = self.banking.deposit(card, amount)
                    
                    sys.stdout.write(f"\n[Robot Activity] Card {card} deposited ${amount:.2f}.\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()
                    
                    response = {"status": "success" if success else "error", "message": msg}

                elif action == "withdraw":
                    card = request["card_number"]
                    amount = float(request["amount"])
                    success, msg = self.banking.withdraw(card, amount)
                    
                    sys.stdout.write(f"\n[Robot Activity] Card {card} withdrew ${amount:.2f}.\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()
                    
                    response = {"status": "success" if success else "error", "message": msg}

                elif action == "transfer":
                    sender = request["sender_card"]
                    receiver = request["receiver_card"]
                    amount = float(request["amount"])
                    success, msg = self.banking.transfer(sender, receiver, amount)
                    
                    sys.stdout.write(f"\n[Robot Activity] Transfer: Card {sender} -> Card {receiver} of ${amount:.2f}.\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()
                    
                    response = {"status": "success" if success else "error", "message": msg}

                elif action == "advance_day":
                    base_dir = os.path.dirname(os.path.abspath(__file__))
                    sim_path = os.path.join(base_dir, "sim_time.json")
                    days_offset = 0
                    if os.path.exists(sim_path):
                        try:
                            with open(sim_path, "r", encoding="utf-8") as f:
                                d = json.load(f)
                                days_offset = d.get("days_offset", 0)
                        except Exception:
                            pass
                    
                    days_offset += 1
                    try:
                        with open(sim_path, "w", encoding="utf-8") as f:
                            json.dump({"days_offset": days_offset}, f)
                    except Exception:
                        pass

                    old_date = datetime.now() + timedelta(days=days_offset - 1)
                    new_date = datetime.now() + timedelta(days=days_offset)

                    sys.stdout.write(f"\n[Robot Calendar] Day advanced to: {new_date.strftime('%Y-%m-%d')} (offset: +{days_offset})\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()

                    if new_date.month != old_date.month:
                        sys.stdout.write(f"\n[Robot Calendar] Month Rollover! Triggering monthly batches (Fees & Interest)...\n")
                        sys.stdout.write("Choose an option (1-4): ")
                        sys.stdout.flush()
                        self.banking.apply_monthly_fee(12.0)
                        self.banking.apply_interest()

                    response = {
                        "status": "success",
                        "sim_date": new_date.strftime("%Y-%m-%d"),
                        "days_offset": days_offset,
                    }

                elif action == "lockout_sim":
                    card = request["card_number"]
                    sys.stdout.write(f"\n[Robot Activity] Security lockout simulation on Card {card}.\n")
                    sys.stdout.write("Choose an option (1-4): ")
                    sys.stdout.flush()
                    for _ in range(3):
                        self.session.login_user(card, "9999")
                    
                    # Unlock
                    self.banking.unlock_account(card)
                    response = {"status": "success"}

                elif action == "stats":
                    stats = self.banking.get_statistics()
                    response = {"status": "success", "stats": stats}

            conn.sendall(json.dumps(response).encode("utf-8"))
        except Exception:
            pass
        finally:
            conn.close()

    def run(self) -> None:
        """Run the main loop for the application."""
        while True:
            clear_screen()
            print("====================")
            print("    PYTHON BANK     ")
            print(f"  Date: {get_simulated_date_str()}")
            print("====================")
            print("1. Create Account")
            print("2. Login")
            print("3. Admin Login")
            print("4. Exit")
            print("====================")

            choice = prompt_string("Choose an option (1-4): ")

            try:
                if choice == "1":
                    self._create_account_flow()
                elif choice == "2":
                    self._login_flow()
                elif choice == "3":
                    self._admin_login_flow()
                elif choice == "4":
                    print("\nThank you for banking with Python National Bank. Goodbye!")
                    sys.exit(0)
                else:
                    print("\nError: Invalid choice. Please select between 1 and 4.")
                    pause_screen()
            except (KeyboardInterrupt, SystemExit):
                print("\nExiting program...")
                sys.exit(0)
            except Exception as e:
                print(f"\nAn unexpected error occurred: {e}")
                pause_screen()

    # --- User Flows ---

    def _create_account_flow(self) -> None:
        """Guide user through creating a new account."""
        clear_screen()
        print("====================")
        print("   CREATE ACCOUNT   ")
        print("====================")

        # Get and validate Name
        while True:
            owner = prompt_string("Enter Full Name: ")
            if validate_name(owner):
                break
            print("Error: Name must contain only alphabetical characters and spaces, and not be empty.")

        # Get and validate PIN
        while True:
            pin = prompt_string("Enter 6-Digit PIN: ")
            if validate_pin(pin):
                confirm_pin = prompt_string("Confirm 6-Digit PIN: ")
                if pin == confirm_pin:
                    break
                else:
                    print("Error: PIN confirmation does not match. Try again.")
            else:
                print("Error: PIN must be exactly 6 digits (0-9).")

        # Get and validate initial deposit
        initial_deposit = prompt_float("Enter Initial Deposit Amount: $", min_val=0.0)

        # Execute creation
        account, msg = self.banking.create_account(owner, pin, initial_deposit)
        print("\n" + "=" * 40)
        print(msg)
        print("=" * 40)
        pause_screen()

    def _login_flow(self) -> None:
        """Authenticate user login."""
        clear_screen()
        print("====================")
        print("     USER LOGIN     ")
        print("====================")
        card_num = prompt_string("Enter 16-Digit Card Number: ")
        pin = prompt_string("Enter 6-Digit PIN: ")

        success, msg = self.session.login_user(card_num, pin)
        print(f"\n{msg}")
        pause_screen()

        if success:
            self._user_menu_loop()

    def _admin_login_flow(self) -> None:
        """Authenticate admin login."""
        clear_screen()
        print("====================")
        print("    ADMIN LOGIN     ")
        print("====================")
        username = prompt_string("Username: ")
        password = prompt_string("Password: ")

        if self.session.login_admin(username, password):
            print("\nAdmin login successful!")
            pause_screen()
            self._admin_menu_loop()
        else:
            print("\nError: Invalid admin credentials.")
            pause_screen()

    # --- Logged-In User Menu ---

    def _user_menu_loop(self) -> None:
        """Display and route user operations for the logged-in session."""
        while self.session.is_user_logged_in():
            # Get fresh data for the user profile
            card_num = self.session.current_user.card_number
            db_data = self.storage.load_data()
            acc_data = db_data.get("accounts", {}).get(card_num)
            
            if not acc_data:
                print("\nLogged-in account could not be retrieved from DB. Logging out...")
                self.session.logout()
                pause_screen()
                break

            # Instantiate class to handle state
            user = self.session.current_user = self.session.current_user.__class__.from_dict(card_num, acc_data)

            clear_screen()
            print("====================")
            print(f"  Welcome {user.owner}")
            print(f"  Date: {get_simulated_date_str()}")
            print("====================")
            print("1. Balance Inquiry")
            print("2. Deposit")
            print("3. Withdraw")
            print("4. Transfer")
            print("5. Bank Statement")
            print("6. Transaction History")
            print("7. Change Name")
            print("8. Change PIN")
            print("9. Delete Account")
            print("10. Logout")
            print("====================")

            choice = prompt_string("Choose an option (1-10): ")

            if choice == "1":
                self._user_balance_inquiry(user)
            elif choice == "2":
                self._user_deposit(user)
            elif choice == "3":
                self._user_withdraw(user)
            elif choice == "4":
                self._user_transfer(user)
            elif choice == "5":
                self._user_statement(user)
            elif choice == "6":
                self._user_history(user)
            elif choice == "7":
                self._user_change_name(user)
            elif choice == "8":
                self._user_change_pin(user)
            elif choice == "9":
                if self._user_delete_account(user):
                    break
            elif choice == "10":
                self.session.logout()
                print("\nSuccessfully logged out.")
                pause_screen()
            else:
                print("\nError: Invalid choice. Try again.")
                pause_screen()

    def _user_balance_inquiry(self, user) -> None:
        """Display balance and run purchasing power simulation."""
        clear_screen()
        print("====================")
        print("  BALANCE INQUIRY   ")
        print("====================")
        print(f"Owner:       {user.owner}")
        print(f"Card Number: {user.card_number}")
        print(f"Balance:     ${user.balance:.2f}")
        print("====================")

        # Purchasing power simulation
        print("\n--- Educational Inflation Simulator ---")
        run_sim = prompt_string("Would you like to simulate purchasing power inflation? (y/n): ").lower()
        if run_sim == "y":
            rate = prompt_float("Enter projected inflation rate % (e.g. 5 for 5%): ", min_val=0.0)
            real_val = self.banking.get_purchasing_power(user.balance, rate)
            print(f"\nAt a projected inflation of {rate:.2f}%,")
            print(f"Real Purchasing Power: ${real_val:.2f}")
        pause_screen()

    def _user_deposit(self, user) -> None:
        """Handle user deposit interface."""
        clear_screen()
        print("====================")
        print("      DEPOSIT       ")
        print("====================")
        amount = prompt_float("Enter deposit amount: $", min_val=0.01)
        success, msg = self.banking.deposit(user.card_number, amount)
        print(f"\n{msg}")
        pause_screen()

    def _user_withdraw(self, user) -> None:
        """Handle user withdrawal interface."""
        clear_screen()
        print("====================")
        print("      WITHDRAW      ")
        print("====================")
        amount = prompt_float("Enter withdrawal amount: $", min_val=0.01)
        success, msg = self.banking.withdraw(user.card_number, amount)
        print(f"\n{msg}")
        pause_screen()

    def _user_transfer(self, user) -> None:
        """Handle user transfer interface."""
        clear_screen()
        print("====================")
        print("      TRANSFER      ")
        print("====================")
        recipient = prompt_string("Enter Recipient's 16-Digit Card Number: ")
        amount = prompt_float("Enter transfer amount: $", min_val=0.01)
        
        success, msg = self.banking.transfer(user.card_number, recipient, amount)
        print(f"\n{msg}")
        pause_screen()

    def _user_statement(self, user) -> None:
        """Print the bank statement in the requested format."""
        clear_screen()
        print("=================================")
        print("Python National Bank")
        print("=================================")
        print(f"Owner: {user.owner}\n")
        print(f"Card Number: {user.card_number}\n")
        print(f"Current Balance: ${user.balance:.2f}\n")
        print("Transactions:\n")
        
        # Header for columns
        print(f"{'Date':<20} | {'Type':<18} | {'Amount':<10} | {'Balance':<10}")
        print("-" * 70)

        # Print all transactions (sorted oldest to newest for chronological flow)
        sorted_txs = sorted(user.transactions, key=lambda x: x.timestamp)
        for tx in sorted_txs:
            sign = "+" if tx.type in ["Deposit", "Transfer In", "Interest"] else "-"
            # Display amounts nicely formatted
            amount_str = f"{sign}${tx.amount:.2f}"
            print(f"{tx.timestamp:<20} | {tx.type:<18} | {amount_str:<10} | ${tx.balance:.2f}")

        print("=================================")
        pause_screen()

    def _user_history(self, user) -> None:
        """Display chronological transaction ledger."""
        clear_screen()
        print("====================")
        print(" TRANSACTION HISTORY")
        print("====================")
        if not user.transactions:
            print("No transactions recorded yet.")
        else:
            for idx, tx in enumerate(reversed(user.transactions), 1):
                print(f"{idx}. [{tx.timestamp}] {tx.type}: ${tx.amount:.2f} (New Balance: ${tx.balance:.2f})")
        pause_screen()

    def _user_change_name(self, user) -> None:
        """Change user account name."""
        clear_screen()
        print("====================")
        print("    CHANGE NAME     ")
        print("====================")
        while True:
            new_name = prompt_string("Enter New Owner Name: ")
            if validate_name(new_name):
                break
            print("Error: Name must contain only alphabetical characters and spaces.")

        success, msg = self.banking.change_name(user.card_number, new_name)
        print(f"\n{msg}")
        pause_screen()

    def _user_change_pin(self, user) -> None:
        """Change user account PIN."""
        clear_screen()
        print("====================")
        print("     CHANGE PIN     ")
        print("====================")
        while True:
            new_pin = prompt_string("Enter New 6-Digit PIN: ")
            if validate_pin(new_pin):
                confirm = prompt_string("Confirm New PIN: ")
                if new_pin == confirm:
                    break
                else:
                    print("Error: PIN confirmation does not match. Try again.")
            else:
                print("Error: PIN must be exactly 6 digits.")

        success, msg = self.banking.change_pin(user.card_number, new_pin)
        print(f"\n{msg}")
        pause_screen()

    def _user_delete_account(self, user) -> bool:
        """Prompt verification loops to delete account permanently."""
        clear_screen()
        print("====================")
        print("   DELETE ACCOUNT   ")
        print("====================")
        pin_verify = prompt_string("Enter PIN to authorize deletion: ")
        
        if pin_verify != user.pin:
            print("\nError: Incorrect PIN. Account deletion aborted.")
            pause_screen()
            return False

        # First Confirmation
        confirm1 = prompt_string("Are you ABSOLUTELY sure you want to permanently delete your account? (yes/no): ").strip().lower()
        if confirm1 != "yes":
            print("\nOperation cancelled.")
            pause_screen()
            return False

        # Second Confirmation
        confirm2 = prompt_string("FINAL WARNING: All funds and history will be lost. Delete? (yes/no): ").strip().lower()
        if confirm2 != "yes":
            print("\nOperation cancelled.")
            pause_screen()
            return False

        # Execute Deletion
        if self.banking.delete_account(user.card_number):
            self.session.logout()
            print("\nAccount permanently deleted. We are sorry to see you go.")
            pause_screen()
            return True
        else:
            print("\nError deleting account. Try again later.")
            pause_screen()
            return False

    # --- Logged-In Admin Menu ---

    def _admin_menu_loop(self) -> None:
        """Display and route admin actions for the logged-in session."""
        while self.session.is_admin_logged_in():
            clear_screen()
            print("====================")
            print("       ADMIN        ")
            print(f"  Date: {get_simulated_date_str()}")
            print("====================")
            print("1. View Accounts")
            print("2. Search Account")
            print("3. Unlock Account")
            print("4. Apply Interest")
            print("5. Apply Maintenance Fee")
            print("6. Statistics")
            print("7. Backup Database")
            print("8. Restore Database")
            print("9. Logout")
            print("====================")

            choice = prompt_string("Choose an option (1-9): ")

            if choice == "1":
                self._admin_view_accounts()
            elif choice == "2":
                self._admin_search_account()
            elif choice == "3":
                self._admin_unlock_account()
            elif choice == "4":
                self._admin_apply_interest()
            elif choice == "5":
                self._admin_apply_fee()
            elif choice == "6":
                self._admin_statistics()
            elif choice == "7":
                self._admin_backup()
            elif choice == "8":
                self._admin_restore()
            elif choice == "9":
                self.session.logout()
                print("\nLogged out from Admin session.")
                pause_screen()
            else:
                print("\nError: Invalid choice. Try again.")
                pause_screen()

    def _admin_view_accounts(self) -> None:
        """List all accounts in the database."""
        clear_screen()
        print("====================")
        print("  ALL BANK ACCOUNTS ")
        print("====================")
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})

        if not accounts_data:
            print("No user accounts found.")
        else:
            for card_num, data in accounts_data.items():
                status = "LOCKED" if data.get("locked") else "ACTIVE"
                print(f"ID: {data['id']} | Card: {card_num} | Owner: {data['owner']} | Balance: ${data['balance']:.2f} | Status: {status}")
        pause_screen()

    def _admin_search_account(self) -> None:
        """Search accounts by owner name or card number."""
        clear_screen()
        print("====================")
        print("   SEARCH ACCOUNT   ")
        print("====================")
        query = prompt_string("Enter name substring or exact card number: ")
        results = self.banking.search_account(query)

        if not results:
            print("\nNo accounts matched the query.")
        else:
            print(f"\nFound {len(results)} match(es):")
            for idx, acc in enumerate(results, 1):
                status = "LOCKED" if acc.locked else "ACTIVE"
                print(f"{idx}. Card: {acc.card_number} | Owner: {acc.owner} | Balance: ${acc.balance:.2f} | Status: {status}")
        pause_screen()

    def _admin_unlock_account(self) -> None:
        """List locked accounts and unlock them."""
        clear_screen()
        print("====================")
        print("   UNLOCK ACCOUNT   ")
        print("====================")
        db = self.storage.load_data()
        accounts_data = db.get("accounts", {})
        
        locked_cards = [card for card, d in accounts_data.items() if d.get("locked")]
        
        if not locked_cards:
            print("There are no locked accounts at this time.")
            pause_screen()
            return

        print("Locked Accounts:")
        for idx, card in enumerate(locked_cards, 1):
            owner = accounts_data[card]["owner"]
            print(f"{idx}. Card: {card} | Owner: {owner}")

        card_to_unlock = prompt_string("\nEnter card number to unlock (or press Enter to cancel): ")
        if not card_to_unlock:
            return

        if card_to_unlock in locked_cards:
            if self.banking.unlock_account(card_to_unlock):
                print(f"\nAccount {card_to_unlock} unlocked successfully.")
            else:
                print("\nError trying to unlock account.")
        else:
            print("\nError: That card number is not in the locked accounts list.")
        pause_screen()

    def _admin_apply_interest(self) -> None:
        """Admin panel to apply interest to one or all accounts."""
        clear_screen()
        print("====================")
        print("   APPLY INTEREST   ")
        print("====================")
        print("1. Apply interest to a single account")
        print("2. Apply interest to all accounts")
        choice = prompt_string("Choose option (1-2): ")

        if choice == "1":
            card_num = prompt_string("Enter target Card Number: ")
            use_custom = prompt_string("Do you want to enter a custom interest rate? (y/n) [default: stored rate]: ").lower()
            rate = None
            if use_custom == "y":
                rate_pct = prompt_float("Enter custom interest rate % (e.g. 3 for 3%): ", min_val=0.0)
                rate = rate_pct / 100.0
            
            success, msg = self.banking.apply_interest(custom_rate=rate, card_number=card_num)
            print(f"\n{msg}")

        elif choice == "2":
            use_custom = prompt_string("Do you want to enter a custom interest rate for all? (y/n) [default: stored rate]: ").lower()
            rate = None
            if use_custom == "y":
                rate_pct = prompt_float("Enter custom interest rate % (e.g. 3 for 3%): ", min_val=0.0)
                rate = rate_pct / 100.0

            success, msg = self.banking.apply_interest(custom_rate=rate)
            print(f"\n{msg}")
        else:
            print("\nInvalid selection. Operation cancelled.")
        
        pause_screen()

    def _admin_apply_fee(self) -> None:
        """Admin panel to apply monthly maintenance fees."""
        clear_screen()
        print("====================")
        print(" APPLY MONTHLY FEE  ")
        print("====================")
        fee = prompt_float("Enter Monthly Maintenance Fee Amount: $", min_val=0.01)
        
        success, msg = self.banking.apply_monthly_fee(fee)
        print(f"\n{msg}")
        pause_screen()

    def _admin_statistics(self) -> None:
        """View banking statistics and log files."""
        clear_screen()
        print("====================")
        print(" BANK STATISTICS    ")
        print("====================")
        stats = self.banking.get_statistics()
        print(f"Total Members:        {stats['total_users']}")
        print(f"Total Money Deposited: ${stats['total_money']:.2f}")
        print(f"Locked Accounts:      {stats['locked_accounts']}")
        
        print("\n--- View All Transactions Log ---")
        view_log = prompt_string("Would you like to print all historical bank transactions? (y/n): ").lower()
        if view_log == "y":
            txs = self.banking.get_all_transactions()
            if not txs:
                print("No transactions found in system history.")
            else:
                print(f"\n{'Timestamp':<20} | {'Card Number':<16} | {'Owner':<12} | {'Type':<18} | {'Amount':<10} | {'New Balance':<10}")
                print("-" * 96)
                for tx in txs:
                    sign = "+" if tx["type"] in ["Deposit", "Transfer In", "Interest"] else "-"
                    amount_str = f"{sign}${tx['amount']:.2f}"
                    print(f"{tx['timestamp']:<20} | {tx['card_number']:<16} | {tx['owner']:<12} | {tx['type']:<18} | {amount_str:<10} | ${tx['balance']:.2f}")
        pause_screen()

    def _admin_backup(self) -> None:
        """Backup active database."""
        clear_screen()
        print("====================")
        print("  DATABASE BACKUP   ")
        print("====================")
        if self.storage.backup():
            print("\nDatabase backup successfully completed.")
        else:
            print("\nError: Backup failed. Check write permissions.")
        pause_screen()

    def _admin_restore(self) -> None:
        """Restore database from backup."""
        clear_screen()
        print("====================")
        print("  DATABASE RESTORE  ")
        print("====================")
        confirm = prompt_string("Restore will overwrite all current changes. Continue? (yes/no): ").lower()
        if confirm == "yes":
            if self.storage.restore():
                print("\nDatabase successfully restored from backup.")
            else:
                print("\nError: Restore failed. Verify backup file exists and is valid.")
        else:
            print("\nRestore cancelled.")
        pause_screen()


if __name__ == "__main__":
    app = BankCLI()
    app.start_server()
    app.run()
