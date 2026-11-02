# FinFlow — Personal Finance & Expense Tracker Dashboard
> **MCA 1st Semester Mini Project**  
> **Tech Stack:** HTML5, CSS3, JavaScript (ES6+ & Chart.js), Python 3 (Flask), MySQL 8.0 (with zero-configuration SQLite automatic fallback).

---

## 📌 Project Overview
**FinFlow** is a modern, full-stack personal finance and expense tracking web application developed specifically for an **MCA 1st Semester** mini-project curriculum. It provides users with complete visibility and control over their income, daily expenditures, monthly category budgets, and long-term savings goals through responsive data visualizations and an intuitive interface.

---

## 🌟 Key Features

1. **User Authentication & Session Security:**
   - User Registration, Login, and Logout.
   - Secure password hashing using `werkzeug.security` (PBKDF2/SHA-256 with salt).
   - Session protection via HTTP-only cookies and `@login_required` decorators.

2. **Real-time Financial KPI Cards:**
   - **Net Balance** (All-time savings: Income - Expenses).
   - **Monthly Income** & **Monthly Expenses** for the active month.
   - **Monthly Savings Rate (%)** calculation.

3. **Dynamic Interactive Data Visualizations (Chart.js):**
   - **Cash Flow Comparison:** Grouped bar chart comparing Income vs Expense over the past 6 months.
   - **Category Distribution:** Doughnut chart breaking down expenses by category with percentages.
   - **Daily Spending Velocity:** Line graph tracking day-by-day expense flow.
   - **Payment Methods Breakdown:** Pie chart of UPI, Debit Card, Credit Card, Net Banking, and Cash.

4. **Complete Transaction Management (CRUD):**
   - **Create:** Add income or expense with category, date, payment mode, and note.
   - **Read:** Filter by Category, Type (Income/Expense), Month, or live text search.
   - **Update:** Edit existing transactions in a dynamic modal.
   - **Delete:** Remove transactions with instant client-side removal and database deletion.
   - **CSV Export:** Download all transaction history into an Excel/Spreadsheet-compatible `.csv` file.

5. **Monthly Budgeting System:**
   - Set monthly spending thresholds for individual categories (Food, Rent, Books, Travel, etc.).
   - Visual progress bars with adaptive color indicators:
     - 🟢 **Green (< 80%)**: Safe spending.
     - 🟡 **Yellow (80% - 99%)**: Approaching budget ceiling.
     - 🔴 **Red (>= 100%)**: Overbudget alert!
   - Real-time warnings banner rendered on the main dashboard.

6. **Savings Goals & Milestone Tracker:**
   - Set financial targets (e.g., "MCA Laptop Upgrade", "AWS Certification Exam").
   - Quick **"+ Deposit"** modal to increment saved funds toward goals.
   - Automatic status transition to **Completed** once the target is reached.

7. **Database Architecture & Zero-Friction Setup:**
   - **MySQL 8.0 Primary Engine:** Full relational schema (`schema.sql`) ready for MySQL Workbench or CLI import.
   - **Graceful Fallback:** If MySQL credentials are not yet configured or the server is unavailable, FinFlow automatically switches to local SQLite (`finance.db`) so the project runs immediately with zero crashes.

---

## 🗄️ Database Architecture (ER & Relational Model)

```
 +--------------------+       1 : N       +-----------------------+
 |       users        |-------------------|     transactions      |
 +--------------------+                   +-----------------------+
 | id (PK)            |                   | id (PK)               |
 | name               |                   | user_id (FK -> users) |
 | email (UNIQUE)     |                   | category_id (FK -> cat|
 | password_hash      |                   | amount (DECIMAL)      |
 | currency           |                   | type (income/expense) |
 | created_at         |                   | payment_method        |
 +--------------------+                   | transaction_date      |
      |          |                        | description           |
 1 : N|     1 : N|                        +-----------------------+
      |          |                                    |
      |          v                                    |
      |   +-------------------+                       |
      |   |   savings_goals   |                       |
      |   +-------------------+                       |
      |   | id (PK)           |                       |
      |   | user_id (FK)      |                       |
      |   | title             |                       |
      |   | target_amount     |                       |
      |   | current_amount    |                       |
      |   | target_date       |                       |
      |   +-------------------+                       |
      v                                               v
 +--------------------+       1 : N       +-----------------------+
 |      budgets       |-------------------|      categories       |
 +--------------------+                   +-----------------------+
 | id (PK)            |                   | id (PK)               |
 | user_id (FK)       |                   | user_id (FK, NULLable)|
 | category_id (FK)   |                   | name                  |
 | monthly_limit      |                   | type (income/expense) |
 | month_year         |                   | icon, color           |
 +--------------------+                   +-----------------------+
```

