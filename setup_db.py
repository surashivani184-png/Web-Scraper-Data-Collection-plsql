"""
setup_db.py - Database Initialization and Demo Seeder
MCA 1st Semester Mini Project: Personal Finance Dashboard
"""
import os
import sys
from datetime import datetime, timedelta
import random
from werkzeug.security import generate_password_hash
from config import Config
import db

def init_mysql_database(password=None):
    """Initializes the MySQL database and tables."""
    import pymysql
    
    pwd = password if password is not None else Config.MYSQL_PASSWORD
    print(f"\n[*] Connecting to MySQL Server (Host: {Config.MYSQL_HOST}, User: {Config.MYSQL_USER})...")
    
    try:
        conn = pymysql.connect(
            host=Config.MYSQL_HOST,
            user=Config.MYSQL_USER,
            password=pwd,
            port=Config.MYSQL_PORT,
            charset='utf8mb4'
        )
        print("[+] MySQL connection established!")
    except Exception as e:
        print(f"[!] Failed to connect to MySQL: {e}")
        print("\nTip: Please update MYSQL_PASSWORD in .env file with your MySQL root password.")
        return False

    with conn.cursor() as cur:
        # Create database
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{Config.MYSQL_DB}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;")
        cur.execute(f"USE `{Config.MYSQL_DB}`;")
        print(f"[+] Database `{Config.MYSQL_DB}` ready.")

        # Read schema.sql
        schema_path = os.path.join(os.path.dirname(__file__), 'schema.sql')
        if os.path.exists(schema_path):
            with open(schema_path, 'r', encoding='utf-8') as f:
                sql_content = f.read()
            
            statements = [s.strip() for s in sql_content.split(';') if s.strip()]
            for stmt in statements:
                if stmt.upper().startswith(('CREATE DATABASE', 'USE ')):
                    continue
                try:
                    cur.execute(stmt)
                except Exception as sql_err:
                    print(f"Warning during execution: {sql_err}")
            conn.commit()
            print("[+] All tables and default categories created successfully!")
        else:
            print("[!] schema.sql not found.")
            return False

    conn.close()
    return True

