import streamlit as st
import pandas as pd
import numpy as np
import altair as alt
from datetime import datetime, timedelta
# Import logic từ file logic.py của nhóm
from logic import DatabaseManager, BankGoal, CashGoal

# --- 1. CẤU HÌNH TRANG & GIAO DIỆN (DARK FINANCE) ---
st.set_page_config(page_title="Smart Savings Navigator", page_icon="💰", layout="wide")

st.markdown("""
    <style>
    .stApp, [data-testid="stHeader"], .main { background-color: #050A18 !important; color: #E0E1DD !important; }
    [data-testid="stSidebar"] { background-color: #0B1426 !important; border-right: 1px solid #1C2541 !important; }
    h1, h2, h3, p, label { color: #FFD700 !important; font-family: 'Segoe UI', sans-serif; }
    input, select, [data-baseweb="select"], [data-baseweb="input"] {
        background-color: #1A2238 !important; color: #FFFFFF !important; border: 1px solid #FFD700 !important;
    }
    .stButton>button {
        background: linear-gradient(45deg, #FFD700, #B8860B) !important;
        color: #050A18 !important; font-weight: bold !important; width: 100% !important;
    }
    /* Nút Xoá màu Đỏ */
    button[kind="secondary"] { background-color: #7B0000 !important; color: white !important; border: 1px solid #FF4B4B !important; }
    .stAlert { background-color: #1A2238 !important; color: #FFD700 !important; border: 1px solid #FFD700 !important; }
    </style>
    """, unsafe_allow_html=True)

db = DatabaseManager() # Khởi tạo Database
# --- MỚI: Đọc dữ liệu từ CSV ---
try:
    banks_df = pd.read_csv("banks.csv")
    # Lọc lấy lãi suất mới nhất của năm 2026 để hiển thị lúc tạo mục tiêu
    banks_2026 = banks_df[banks_df['year'] == 2026]
except Exception as e:
    st.error(f"Lỗi đọc file banks.csv: {e}")
    # Dữ liệu dự phòng nếu file lỗi
    banks_2026 = pd.DataFrame({"bank_name": ["MB Bank"], "interest_rate": [0.061]})
    
# --- 2. SIDEBAR NAVIGATION ---
st.sidebar.title("📌 Navigation")
page = st.sidebar.radio("Go to", ["Create Goal", "Savings Plans", "Analytics Dashboard"])

st.title("🚀 Smart Savings Navigator")
st.write("An intelligent financial 'GPS' that reroutes your path based on actual income.")

# --- 3. PAGE 1: CREATE GOAL ---
if page == "Create Goal":
    st.header("🎯 Architect a New Goal")
    currency = st.sidebar.radio("Transaction Currency", ["VND", "$"], horizontal=False)
    
    # Đặt Category và Bank Selection ở ngoài Form để Label & Rate nhảy ngay lập tức
    goal_type = st.selectbox("Savings Category", ["Cash Savings (CashGoal)", "Bank Deposit (BankGoal)"])
    
    interest = 0.0
    if "BankGoal" in goal_type:
        bank_names = banks_2026['bank_name'].tolist()
        bank_choice = st.selectbox("Select Bank (Interest Rate 2026)", bank_names)
        interest_raw = banks_2026[banks_2026['bank_name'] == bank_choice]['interest_rate'].values[0]
        # Fix lỗi 520% nếu CSV để số 5.2 thay vì 0.052
        interest = interest_raw if interest_raw < 1 else interest_raw / 100
        st.info(f"System-recorded interest rate: {interest*100:.2f}%/year")

    with st.form("goal_form"):
        col1, col2 = st.columns(2)
        with col1:
            goal_name = st.text_input("Goal Name")
            target = st.number_input(f"Target Amount ({currency})", min_value=0.0, step=100.0, value=50000000.0 if currency == "VND" else 2500.0)
        
        with col2:
            st.write("Duration to Save")
            c_year, c_month = st.columns(2)
            with c_year: years = st.number_input("Years", min_value=0, step=1, value=0)
            with c_month: months_input = st.number_input("Months", min_value=0, max_value=11, step=1, value=6)
            total_months = (years * 12) + months_input 

        submit = st.form_submit_button("Initialize Financial Architecture")

    if submit and total_months > 0:
        goal_id = goal_name.lower().replace(" ", "_")
        start_date = datetime.now().strftime("%Y-%m-%d")
        deadline = (datetime.now() + timedelta(days=int(total_months*30))).strftime("%Y-%m-%d")
        
        if "BankGoal" in goal_type:
            new_goal = BankGoal(goal_id, goal_name, target, start_date, deadline, interest, target/total_months, currency=currency)
        else:
            new_goal = CashGoal(goal_id, goal_name, target, start_date, deadline, target/total_months, currency=currency)
        
        db.save_goal(new_goal.to_dict())
        st.success(f"Goal '{goal_name}' created!")
        st.rerun()


