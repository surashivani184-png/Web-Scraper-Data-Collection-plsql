import os
import re
import sqlite3
import pymysql
from pymysql.cursors import DictCursor
from flask import g, has_app_context
from config import Config

DB_ENGINE = None  # Cached after first check: 'mysql' or 'sqlite'
DB_STATUS_INFO = {}
_standalone_db = None

def check_mysql_connection():
    """Test if MySQL server is accessible with provided config."""
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            port=Config.MYSQL_PORT,
            charset='utf8mb4',
            cursorclass=DictCursor,
            connect_timeout=2
        )
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}`;")
            cur.execute(f"USE `{Config.MYSQL_DB}`;")
        conn.close()
        return True, "Connected to MySQL successfully"
    except Exception as e:
        return False, str(e)

def get_db():
    """Returns database connection for current request context or standalone script."""
    global DB_ENGINE, DB_STATUS_INFO, _standalone_db
    
    # Check if we are inside a Flask application/request context
    in_flask = has_app_context()
    if in_flask and 'db' in g:
        return g.db

    # Determine engine if not already decided
    if DB_ENGINE is None:
        can_connect, err_msg = check_mysql_connection()
        if can_connect:
            DB_ENGINE = 'mysql'
            DB_STATUS_INFO = {
                'engine': 'MySQL',
                'host': Config.MYSQL_HOST,
                'database': Config.MYSQL_DB,
                'message': 'Connected to MySQL 8.0'
            }
        else:
            DB_ENGINE = 'sqlite'
            DB_STATUS_INFO = {
                'engine': 'SQLite',
                'file': Config.SQLITE_DB,
                'message': f'MySQL not reachable ({err_msg}). Using SQLite fallback for instant run.'
            }

    if DB_ENGINE == 'mysql':
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=Config.MYSQL_PASSWORD,
            database=Config.MYSQL_DB,
            port=Config.MYSQL_PORT,
            charset='utf8mb4',
            cursorclass=DictCursor,
            autocommit=True
        )
    else:
        db_path = os.path.join(os.path.dirname(__file__), Config.SQLITE_DB)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        
    if in_flask:
        g.db = conn
        return g.db
    else:
        _standalone_db = conn
        return _standalone_db

def close_db(e=None):
    """Closes database connection at the end of the request."""
    if has_app_context():
        db = g.pop('db', None)
        if db is not None:
            db.close()
    else:
        global _standalone_db
        if _standalone_db is not None:
            _standalone_db.close()
            _standalone_db = None

def query_db(query, args=(), one=False, commit=False):
    """
    Executes a query safely. Automatically converts %s to ? for SQLite.
    Returns list of dictionaries (or single dict if one=True).
    """
    db = get_db()
    is_sqlite = (DB_ENGINE == 'sqlite')
    
    formatted_query = query
    if is_sqlite:
        # Replace %s with ? for SQLite compatibility
        formatted_query = formatted_query.replace('%s', '?')
        # Replace MySQL specific functions if any
        formatted_query = formatted_query.replace('NOW()', "datetime('now', 'localtime')")
        formatted_query = formatted_query.replace('CURDATE()', "date('now', 'localtime')")
        
    cur = db.cursor()
    try:
        cur.execute(formatted_query, args)
        if commit or is_sqlite:
            db.commit()
            
        if query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE', 'CREATE', 'DROP', 'ALTER')):
            last_id = getattr(cur, 'lastrowid', None)
            row_count = cur.rowcount
            cur.close()
            return {'lastrowid': last_id, 'rowcount': row_count}
            
        rows = cur.fetchall()
        cur.close()
        
        # Convert sqlite3.Row objects to standard Python dicts for consistency
        if is_sqlite and rows:
            result = [dict(row) for row in rows]
        else:
            result = rows
            
        return (result[0] if result else None) if one else result
    except Exception as e:
        if is_sqlite:
            db.rollback()
        raise e

def init_tables():
    """Initializes tables for MySQL or SQLite."""
    global DB_ENGINE
    db = get_db()
    
    if DB_ENGINE == 'mysql':
        with db.cursor() as cur:
            # Users table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(120) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                currency VARCHAR(10) DEFAULT '₹',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Categories table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS categories (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NULL,
                name VARCHAR(50) NOT NULL,
                type ENUM('income', 'expense') NOT NULL,
                icon VARCHAR(50) DEFAULT 'tag',
                color VARCHAR(20) DEFAULT '#4f46e5',
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Transactions table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                category_id INT NOT NULL,
                amount DECIMAL(10, 2) NOT NULL,
                type ENUM('income', 'expense') NOT NULL,
                payment_method VARCHAR(30) DEFAULT 'UPI',
                transaction_date DATE NOT NULL,
                description VARCHAR(255) NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Budgets table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                category_id INT NOT NULL,
                monthly_limit DECIMAL(10, 2) NOT NULL,
                month_year VARCHAR(7) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE KEY unique_user_cat_month (user_id, category_id, month_year),
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
            
            # Savings Goals table
            cur.execute("""
            CREATE TABLE IF NOT EXISTS savings_goals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                title VARCHAR(100) NOT NULL,
                target_amount DECIMAL(10, 2) NOT NULL,
                current_amount DECIMAL(10, 2) DEFAULT 0.00,
                target_date DATE NULL,
                color VARCHAR(20) DEFAULT '#10b981',
                status ENUM('in_progress', 'completed') DEFAULT 'in_progress',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
            """)
    else:
        # SQLite dialect
        cur = db.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            currency TEXT DEFAULT '₹',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NULL,
            name TEXT NOT NULL,
            type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
            icon TEXT DEFAULT 'tag',
            color TEXT DEFAULT '#4f46e5',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            type TEXT CHECK(type IN ('income', 'expense')) NOT NULL,
            payment_method TEXT DEFAULT 'UPI',
            transaction_date TEXT NOT NULL,
            description TEXT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
        );

        CREATE TABLE IF NOT EXISTS budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category_id INTEGER NOT NULL,
            monthly_limit REAL NOT NULL,
            month_year TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE (user_id, category_id, month_year),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS savings_goals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL DEFAULT 0.00,
            target_date TEXT NULL,
            color TEXT DEFAULT '#10b981',
            status TEXT CHECK(status IN ('in_progress', 'completed')) DEFAULT 'in_progress',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """)
        db.commit()

    # Seed system categories if table is empty
    seed_categories()

def seed_categories():
    """Populates standard transaction categories if none exist."""
    cats = query_db("SELECT COUNT(*) as count FROM categories WHERE user_id IS NULL", one=True)
    if cats and (cats['count'] > 0 if isinstance(cats, dict) else cats[0] > 0):
        return

    default_categories = [
        # Income categories
        (None, 'Salary', 'income', 'briefcase', '#10b981'),
        (None, 'Freelance', 'income', 'laptop', '#06b6d4'),
        (None, 'Investments', 'income', 'graph-up-arrow', '#8b5cf6'),
        (None, 'Allowance / Gift', 'income', 'gift', '#ec4899'),
        (None, 'Other Income', 'income', 'cash-stack', '#14b8a6'),
        # Expense categories
        (None, 'Food & Dining', 'expense', 'cup-hot', '#ef4444'),
        (None, 'Rent & Housing', 'expense', 'house-door', '#f97316'),
        (None, 'College & Books', 'expense', 'book', '#f59e0b'),
        (None, 'Groceries', 'expense', 'basket', '#84cc16'),
        (None, 'Travel & Fuel', 'expense', 'car-front', '#3b82f6'),
        (None, 'Entertainment', 'expense', 'film', '#a855f7'),
        (None, 'Utilities & Bills', 'expense', 'lightning-charge', '#6366f1'),
        (None, 'Health & Medical', 'expense', 'heart-pulse', '#e11d48'),
        (None, 'Shopping', 'expense', 'bag-check', '#d946ef'),
        (None, 'Other Expense', 'expense', 'three-dots', '#64748b'),
    ]

    for cat in default_categories:
        query_db(
            "INSERT INTO categories (user_id, name, type, icon, color) VALUES (%s, %s, %s, %s, %s)",
            cat,
            commit=True
        )

def get_db_status():
    """Returns status information about the active database engine."""
    global DB_STATUS_INFO
    if not DB_STATUS_INFO:
        get_db()
    return DB_STATUS_INFO
