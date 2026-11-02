import os
import csv
import io
from functools import wraps
from datetime import datetime, timedelta
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, session, jsonify, make_response
)
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from db import query_db, get_db, close_db, init_tables, get_db_status

app = Flask(__name__)
app.config.from_object(Config)

# Register database teardown
app.teardown_appcontext(close_db)

# -------------------------------------------------------------
# Initialize Tables on First Run
# -------------------------------------------------------------
with app.app_context():
    try:
        init_tables()
    except Exception as e:
        print(f"[Init Error] Failed to initialize tables: {e}")

# -------------------------------------------------------------
# Helper Decorator: Login Required
# -------------------------------------------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash("Please sign in to access your financial dashboard.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------------------------------------
# Context Processor for Global Template Variables
# -------------------------------------------------------------
@app.context_processor
def inject_global_data():
    currency = session.get('currency', '₹')
    user_name = session.get('user_name', 'Guest')
    db_status = get_db_status()
    now = datetime.now()
    return {
        'current_currency': currency,
        'user_name': user_name,
        'db_status': db_status,
        'current_year': now.year,
        'current_month_str': now.strftime('%Y-%m'),
        'current_date_str': now.strftime('%Y-%m-%d')
    }

# -------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not email or not password:
            flash("Please fill in both email and password.", "danger")
            return render_template('login.html')

        user = query_db("SELECT * FROM users WHERE email = %s", (email,), one=True)
        if user and check_password_hash(user['password_hash'], password):
            session.clear()
            session['user_id'] = user['id']
            session['user_name'] = user['name']
            session['user_email'] = user['email']
            session['currency'] = user.get('currency', '₹') or '₹'
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid email or password. Please try again.", "danger")

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        currency = request.form.get('currency', '₹').strip()

        if not name or not email or not password:
            flash("All fields marked with an asterisk are required.", "danger")
            return render_template('register.html')

        if len(password) < 6:
            flash("Password must be at least 6 characters long.", "danger")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "danger")
            return render_template('register.html')

        # Check existing user
        existing = query_db("SELECT id FROM users WHERE email = %s", (email,), one=True)
        if existing:
            flash("An account with this email already exists. Please log in.", "warning")
            return redirect(url_for('login'))

        # Hash password and insert
        hashed = generate_password_hash(password)
        res = query_db(
            "INSERT INTO users (name, email, password_hash, currency) VALUES (%s, %s, %s, %s)",
            (name, email, hashed, currency),
            commit=True
        )
        user_id = res['lastrowid']

        # Log user in
        session['user_id'] = user_id
        session['user_name'] = name
        session['user_email'] = email
        session['currency'] = currency

        flash("Account created successfully! Welcome to FinFlow.", "success")
        return redirect(url_for('dashboard'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been signed out safely.", "info")
    return redirect(url_for('login'))

# -------------------------------------------------------------
# Main Dashboard
# -------------------------------------------------------------
@app.route('/')
@login_required
def dashboard():
    user_id = session['user_id']
    now = datetime.now()
    curr_month = now.strftime('%Y-%m')

    # All-time Total Income, Expense, Balance
    tot_inc = query_db(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'income'",
        (user_id,), one=True
    )['total']
    
    tot_exp = query_db(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'expense'",
        (user_id,), one=True
    )['total']
    
    total_balance = float(tot_inc) - float(tot_exp)

    # Current Month Stats
    # Using substr or strftime compatible with both MySQL and SQLite
    m_inc = query_db(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'income' AND transaction_date LIKE %s",
        (user_id, f"{curr_month}%"), one=True
    )['total']

    m_exp = query_db(
        "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'expense' AND transaction_date LIKE %s",
        (user_id, f"{curr_month}%"), one=True
    )['total']

    m_inc_val = float(m_inc)
    m_exp_val = float(m_exp)
    monthly_savings = m_inc_val - m_exp_val
    savings_rate = round((monthly_savings / m_inc_val * 100), 1) if m_inc_val > 0 else 0

    # Recent 6 Transactions
    recent_transactions = query_db(
        """SELECT t.*, c.name as category_name, c.color as category_color, c.icon as category_icon
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE t.user_id = %s
           ORDER BY t.transaction_date DESC, t.id DESC
           LIMIT 6""",
        (user_id,)
    )

    # Active Savings Goals
    goals = query_db(
        """SELECT *, ROUND((current_amount / target_amount) * 100, 1) as progress_pct
           FROM savings_goals
           WHERE user_id = %s
           ORDER BY status ASC, id DESC
           LIMIT 3""",
        (user_id,)
    )

    # Category list for modal
    categories = query_db(
        "SELECT * FROM categories WHERE user_id IS NULL OR user_id = %s ORDER BY name ASC",
        (user_id,)
    )

    # Check for budget warnings
    budgets = query_db(
        """SELECT b.*, c.name as category_name, c.color as category_color,
                  COALESCE((
                      SELECT SUM(t.amount) 
                      FROM transactions t 
                      WHERE t.user_id = b.user_id 
                        AND t.category_id = b.category_id 
                        AND t.type = 'expense' 
                        AND t.transaction_date LIKE %s
                  ), 0) as spent
           FROM budgets b
           JOIN categories c ON b.category_id = c.id
           WHERE b.user_id = %s AND b.month_year = %s""",
        (f"{curr_month}%", user_id, curr_month)
    )

    budget_alerts = []
    for b in budgets:
        spent = float(b['spent'])
        limit = float(b['monthly_limit'])
        pct = round((spent / limit) * 100, 1) if limit > 0 else 0
        if pct >= 85:
            budget_alerts.append({
                'category_name': b['category_name'],
                'limit': limit,
                'spent': spent,
                'percent': pct,
                'is_exceeded': (pct > 100)
            })

    return render_template(
        'dashboard.html',
        total_balance=total_balance,
        monthly_income=m_inc_val,
        monthly_expense=m_exp_val,
        monthly_savings=monthly_savings,
        savings_rate=savings_rate,
        recent_transactions=recent_transactions,
        goals=goals,
        categories=categories,
        budget_alerts=budget_alerts,
        curr_month_name=now.strftime('%B %Y')
    )

# -------------------------------------------------------------
# Transactions Management (Full Page & APIs)
# -------------------------------------------------------------
@app.route('/transactions')
@login_required
def transactions():
    user_id = session['user_id']
    cat_filter = request.args.get('category', '')
    type_filter = request.args.get('type', '')
    search = request.args.get('search', '').strip()
    month_filter = request.args.get('month', '')

    query = """
        SELECT t.*, c.name as category_name, c.color as category_color, c.icon as category_icon
        FROM transactions t
        JOIN categories c ON t.category_id = c.id
        WHERE t.user_id = %s
    """
    params = [user_id]

    if cat_filter:
        query += " AND t.category_id = %s"
        params.append(cat_filter)
    if type_filter in ['income', 'expense']:
        query += " AND t.type = %s"
        params.append(type_filter)
    if month_filter:
        query += " AND t.transaction_date LIKE %s"
        params.append(f"{month_filter}%")
    if search:
        query += " AND (t.description LIKE %s OR c.name LIKE %s OR t.payment_method LIKE %s)"
        like_search = f"%{search}%"
        params.extend([like_search, like_search, like_search])

    query += " ORDER BY t.transaction_date DESC, t.id DESC"

    all_txs = query_db(query, tuple(params))

    # All user categories for filter dropdown
    categories = query_db(
        "SELECT * FROM categories WHERE user_id IS NULL OR user_id = %s ORDER BY name ASC",
        (user_id,)
    )

    # Calculate summary of currently filtered transactions
    filtered_inc = sum(float(t['amount']) for t in all_txs if t['type'] == 'income')
    filtered_exp = sum(float(t['amount']) for t in all_txs if t['type'] == 'expense')
    net_filtered = filtered_inc - filtered_exp

    return render_template(
        'transactions.html',
        transactions=all_txs,
        categories=categories,
        selected_cat=cat_filter,
        selected_type=type_filter,
        selected_month=month_filter,
        search_query=search,
        filtered_inc=filtered_inc,
        filtered_exp=filtered_exp,
        net_filtered=net_filtered
    )

@app.route('/api/transactions', methods=['POST'])
@login_required
def api_add_transaction():
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form

    amount = data.get('amount')
    tx_type = data.get('type')
    category_id = data.get('category_id')
    payment_method = data.get('payment_method', 'UPI')
    tx_date = data.get('transaction_date')
    description = data.get('description', '').strip()

    if not amount or not tx_type or not category_id or not tx_date:
        return jsonify({'success': False, 'message': 'Please fill all required fields.'}), 400

    try:
        amt = float(amount)
        if amt <= 0:
            return jsonify({'success': False, 'message': 'Amount must be greater than zero.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid amount value.'}), 400

    res = query_db(
        """INSERT INTO transactions (user_id, category_id, amount, type, payment_method, transaction_date, description)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, category_id, amt, tx_type, payment_method, tx_date, description),
        commit=True
    )

    if request.is_json:
        return jsonify({'success': True, 'message': 'Transaction recorded successfully!', 'id': res['lastrowid']})
    
    flash("Transaction added successfully!", "success")
    return redirect(request.referrer or url_for('transactions'))

@app.route('/api/transactions/<int:tx_id>', methods=['GET'])
@login_required
def api_get_transaction(tx_id):
    user_id = session['user_id']
    tx = query_db("SELECT * FROM transactions WHERE id = %s AND user_id = %s", (tx_id, user_id), one=True)
    if not tx:
        return jsonify({'success': False, 'message': 'Transaction not found.'}), 404
    return jsonify({'success': True, 'transaction': tx})

@app.route('/api/transactions/<int:tx_id>', methods=['POST', 'PUT'])
@login_required
def api_update_transaction(tx_id):
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form

    existing = query_db("SELECT id FROM transactions WHERE id = %s AND user_id = %s", (tx_id, user_id), one=True)
    if not existing:
        return jsonify({'success': False, 'message': 'Transaction not found.'}), 404

    amount = float(data.get('amount', 0))
    tx_type = data.get('type')
    category_id = data.get('category_id')
    payment_method = data.get('payment_method', 'UPI')
    tx_date = data.get('transaction_date')
    description = data.get('description', '').strip()

    if amount <= 0:
        return jsonify({'success': False, 'message': 'Amount must be positive.'}), 400

    query_db(
        """UPDATE transactions
           SET category_id = %s, amount = %s, type = %s, payment_method = %s,
               transaction_date = %s, description = %s
           WHERE id = %s AND user_id = %s""",
        (category_id, amount, tx_type, payment_method, tx_date, description, tx_id, user_id),
        commit=True
    )

    if request.is_json:
        return jsonify({'success': True, 'message': 'Transaction updated successfully.'})
    
    flash("Transaction updated successfully!", "success")
    return redirect(url_for('transactions'))

@app.route('/api/transactions/<int:tx_id>/delete', methods=['POST', 'DELETE'])
@login_required
def api_delete_transaction(tx_id):
    user_id = session['user_id']
    query_db("DELETE FROM transactions WHERE id = %s AND user_id = %s", (tx_id, user_id), commit=True)
    
    if request.is_json or request.method == 'DELETE':
        return jsonify({'success': True, 'message': 'Transaction deleted successfully.'})
    
    flash("Transaction deleted.", "info")
    return redirect(request.referrer or url_for('transactions'))

# -------------------------------------------------------------
# Budgets Management
# -------------------------------------------------------------
@app.route('/budgets')
@login_required
def budgets():
    user_id = session['user_id']
    now = datetime.now()
    month_selected = request.args.get('month', now.strftime('%Y-%m'))

    # Get budget list joined with actual spending
    budget_items = query_db(
        """SELECT b.*, c.name as category_name, c.color as category_color, c.icon as category_icon,
                  COALESCE((
                      SELECT SUM(t.amount) 
                      FROM transactions t 
                      WHERE t.user_id = b.user_id 
                        AND t.category_id = b.category_id 
                        AND t.type = 'expense' 
                        AND t.transaction_date LIKE %s
                  ), 0) as spent
           FROM budgets b
           JOIN categories c ON b.category_id = c.id
           WHERE b.user_id = %s AND b.month_year = %s
           ORDER BY b.monthly_limit DESC""",
        (f"{month_selected}%", user_id, month_selected)
    )

    total_budgeted = 0
    total_spent = 0
    formatted_budgets = []

    for b in budget_items:
        limit = float(b['monthly_limit'])
        spent = float(b['spent'])
        total_budgeted += limit
        total_spent += spent
        pct = round((spent / limit) * 100, 1) if limit > 0 else 0
        remaining = limit - spent

        formatted_budgets.append({
            'id': b['id'],
            'category_id': b['category_id'],
            'category_name': b['category_name'],
            'category_color': b['category_color'],
            'category_icon': b['category_icon'],
            'limit': limit,
            'spent': spent,
            'remaining': remaining,
            'percent': pct,
            'is_over': (spent > limit),
            'status_class': 'danger' if pct >= 100 else ('warning' if pct >= 80 else 'success')
        })

    # Expense categories for modal
    expense_categories = query_db(
        "SELECT * FROM categories WHERE type = 'expense' AND (user_id IS NULL OR user_id = %s) ORDER BY name ASC",
        (user_id,)
    )

    return render_template(
        'budgets.html',
        budgets=formatted_budgets,
        categories=expense_categories,
        total_budgeted=total_budgeted,
        total_spent=total_spent,
        total_remaining=(total_budgeted - total_spent),
        selected_month=month_selected
    )

@app.route('/api/budgets', methods=['POST'])
@login_required
def api_set_budget():
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form

    category_id = data.get('category_id')
    monthly_limit = data.get('monthly_limit')
    month_year = data.get('month_year', datetime.now().strftime('%Y-%m'))

    if not category_id or not monthly_limit:
        return jsonify({'success': False, 'message': 'Category and limit are required.'}), 400

    try:
        limit = float(monthly_limit)
        if limit <= 0:
            return jsonify({'success': False, 'message': 'Budget limit must be greater than zero.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid budget amount.'}), 400

    # Check if budget exists
    existing = query_db(
        "SELECT id FROM budgets WHERE user_id = %s AND category_id = %s AND month_year = %s",
        (user_id, category_id, month_year),
        one=True
    )

    if existing:
        query_db(
            "UPDATE budgets SET monthly_limit = %s WHERE id = %s",
            (limit, existing['id']),
            commit=True
        )
    else:
        query_db(
            "INSERT INTO budgets (user_id, category_id, monthly_limit, month_year) VALUES (%s, %s, %s, %s)",
            (user_id, category_id, limit, month_year),
            commit=True
        )

    if request.is_json:
        return jsonify({'success': True, 'message': 'Budget allocated successfully!'})
    
    flash("Budget updated successfully!", "success")
    return redirect(url_for('budgets', month=month_year))

@app.route('/api/budgets/<int:b_id>/delete', methods=['POST', 'DELETE'])
@login_required
def api_delete_budget(b_id):
    user_id = session['user_id']
    query_db("DELETE FROM budgets WHERE id = %s AND user_id = %s", (b_id, user_id), commit=True)
    if request.is_json or request.method == 'DELETE':
        return jsonify({'success': True, 'message': 'Budget deleted.'})
    flash("Budget removed.", "info")
    return redirect(request.referrer or url_for('budgets'))

# -------------------------------------------------------------
# Savings Goals Management
# -------------------------------------------------------------
@app.route('/goals')
@login_required
def goals():
    user_id = session['user_id']
    raw_goals = query_db(
        "SELECT * FROM savings_goals WHERE user_id = %s ORDER BY status ASC, target_date ASC",
        (user_id,)
    )

    total_target = 0
    total_saved = 0
    formatted_goals = []

    for g in raw_goals:
        target = float(g['target_amount'])
        current = float(g['current_amount'])
        total_target += target
        total_saved += current
        pct = round((current / target) * 100, 1) if target > 0 else 0
        pct = min(pct, 100.0)

        formatted_goals.append({
            'id': g['id'],
            'title': g['title'],
            'target_amount': target,
            'current_amount': current,
            'remaining': max(0.0, target - current),
            'target_date': g['target_date'],
            'color': g['color'] or '#3b82f6',
            'status': g['status'],
            'progress_pct': pct
        })

    return render_template(
        'goals.html',
        goals=formatted_goals,
        total_target=total_target,
        total_saved=total_saved
    )

@app.route('/api/goals', methods=['POST'])
@login_required
def api_create_goal():
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form

    title = data.get('title', '').strip()
    target_amount = data.get('target_amount')
    initial_amount = data.get('initial_amount', 0)
    target_date = data.get('target_date') or None
    color = data.get('color', '#3b82f6')

    if not title or not target_amount:
        return jsonify({'success': False, 'message': 'Title and Target Amount are required.'}), 400

    try:
        target = float(target_amount)
        current = float(initial_amount) if initial_amount else 0.0
        if target <= 0:
            return jsonify({'success': False, 'message': 'Target amount must be greater than zero.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid numerical value.'}), 400

    status = 'completed' if current >= target else 'in_progress'

    query_db(
        """INSERT INTO savings_goals (user_id, title, target_amount, current_amount, target_date, color, status)
           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
        (user_id, title, target, current, target_date, color, status),
        commit=True
    )

    if request.is_json:
        return jsonify({'success': True, 'message': 'Savings goal established successfully!'})
    flash("Savings Goal created!", "success")
    return redirect(url_for('goals'))

@app.route('/api/goals/<int:goal_id>/deposit', methods=['POST'])
@login_required
def api_goal_deposit(goal_id):
    user_id = session['user_id']
    data = request.get_json() if request.is_json else request.form

    deposit_amt = data.get('amount')
    if not deposit_amt:
        return jsonify({'success': False, 'message': 'Amount is required.'}), 400

    try:
        amt = float(deposit_amt)
        if amt <= 0:
            return jsonify({'success': False, 'message': 'Deposit amount must be positive.'}), 400
    except ValueError:
        return jsonify({'success': False, 'message': 'Invalid deposit value.'}), 400

    goal = query_db("SELECT * FROM savings_goals WHERE id = %s AND user_id = %s", (goal_id, user_id), one=True)
    if not goal:
        return jsonify({'success': False, 'message': 'Goal not found.'}), 404

    new_amt = float(goal['current_amount']) + amt
    target = float(goal['target_amount'])
    status = 'completed' if new_amt >= target else 'in_progress'

    query_db(
        "UPDATE savings_goals SET current_amount = %s, status = %s WHERE id = %s",
        (new_amt, status, goal_id),
        commit=True
    )

    if request.is_json:
        return jsonify({'success': True, 'message': f'Added {session.get("currency", "₹")}{amt:.2f} to your goal!'})
    flash(f"Added {session.get('currency', '₹')}{amt:.2f} to goal: {goal['title']}!", "success")
    return redirect(url_for('goals'))

@app.route('/api/goals/<int:goal_id>/delete', methods=['POST', 'DELETE'])
@login_required
def api_delete_goal(goal_id):
    user_id = session['user_id']
    query_db("DELETE FROM savings_goals WHERE id = %s AND user_id = %s", (goal_id, user_id), commit=True)
    if request.is_json or request.method == 'DELETE':
        return jsonify({'success': True, 'message': 'Goal deleted.'})
    flash("Savings goal deleted.", "info")
    return redirect(url_for('goals'))

# -------------------------------------------------------------
# Deep Analytics & Chart APIs
# -------------------------------------------------------------
@app.route('/analytics')
@login_required
def analytics():
    user_id = session['user_id']
    return render_template('analytics.html')

@app.route('/api/chart-data')
@login_required
def api_chart_data():
    """Provides JSON datasets for Chart.js interactive visualizations."""
    user_id = session['user_id']
    now = datetime.now()
    curr_month = now.strftime('%Y-%m')

    # 1. Expense Breakdown by Category (Current Month)
    category_expenses = query_db(
        """SELECT c.name, c.color, COALESCE(SUM(t.amount), 0) as total
           FROM categories c
           LEFT JOIN transactions t ON c.id = t.category_id AND t.user_id = %s AND t.type = 'expense' AND t.transaction_date LIKE %s
           WHERE c.type = 'expense'
           GROUP BY c.id, c.name, c.color
           HAVING total > 0
           ORDER BY total DESC""",
        (user_id, f"{curr_month}%")
    )

    # 2. Monthly Cash Flow (Past 6 Months)
    months = []
    for i in range(5, -1, -1):
        # Calculate month strings
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        m_str = f"{year:04d}-{month:02d}"
        months.append(m_str)

    cashflow_data = []
    for m in months:
        inc = query_db(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'income' AND transaction_date LIKE %s",
            (user_id, f"{m}%"), one=True
        )['total']
        
        exp = query_db(
            "SELECT COALESCE(SUM(amount), 0) as total FROM transactions WHERE user_id = %s AND type = 'expense' AND transaction_date LIKE %s",
            (user_id, f"{m}%"), one=True
        )['total']

        # Format label like "May 2026"
        dt_obj = datetime.strptime(m, '%Y-%m')
        label = dt_obj.strftime('%b %y')

        cashflow_data.append({
            'month': m,
            'label': label,
            'income': float(inc),
            'expense': float(exp),
            'net': float(inc) - float(exp)
        })

    # 3. Payment Method Distribution
    payment_methods = query_db(
        """SELECT payment_method, COUNT(*) as count, SUM(amount) as total
           FROM transactions
           WHERE user_id = %s
           GROUP BY payment_method
           ORDER BY total DESC""",
        (user_id,)
    )

    # 4. Daily Spending for Current Month
    daily_txs = query_db(
        """SELECT transaction_date, SUM(amount) as total
           FROM transactions
           WHERE user_id = %s AND type = 'expense' AND transaction_date LIKE %s
           GROUP BY transaction_date
           ORDER BY transaction_date ASC""",
        (user_id, f"{curr_month}%")
    )

    return jsonify({
        'categories': category_expenses,
        'cashflow': cashflow_data,
        'payment_methods': payment_methods,
        'daily': daily_txs
    })

# -------------------------------------------------------------
# Data Export (CSV)
# -------------------------------------------------------------
@app.route('/export/csv')
@login_required
def export_csv():
    user_id = session['user_id']
    transactions = query_db(
        """SELECT t.transaction_date, t.type, c.name as category, t.amount, t.payment_method, t.description
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE t.user_id = %s
           ORDER BY t.transaction_date DESC""",
        (user_id,)
    )

    si = io.StringIO()
    writer = csv.writer(si)
    writer.writerow(['Date', 'Type', 'Category', f'Amount ({session.get("currency", "₹")})', 'Payment Method', 'Description / Notes'])

    for tx in transactions:
        writer.writerow([
            tx['transaction_date'],
            tx['type'].capitalize(),
            tx['category'],
            f"{float(tx['amount']):.2f}",
            tx['payment_method'],
            tx['description'] or ''
        ])

    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=FinFlow_Transactions_{datetime.now().strftime('%Y%m%d')}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

# -------------------------------------------------------------
# User Settings / Profile
# -------------------------------------------------------------
@app.route('/api/profile/currency', methods=['POST'])
@login_required
def update_currency():
    user_id = session['user_id']
    curr = request.form.get('currency', '₹').strip()
    if curr:
        query_db("UPDATE users SET currency = %s WHERE id = %s", (curr, user_id), commit=True)
        session['currency'] = curr
        flash(f"Currency updated to {curr}", "success")
    return redirect(request.referrer or url_for('dashboard'))

# -------------------------------------------------------------
# Database Status Diagnostic API
# -------------------------------------------------------------
@app.route('/api/db-status')
def api_db_status():
    status = get_db_status()
    # Check table count
    is_sqlite = (status.get('engine') == 'SQLite')
    try:
        if is_sqlite:
            tbl_count = query_db("SELECT COUNT(*) as cnt FROM sqlite_master WHERE type='table'", one=True)['cnt']
        else:
            tbl_count = query_db("SELECT COUNT(*) as cnt FROM information_schema.tables WHERE table_schema = %s", (Config.MYSQL_DB,), one=True)['cnt']
    except Exception:
        tbl_count = 0
    return jsonify({
        'status': status,
        'table_count': tbl_count,
        'app': 'FinFlow Personal Finance Dashboard'
    })

# -------------------------------------------------------------
# Run Server
# -------------------------------------------------------------
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("\n=======================================================")
    print(f">> FinFlow Dashboard running at: http://127.0.0.1:{port}")
    print(f">> Active Database Engine: {get_db_status()['engine']}")
    print("=======================================================\n")
    app.run(debug=True, host='127.0.0.1', port=port)
