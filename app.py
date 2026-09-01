import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import re
import json
import sqlite3
import random
from collections import Counter
import plotly.express as px
from urllib.parse import quote

# 1. Сеттинг страницы ОБЯЗАТЕЛЬНО идет первой командой Streamlit
st.set_page_config(page_title="Prom Analyzer Pro", page_icon="📊", layout="wide")

# --- Безопасная работа с SQLite на сервере ---
DB_NAME = "favorites.db"

def init_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute('''
                CREATE TABLE IF NOT EXISTS favorites (
                    link TEXT PRIMARY KEY,
                    data TEXT
                )
            ''')
            conn.commit()
    except Exception as e:
        st.error(f"Ошибка БД при инициализации: {e}")

def sanitize_item(item):
    """Приведение любого объекта (Pandas Series, dict) к чистому Python dict"""
    if hasattr(item, "to_dict"):
        d = item.to_dict()
    elif isinstance(item, dict):
        d = item
    else:
        d = dict(item)
        
    return {
        "Название": str(d.get("Название", "")),
        "Цена": int(d.get("Цена", 0)),
        "Поставщик": str(d.get("Поставщик", "")),
        "Ссылка_поставщика": str(d.get("Ссылка_поставщика", "")),
        "Статус": str(d.get("Статус", "")),
        "Картинка": str(d.get("Картинка", "")),
        "Ссылка": str(d.get("Ссылка", ""))
    }

def load_favorites_db():
    init_db()
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT data FROM favorites")
            rows = c.fetchall()
            return [json.loads(r[0]) for r in rows]
    except Exception:
        return []

def add_favorite_db(item):
    clean_dict = sanitize_item(item)
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("INSERT OR REPLACE INTO favorites (link, data) VALUES (?, ?)", 
                      (clean_dict["Ссылка"], json.dumps(clean_dict, ensure_ascii=False)))
            conn.commit()
    except Exception as e:
        st.error(f"Не удалось сохранить в БД: {e}")

def remove_favorite_db(link):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM favorites WHERE link = ?", (link,))
            conn.commit()
    except Exception as e:
        st.error(f"Не удалось удалить из БД: {e}")

def clear_favorites_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM favorites")
            conn.commit()
    except Exception as e:
        st.error(f"Не удалось очистить БД: {e}")

# --- Инициализация состояний ---
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

st.session_state["favorites"] = load_favorites_db()

if "results" not in st.session_state:
    st.session_state["results"] = []

st.markdown("""
<style>
    .product-card {
        padding: 14px;
        border: 1px solid #EAE6F8;
        border-radius: 10px;
        background-color: #FFFFFF;
        margin-bottom: 12px;
    }
    .product-card:hover { background-color: #FBFBFE; }
    
    .btn-dropship {
        display: inline-block;
        padding: 6px 14px;
        font-size: 0.8rem;
        font-weight: 600;
        color: #059669 !important;
        border: 1px solid #D1FAE5;
        border-radius: 6px;
        background: #ECFDF5;
        text-decoration: none !important;
        cursor: pointer;
    }
    .btn-dropship:hover { background: #D1FAE5; }
</style>
""", unsafe_allow_html=True)

st.title("📊 Prom.ua Product & Market Analyzer Pro")

# --- Сайдбар ---
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

# --- Запуск сканирования ---
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    start_scan = st.button("🚀 Запустить сканирование", type="primary", use_container_width=True)

if start_scan:
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
    st.rerun()

st.markdown("---")

# --- Вкладки интерфейса ---
tab_list, tab_fav, tab_analytics, tab_seo = st.tabs([
    f"📋 Найдено товаров ({len(st.session_state['results'])})", 
    f"⭐ Избранное в БД ({len(st.session_state['favorites'])})",
    "📊 Аналитика ниши", 
    "🔍 SEO & Ключевые слова"
])

