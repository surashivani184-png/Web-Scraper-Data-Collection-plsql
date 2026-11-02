-- =======================================================
-- FinFlow - Personal Finance Dashboard
-- MCA 1st Semester Mini Project
-- Database Schema for MySQL 8.0+
-- =======================================================

CREATE DATABASE IF NOT EXISTS personal_finance;
USE personal_finance;

-- -------------------------------------------------------
-- Table: users
-- Stores registered users with hashed passwords
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(120) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    currency VARCHAR(10) DEFAULT '₹',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- Table: categories
-- System-defined and user-defined transaction categories
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS categories (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NULL,
    name VARCHAR(50) NOT NULL,
    type ENUM('income', 'expense') NOT NULL,
    icon VARCHAR(50) DEFAULT 'bi-tag',
    color VARCHAR(20) DEFAULT '#4f46e5',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- Table: transactions
-- Records all income and expense entries
-- -------------------------------------------------------
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
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT,
    INDEX idx_user_date (user_id, transaction_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- Table: budgets
-- Monthly budget thresholds per category
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS budgets (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,
    category_id INT NOT NULL,
    monthly_limit DECIMAL(10, 2) NOT NULL,
    month_year VARCHAR(7) NOT NULL, -- Format: YYYY-MM
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY unique_user_cat_month (user_id, category_id, month_year),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- -------------------------------------------------------
-- Table: savings_goals
-- Financial targets and progress tracking
-- -------------------------------------------------------
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

-- -------------------------------------------------------
-- Seed Default Categories
-- -------------------------------------------------------
INSERT INTO categories (user_id, name, type, icon, color) VALUES
(NULL, 'Salary', 'income', 'briefcase', '#10b981'),
(NULL, 'Freelance', 'income', 'laptop', '#06b6d4'),
(NULL, 'Investments', 'income', 'graph-up-arrow', '#8b5cf6'),
(NULL, 'Allowance / Gift', 'income', 'gift', '#ec4899'),
(NULL, 'Other Income', 'income', 'cash-stack', '#14b8a6'),
(NULL, 'Food & Dining', 'expense', 'cup-hot', '#ef4444'),
(NULL, 'Rent & Housing', 'expense', 'house-door', '#f97316'),
(NULL, 'College & Books', 'expense', 'book', '#f59e0b'),
(NULL, 'Groceries', 'expense', 'basket', '#84cc16'),
(NULL, 'Travel & Fuel', 'expense', 'car-front', '#3b82f6'),
(NULL, 'Entertainment', 'expense', 'film', '#a855f7'),
(NULL, 'Utilities & Bills', 'expense', 'lightning-charge', '#6366f1'),
(NULL, 'Health & Medical', 'expense', 'heart-pulse', '#e11d48'),
(NULL, 'Shopping', 'expense', 'bag-check', '#d946ef'),
(NULL, 'Other Expense', 'expense', 'three-dots', '#64748b');
