"""Flask Web Application Server for the Python Banking Management System.

This module exposes a REST API for web-based operations and serves the HTML interface,
while concurrently running a background TCP socket server to maintain compatibility
with the robot tester simulator.
"""

import os
import json
import socket
import threading
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session

from storage import Storage
from auth import SessionManager
from banking import BankService
from constants import DEFAULT_DB_PATH, DEFAULT_BACKUP_PATH
from utils import get_simulated_date_str

# Initialize Flask app
app = Flask(__name__)
app.secret_key = "python_national_bank_secure_key"

# Global backend managers
storage = Storage(DEFAULT_DB_PATH, DEFAULT_BACKUP_PATH)
session_manager = SessionManager(storage)
banking = BankService(storage)
db_lock = threading.Lock()


def safe_float(val, default=0.0):
    """Safely convert a value to float, returning a default if invalid or None."""
    if val is None or val == "":
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


# --- Background TCP Socket Server for Robot Compatibility ---

def _run_socket_server() -> None:
    """Socket server thread running in parallel with Flask, listening on port 65432."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server_socket.bind(("127.0.0.1", 65432))
        server_socket.listen(5)
    except Exception:
        # Port already in use, fail silently
        return

    while True:
        try:
            # Simple accept loop
            conn, addr = server_socket.accept()
            threading.Thread(
                target=_handle_socket_client,
                args=(conn,),
                daemon=True
            ).start()
        except Exception:
            break
    server_socket.close()


def _handle_socket_client(conn: socket.socket) -> None:
    """Process robot client socket queries safely using shared locking."""
    try:
        data_bytes = conn.recv(4096)
        if not data_bytes:
            return
        
        request_data = json.loads(data_bytes.decode("utf-8"))
        action = request_data.get("action")
        response = {"status": "error", "message": "Unknown action"}

        with db_lock:
            if action == "create":
                owner = request_data["owner"]
                pin = request_data["pin"]
                deposit_amt = float(request_data["initial_deposit"])
                account, msg = banking.create_account(owner, pin, deposit_amt)
                print(f"[Socket Server] Registered robot user '{owner}'. Card: {account.card_number}")
                response = {"status": "success", "card_number": account.card_number}

            elif action == "deposit":
                card = request_data["card_number"]
                amount = float(request_data["amount"])
                success, msg = banking.deposit(card, amount)
                print(f"[Socket Server] Card {card} deposited ${amount:.2f}")
                response = {"status": "success" if success else "error", "message": msg}

            elif action == "withdraw":
                card = request_data["card_number"]
                amount = float(request_data["amount"])
                success, msg = banking.withdraw(card, amount)
                print(f"[Socket Server] Card {card} withdrew ${amount:.2f}")
                response = {"status": "success" if success else "error", "message": msg}

            elif action == "transfer":
                sender = request_data["sender_card"]
                receiver = request_data["receiver_card"]
                amount = float(request_data["amount"])
                success, msg = banking.transfer(sender, receiver, amount)
                print(f"[Socket Server] Transfer: Card {sender} -> Card {receiver} of ${amount:.2f}")
                response = {"status": "success" if success else "error", "message": msg}

            elif action == "advance_day":
                # Handle calendar incrementing
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
                print(f"[Socket Server] Day advanced to: {new_date.strftime('%Y-%m-%d')} (offset: +{days_offset})")

                if new_date.month != old_date.month:
                    print(f"[Socket Server] Month Rollover! Triggering monthly payouts/fees...")
                    banking.apply_monthly_fee(12.0)
                    banking.apply_interest()

                response = {
                    "status": "success",
                    "sim_date": new_date.strftime("%Y-%m-%d"),
                    "days_offset": days_offset,
                }

            elif action == "lockout_sim":
                card = request_data["card_number"]
                for _ in range(3):
                    session_manager.login_user(card, "9999")
                banking.unlock_account(card)
                response = {"status": "success"}

            elif action == "stats":
                stats = banking.get_statistics()
                response = {"status": "success", "stats": stats}

        conn.sendall(json.dumps(response).encode("utf-8"))
    except Exception as e:
        print(f"[Socket Server Warning] Handling failed: {e}")
    finally:
        conn.close()


# --- Flask Web App Controllers / Routes ---

@app.route("/")
def index():
    """Render the primary single-page visual web portal."""
    return render_template("index.html", mode="client")


@app.route("/admin")
def index_admin():
    """Render the admin login page directly."""
    return render_template("index.html", mode="admin")


@app.route("/register")
def index_register():
    """Render the register account page directly."""
    return render_template("index.html", mode="register")


@app.route("/api/register", methods=["POST"])
def api_register():
    """Endpoint for registering new user accounts."""
    data = request.get_json() or {}
    owner = data.get("owner", "").strip()
    pin = data.get("pin", "").strip()
    initial_deposit = safe_float(data.get("initial_deposit"), 0.0)

    if not owner or not pin:
        return jsonify({"status": "error", "message": "Owner name and PIN are required."}), 400

    from utils import validate_pin
    if not validate_pin(pin):
        return jsonify({"status": "error", "message": "PIN must be exactly 6 digits."}), 400

    with db_lock:
        try:
            account, msg = banking.create_account(owner, pin, initial_deposit)
            return jsonify({
                "status": "success",
                "card_number": account.card_number,
                "message": "Registration successful."
            })
        except Exception as e:
            return jsonify({"status": "error", "message": f"Server registration error: {e}"}), 500


@app.route("/api/login", methods=["POST"])
def api_login():
    """Endpoint for authenticating client and administrator users."""
    data = request.get_json() or {}
    identifier = data.get("identifier", "").strip()
    pin = data.get("pin", "").strip()
    login_type = data.get("type", "client")  # 'client' or 'admin'

    if login_type == "admin":
        if not identifier or not pin:
            return jsonify({"status": "error", "message": "Credentials cannot be blank."}), 400
        with db_lock:
            if session_manager.login_admin(identifier, pin):
                session["logged_in"] = True
                session["is_admin"] = True
                session["card_number"] = None
                return jsonify({"status": "success", "is_admin": True, "message": "Welcome, Administrator!"})
            return jsonify({"status": "error", "message": "Invalid administrator credentials."}), 401
    else:
        # Client Login (Card verification only when pin is blank)
        if not identifier:
            return jsonify({"status": "error", "message": "Card number is required."}), 400
        with db_lock:
            db = storage.load_data()
            if identifier not in db.get("accounts", {}):
                return jsonify({"status": "error", "message": "Card not recognized."}), 401
            
            acc = db["accounts"][identifier]
            if acc.get("locked"):
                return jsonify({"status": "error", "message": "This account is locked. Please contact an Administrator."}), 401
            
            # If PIN is provided, full login validation
            if pin:
                success, msg = session_manager.login_user(identifier, pin)
                if success:
                    session["logged_in"] = True
                    session["is_admin"] = False
                    session["card_number"] = identifier
                    return jsonify({"status": "success", "is_admin": False, "message": msg, "owner": acc.get("owner")})
                return jsonify({"status": "error", "message": msg}), 401
            else:
                # Just verify card validity for insertion
                return jsonify({"status": "success", "message": "Card accepted.", "owner": acc.get("owner"), "card_number": identifier})


@app.route("/api/logout")
def api_logout():
    """Clear Flask web cookies and backend session states."""
    session.clear()
    with db_lock:
        session_manager.logout()
    return jsonify({"status": "success", "message": "Signed out successfully."})


@app.route("/api/dashboard", methods=["GET", "POST"])
def api_dashboard():
    """Fetch current logged-in user profile, balance, and transaction ledger."""
    if request.method == "POST":
        data = request.get_json() or {}
        card_number = data.get("card_number")
        pin = data.get("pin")
    else:
        card_number = session.get("card_number")
        pin = None

    if not card_number:
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    with db_lock:
        if pin:
            success_auth, msg_auth = session_manager.login_user(card_number, pin)
            if not success_auth:
                return jsonify({"status": "error", "message": msg_auth}), 401
        elif not session.get("logged_in") or session.get("is_admin"):
            return jsonify({"status": "error", "message": "Unauthorized access."}), 401

        db = storage.load_data()
        accounts_data = db.get("accounts", {})
        if card_number not in accounts_data:
            return jsonify({"status": "error", "message": "Session expired or invalid."}), 401

        account_data = accounts_data[card_number]
        account_data["card_number"] = card_number
        return jsonify({
            "status": "success",
            "account": account_data,
            "system_date": get_simulated_date_str()
        })


@app.route("/api/deposit", methods=["POST"])
def api_deposit():
    """Execute a deposit on the active session account."""
    data = request.get_json() or {}
    card_number = data.get("card_number") or session.get("card_number")
    pin = data.get("pin")
    amount = safe_float(data.get("amount"), 0.0)

    if not card_number:
        return jsonify({"status": "error", "message": "Unauthorized action."}), 401

    with db_lock:
        if pin:
            success_auth, msg_auth = session_manager.login_user(card_number, pin)
            if not success_auth:
                return jsonify({"status": "error", "message": msg_auth}), 401
        elif not session.get("logged_in") or session.get("is_admin"):
            return jsonify({"status": "error", "message": "Unauthorized action."}), 401

        success, msg = banking.deposit(card_number, amount)
        if success:
            return jsonify({"status": "success", "message": msg})
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/withdraw", methods=["POST"])
def api_withdraw():
    """Execute a withdrawal on the active session account."""
    data = request.get_json() or {}
    card_number = data.get("card_number") or session.get("card_number")
    pin = data.get("pin")
    amount = safe_float(data.get("amount"), 0.0)

    if not card_number:
        return jsonify({"status": "error", "message": "Unauthorized action."}), 401

    with db_lock:
        if pin:
            success_auth, msg_auth = session_manager.login_user(card_number, pin)
            if not success_auth:
                return jsonify({"status": "error", "message": msg_auth}), 401
        elif not session.get("logged_in") or session.get("is_admin"):
            return jsonify({"status": "error", "message": "Unauthorized action."}), 401

        success, msg = banking.withdraw(card_number, amount)
        if success:
            return jsonify({"status": "success", "message": msg})
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/transfer", methods=["POST"])
def api_transfer():
    """Execute an inter-account wire transfer from the active session account."""
    data = request.get_json() or {}
    sender = data.get("card_number") or session.get("card_number")
    pin = data.get("pin")
    recipient = data.get("recipient", "").strip()
    amount = safe_float(data.get("amount"), 0.0)

    if not sender:
        return jsonify({"status": "error", "message": "Unauthorized action."}), 401

    with db_lock:
        if pin:
            success_auth, msg_auth = session_manager.login_user(sender, pin)
            if not success_auth:
                return jsonify({"status": "error", "message": msg_auth}), 401
        elif not session.get("logged_in") or session.get("is_admin"):
            return jsonify({"status": "error", "message": "Unauthorized action."}), 401

        success, msg = banking.transfer(sender, recipient, amount)
        if success:
            return jsonify({"status": "success", "message": msg})
        return jsonify({"status": "error", "message": msg}), 400


# --- Admin-Only Endpoints ---

@app.route("/api/admin/stats")
def api_admin_stats():
    """Fetch administrative bank parameters."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    with db_lock:
        stats = banking.get_statistics()
        return jsonify({
            "status": "success",
            "stats": stats,
            "system_date": get_simulated_date_str()
        })