# === ВКЛАДКА 1: Поиск ===
with tab_list:
    if not st.session_state["results"]:
        st.info("💡 Нажмите **'🚀 Запустить сканирование'**, чтобы собрать товары по выбранному запросу.")
    else:
        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            search_filter = st.text_input("🔍 Быстрый поиск в результатах:", placeholder="Введите слово для фильтрации...")
        with f_col2:
            sort_option = st.selectbox("Сортировка:", ["По умолчанию", "Сначала дешевые", "Сначала дорогие", "По продавцу"])

        df = pd.DataFrame(st.session_state["results"])
        view_df = df.copy()
        
        if search_filter:
            view_df = view_df[view_df["Название"].str.contains(search_filter, case=False, na=False)]
        
        if sort_option == "Сначала дешевые":
            view_df = view_df.sort_values(by="Цена", ascending=True)
        elif sort_option == "Сначала дорогие":
            view_df = view_df.sort_values(by="Цена", ascending=False)
        elif sort_option == "По продавцу":
            view_df = view_df.sort_values(by="Поставщик")

        for row_idx, item in view_df.iterrows():
            with st.container():
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                col_img, col_main, col_price, col_seller = st.columns([1, 4.5, 1.5, 2])
                
                with col_img:
                    st.image(item["Картинка"], use_container_width=True)
                    
                with col_main:
                    st.markdown(f"**[{item['Название']}]({item['Ссылка']})**")
                    st.caption(f"{item['Статус']} · [Открыть на Prom.ua ↗]({item['Ссылка']})")
                    
                    target_url = item["Ссылка_поставщика"] if item["Ссылка_поставщика"] else item["Ссылка"]
                    msg_raw = f"Вітаю! Підкажіть, будь ласка, чи працюєте ви по дропшипінгу? Якщо так, дайте свої контакти для зв'язку (Telegram/Viber). Товар: {item['Ссылка']}"
                    msg_encoded = quote(msg_raw)

                    js_copy = f"""
                        event.preventDefault();
                        const link = this.href;
                        const txt = decodeURIComponent('{msg_encoded}');
                        if (navigator.clipboard) {{
                            navigator.clipboard.writeText(txt).then(() => window.open(link, '_blank')).catch(() => window.open(link, '_blank'));
                        }} else {{
                            window.open(link, '_blank');
                        }}
                    """
                    
                    b_col1, b_col2 = st.columns([1.2, 2])
                    
                    with b_col1:
                        is_in_fav = any(f["Ссылка"] == item["Ссылка"] for f in st.session_state["favorites"])
                        btn_label = "✅ В избранном" if is_in_fav else "⭐ В избранное"
                        
                        if st.button(btn_label, key=f"fav_btn_{row_idx}_{item['Ссылка'][-10:]}"):
                            if is_in_fav:
                                remove_favorite_db(item["Ссылка"])
                                st.toast("Удалено из БД", icon="🗑️")
                            else:
                                add_favorite_db(item)
                                st.toast("Сохранено в БД сервера! ⭐", icon="✅")
                            st.session_state["favorites"] = load_favorites_db()
                            st.rerun()

                    with b_col2:
                        st.markdown(f'<a href="{target_url}" target="_blank" class="btn-dropship" onclick="{js_copy}">🤝 Запрос на дропшиппинг</a>', unsafe_allow_html=True)

                with col_price:
                    st.markdown(f"### {item['Цена']} грн")

                with col_seller:
                    if item["Ссылка_поставщика"]:
                        st.markdown(f"**Продавец:** [{item['Поставщик']}]({item['Ссылка_поставщика']})")
                    else:
                        st.markdown(f"**Продавец:** {item['Поставщик']}")
                
                st.markdown('</div>', unsafe_allow_html=True)

# === ВКЛАДКА 2: ИЗБРАННОЕ В SQLite ===
with tab_fav:
    c_fav_head, c_fav_clear = st.columns([4, 1])
    with c_fav_head:
        st.subheader("⭐ Сохраненные товары в SQLite БД")
    with c_fav_clear:
        if st.session_state["favorites"]:
            if st.button("🧹 Очистить БД"):
                clear_favorites_db()
                st.session_state["favorites"] = []
                st.rerun()

    if not st.session_state["favorites"]:
        st.info("В базе данных сервера пока нет сохраненных товаров. Нажимайте кнопку **'⭐ В избранное'** возле товаров.")
    else:
        fav_df = pd.DataFrame(st.session_state["favorites"])
        st.write("Отметьте галочками **до 3-х лучших товаров** для запуска в рекламу:")
        
        selected_for_ads = []
        for f_idx, f_item in fav_df.iterrows():
            f_c1, f_c2, f_c3, f_c4 = st.columns([0.5, 1, 4, 1.5])
            
            with f_c1:
                if st.checkbox("", key=f"chk_fav_{f_idx}"):
                    selected_for_ads.append(f_item)
            with f_c2:
                st.image(f_item["Картинка"], width=65)
            with f_c3:
                st.markdown(f"**[{f_item['Название']}]({f_item['Ссылка']})**")
                st.caption(f"Продавец: {f_item['Поставщик']} | Цена: {f_item['Цена']} грн")
            with f_c4:
                if st.button("🗑️ Удалить", key=f"del_fav_{f_idx}"):
                    remove_favorite_db(f_item["Ссылка"])
                    st.session_state["favorites"] = load_favorites_db()
                    st.rerun()
            st.markdown("---")

        if len(selected_for_ads) > 3:
            st.warning("⚠️ Выбрано больше 3-х товаров. Рекомендуется выбрать не более 3-х офферов.")
        
        if selected_for_ads:
            st.subheader("🚀 Ваша тройка для рекламного теста")
            top_df = pd.DataFrame(selected_for_ads)
            st.dataframe(top_df[["Название", "Цена", "Поставщик", "Ссылка"]], use_container_width=True)

# === ВКЛАДКА 3: АНАЛИТИКА ===
with tab_analytics:
    if st.session_state["results"]:
        df_an = pd.DataFrame(st.session_state["results"])
        st.subheader("📈 Распределение цен в нише")
        fig_hist = px.histogram(df_an, x="Цена", nbins=20, title="Гистограмма цен",
                                labels={"Цена": "Цена (грн)", "count": "Количество"},
                                color_discrete_sequence=['#635BFF'])
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Сначала запустите сканирование товаров.")

# === ВКЛАДКА 4: SEO ===
with tab_seo:
    if st.session_state["results"]:
        df_seo = pd.DataFrame(st.session_state["results"])
        st.subheader("🔑 Популярные ключевые слова")
        raw_text = " ".join(df_seo["Название"].tolist()).lower()
        words = re.findall(r'\b[a-ua-яєії0-9]{3,}\b', raw_text)
        stop_words = {'для', 'над', 'под', 'під', 'или', 'або', 'при', 'пластиковый', 'набор', 'шт', 'грн'}
        filtered_words = [w for w in words if w not in stop_words and not w.isdigit()]
        word_counts = Counter(filtered_words).most_common(15)
        seo_df = pd.DataFrame(word_counts, columns=["Слово", "Частота"])
        st.dataframe(seo_df, use_container_width=True)
    else:
        st.info("Сначала запустите сканирование товаров.")