def seed_demo_user():
    """Seeds a realistic demo user with sample transactions, budgets, and savings goals."""
    from db import query_db, init_tables
    
    # Ensure tables are initialized
    init_tables()
    
    demo_email = "demo@example.com"
    existing = query_db("SELECT id FROM users WHERE email = %s", (demo_email,), one=True)
    if existing:
        print(f"[i] Demo user ({demo_email}) already exists with ID: {existing['id']}.")
        user_id = existing['id']
    else:
        hashed = generate_password_hash("password123")
        res = query_db(
            "INSERT INTO users (name, email, password_hash, currency) VALUES (%s, %s, %s, %s)",
            ("Arun Sharma (MCA Demo)", demo_email, hashed, "₹"),
            commit=True
        )
        user_id = res['lastrowid']
        print(f"[+] Created Demo User: {demo_email} | Password: password123 (User ID: {user_id})")

    # Check if user already has transactions
    tx_count = query_db("SELECT COUNT(*) as cnt FROM transactions WHERE user_id = %s", (user_id,), one=True)
    if tx_count and tx_count['cnt'] > 0:
        print("[i] Demo transactions already present.")
        return

    print("[*] Generating realistic demo financial data for MCA presentation...")

    # Fetch categories
    income_cats = query_db("SELECT id, name FROM categories WHERE type = 'income'")
    expense_cats = query_db("SELECT id, name FROM categories WHERE type = 'expense'")

    income_cat_map = {c['name']: c['id'] for c in income_cats}
    expense_cat_map = {c['name']: c['id'] for c in expense_cats}

    today = datetime.now()
    curr_month_str = today.strftime('%Y-%m')

    # Seed Sample Incomes for last 2 months
    incomes = [
        ("Monthly MCA Internship Stipend", 28000, "Salary", "Net Banking", today - timedelta(days=2)),
        ("Web Freelance Project Milestone", 12500, "Freelance", "UPI", today - timedelta(days=12)),
        ("Monthly MCA Internship Stipend", 28000, "Salary", "Net Banking", today - timedelta(days=32)),
        ("Academic Research Grant", 5000, "Allowance / Gift", "Net Banking", today - timedelta(days=25)),
        ("Dividend Payout", 1850, "Investments", "Net Banking", today - timedelta(days=18))
    ]

    for desc, amt, cat_name, method, dt in incomes:
        cat_id = income_cat_map.get(cat_name, list(income_cat_map.values())[0])
        query_db(
            """INSERT INTO transactions (user_id, category_id, amount, type, payment_method, transaction_date, description)
               VALUES (%s, %s, %s, 'income', %s, %s, %s)""",
            (user_id, cat_id, amt, method, dt.strftime('%Y-%m-%d'), desc),
            commit=True
        )

    # Seed Sample Expenses for current and past month
    sample_expenses = [
        ("Semester Reference Books & Notes", 1850, "College & Books", "UPI", 1),
        ("Hostel / Flat Rent Payment", 9500, "Rent & Housing", "Net Banking", 3),
        ("Monthly Grocery Supermarket", 3450, "Groceries", "Debit Card", 5),
        ("Electricity & WiFi Broadband Bill", 1650, "Utilities & Bills", "UPI", 6),
        ("Dinner with MCA Project Team", 1200, "Food & Dining", "UPI", 8),
        ("Two-wheeler Petrol Fillup", 800, "Travel & Fuel", "Cash", 10),
        ("College Canteen Coffee & Snacks", 320, "Food & Dining", "UPI", 11),
        ("Online Cloud Server Hosting (Dev)", 650, "Utilities & Bills", "Credit Card", 14),
        ("Movie Weekend Tickets & Popcorn", 750, "Entertainment", "UPI", 16),
        ("Medical Pharmacy Prescription", 420, "Health & Medical", "Cash", 19),
        ("Ergonomic Coding Mouse & Pad", 1199, "Shopping", "Credit Card", 22),
        ("Weekly Bus Pass & Metro Recharge", 500, "Travel & Fuel", "UPI", 24),
        ("Campus Cafeteria Lunch", 260, "Food & Dining", "Cash", 27),
        ("Previous Month Hostel Rent", 9500, "Rent & Housing", "Net Banking", 33),
        ("Previous Month Grocery", 3100, "Groceries", "Debit Card", 35)
    ]

    for desc, amt, cat_name, method, days_ago in sample_expenses:
        cat_id = expense_cat_map.get(cat_name, list(expense_cat_map.values())[0])
        dt = today - timedelta(days=days_ago)
        query_db(
            """INSERT INTO transactions (user_id, category_id, amount, type, payment_method, transaction_date, description)
               VALUES (%s, %s, %s, 'expense', %s, %s, %s)""",
            (user_id, cat_id, amt, method, dt.strftime('%Y-%m-%d'), desc),
            commit=True
        )

    # Seed Budgets for current month
    budget_allocations = [
        ("Rent & Housing", 10000),
        ("Food & Dining", 4000),
        ("Groceries", 4500),
        ("College & Books", 3000),
        ("Travel & Fuel", 2000),
        ("Utilities & Bills", 2500),
        ("Entertainment", 1500)
    ]

    for cat_name, limit in budget_allocations:
        cat_id = expense_cat_map.get(cat_name)
        if cat_id:
            # Check if budget already exists for this month
            b_exist = query_db(
                "SELECT id FROM budgets WHERE user_id = %s AND category_id = %s AND month_year = %s",
                (user_id, cat_id, curr_month_str),
                one=True
            )
            if b_exist:
                query_db(
                    "UPDATE budgets SET monthly_limit = %s WHERE id = %s",
                    (limit, b_exist['id']),
                    commit=True
                )
            else:
                query_db(
                    "INSERT INTO budgets (user_id, category_id, monthly_limit, month_year) VALUES (%s, %s, %s, %s)",
                    (user_id, cat_id, limit, curr_month_str),
                    commit=True
                )

    # Seed Savings Goals
    savings_goals = [
        ("MCA Final Year Laptop Upgrade", 75000, 32000, (today + timedelta(days=180)).strftime('%Y-%m-%d'), '#3b82f6'),
        ("AWS / Cloud Certification Exam", 15000, 9500, (today + timedelta(days=60)).strftime('%Y-%m-%d'), '#10b981'),
        ("Emergency Rainy-Day Fund", 30000, 21000, (today + timedelta(days=120)).strftime('%Y-%m-%d'), '#f59e0b')
    ]

    for title, target, current, target_dt, color in savings_goals:
        query_db(
            """INSERT INTO savings_goals (user_id, title, target_amount, current_amount, target_date, color, status)
               VALUES (%s, %s, %s, %s, %s, %s, 'in_progress')""",
            (user_id, title, target, current, target_dt, color),
            commit=True
        )

    print("[+] Successfully seeded demo data!")
    print("\n" + "="*50)
    print("DEMO LOGIN CREDENTIALS:")
    print("Email:    demo@example.com")
    print("Password: password123")
    print("="*50)

if __name__ == '__main__':
    print("=== FinFlow Database Setup Tool ===")
    user_pwd = None
    if len(sys.argv) > 1:
        user_pwd = sys.argv[1]
    
    # Check MySQL
    success = init_mysql_database(password=user_pwd)
    if not success:
        print("[!] MySQL setup skipped or failed. Falling back to SQLite setup...")
        db.DB_ENGINE = 'sqlite'
    else:
        db.DB_ENGINE = 'mysql'
        
    seed_demo_user()
    print("\nDatabase initialization complete! You can now run: python app.py")
