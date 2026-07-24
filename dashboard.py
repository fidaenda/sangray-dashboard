import streamlit as st
import pandas as pd
import mysql.connector
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- PAGE CONFIG ---
st.set_page_config(page_title="SANGRAY Analytics", layout="wide")

# --- DATA RETRIEVAL ---
@st.cache_data(ttl=60)
def get_data():
    conn = mysql.connector.connect(
        host=st.secrets["db_host"],
        port=st.secrets["db_port"],
        user=st.secrets["db_user"],
        password=st.secrets["db_password"],
        database=st.secrets["db_name"],
        ssl_ca="isrgrootx1.pem",
        ssl_verify_cert=True
    )
    
    df_traffic = pd.read_sql("SELECT t.*, s.store_name FROM traffic_logs t LEFT JOIN dim_stores s ON t.store_id = s.store_id", conn)
    df_cust = pd.read_sql("SELECT c.*, s.store_name FROM customers c LEFT JOIN dim_stores s ON c.store_id = s.store_id", conn)
    
    query_trans = """
    SELECT t.*, p.product_name, p.price_per_g, c.gender, c.age_group, c.ethnicity, s.store_name, c.record_time
    FROM transactions t 
    JOIN dim_products p ON t.product_id = p.product_id
    JOIN customers c ON t.customer_id = c.customer_id
    LEFT JOIN dim_stores s ON t.store_id = s.store_id
    """
    df_trans = pd.read_sql(query_trans, conn)
    
    conn.close()
    return df_traffic, df_cust, df_trans

df_traffic_raw, df_cust_raw, df_trans_raw = get_data()

# Preprocessing Jam & Tanggal
for df in [df_traffic_raw, df_cust_raw, df_trans_raw]:
    if not df.empty and 'record_time' in df.columns:
        df['date'] = pd.to_datetime(df['record_time']).dt.date
        df['hour'] = pd.to_datetime(df['record_time']).dt.strftime('%H:00')

# Definisi Urutan Kategori Baku
CAT_ORDERS = {
    'ethnicity': ['Indonesian', 'Chinese', 'Others'],
    'age_group': ['18-25', '26-35', '36-45', '46+'],
    'gender': ['Male', 'Female']
}

# --- SIDEBAR: FILTERS ---
st.sidebar.markdown("### ⚙️ Dashboard Controls")

store_list = ["All Stores"]
if not df_cust_raw.empty:
    store_list.extend(df_cust_raw['store_name'].dropna().unique().tolist())
selected_store = st.sidebar.selectbox("Select Outlet / 选择门店", store_list)

date_list = ["All Dates"]
if not df_cust_raw.empty:
    unique_dates = sorted(df_cust_raw['date'].dropna().unique().tolist(), reverse=True)
    date_list.extend(unique_dates)
selected_date = st.sidebar.selectbox("Select Date / 选择日期", date_list)

# Drill-Down Target di Sidebar
st.sidebar.markdown("---")
st.sidebar.markdown("#### 🎯 Specific Target Filtering")
selected_gender = st.sidebar.selectbox("Gender / 性别", ["All Genders", "Female", "Male"])
selected_ethnicity = st.sidebar.selectbox("Ethnicity / 种族", ["All Ethnicities", "Indonesian", "Chinese", "Others"])
selected_age = st.sidebar.selectbox("Age Group / 年龄段", ["All Age Groups", "18-25", "26-35", "36-45", "46+"])

# Apply Filter Logic
df_traffic = df_traffic_raw.copy()
df_cust = df_cust_raw.copy()
df_trans = df_trans_raw.copy()

if selected_store != "All Stores":
    df_traffic = df_traffic[df_traffic['store_name'] == selected_store]
    df_cust = df_cust[df_cust['store_name'] == selected_store]
    df_trans = df_trans[df_trans['store_name'] == selected_store]

if selected_date != "All Dates":
    df_traffic = df_traffic[df_traffic['date'] == selected_date]
    df_cust = df_cust[df_cust['date'] == selected_date]
    df_trans = df_trans[df_trans['date'] == selected_date]