@app.route("/api/admin/accounts")
def api_admin_accounts():
    """Search and load user profiles within the bank registry."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    query = request.args.get("query", "").strip()
    with db_lock:
        if query:
            results = banking.search_account(query)
        else:
            db = storage.load_data()
            results_data = db.get("accounts", {})
            results = []
            for c_num, data in results_data.items():
                # Reconstruct dict for serialization
                results.append({
                    "card_number": c_num,
                    "owner": data.get("owner"),
                    "balance": data.get("balance"),
                    "locked": data.get("locked")
                })

        # Format accounts list response
        accounts_list = []
        for res in results:
            if isinstance(res, dict):
                accounts_list.append(res)
            else:
                accounts_list.append({
                    "card_number": res.card_number,
                    "owner": res.owner,
                    "balance": res.balance,
                    "locked": res.locked
                })
        return jsonify({"status": "success", "accounts": accounts_list})


@app.route("/api/admin/unlock", methods=["POST"])
def api_admin_unlock():
    """Unlock a locked account."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    data = request.get_json() or {}
    card_number = data.get("card_number", "").strip()

    with db_lock:
        if banking.unlock_account(card_number):
            return jsonify({"status": "success", "message": f"Account {card_number} unlocked."})
        return jsonify({"status": "error", "message": "Failed to unlock account."}), 400


