"""Robot Tester Client for Python Banking Management System.

This script runs in a separate terminal and acts as a TCP client connecting to
the main server hosted by main.py. It automatically halts if main.py is killed.
"""

import socket
import json
import random
import time
import sys
from typing import List


class RobotClient:
    """Simulates real-time user actions by sending TCP commands to main.py."""

    def __init__(self) -> None:
        """Initialize simulation configuration and names pools."""
        self.server_address = ("127.0.0.1", 65432)
        self.active_cards: List[str] = []
        self.names_pool = [
            "Robot Alice",
            "Robot Bob",
            "Robot Charlie",
            "Robot Diana",
            "Robot Ethan",
            "Robot Fiona",
            "Robot George",
            "Robot Helen",
            "Robot Ian",
            "Robot Julia",
        ]
        self.pins_pool = ["1111", "2222", "3333", "4444", "5555"]

    def _send_action(self, payload: dict) -> dict:
        """Send a JSON request to the main server and receive the response.

        Hhalts the program if the main server is not running.
        """
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect(self.server_address)
            s.sendall(json.dumps(payload).encode("utf-8"))
            resp = s.recv(4096)
            s.close()
            return json.loads(resp.decode("utf-8"))
        except (ConnectionRefusedError, socket.error):
            print("\n[Error] Cannot connect to Main Server at 127.0.0.1:65432.")
            print("Please make sure that 'python main.py' is running in another terminal.")
            print("Halting robot simulation...")
            sys.exit(1)

    def run_simulation(self) -> None:
        """Main loop that executes simulated human steps and calendar steps."""
        print("==================================================")
        print("     PYTHON BANKING SYSTEM - ROBOT CLIENT         ")
        print("==================================================")
        print("Status: CONNECTING TO SERVER...")
        
        # Test connection with initial stats check
        self._send_action({"action": "stats"})
        print("Status: CONNECTED AND RUNNING")
        print("Logs:")

        step = 0
        try:
            while True:
                # Advance day offset every 3 steps (15 seconds)
                if step % 3 == 0:
                    print("\n[TIME] Advancing calendar clock...")
                    resp = self._send_action({"action": "advance_day"})
                    if resp.get("status") == "success":
                        print(f"[TIME] Server Date is now: {resp.get('sim_date')} (Offset: +{resp.get('days_offset')})")
                
                # Determine next action
                # If we don't have enough accounts to simulate transfers, force creation
                if len(self.active_cards) < 2:
                    chosen_action = "create"
                else:
                    chosen_action = random.choice(["create", "deposit", "withdraw", "transfer", "lockout_sim", "stats"])

                if chosen_action == "create":
                    name = f"{random.choice(self.names_pool)} #{random.randint(100, 999)}"
                    pin = random.choice(self.pins_pool)
                    initial = float(random.randint(200, 1500))
                    print(f"[CREATE] Registering account: Name='{name}', Initial Deposit=${initial:.2f}")
                    
                    resp = self._send_action({
                        "action": "create",
                        "owner": name,
                        "pin": pin,
                        "initial_deposit": initial
                    })
                    if resp.get("status") == "success":
                        card_num = resp.get("card_number")
                        self.active_cards.append(card_num)
                        print(f"[SUCCESS] Registered. Card Number: {card_num} (PIN: {pin})")
                    else:
                        print(f"[FAIL] Registration failed: {resp.get('message')}")

                elif chosen_action == "deposit":
                    card = random.choice(self.active_cards)
                    amount = float(random.randint(50, 300))
                    print(f"[DEPOSIT] Depositing on card {card}: Amount=${amount:.2f}")
                    resp = self._send_action({
                        "action": "deposit",
                        "card_number": card,
                        "amount": amount
                    })
                    print(f"[RESULT] {resp.get('message')}")

                elif chosen_action == "withdraw":
                    card = random.choice(self.active_cards)
                    amount = float(random.randint(20, 150))
                    print(f"[WITHDRAW] Withdrawing from card {card}: Amount=${amount:.2f}")
                    resp = self._send_action({
                        "action": "withdraw",
                        "card_number": card,
                        "amount": amount
                    })
                    print(f"[RESULT] {resp.get('message')}")

                elif chosen_action == "transfer":
                    sender = random.choice(self.active_cards)
                    # Filter self out
                    receivers = [c for c in self.active_cards if c != sender]
                    if receivers:
                        receiver = random.choice(receivers)
                        amount = float(random.randint(30, 200))
                        print(f"[TRANSFER] Sending: Card {sender} -> Card {receiver}, Amount=${amount:.2f}")
                        resp = self._send_action({
                            "action": "transfer",
                            "sender_card": sender,
                            "receiver_card": receiver,
                            "amount": amount
                        })
                        print(f"[RESULT] {resp.get('message')}")

                elif chosen_action == "lockout_sim":
                    card = random.choice(self.active_cards)
                    print(f"[SECURITY] Triggering locking/unlocking sequence on card {card}")
                    resp = self._send_action({
                        "action": "lockout_sim",
                        "card_number": card
                    })
                    print("[SUCCESS] Lockout sequence completed.")

                elif chosen_action == "stats":
                    resp = self._send_action({"action": "stats"})
                    stats = resp.get("stats", {})
                    print(f"[STATS] Total Users: {stats.get('total_users')} | Bank Funds: ${stats.get('total_money', 0.0):.2f}")

                step += 1
                time.sleep(5)
        except KeyboardInterrupt:
            print("\nRobot simulator stopped by user.")


if __name__ == "__main__":
    client = RobotClient()
    client.run_simulation()