# --- 4. PAGE 2: SAVINGS PLANS ---
elif page == "Savings Plans":
    st.header("📋 Your Saving Architectures")
    with db._get_connection() as conn:
        goals_df = pd.read_sql("SELECT * FROM Goals", conn) #

    if goals_df.empty:
        st.info("No active plans found.")
    else:
        for index, row in goals_df.iterrows():
            # Khôi phục Object với đầy đủ thuộc tính từ DB
            if row['goal_type'] == "BankGoal":
                goal_obj = BankGoal(row['goal_id'], row['goal_name'], row['target'], row['start_date'], row['deadline'], 
                                    row['annual_interest_rate'], row['monthly_contribution'], currency=row['currency'])
            else:
                goal_obj = CashGoal(row['goal_id'], row['goal_name'], row['target'], row['start_date'], 
                                   row['deadline'], row['monthly_contribution'], currency=row['currency'])
            
            goal_obj._balance = row['balance'] 
            analysis = goal_obj.recalculate_route() 
            sym = "₫" if row['currency'] == "VND" else "$"

            with st.expander(f"🔹 {row['goal_name']} ({row['currency']}) - {goal_obj.get_progress_percentage():.1f}%"):
                col_info, col_action = st.columns([2, 1])
                with col_info:
                    # 1. Tổng quan tiến độ
                    st.write(f"#### 💰 {row['goal_name']} Status")
                    st.write(f"**Target:** {row['target']:,.0f} {sym} | **Current Saved:** {row['balance']:,.0f} {sym}")
                    st.progress(min(goal_obj.get_progress_percentage()/100, 1.0))
                    
                    # 2. Hệ thống định vị tài chính (Dynamic Tracking)
                    st.write("### 🛰️ Financial GPS Tracking")
                    met1, met2, met3 = st.columns(3)
                    
                    # Cột 1: Lộ trình nạp tiền mới hàng tháng
                    met1.metric("Required/Mo", f"{analysis['new_monthly_required']:,.0f} {sym}", 
                               help="Số tiền thực tế bạn cần nạp mỗi tháng từ bây giờ để đạt mục tiêu.")

                    # Cột 2: Quy chế lãi suất vs. Tiền nạp bù
                    # PHẦN THAY ĐỔI: THÊM BẢNG ĐỘ NHẠY
                    if row['goal_type'] == "BankGoal":
                        interest_val = analysis.get('interest_gain_projection', 0)
                        met2.metric("Projected Interest", f"+{interest_val:,.0f} {sym}")
                        
                        st.write("---")
                        st.write("🔍 **Interest Sensitivity (Market Comparison 2026)**")
                        # Chuẩn bị kịch bản từ CSV để gọi hàm analyze_interest_sensitivity
                        scenarios = banks_2026.rename(columns={'bank_name': 'bank', 'interest_rate': 'rate'}).to_dict('records')
                        sensitivity_results = goal_obj.analyze_interest_sensitivity(scenarios)
                        
                        sens_df = pd.DataFrame(sensitivity_results)
                        # Chèn vào phần render table ở Savings Plans
                        # Chèn vào phần render table ở Savings Plans
                        st.table(sens_df[['bank', 'annual_interest_rate', 'required_monthly_saving', 'monthly_saving_difference']]
                                 .rename(columns={'bank': 'Bank', 'annual_interest_rate': 'Rate', 
                                  'required_monthly_saving': 'New Req/Mo', 'monthly_saving_difference': 'Gain/Loss'})
                                 .style.format({'Rate': '{:.2%}', 'New Req/Mo': '{:,.0f}', 'Gain/Loss': '{:+,.0f}'})
                                 .highlight_max(subset=['Gain/Loss'], color='#004d00')) # Tô đậm ngân hàng hời nhất
                    else:
                        met2.metric("Catch-up", f"+{int(analysis['catch_up_per_month']):,} {sym}")
                    # Cột 3: Thời gian còn lại
                    met3.metric("Remaining", f"{analysis['remaining_months']:.1f} Mo", 
                               help="Số tháng còn lại tính từ hôm nay đến ngày Deadline.")
                    
                    # 3. Thông tin tư vấn từ hệ thống
                    st.info(f"💡 **Financial Advisor:** {analysis['status_message']}")

                with col_action:
                    deposit_amt = st.number_input(f"Deposit ({sym})", min_value=0.0, step=100.0, key=f"in_{row['goal_id']}")
                    if st.button("Confirm Deposit", key=f"btn_{row['goal_id']}"):
                        db.add_transaction(row['goal_id'], deposit_amt, 'DEPOSIT') #
                        st.rerun()
                    if st.button("🗑️ Delete Goal", key=f"del_{row['goal_id']}"):
                        db.delete_goal(row['goal_id']) #
                        st.rerun()

                # Biểu đồ lịch sử
                st.write("---")
                st.write("### 📈 Progress History")
                history = db.get_history(row['goal_id'])
                if history:
                    h_df = pd.DataFrame(history, columns=['ID', 'Goal_ID', 'Amount', 'Type', 'Timestamp'])
                    h_df['Timestamp'] = pd.to_datetime(h_df['Timestamp'])
                    h_df = h_df.sort_values('Timestamp')
                    h_df['Cumulative'] = h_df['Amount'].cumsum()
                    h_df['Time'] = h_df['Timestamp'].dt.strftime('%d/%m %H:%M')
                    st.line_chart(h_df.set_index('Time')['Cumulative'])
                
