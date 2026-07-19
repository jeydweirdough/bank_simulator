# Mooserage Banking System Simulation (Flask Web Application)

A visually stunning, modern, and modular console-and-web banking management system built in Python 3.11+ using Flask. The project integrates secure authentication, client-side QR Code card display, HTML5 camera-based login scanning, automated transaction histories, educational inflation simulations, and an admin statistics dashboard.

---

## Features

- **Premium Responsive Interface**: Glassmorphism dark-mode UI with floating animated glow background lights and glowing status badges.
- **QR Code Card Generation**: Automatically renders a card QR code on the user's dashboard (powered by `qrious.js` via CDN).
- **Webcam QR Login Scanner**: Features camera card scanning (powered by `jsQR.js` via CDN). Clicking "Scan QR to Login" mirrors the webcam feed, decodes the card number, focuses the PIN field, and plays a success audio tone.
- **REST JSON API Backend**: Integrates REST routes for balances, registration, logins, wire transfers, statistics, interest batches, and databases.
- **Stateless Concurrency Lock**: Employs `threading.Lock` to serialise database updates between web sessions and socket clients.
- **Automated Client Simulator**: Integrates `robot_tester.py` as a client. It creates robot accounts, deposits, wires funds, and increments calendar dates, which update the web dashboard dynamically in real time.
- **Admin Dashboard**: View metrics, search registered accounts, unlock lockouts, trigger fee/interest batches, and run database backups/restores.

---

## Folder Structure

```
.
├── templates/
│   └── index.html      # Responsive Glassmorphic Web Frontend
├── app.py              # Flask Web Server & daemon TCP Socket Server
├── robot_tester.py     # Robot Client Transaction Simulator
├── auth.py             # User & Admin Authentication Session Manager
├── accounts.py         # Account Entity Model
├── banking.py          # Core Financial Logic (deposits, transfers, interest)
├── transactions.py     # Transaction Log Dataclass
├── storage.py          # Database I/O Layer (atomic writes, backups)
├── utils.py            # Input Prompts, Validations, and Clock Offsets
├── constants.py        # Configuration Constants (admin login, path variables)
├── database.json       # active account registry (JSON Database)
├── Pipfile             # Pipenv dependency manifest
├── Pipfile.lock        # Pipenv dependency lock
└── README.md           # Project Documentation
```

---

## Installation & How to Run

### Requirements
- Python 3.11 or higher installed on your system.
- `pipenv` package manager (`pip install pipenv`).

### Environment Setup
1. Open your terminal in the project directory.
2. Install dependencies and activate the virtual environment using `pipenv`:
   ```bash
   pipenv install
   ```

### Running the Application

To run the application, you need to launch the server and, optionally, the simulator client in separate terminals:

1. **Terminal 1 (Flask Web Server)**:
   ```bash
   pipenv run python app.py
   ```
   Open your browser and navigate to: **`http://127.0.0.1:5000`**

2. **Terminal 2 (Robot Client Simulator)**:
   ```bash
   pipenv run python robot_tester.py
   ```
   Observe simulated users registering and transferring money, which dynamically reflects on your web dashboard.

---

## Portal Routing (Hidden Routes)

To maintain a clean and secure ATM experience, the default dashboard path `/` displays only the debit card reader slot. Administrative operations and user registration forms are hidden from general view and must be accessed via specific URLs:

- **Register Account**: [`http://127.0.0.1:5000/register`](http://127.0.0.1:5000/register)
- **Administrator Panel**: [`http://127.0.0.1:5000/admin`](http://127.0.0.1:5000/admin)
- **Ledger Blockchain Explorer**: [`http://127.0.0.1:5000/database`](http://127.0.0.1:5000/database)

---

## Default Admin Credentials
- **Username**: `admin`
- **Password**: `admin123`