if selected_gender != "All Genders":
    df_cust = df_cust[df_cust['gender'] == selected_gender]
    df_trans = df_trans[df_trans['gender'] == selected_gender]

if selected_ethnicity != "All Ethnicities":
    df_cust = df_cust[df_cust['ethnicity'] == selected_ethnicity]
    df_trans = df_trans[df_trans['ethnicity'] == selected_ethnicity]

if selected_age != "All Age Groups":
    df_cust = df_cust[df_cust['age_group'] == selected_age]
    df_trans = df_trans[df_trans['age_group'] == selected_age]


# --- HEADER ---
st.markdown("## SANGRAY Analytics / 数据分析")
date_label = "All Time" if selected_date == "All Dates" else selected_date.strftime('%d %B %Y')
st.markdown(f"**Integrated CCTV & POS Dashboard | Store: {selected_store} | Date: {date_label}**")
st.markdown("---")

# --- 1. KPI METRICS ---
total_passerby = df_traffic['passerby_count'].sum() if not df_traffic.empty else 0
total_entrants = df_cust.shape[0]
total_sampled = df_cust[df_cust['is_sampled'] == 1].shape[0] if not df_cust.empty else 0
total_purchases = df_cust[df_cust['final_result'] == 'Purchase'].shape[0] if not df_cust.empty else 0
est_revenue = (df_trans['subtotal'].sum() * 1.11) if not df_trans.empty else 0 

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("PASSERBY / 路人", f"{total_passerby:,}")
col2.metric("ENTRANTS / 进店", f"{total_entrants:,}")
col3.metric("SAMPLED / 试吃", f"{total_sampled:,}")
col4.metric("PURCHASES / 购买", f"{total_purchases:,}")
col5.metric("EST. REVENUE (w/ Tax)", f"Rp {est_revenue:,.0f}")

st.markdown("---")

# --- 2. HOURLY CONVERSION FLOW & FUNNEL ---
col_flow, col_funnel = st.columns([2, 1])

with col_flow:
    st.markdown("#### Hourly Traffic Flow / 每小时流量趋势")
    st.caption("Tracking journey: Passerby ➡️ Entrants ➡️ Sampled ➡️ Purchase")

    if not df_traffic.empty and not df_cust.empty:
        traffic_hr = df_traffic.groupby('hour')['passerby_count'].sum().reset_index()
        entrants_hr = df_cust.groupby('hour').size().reset_index(name='entrants')
        sampled_hr = df_cust[df_cust['is_sampled'] == 1].groupby('hour').size().reset_index(name='sampled')
        purchases_hr = df_cust[df_cust['final_result'] == 'Purchase'].groupby('hour').size().reset_index(name='purchases')
        
        df_hourly = pd.merge(traffic_hr, entrants_hr, on='hour', how='outer')
        df_hourly = pd.merge(df_hourly, sampled_hr, on='hour', how='outer')
        df_hourly = pd.merge(df_hourly, purchases_hr, on='hour', how='outer')
        df_hourly = df_hourly.fillna(0).sort_values('hour')
        
        fig_flow = go.Figure()
        fig_flow.add_trace(go.Scatter(x=df_hourly['hour'], y=df_hourly['passerby_count'], mode='lines', name='Passerby', fill='tozeroy', line=dict(color='#cbd5e1', width=2)))
        fig_flow.add_trace(go.Scatter(x=df_hourly['hour'], y=df_hourly['entrants'], mode='lines', name='Entrants', fill='tozeroy', line=dict(color='#60a5fa', width=2)))
        fig_flow.add_trace(go.Scatter(x=df_hourly['hour'], y=df_hourly['sampled'], mode='lines', name='Sampled', fill='tozeroy', line=dict(color='#a855f7', width=2)))
        fig_flow.add_trace(go.Scatter(x=df_hourly['hour'], y=df_hourly['purchases'], mode='lines', name='Purchases', fill='tozeroy', line=dict(color='#f43f5e', width=2)))
        
        fig_flow.update_layout(
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), 
            hovermode="x unified", 
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor='#f1f5f9')
        )
        st.plotly_chart(fig_flow, use_container_width=True)

