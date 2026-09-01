import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import io
from collections import Counter
import plotly.express as px
from urllib.parse import quote

st.set_page_config(page_title="Prom Analyzer Pro", page_icon="📊", layout="wide")

st.markdown("""
<style>
    .table-header {
        display: flex;
        padding: 12px 16px;
        background-color: #FAF9FE;
        border: 1px solid #EAE6F8;
        border-radius: 8px 8px 0 0;
        font-weight: 700;
        font-size: 0.75rem;
        color: #79768A;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }
    .product-row {
        display: flex;
        align-items: flex-start;
        padding: 16px;
        border-left: 1px solid #EAE6F8;
        border-right: 1px solid #EAE6F8;
        border-bottom: 1px solid #EAE6F8;
        background-color: #FFFFFF;
    }
    .product-row:hover { background-color: #FBFBFE; }
    .col-product { flex: 3.5; display: flex; gap: 16px; }
    .col-price { flex: 1; font-weight: 700; font-size: 1.1rem; color: #111827; padding-top: 4px; }
    .col-store { flex: 1.5; padding-top: 4px; }
    .product-img {
        width: 85px;
        height: 85px;
        object-fit: contain;
        border-radius: 8px;
        border: 1px solid #F0F0F5;
        background: #FFFFFF;
        flex-shrink: 0;
    }
    .product-title {
        font-weight: 700;
        font-size: 0.98rem;
        color: #111827 !important;
        text-decoration: none;
        line-height: 1.35;
        display: block;
        margin-bottom: 4px;
    }
    .product-title:hover { color: #635BFF !important; }
    .product-sub { font-size: 0.8rem; color: #6B7280; margin-bottom: 8px; }
    .product-sub a { color: #635BFF; text-decoration: none; }
    .store-link {
        font-weight: 600;
        font-size: 0.9rem;
        color: #374151 !important;
        text-decoration: none;
    }
    .store-link:hover { color: #635BFF !important; }
    .badge-status {
        display: inline-block;
        padding: 3px 8px;
        font-size: 0.75rem;
        background: #F3F4F6;
        color: #4B5563;
        border-radius: 6px;
        border: 1px solid #E5E7EB;
        margin-top: 4px;
    }
    .btn-action {
        display: inline-block;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #5850EC;
        border: 1px solid #E0E0FE;
        border-radius: 6px;
        background: #F5F5FE;
        text-decoration: none;
        margin-top: 6px;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Prom.ua Product & Market Analyzer Pro")

# --- Сайдбар с настройками парсинга ---
with st.sidebar:
    st.header("⚙️ Поисковый модуль")
    query = st.text_input("Поисковый запрос:", "органайзер")
    pages_count = st.slider("Страниц для сбора:", 1, 10, 3)
    
    st.header("💰 Фильтр по цене при сборе")
    price_filter_enabled = st.checkbox("Включить лимит цены", value=False)
    min_price_input = st.number_input("Мин. цена (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. цена (грн):", min_value=0, value=5000, step=50)

    st.header("🚫 Черный список")
    exclude_keywords = st.text_input("Исключить слова (через запятую):", "чехол, подставка")
    exclude_sellers = st.text_input("Исключить продавцов (через запятую):", "")

# --- Логика сканирования ---
if st.button("🚀 Запустить полное сканирование", type="primary"):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en-US;q=0.7,en;q=0.6"
    })
    
    products = []
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    stop_words_filter = [w.strip().lower() for w in exclude_keywords.split(",") if w.strip()]
    stop_sellers_filter = [s.strip().lower() for s in exclude_sellers.split(",") if s.strip()]
    
    # URL-кодирование поискового запроса для безопасной передачи в заголовках Referer
    encoded_query = quote(query)

    for page in range(1, pages_count + 1):
        status_box.info(f"⏳ Сканирование страницы {page} из {pages_count}...")
        url = "https://prom.ua/ua/search"
        params = {"search_term": query, "page": page}
        
        if page > 1:
            session.headers.update({"Referer": f"https://prom.ua/ua/search?search_term={encoded_query}&page={page-1}"})

        try:
            res = session.get(url, params=params, timeout=12)
            if res.status_code == 200:
                soup = BeautifulSoup(res.text, "html.parser")
                blocks = soup.select('[data-qaid="product_block"]')
                
                for b in blocks:
                    name_el = b.select_one('[data-qaid="product_name"]')
                    price_el = b.select_one('[data-qaid="product_price"]')
                    link_el = b.select_one('a')
                    img_el = b.select_one('img')
                    sales_el = b.select_one('[data-qaid="rating_info"]') or b.select_one('[data-qaid="reviews_count"]')
                    supplier_el = b.select_one('[data-qaid="company_link"]') or b.select_one('[data-qaid="company_name"]')
                    
                    if name_el and price_el:
                        name = name_el.text.strip()
                        raw_price = price_el.text.strip()
                        digits = "".join(c for c in raw_price if c.isdigit())
                        price = int(digits) if digits else 0
                        
                        if price_filter_enabled:
                            if min_price_input > 0 and price < min_price_input:
                                continue
                            if max_price_input > 0 and price > max_price_input:
                                continue

                        if any(sw in name.lower() for sw in stop_words_filter):
                            continue

                        supplier_name = supplier_el.text.strip() if supplier_el else "Продавец не указан"
                        if any(ss in supplier_name.lower() for ss in stop_sellers_filter):
                            continue

                        href = link_el.get("href", "") if link_el else ""
                        full_link = f"https://prom.ua{href}" if href.startswith("/") else href
                        
                        supplier_link = ""
                        if supplier_el:
                            s_href = supplier_el.get("href", "") if supplier_el.name == "a" else ""
                            if not s_href and supplier_el.parent and supplier_el.parent.name == "a":
                                s_href = supplier_el.parent.get("href", "")
                            if s_href:
                                supplier_link = f"https://prom.ua{s_href}" if s_href.startswith("/") else s_href

                        img_url = "https://via.placeholder.com/85?text=No+Photo"
                        if img_el:
                            src = img_el.get("src") or img_el.get("data-src") or ""
                            if src:
                                img_url = "https:" + src if src.startswith("//") else src

                        sales_info = sales_el.text.strip() if sales_el else "В наличии"

                        products.append({
                            "Название": name,
                            "Цена": price,
                            "Поставщик": supplier_name,
                            "Ссылка_поставщика": supplier_link,
                            "Статус": sales_info,
                            "Картинка": img_url,
                            "Ссылка": full_link
                        })
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(1.0)
        
    status_box.empty()
    st.session_state["results"] = products

# --- Основной интерфейс результатов ---
if "results" in st.session_state and st.session_state["results"]:
    data = st.session_state["results"]
    df = pd.DataFrame(data)
    
    st.markdown("---")
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Собрано товаров", len(df))
    c2.metric("Средняя цена", f"{int(df['Цена'].mean()):,} грн".replace(",", " "))
    c3.metric("Медианная цена", f"{int(df['Цена'].median()):,} грн".replace(",", " "))
    c4.metric("Диапазон цен", f"{df['Цена'].min()} - {df['Цена'].max()} грн")
    
    st.markdown("---")

    tab_list, tab_analytics, tab_seo, tab_export = st.tabs([
        "📋 Список товаров", 
        "📊 Аналитика ниши", 
        "🔍 SEO & Ключевые слова", 
        "💾 Экспорт данных"
    ])

    with tab_list:
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            search_filter = st.text_input("🔍 Быстрый поиск в результатах:", placeholder="Введите слово для фильтрации...")
        with f_col2:
            sort_option = st.selectbox("Сортировка:", ["По умолчанию", "Сначала дешевые", "Сначала дорогие", "По продавцу"])

        view_df = df.copy()
        if search_filter:
            view_df = view_df[view_df["Название"].str.contains(search_filter, case=False, na=False)]
        
        if sort_option == "Сначала дешевые":
            view_df = view_df.sort_values(by="Цена", ascending=True)
        elif sort_option == "Сначала дорогие":
            view_df = view_df.sort_values(by="Цена", ascending=False)
        elif sort_option == "По продавцу":
            view_df = view_df.sort_values(by="Поставщик")

        st.markdown("""
        <div class="table-header">
            <div class="col-product">ТОВАР</div>
            <div class="col-price">ЦЕНА</div>
            <div class="col-store">МАГАЗИН</div>
        </div>
        """, unsafe_allow_html=True)
        
        html_content = ""
        for _, item in view_df.iterrows():
            store_html = f'<a href="{item["Ссылка_поставщика"]}" target="_blank" class="store-link">"{item["Поставщик"]}"</a>' if item["Ссылка_поставщика"] else f'<span class="store-link">"{item["Поставщик"]}"</span>'
            
            html_content += f"""
            <div class="product-row">
                <div class="col-product">
                    <img src="{item['Картинка']}" class="product-img" alt="Product Image">
                    <div>
                        <a href="{item['Ссылка']}" target="_blank" class="product-title">{item['Название']}</a>
                        <div class="product-sub">{item['Статус']} · <a href="{item['Ссылка']}" target="_blank">открыть на Prom.ua ↗</a></div>
                        <a href="{item['Ссылка']}" target="_blank" class="btn-action">✦ Анализировать</a>
                    </div>
                </div>
                <div class="col-price">
                    {item['Цена']} грн
                </div>
                <div class="col-store">
                    {store_html}
                    <br>
                    <span class="badge-status">Проверен</span>
                </div>
            </div>
            """
        st.markdown(html_content, unsafe_allow_html=True)

    with tab_analytics:
        st.subheader("📈 Распределение цен в нише")
        fig_hist = px.histogram(df, x="Цена", nbins=20, title="Гистограмма цен товаров",
                                labels={"Цена": "Цена (грн)", "count": "Количество товаров"},
                                color_discrete_sequence=['#635BFF'])
        st.plotly_chart(fig_hist, use_container_width=True)

        st.subheader("🏆 Топ-10 Продавцов по количеству карточек")
        top_sellers = df["Поставщик"].value_counts().head(10).reset_index()
        top_sellers.columns = ["Продавец", "Количество товаров"]
        fig_sellers = px.bar(top_sellers, x="Количество товаров", y="Продавец", orientation='h',
                             color="Количество товаров", color_continuous_scale="Viridis")
        fig_sellers.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_sellers, use_container_width=True)

    with tab_seo:
        st.subheader("🔑 Часто используемые слова в названиях (SEO)")
        raw_text = " ".join(df["Название"].tolist()).lower()
        words = re.findall(r'\b[a-zA-ua-яєії0-9]{3,}\b', raw_text)
        
        stop_words = {'для', 'над', 'под', 'під', 'или', 'або', 'при', 'пластиковый', 'набор', 'шт', 'грн'}
        filtered_words = [w for w in words if w not in stop_words and not w.isdigit()]
        
        word_counts = Counter(filtered_words).most_common(15)
        seo_df = pd.DataFrame(word_counts, columns=["Слово", "Частота"])
        
        fig_words = px.bar(seo_df, x="Слово", y="Частота", color="Частота", color_continuous_scale="Purples")
        st.plotly_chart(fig_words, use_container_width=True)
        st.dataframe(seo_df, use_container_width=True)

    with tab_export:
        st.subheader("📥 Выгрузить отчет")
        col_exp1, col_exp2 = st.columns(2)
        
        with col_exp1:
            csv_data = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="📄 Скачать CSV-отчет",
                data=csv_data,
                file_name="prom_report.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col_exp2:
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Prom_Data')
            excel_data = buffer.getvalue()
            
            st.download_button(
                label="📊 Скачать Excel-отчет (.xlsx)",
                data=excel_data,
                file_name="prom_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
