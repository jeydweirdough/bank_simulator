# Mooserage Banking System Simulation (Flask Web Application)

A banking system simulation built with Python (Flask) that demonstrates account management, authentication, money transfers, transaction history, and an admin dashboard. The project also includes QR code-based login, a simple banking interface, and a robot client that simulates user transactions.

---

## Features

- User registration and login
- QR code generation for account cards
- QR code login using a webcam
- Deposit, withdrawal, and money transfer functions
- Transaction history for each account
- Admin dashboard for viewing accounts and system statistics
- Database backup and restore
- Robot client that automatically creates accounts and performs transactions for testing
- REST API for banking operations

---

## Folder Structure

```text
.
├── templates/
│   └── index.html      # Web interface
├── app.py              # Flask application
├── robot_tester.py     # Transaction simulator
├── auth.py             # Authentication
├── accounts.py         # Account model
├── banking.py          # Banking functions
├── transactions.py     # Transaction records
├── storage.py          # Database handling
├── utils.py            # Helper functions
├── constants.py        # Configuration
├── database.json       # JSON database
├── Pipfile             # Dependencies
├── Pipfile.lock
└── README.md
```

---

## Installation

### Requirements

- Python 3.11 or later
- Pipenv

Install dependencies:

```bash
pipenv install
```

---

## Running the Project

Start the Flask server:

```bash
pipenv run python app.py
```

Open your browser and go to:

```
http://127.0.0.1:5000
```

To run the transaction simulator in another terminal:

```bash
pipenv run python robot_tester.py
```

---

## Routes

- `/` - Login page
- `/register` - Register a new account
- `/admin` - Admin dashboard
- `/database` - View stored account data

---

## Default Admin Account

**Username:** `admin`

**Password:** `admin123`

## License

This project is licensed under the MIT License. See the `LICENSE` file for more information.