@app.route("/api/admin/interest", methods=["POST"])
def api_admin_interest():
    """Trigger the monthly interest accrual batch operation."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    data = request.get_json() or {}
    custom_rate_val = data.get("custom_rate")
    custom_rate = safe_float(custom_rate_val, None) if custom_rate_val is not None and custom_rate_val != "" else None

    with db_lock:
        success, msg = banking.apply_interest(custom_rate)
        if success:
            return jsonify({"status": "success", "message": msg})
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/admin/fee", methods=["POST"])
def api_admin_fee():
    """Trigger the monthly maintenance fee batch deduction."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    data = request.get_json() or {}
    amount = safe_float(data.get("amount"), 0.0)

    with db_lock:
        success, msg = banking.apply_monthly_fee(amount)
        if success:
            return jsonify({"status": "success", "message": msg})
        return jsonify({"status": "error", "message": msg}), 400


@app.route("/api/admin/backup", methods=["POST"])
def api_admin_backup():
    """Create a database backup copy."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    with db_lock:
        if storage.backup():
            return jsonify({"status": "success", "message": "Database backup completed successfully."})
        return jsonify({"status": "error", "message": "Failed to complete database backup."}), 500


@app.route("/api/admin/restore", methods=["POST"])
def api_admin_restore():
    """Restore database from backup copy."""
    if not session.get("logged_in") or not session.get("is_admin"):
        return jsonify({"status": "error", "message": "Unauthorized access."}), 401

    with db_lock:
        if storage.restore():
            return jsonify({"status": "success", "message": "Database restored from backup copy."})
        return jsonify({"status": "error", "message": "Failed to restore database from backup copy."}), 500


if __name__ == "__main__":
    # Start the daemon TCP socket server in a separate background thread
    socket_thread = threading.Thread(target=_run_socket_server, daemon=True)
    socket_thread.start()
    print("[Server Init] Background TCP socket server thread started on port 65432.")

    # Run the Flask local dev web server
    app.run(host="127.0.0.1", port=5000, debug=True)
