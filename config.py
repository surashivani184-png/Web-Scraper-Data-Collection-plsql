import os
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'finflow_mca_project_secret_key_2026_x99')
    
    # MySQL Database Settings
    MYSQL_HOST = os.getenv('MYSQL_HOST', 'localhost')
    MYSQL_USER = os.getenv('MYSQL_USER', 'root')
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD', '')
    MYSQL_DB = os.getenv('MYSQL_DB', 'personal_finance')
    MYSQL_PORT = int(os.getenv('MYSQL_PORT', 3306))
    
    # SQLite Fallback File (Ensures immediate out-of-the-box run without setup errors)
    SQLITE_DB = os.getenv('SQLITE_DB', 'finance.db')
    
    # App Settings
    DEFAULT_CURRENCY = '₹'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
