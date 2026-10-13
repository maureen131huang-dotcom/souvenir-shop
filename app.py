import streamlit as st
import pandas as pd
import os
from supabase import create_client, Client

# --- 0. 連線至 Supabase 雲端資料庫 ---
@st.cache_resource
def init_supabase() -> Client:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- 1. 讀取商品、價格與圖片 (從 CSV) ---
if not os.path.exists('products.csv'):
    default_data = {
        "name": ["超商 50 元商品卡", "不鏽鋼保溫杯"],
        "price": [50, 150],
        "image_url": ["https://dummyimage.com/400x300/e0e0e0/000000&text=Gift+Card", "https://dummyimage.com/400x300/e0e0e0/000000&text=Thermo+Cup"]
    }
    pd.DataFrame(default_data).to_csv('products.csv', index=False, encoding='utf-8-sig')

df_products = pd.read_csv('products.csv', encoding='utf-8-sig')
PRODUCTS = {row['name']: {'price': int(row['price']), 'image_url': row['image_url']} for _, row in df_products.iterrows()}

# --- 2. 資料庫操作函數 (Supabase 版) ---
def add_order(username, item, price, quantity, total_price):
    """新增訂單至雲端"""
    data = {
        "username": username,
        "item": item,
        "price": int(price),
        "quantity": int(quantity),
        "total_price": int(total_price)
    }
    supabase.table("orders").insert(data).execute()

def delete_order(order_id):
    """從雲端刪除指定訂單"""
    supabase.table("orders").delete().eq("id", int(order_id)).execute()

def get_user_orders(username):
    """讀取特定使用者的訂單"""
    res = supabase.table("orders").select("id, item, price, quantity, total_price").eq("username", username).order("id").execute()
    return pd.DataFrame(res.data)

def get_all_orders():
    """讀取所有訂單"""
    res = supabase.table("orders").select("*").order("id").execute()
    return pd.DataFrame(res.data)

# --- 3. Streamlit 網頁介面 ---
st.title("🎁 股東會紀念品簡易訂購網")

st.sidebar.header("身分識別")
username = st.sidebar.text_input("請輸入您的姓名或暱稱：").strip()

if username:
    st.sidebar.success(f"歡迎，{username}！")
    
    tab1, tab2, tab3 = st.tabs(["🛒 紀念品訂購", "📋 我的訂單", "📊 總計數據"])

    # 頁籤 1：商品訂購
    with tab1:
        st.subheader("可訂購品項")
        
        item_options = [f"{name} (單價: {info['price']}元)" for name, info in PRODUCTS.items()]
        selected_option = st.selectbox("選擇紀念品：", item_options)
        
        selected_item_name = selected_option.split(" (")[0]
        item_price = PRODUCTS[selected_item_name]['price']
        item_image = PRODUCTS[selected_item_name]['image_url']
        
        if pd.notna(item_image) and str(item_image).strip() != "":
            st.image(item_image, use_container_width=True)
            
        with st.form("order_form"):
            quantity = st.number_input("數量：", min_value=1, max_value=10, value=1)
            st.info(f"💰 預估金額： {item_price} x {quantity} = **{item_price * quantity} 元**")
            
            submit_button = st.form_submit_button("送出訂購")
            if submit_button:
                total_price = item_price * quantity
                add_order(username, selected_item_name, item_price, quantity, total_price)
                st.success(f"已成功為 {username} 訂購 {quantity} 份 {selected_item_name}！總計 {total_price} 元。")

    # 頁籤 2：我的訂單
    with tab2:
        st.subheader("我的訂購紀錄")
        my_orders = get_user_orders(username)

        if my_orders.empty:
            st.info("目前尚無訂購紀錄。")
        else:
            my_orders = my_orders.rename(columns={
                'id': '訂單編號',
                'item': '品項',
                'price': '單價',
                'quantity': '數量',
                'total_price': '總價'
            })
            st.dataframe(my_orders.set_index('訂單編號'), use_container_width=True)
            
            personal_total = my_orders['總價'].sum()
            st.markdown(f"### 💳 您的應付總金額： **{personal_total} 元**")
            
            st.divider()
            st.markdown("### 取消訂單")
            order_to_cancel = st.selectbox("請選擇要取消的訂單編號：", my_orders['訂單編號'].tolist())
            if st.button("確認取消此訂單"):
                delete_order(order_to_cancel)
                st.success("訂單已取消！")
                st.rerun()

    # 頁籤 3：總計數據
    with tab3:
        st.subheader("後台統計數據")
        all_orders = get_all_orders()
        
        st.markdown("### 📦 交付明細 (按人員小計)")
        if all_orders.empty:
            st.info("目前尚無任何人訂購。")
        else:
            # 依訂購人與品項分組加總
            raw_delivery = all_orders.groupby(['username', 'item'], as_index=False).agg(
                qty=('quantity', 'sum'),
                subtotal=('total_price', 'sum')
            ).sort_values('username')
            
            summary_data = []
            for user, group in raw_delivery.groupby('username'):
                details = "<br>".join([f"• {row['item']} x{row['qty']}" for _, row in group.iterrows()])
                summary_data.append({
                    "訂購人": user,
                    "交付明細": details,
                    "應收金額 (元)": group['subtotal'].sum()
                })
            
            delivery_summary = pd.DataFrame(summary_data)
            delivery_summary.index = range(1, len(delivery_summary) + 1)
            st.markdown(delivery_summary.to_html(escape=False), unsafe_allow_html=True)
            
            st.divider()
            st.markdown("### 🛒 總採購統計 (按品項)")
            item_summary = all_orders.groupby('item', as_index=False).agg(
                總數量=('quantity', 'sum'),
                總金額=('total_price', 'sum')
            ).rename(columns={'item': '品項'})
            
            item_summary.index = range(1, len(item_summary) + 1)
            st.dataframe(item_summary, use_container_width=True)
            st.markdown(f"### 🏆 訂購總金額： **{item_summary['總金額'].sum()} 元**")
            
            st.divider()
            # 依然保留一鍵下載 Excel/CSV 報表的功能，方便你對帳
            csv_backup = all_orders.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
            st.download_button(
                label="📥 下載完整訂單明細表 (CSV)",
                data=csv_backup,
                file_name="orders_export.csv",
                mime="text/csv"
            )
else:
    st.warning("👈 請先在左側輸入姓名，即可開始使用訂購系統。")
