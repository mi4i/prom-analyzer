import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import io
import random
from collections import Counter
import plotly.express as px
from urllib.parse import quote

st.set_page_config(page_title="Prom Analyzer Pro", page_icon="📊", layout="wide")

# Инициализация состояний
TOP_DROPSHIP_QUERIES = [
    "подсветка для унитаза с датчиком движения",
    "сенсорный аэратор на кран 1080 градусов",
    "аккумуляторный светодиодный светильник с датчиком движения",
    "электрический трос для очистки засоров каналов",
    "портативный вакууматор для пакетов ручной",
    "ультразвуковая ванночка для очистки предметов",
    "силиконовый ленточный уплотнитель для дверей и окон",
    "машинка для удаления катышек аккумуляторная",
    "антивибрационные подставки для стиральной машины",
    "бесконтактный сенсорный дозатор жидкого мыла",
    "магнитная щетка для мытья окон с двух сторон",
    "гибкая насадка на душ с фильтром и турбиной"
]

if "default_query" not in st.session_state:
    st.session_state["default_query"] = random.choice(TOP_DROPSHIP_QUERIES)

if "favorites" not in st.session_state:
    st.session_state["favorites"] = []

# Обработка добавления/удаления из избранного через Query Params
if "add_fav" in st.query_params:
    try:
        fav_idx = int(st.query_params["add_fav"])
        if "results" in st.session_state and 0 <= fav_idx < len(st.session_state["results"]):
            item = st.session_state["results"][fav_idx]
            if not any(f["Ссылка"] == item["Ссылка"] for f in st.session_state["favorites"]):
                st.session_state["favorites"].append(item)
                st.toast("Товар добавлен в Избранное! ⭐", icon="✅")
        st.query_params.clear()
    except Exception:
        pass

if "rem_fav" in st.query_params:
    try:
        rem_idx = int(st.query_params["rem_fav"])
        if 0 <= rem_idx < len(st.session_state["favorites"]):
            st.session_state["favorites"].pop(rem_idx)
            st.toast("Товар удален из Избранного", icon="🗑️")
        st.query_params.clear()
    except Exception:
        pass

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
        transition: transform 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        position: relative;
        z-index: 1;
        cursor: pointer;
    }
    .product-img:hover {
        transform: scale(2.4);
        z-index: 100;
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
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
    
    .btn-group {
        display: flex;
        gap: 8px;
        margin-top: 8px;
        flex-wrap: wrap;
    }
    .btn-action {
        display: inline-block;
        padding: 5px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #5850EC !important;
        border: 1px solid #E0E0FE;
        border-radius: 6px;
        background: #F5F5FE;
        text-decoration: none !important;
    }
    .btn-fav {
        display: inline-block;
        padding: 5px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #D97706 !important;
        border: 1px solid #FEF3C7;
        border-radius: 6px;
        background: #FFFBEB;
        text-decoration: none !important;
    }
    .btn-dropship {
        display: inline-block;
        padding: 5px 10px;
        font-size: 0.75rem;
        font-weight: 600;
        color: #059669 !important;
        border: 1px solid #D1FAE5;
        border-radius: 6px;
        background: #ECFDF5;
        text-decoration: none !important;
        cursor: pointer;
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 Prom.ua Product & Market Analyzer Pro")

with st.sidebar:
    st.header("⚙️ Поисковый модуль")
    query = st.text_input("Поисковый запрос:", value=st.session_state["default_query"])
    
    if st.button("🎲 Другой трендовый оффер"):
        st.session_state["default_query"] = random.choice(TOP_DROPSHIP_QUERIES)
        st.rerun()

    pages_count = st.slider("Страниц для сбора:", 1, 10, 3)
    
    st.header("💰 Фильтр по цене при сборе")
    price_filter_enabled = st.checkbox("Включить лимит цены", value=False)
    min_price_input = st.number_input("Мин. цена (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. цена (грн):", min_value=0, value=5000, step=50)

    st.header("🚫 Черный список")
    exclude_keywords = st.text_input("Исключить слова (через запятую):", "чехол, подставка")
    exclude_sellers = st.text_input("Исключить продавцов (через запятую):", "")

if st.button("🚀 Запустить полное сканирование", type="primary"):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "uk-UA,uk;q=0.9,ru;q=0.8,en-US;q=0.7,en;q=0.6"
    })
    
    products = []
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    stop_words_filter = [w.strip().lower() for w in exclude_keywords.split(",") if w.strip()]
    stop_sellers_filter = [s.strip().lower() for s in exclude_sellers.split(",") if s.strip()]
    
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
                blocks = (
                    soup.select('[data-qaid="product_block"]') or 
                    soup.select('[data-qaid="product_card"]') or 
                    soup.select('div[data-qaid="product_link"]') or
                    soup.select('article')
                )
                
                for b in blocks:
                    name_el = b.select_one('[data-qaid="product_name"]') or b.select_one('a[title]')
                    price_el = b.select_one('[data-qaid="product_price"]') or b.select_one('span[data-qaid="price"]')
                    link_el = b.select_one('a[href]')
                    img_el = b.select_one('img')
                    sales_el = b.select_one('[data-qaid="rating_info"]') or b.select_one('[data-qaid="reviews_count"]')
                    supplier_el = b.select_one('[data-qaid="company_link"]') or b.select_one('[data-qaid="company_name"]')
                    
                    if name_el and price_el:
                        name = name_el.text.strip() if name_el.text.strip() else name_el.get("title", "").strip()
                        raw_price = price_el.text.strip()
                        digits = "".join(c for c in raw_price if c.isdigit())
                        price = int(digits) if digits else 0
                        
                        if price == 0 or not name:
                            continue

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
                            src = img_el.get("src") or img_el.get("data-src") or img_el.get("srcset", "").split(" ")[0]
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

