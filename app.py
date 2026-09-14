import streamlit as st
import sqlite3
import pandas as pd
import os

# --- 0. 讀取商品、價格與圖片 (從 CSV) ---
# 如果找不到 CSV，自動建立一個預設的，避免程式當掉
if not os.path.exists('products.csv'):
    default_data = {
        "name": ["超商 50 元商品卡", "不鏽鋼保溫杯"],
        "price": [50, 150],
        "image_url": ["https://dummyimage.com/400x300/e0e0e0/000000&text=Gift+Card", "https://dummyimage.com/400x300/e0e0e0/000000&text=Thermo+Cup"]
    }
    pd.DataFrame(default_data).to_csv('products.csv', index=False, encoding='utf-8-sig')

# 讀取 CSV 並轉換為字典格式方便後續使用
df_products = pd.read_csv('products.csv', encoding='utf-8-sig')
PRODUCTS = {row['name']: {'price': row['price'], 'image_url': row['image_url']} for _, row in df_products.iterrows()}

# --- 1. 資料庫設定與基礎操作 ---
def init_db():
    conn = sqlite3.connect('souvenirs.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            item TEXT,
            price INTEGER,
            quantity INTEGER,
            total_price INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_order(username, item, price, quantity, total_price):
    conn = sqlite3.connect('souvenirs.db')
    c = conn.cursor()
    c.execute('INSERT INTO orders (username, item, price, quantity, total_price) VALUES (?, ?, ?, ?, ?)', 
              (username, item, price, quantity, total_price))
    conn.commit()
    conn.close()

def delete_order(order_id):
    conn = sqlite3.connect('souvenirs.db')
    c = conn.cursor()
    c.execute('DELETE FROM orders WHERE id=?', (order_id,))
    conn.commit()
    conn.close()

# --- 2. Streamlit 網頁介面 ---
init_db()

st.title("🎁 股東會紀念品簡易訂購網")

st.sidebar.header("身分識別")
username = st.sidebar.text_input("請輸入您的姓名或暱稱：")

if username:
    st.sidebar.success(f"歡迎，{username}！")
    
    tab1, tab2, tab3 = st.tabs(["🛒 紀念品訂購", "📋 我的訂單", "📊 總計數據"])

    # 頁籤 1：商品訂購 (加入圖片顯示)
    with tab1:
        st.subheader("可訂購品項")
        
        item_options = [f"{name} (單價: {info['price']}元)" for name, info in PRODUCTS.items()]
        selected_option = st.selectbox("選擇紀念品：", item_options)
        
        # 解析出商品名稱、價格與圖片網址
        selected_item_name = selected_option.split(" (")[0]
        item_price = PRODUCTS[selected_item_name]['price']
        item_image = PRODUCTS[selected_item_name]['image_url']
        
        # 在表單外顯示圖片，讓它能隨選單即時變化
        if pd.notna(item_image) and str(item_image).strip() != "":
            st.image(item_image, use_container_width=True) # 圖片自動適應手機寬度
            
        with st.form("order_form"):
            quantity = st.number_input("數量：", min_value=1, max_value=10, value=1)
            st.info(f"💰 預估金額： {item_price} x {quantity} = **{item_price * quantity} 元**")
            
            submit_button = st.form_submit_button("送出訂購")
            if submit_button:
                total_price = item_price * quantity
                add_order(username, selected_item_name, item_price, quantity, total_price)
                st.success(f"已成功為 {username} 訂購 {quantity} 份 {selected_item_name}！")

    # 頁籤 2：我的訂單
    with tab2:
        st.subheader("我的訂購紀錄")
        conn = sqlite3.connect('souvenirs.db')
        my_orders = pd.read_sql_query(f"SELECT id AS '訂單編號', item AS '品項', price AS '單價', quantity AS '數量', total_price AS '總價' FROM orders WHERE username='{username}'", conn)
        conn.close()

        if my_orders.empty:
            st.info("目前尚無訂購紀錄。")
        else:
            st.dataframe(my_orders.set_index('訂單編號'), use_container_width=True)
            st.markdown(f"### 💳 您的應付總金額： **{my_orders['總價'].sum()} 元**")
            st.divider()
            st.markdown("### 取消訂單")
            order_to_cancel = st.selectbox("請選擇要取消的訂單編號：", my_orders['訂單編號'].tolist())
            if st.button("確認取消此訂單"):
                delete_order(order_to_cancel)
                st.success("訂單已取消！請重整頁面。")
                st.rerun()

    # 頁籤 3：總計數據
    with tab3:
        st.subheader("後台統計數據")
        conn = sqlite3.connect('souvenirs.db')
        
        st.markdown("### 📦 交付明細 (按人員小計)")
        raw_delivery = pd.read_sql_query("SELECT username, item, SUM(quantity) AS qty, SUM(total_price) AS subtotal FROM orders GROUP BY username, item ORDER BY username", conn)
        
        if raw_delivery.empty:
            st.info("目前尚無任何人訂購。")
        else:
            summary_data = []
            for user, group in raw_delivery.groupby('username'):
                details = "<br>".join([f"• {row['item']} x{row['qty']}" for _, row in group.iterrows()])
                summary_data.append({"訂購人": user, "交付明細": details, "應收金額 (元)": group['subtotal'].sum()})
            
            delivery_summary = pd.DataFrame(summary_data)
            delivery_summary.index = range(1, len(delivery_summary) + 1)
            st.markdown(delivery_summary.to_html(escape=False), unsafe_allow_html=True)
            
            st.divider()
            st.markdown("### 🛒 總採購統計 (按品項)")
            item_summary = pd.read_sql_query("SELECT item AS '品項', SUM(quantity) AS '總數量', SUM(total_price) AS '總金額' FROM orders GROUP BY item", conn)
            item_summary.index = range(1, len(item_summary) + 1)
            st.dataframe(item_summary, use_container_width=True)
            st.markdown(f"### 🏆 訂購總金額： **{item_summary['總金額'].sum()} 元**")
        conn.close()
else:
    st.warning("👈 請先在左側輸入姓名，即可開始使用訂購系統。")