# --- 5. PAGE 3: ANALYTICS DASHBOARD ---
elif page == "Analytics Dashboard":
    st.header("📊 Financial Architect Insights")
    with db._get_connection() as conn:
        df = pd.read_sql("SELECT * FROM Goals", conn) 
    
    if not df.empty:
        # Chia 2 Chart riêng biệt để không lệch tỷ giá
        vnd_df = df[df['currency'] == "VND"]
        usd_df = df[df['currency'] == "$"]

        if not vnd_df.empty:
            st.subheader("🇻🇳 VND Portfolio")
            st.metric("Total VND Saved", f"{vnd_df['balance'].sum():,.0f} ₫")
            st.bar_chart(vnd_df.set_index('goal_name')[['balance', 'target']])

        if not usd_df.empty:
            st.subheader("🇺🇸 USD Portfolio")
            st.metric("Total USD Saved", f"${usd_df['balance'].sum():,.2f}")
            st.bar_chart(usd_df.set_index('goal_name')[['balance', 'target']])
        
        # --- TRONG PHẦN ANALYTICS DASHBOARD --- 

        st.write("### 🏦 Interest Rate Comparison & Trends (2024 - 2026)")

# 1. Chuẩn bị dữ liệu: Chuyển Year sang String để cố định 3 mốc
        chart_data = banks_df.copy()
        chart_data['year'] = chart_data['year'].astype(str)

# 2. Tạo biểu đồ đường với Altair để "Focus" vào sự khác biệt
        line_chart = alt.Chart(chart_data).mark_line(point=True).encode(
            x=alt.X('year:N', title='Year'), # N là Nominal (định danh) để hiện đúng 2024, 2025, 2026
            y=alt.Y('interest_rate:Q', 
                title='Annual Interest Rate', 
                scale=alt.Scale(zero=False)), # QUAN TRỌNG: Không bắt đầu từ 0 để thấy rõ độ dốc
            color=alt.Color('bank_name:N', title='Bank'),
            tooltip=['bank_name', 'year', 'interest_rate'] # Rà chuột để xem số chi tiết
        ).properties(
            height=450 # Tăng chiều cao để biểu đồ thoáng hơn
        ).interactive() # Cho phép user phóng to/thu nhỏ nếu muốn

        st.altair_chart(line_chart, use_container_width=True)