if "results" in st.session_state and st.session_state["results"]:
    data = st.session_state["results"]
    df = pd.DataFrame(data)
    
    st.markdown("---")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Собрано товаров", len(df))
    c2.metric("Средняя цена", f"{int(df['Цена'].mean()):,} грн".replace(",", " "))
    c3.metric("В Избранном", len(st.session_state["favorites"]))
    c4.metric("Диапазон цен", f"{df['Цена'].min()} - {df['Цена'].max()} грн")
    st.markdown("---")

    tab_list, tab_fav, tab_analytics, tab_seo = st.tabs([
        "📋 Список товаров", 
        f"⭐ Избранное & Топ-3 ({len(st.session_state['favorites'])})",
        "📊 Аналитика ниши", 
        "🔍 SEO & Ключевые слова"
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
        for idx, item in view_df.iterrows():
            store_html = f'<a href="{item["Ссылка_поставщика"]}" target="_blank" class="store-link">"{item["Поставщик"]}"</a>' if item["Ссылка_поставщика"] else f'<span class="store-link">"{item["Поставщик"]}"</span>'
            target_url = item["Ссылка_поставщика"] if item["Ссылка_поставщика"] else item["Ссылка"]
            
            msg_raw = f"Вітаю! Підкажіть, будь ласка, чи працюєте ви по дропшипінгу? Якщо так, дайте свої контакти для зв'язку (Telegram/Viber). Товар: {item['Ссылка']}"
            msg_encoded = quote(msg_raw)

            # Надежный JS-код гарантированного копирования текста перед переходом по ссылке
            js_copy_click = f"""
                event.preventDefault();
                const link = this.href;
                const txt = decodeURIComponent('{msg_encoded}');
                if (navigator.clipboard && navigator.clipboard.writeText) {{
                    navigator.clipboard.writeText(txt).then(() => {{
                        window.open(link, '_blank');
                    }}).catch(() => {{
                        window.open(link, '_blank');
                    }});
                }} else {{
                    window.open(link, '_blank');
                }}
            """

            is_in_fav = any(f["Ссылка"] == item["Ссылка"] for f in st.session_state["favorites"])
            fav_btn_label = "✅ В избранном" if is_in_fav else "⭐ В избранное"

            html_content += f"""
            <div class="product-row">
                <div class="col-product">
                    <img src="{item['Картинка']}" class="product-img" alt="Product Image">
                    <div>
                        <a href="{item['Ссылка']}" target="_blank" class="product-title">{item['Название']}</a>
                        <div class="product-sub">{item['Статус']} · <a href="{item['Ссылка']}" target="_blank">открыть на Prom ↗</a></div>
                        <div class="btn-group">
                            <a href="?add_fav={idx}" class="btn-fav">{fav_btn_label}</a>
                            <a href="{target_url}" target="_blank" class="btn-dropship" onclick="{js_copy_click}">🤝 Запрос на дропшиппинг</a>
                        </div>
                    </div>
                </div>
                <div class="col-price">
                    {item['Цена']} грн
                </div>
                <div class="col-store">
                    {store_html}
                </div>
            </div>
            """
        st.markdown(html_content, unsafe_allow_html=True)

    with tab_fav:
        st.subheader("⭐ Шорт-лист отобранных товаров")
        
        if not st.session_state["favorites"]:
            st.info("Вы пока не добавили ни одного товара в избранное. Нажимайте кнопку '⭐ В избранное' в общем списке.")
        else:
            fav_df = pd.DataFrame(st.session_state["favorites"])
            
            st.write("Отметьте **до 3-х товаров**, которые планируете запускать в тестовую рекламу (Meta Ads / TikTok):")
            
            selected_for_ads = []
            for f_idx, f_item in fav_df.iterrows():
                f_col1, f_col2, f_col3, f_col4 = st.columns([0.5, 1, 4, 1.5])
                
                with f_col1:
                    is_selected = st.checkbox("", key=f"fav_chk_{f_idx}")
                    if is_selected:
                        selected_for_ads.append(f_item)
                with f_col2:
                    st.image(f_item["Картинка"], width=60)
                with f_col3:
                    st.markdown(f"**[{f_item['Название']}]({f_item['Ссылка']})**")
                    st.caption(f"Продавец: {f_item['Поставщик']} | Цена: {f_item['Цена']} грн")
                with f_col4:
                    st.markdown(f"[🗑️ Удалить](?rem_fav={f_idx})")
                st.markdown("---")

            if len(selected_for_ads) > 3:
                st.warning("⚠️ Вы выбрали больше 3 товаров. Для фокусного теста рекомендуется оставить максимум 3 оффера!")
            
            if selected_for_ads:
                st.subheader("🚀 Выбранный ТОП для тестирования")
                top_df = pd.DataFrame(selected_for_ads)
                st.dataframe(top_df[["Название", "Цена", "Поставщик", "Ссылка"]], use_container_width=True)

    with tab_analytics:
        st.subheader("📈 Распределение цен в нише")
        fig_hist = px.histogram(df, x="Цена", nbins=20, title="Гистограмма цен товаров",
                                labels={"Цена": "Цена (грн)", "count": "Количество товаров"},
                                color_discrete_sequence=['#635BFF'])
        st.plotly_chart(fig_hist, use_container_width=True)

    with tab_seo:
        st.subheader("🔑 Часто используемые слова в названиях (SEO)")
        raw_text = " ".join(df["Название"].tolist()).lower()
        words = re.findall(r'\b[a-ua-яєії0-9]{3,}\b', raw_text)
        stop_words = {'для', 'над', 'под', 'під', 'или', 'або', 'при', 'пластиковый', 'набор', 'шт', 'грн'}
        filtered_words = [w for w in words if w not in stop_words and not w.isdigit()]
        word_counts = Counter(filtered_words).most_common(15)
        seo_df = pd.DataFrame(word_counts, columns=["Слово", "Частота"])
        st.dataframe(seo_df, use_container_width=True)