### Normalization (3NF) Compliance:
1. **1NF:** All attributes contain atomic values (single values per cell); each record has a unique Primary Key.
2. **2NF:** No partial dependencies; non-prime attributes depend on the entire primary key.
3. **3NF:** No transitive dependencies; non-prime attributes depend only on primary keys. Categories are decoupled from transactions into a dedicated normalized table.

---

## 🚀 How to Run the Project

### 1. Prerequisites
- Python 3.10+ installed
- MySQL Server 8.0 (optional, SQLite runs out-of-the-box if MySQL is not configured)

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Database & Seed Demo Data
Run the setup tool to create all tables and populate realistic demo data:
```bash
python setup_db.py
```

### 4. Start the Application Server
```bash
python app.py
```
Open your web browser and navigate to:  
👉 **`http://127.0.0.1:5000`**

---

## 🔑 Demo Login Credentials
For immediate presentation and evaluation:
- **Email:** `demo@example.com`
- **Password:** `password123`
*(A 1-click auto-fill button is also available on the Login screen).*

---

## ⚙️ Configuring with MySQL 8.0 (Optional)
To point the application directly to your local MySQL Server:
1. Open `.env` in the project root.
2. Set your MySQL root password:
   ```ini
   MYSQL_HOST=localhost
   MYSQL_PORT=3306
   MYSQL_USER=root
   MYSQL_PASSWORD=your_mysql_password_here
   MYSQL_DB=personal_finance
   ```
3. Run the setup script to create the database in MySQL:
   ```bash
   python setup_db.py
   ```
4. Start the app:
   ```bash
   python app.py
   ```
The status pill in the sidebar will display: **`DB: MySQL`**.

---

## 🎓 MCA Viva Voce Questions & Answers

### Q1: What is the architecture used in this project?
**Answer:** The project follows the **MVC (Model-View-Controller)** pattern.
- **Model:** Handled in `db.py` and `schema.sql`, executing normalized SQL queries.
- **View:** User interface created using semantic HTML5, CSS3 variables, and Jinja2 templates (`templates/`).
- **Controller:** Python Flask application (`app.py`), routing HTTP requests, handling business logic, session validation, and serving both JSON APIs and rendered views.

### Q2: How does the application prevent SQL Injection?
**Answer:** All database operations utilize **parameterized queries** (`query_db(sql, params)`). Query parameters are passed separately from SQL commands and escaped by the database driver (`pymysql` / `sqlite3`), ensuring user input is treated strictly as literal data rather than executable SQL code.

### Q3: How are passwords stored securely?
**Answer:** Plain-text passwords are never stored in the database. When a user registers, `werkzeug.security.generate_password_hash()` hashes the password using **PBKDF2 with SHA-256 and a random salt**. When authenticating, `check_password_hash()` verifies the input against the stored hash.

### Q4: What is the purpose of Foreign Keys with `ON DELETE CASCADE`?
**Answer:** Foreign key constraints maintain **Referential Integrity**. When a parent user record is deleted, `ON DELETE CASCADE` automatically removes all associated transactions, budgets, and savings goals, preventing orphaned records.

### Q5: How are dynamic charts populated?
**Answer:** The client-side JavaScript (`static/js/charts.js`) sends an asynchronous HTTP request using the native **Fetch API** to the backend endpoint `/api/chart-data`. The Flask controller queries the database, aggregates spending by month and category, and returns a JSON response that **Chart.js** renders onto HTML5 `<canvas>` elements.

### Q6: What is the advantage of using HTTP-only cookies for sessions?
**Answer:** Storing session tokens in `HttpOnly` cookies prevents client-side JavaScript from accessing session IDs, effectively protecting the application from session hijacking via **Cross-Site Scripting (XSS)** attacks.
