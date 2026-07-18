"""Constants used across the Python Banking Management System.

This module houses configuration parameters including file paths, credentials,
interest rates, and security limits.
"""

import os

# Database Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_DB_PATH = os.path.join(BASE_DIR, "database.json")
DEFAULT_BACKUP_PATH = os.path.join(BASE_DIR, "database_backup.json")

# Admin Credentials
ADMIN_USERNAME = "admin"
ADMIN_PASSWORD = "admin123"

# Security Configuration
MAX_FAILED_ATTEMPTS = 3

# Financial Defaults
DEFAULT_INTEREST_RATE = 0.03
