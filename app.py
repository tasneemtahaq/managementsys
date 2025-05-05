import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime

# Data model classes
class MenuItem:
    def __init__(self, id, name, price, cost):
        self.id = id
        self.name = name
        self.price = price
        self.cost = cost

# Database handler
class RestaurantDB:
    def __init__(self, db_name="restaurant.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self._create_tables()

    def _create_tables(self):
        cursor = self.conn.cursor()
        # Create menu table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price REAL,
                cost REAL DEFAULT 0.0
            )
        """)
        # Create orders table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_revenue REAL DEFAULT 0.0,
                total_cost REAL DEFAULT 0.0
            )
        """)
        # Create order_items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                order_id INTEGER,
                menu_id INTEGER,
                FOREIGN KEY(order_id) REFERENCES orders(id) ON DELETE CASCADE,
                FOREIGN KEY(menu_id) REFERENCES menu(id) ON DELETE CASCADE
            )
        """)
        # Migrate menu
        cursor.execute("PRAGMA table_info(menu)")
        if 'cost' not in [col[1] for col in cursor.fetchall()]:
            cursor.execute("ALTER TABLE menu ADD COLUMN cost REAL DEFAULT 0.0")
        # Migrate orders
        cursor.execute("PRAGMA table_info(orders)")
        order_cols = [col[1] for col in cursor.fetchall()]
        if 'created_at' not in order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN created_at TIMESTAMP")
            cursor.execute("UPDATE orders SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        if 'total_revenue' not in order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN total_revenue REAL DEFAULT 0.0")
        if 'total_cost' not in order_cols:
            cursor.execute("ALTER TABLE orders ADD COLUMN total_cost REAL DEFAULT 0.0")
        self.conn.commit()

    def add_menu_item(self, name, price, cost):
        cursor = self.conn.cursor()
        cursor.execute("INSERT INTO menu (name, price, cost) VALUES (?, ?, ?)", (name, price, cost))
        self.conn.commit()

    def get_menu(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id, name, price, cost FROM menu")
        return [MenuItem(*row) for row in cursor.fetchall()]

    def delete_menu_item(self, item_id):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM order_items WHERE menu_id = ?", (item_id,))
        cursor.execute("DELETE FROM menu WHERE id = ?", (item_id,))
        self.conn.commit()

    def place_order(self, item_ids):
        cursor = self.conn.cursor()
        total_rev, total_cost = 0.0, 0.0
        for item_id in item_ids:
            cursor.execute("SELECT price, cost FROM menu WHERE id = ?", (item_id,))
            row = cursor.fetchone()
            if row:
                total_rev += row[0]
                total_cost += row[1]
        cursor.execute("INSERT INTO orders (total_revenue, total_cost) VALUES (?, ?)", (total_rev, total_cost))
        order_id = cursor.lastrowid
        for item_id in item_ids:
            cursor.execute("INSERT INTO order_items (order_id, menu_id) VALUES (?, ?)", (order_id, item_id))
        self.conn.commit()

    def get_orders_df(self):
        df = pd.read_sql_query(
            "SELECT id, created_at, total_revenue, total_cost FROM orders", 
            self.conn, 
            parse_dates=['created_at']
        )
        df['profit'] = df['total_revenue'] - df['total_cost']
        return df

# Streamlit UI
st.title("🍽️ Restaurant Management System")

# Initialize database
db = RestaurantDB()
menu_items = db.get_menu()

# Sidebar: Add menu item
st.sidebar.header("Add Menu Item")
name = st.sidebar.text_input("Name")
price = st.sidebar.number_input("Price", 0.0, 10000.0, step=0.5)
cost = st.sidebar.number_input("Cost", 0.0, 10000.0, step=0.5)
if st.sidebar.button("Add Item"):
    db.add_menu_item(name, price, cost)
    st.sidebar.success("Item added")

# Menu display and delete
st.header("📋 Menu")
for item in menu_items:
    col1, col2 = st.columns([4,1])
    with col1:
        st.write(f"**{item.name}** - Sell: ${item.price:.2f} | Cost: ${item.cost:.2f}")
    with col2:
        if st.button("❌", key=f"del_{item.id}"):
            db.delete_menu_item(item.id)
            st.experimental_rerun()

# Place order
st.header("🛒 Place Order")
selected = st.multiselect(
    "Select items to order", 
    options=[(item.id, item.name) for item in menu_items], 
    format_func=lambda x: x[1]
)
if st.button("Place Order") and selected:
    db.place_order([x[0] for x in selected])
    st.success("Order placed")

# Sales report
df = db.get_orders_df()
st.header("📈 Sales Report")
if df.empty:
    st.info("No orders yet. Place an order to see reports.")
else:
    timeframe = st.selectbox("View by", ["Daily", "Weekly", "Monthly", "Yearly"])
    
    if timeframe == "Daily":
        df['period'] = df['created_at'].dt.date.astype(str)
    elif timeframe == "Weekly":
        df['period'] = df['created_at'].dt.to_period("W").astype(str)
    elif timeframe == "Monthly":
        df['period'] = df['created_at'].dt.to_period("M").astype(str)
    else:  # Yearly
        df['period'] = df['created_at'].dt.to_period("Y").astype(str)

    grouped = df.groupby('period')[['total_revenue','total_cost','profit']].sum()

    st.line_chart(grouped)
    st.dataframe(grouped)