with col_funnel:
    st.markdown("#### Overall Conversion Funnel / 转化漏斗")
    st.caption("Global conversion rates from street to register.")
    
    if total_passerby > 0:
        funnel_vals = [total_passerby, total_entrants, total_sampled, total_purchases]
        funnel_stages = ["Passerby", "Entrants", "Sampled", "Purchases"]
        
        fig_funnel = go.Figure(go.Funnel(
            y=funnel_stages, x=funnel_vals,
            textinfo="value+percent initial",
            marker={"color": ["#cbd5e1", "#60a5fa", "#a855f7", "#f43f5e"]}
        ))
        fig_funnel.update_layout(margin=dict(l=20, r=20, t=20, b=0), showlegend=False)
        st.plotly_chart(fig_funnel, use_container_width=True)

st.markdown("---")

# --- 3. PRODUCT & SALES PERFORMANCE ---
st.markdown("#### Product & Sales Performance / 产品与销售")
if not df_trans.empty:
    df_prod_summary = df_trans.groupby('product_name').agg(
        unique_buyers=('customer_id', 'nunique'),
        buy_count=('weight_g', 'count'),
        avg_g=('weight_g', 'mean'),
        total_g=('weight_g', 'sum'),
        total_revenue=('subtotal', 'sum')
    ).reset_index().sort_values(by='total_revenue', ascending=False)

    col_bar, col_table = st.columns([1, 1.3])
    
    with col_bar:
        fig_bar = px.bar(df_prod_summary, x='total_revenue', y='product_name', orientation='h', 
                         title="Top Revenue by Product",
                         labels={'total_revenue': 'Total Revenue (Rp)', 'product_name': 'Product Name'})
        
        fig_bar.update_traces(hovertemplate='Product Name: %{y}<br>Total Revenue: Rp %{x:,.0f}')
        fig_bar.update_layout(yaxis={'categoryorder':'total ascending'}, xaxis_tickformat=',.0f', margin=dict(l=0, r=0, t=30, b=0))
        st.plotly_chart(fig_bar, use_container_width=True)
        
    with col_table:
        st.markdown("**Detailed Sales Summary (with Unique Buyers)**")
        df_display = df_prod_summary.rename(columns={
            'product_name': 'Product', 
            'unique_buyers': 'Buyers',
            'buy_count': 'Trans. Freq',
            'avg_g': 'Avg. Vol (g)',
            'total_g': 'Total Vol (g)', 
            'total_revenue': 'Revenue (Rp)'
        })
        
        df_display['Buyers'] = df_display['Buyers'].apply(lambda x: f"{x} person(s)")
        df_display['Trans. Freq'] = df_display['Trans. Freq'].apply(lambda x: f"{x}x")
        df_display['Avg. Vol (g)'] = df_display['Avg. Vol (g)'].apply(lambda x: f"{x:,.1f} g")
        df_display['Total Vol (g)'] = df_display['Total Vol (g)'].apply(lambda x: f"{x:,.1f} g")
        df_display['Revenue (Rp)'] = df_display['Revenue (Rp)'].apply(lambda x: f"Rp {x:,.0f}")
        
        df_display = df_display[['Product', 'Buyers', 'Trans. Freq', 'Avg. Vol (g)', 'Total Vol (g)', 'Revenue (Rp)']]
        st.dataframe(df_display, use_container_width=True, hide_index=True)

st.markdown("---")

# --- 4. CUSTOMER SEGMENTATION CROSS-TABULATION (Subplots with Totals & Clean Hover) ---
st.markdown("#### Product Preference Profiling")
st.caption("What do specific demographic groups tend to buy?")

if not df_trans.empty:
    color_map = {
        'okra': '#22c55e',          
        'green bean': '#10b981',    
        'strawberry': '#f43f5e',
        'sweet potato': '#d97706',
        'pumpkin': '#f97316',       
        'mango': '#fbbf24',         
        'apricot': '#ea580c',       
        'peach': '#facc15',         
        'lotus': '#fbcfe8',         
        'mushroom': '#a8a29e',      
        'pecan': '#713f12',         
        'macadamia': '#d97706',     
        'apple': '#84cc16',         
        'guava': '#34d399',         
        'orange': '#f97316',        
        'cranberry': '#e11d48',     
        'kiwi': '#65a30d',          
        'pineapple': '#fde047',     
        'ball': '#ec4899',
        'cashew': '#b45309',
        'berry' : '#db2777'          
    }

    def get_color(prod_name):
        for key, hex_code in color_map.items():
            if key.lower() in prod_name.lower():
                return hex_code
        return '#94a3b8'

    product_totals = df_trans.groupby('product_name')['weight_g'].sum().sort_values(ascending=False)
    sorted_products = product_totals.index.tolist()

    df_gen = df_trans.groupby(['gender', 'product_name'])['weight_g'].sum().reset_index()
    df_eth = df_trans.groupby(['ethnicity', 'product_name'])['weight_g'].sum().reset_index()
    df_age = df_trans.groupby(['age_group', 'product_name'])['weight_g'].sum().reset_index()

    fig_seg = make_subplots(rows=1, cols=3, 
                            subplot_titles=("Volume by Gender", "Volume by Ethnicity", "Volume by Age Group"),
                            shared_yaxes=False)

    def add_layer(df_sub, x_col, col_idx):
        for prod in sorted_products:
            df_prod = df_sub[df_sub['product_name'] == prod]
            if not df_prod.empty:
                fig_seg.add_trace(go.Bar(
                    x=df_prod[x_col], 
                    y=df_prod['weight_g'],
                    name=prod,
                    marker_color=get_color(prod),
                    text=df_prod['weight_g'].apply(lambda x: f"{x:.0f}" if x > 50 else ""),
                    textposition='inside',
                    insidetextanchor='middle',
                    legendgroup=prod,
                    showlegend=(col_idx == 1),
                    hovertemplate="<b>%{x}</b><br>" + prod + ": %{y:,.0f} g<extra></extra>"
                ), row=1, col=col_idx)

    add_layer(df_gen, 'gender', 1)
    add_layer(df_eth, 'ethnicity', 2)
    add_layer(df_age, 'age_group', 3)

    def add_totals_annotation(df_sub, x_col, col_idx):
        totals = df_sub.groupby(x_col)['weight_g'].sum().reset_index()
        for _, row in totals.iterrows():
            fig_seg.add_annotation(
                x=row[x_col],
                y=row['weight_g'],
                text=f"<b>Total: {row['weight_g']:,.0f}g</b>",
                showarrow=False,
                yshift=10,
                row=1, col=col_idx,
                font=dict(size=10, color="#1e293b")
            )

    add_totals_annotation(df_gen, 'gender', 1)
    add_totals_annotation(df_eth, 'ethnicity', 2)
    add_totals_annotation(df_age, 'age_group', 3)

    fig_seg.update_layout(
        barmode='stack',
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.2,
            xanchor="center",
            x=0.5
        ),
        margin=dict(t=50, b=0, l=0, r=0),
        height=580
    )
    
    fig_seg.update_xaxes(categoryorder='array', categoryarray=CAT_ORDERS['gender'], row=1, col=1)
    fig_seg.update_xaxes(categoryorder='array', categoryarray=CAT_ORDERS['ethnicity'], row=1, col=2)
    fig_seg.update_xaxes(categoryorder='array', categoryarray=CAT_ORDERS['age_group'], row=1, col=3)

    st.plotly_chart(fig_seg, use_container_width=True)
else:
    st.info("Belum ada data transaksi pembelian.")

st.markdown("---")

# --- 5. CCTV-EXCLUSIVE BEHAVIORAL INSIGHTS ---
st.markdown("## 🎥 CCTV Behavioral Analytics / 监控行为分析")
st.caption("Advanced insights derived exclusively from interaction durations, traffic capture, and sampling behavior.")

if not df_cust.empty and 'end_time' in df_cust.columns:
    df_cust['record_dt'] = pd.to_datetime(df_cust['record_time'])
    df_cust['end_dt'] = pd.to_datetime(df_cust['end_time'])
    df_cust['dwell_time_mins'] = (df_cust['end_dt'] - df_cust['record_dt']).dt.total_seconds() / 60
    
    col_dwell, col_capture = st.columns(2)
    
    with col_dwell:
        st.markdown("#### Avg. Dwell Time by Result / 停留时间与结果")
        st.caption("Do buyers spend more time at the booth than window shoppers?")
        df_dwell = df_cust.groupby('final_result')['dwell_time_mins'].mean().reset_index()
        df_dwell['dwell_time_mins'] = df_dwell['dwell_time_mins'].round(1)
        
        fig_dwell = px.bar(df_dwell, x='final_result', y='dwell_time_mins', text='dwell_time_mins',
                           color='final_result', color_discrete_map={'Purchase': '#10b981', 'Just Looking': '#94a3b8'},
                           labels={'final_result': 'Final Result', 'dwell_time_mins': 'Dwell Time (Mins)'}) 
        fig_dwell.update_traces(texttemplate='%{text} Mins', textposition='outside')
        fig_dwell.update_layout(showlegend=False, margin=dict(t=30, b=0), yaxis_title="Minutes")
        st.plotly_chart(fig_dwell, use_container_width=True)

    with col_capture:
        st.markdown("#### Store Capture Rate by Hour / 进店率")
        st.caption("Percentage of Passerby who actually stepped into the booth.")
        if not df_traffic.empty:
            df_cap_traf = df_traffic.groupby('hour')['passerby_count'].sum().reset_index()
            df_cap_cust = df_cust.groupby('hour').size().reset_index(name='entrants')
            df_capture = pd.merge(df_cap_traf, df_cap_cust, on='hour', how='inner')
            df_capture['capture_rate'] = (df_capture['entrants'] / df_capture['passerby_count']) * 100
            df_capture['capture_rate'] = df_capture['capture_rate'].round(1)
            
            fig_cap = px.line(df_capture, x='hour', y='capture_rate', markers=True, text='capture_rate',
                              labels={'hour': 'Time (Hour)', 'capture_rate': 'Capture Rate (%)'})
            fig_cap.update_traces(texttemplate='%{text}%', textposition='top center', line=dict(color='#f59e0b', width=3))
            fig_let = fig_cap.update_layout(margin=dict(t=30, b=0), yaxis_title="Capture Rate (%)")
            st.plotly_chart(fig_cap, use_container_width=True)

    st.markdown("#### Tester Conversion Effectiveness by Segment / 试吃转化率")
    st.caption("Which demographic has the highest probability of buying AFTER trying a sample?")
    
    df_sampled = df_cust[df_cust['is_sampled'] == 1].copy()
    if not df_sampled.empty:
        seg_total = df_sampled.groupby(['age_group', 'ethnicity']).size().reset_index(name='total_sampled')
        seg_buy = df_sampled[df_sampled['final_result'] == 'Purchase'].groupby(['age_group', 'ethnicity']).size().reset_index(name='total_buy')
        
        df_seg_conv = pd.merge(seg_total, seg_buy, on=['age_group', 'ethnicity'], how='left').fillna(0)
        df_seg_conv['conversion_rate'] = (df_seg_conv['total_buy'] / df_seg_conv['total_sampled']) * 100
        df_seg_conv['conversion_rate'] = df_seg_conv['conversion_rate'].round(0)
        
        heatmap_data = df_seg_conv.pivot(index='age_group', columns='ethnicity', values='conversion_rate')
        heatmap_data = heatmap_data.reindex(index=CAT_ORDERS['age_group'], columns=CAT_ORDERS['ethnicity'], fill_value=0)
        
        fig_heat = px.imshow(heatmap_data, aspect="auto", color_continuous_scale='Blues',
                             labels=dict(x="Ethnicity", y="Age Group", color="Conv. Rate (%)")) 
        
        fig_heat.update_traces(texttemplate="%{z:.0f}%", textfont_size=12)
        fig_heat.update_layout(margin=dict(t=30, b=0), xaxis_title="Ethnicity", yaxis_title="Age Group")
        
        st.plotly_chart(fig_heat, use_container_width=True)