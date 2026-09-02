import os
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

# 1. Настройка страницы
st.set_page_config(page_title="MySales Trend - Prom Analyzer Pro", page_icon="📊", layout="wide")

# --- База данных SQLite ---
DB_NAME = "mysales_trend.db"

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
            c.execute('''
                CREATE TABLE IF NOT EXISTS query_pool (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query TEXT UNIQUE,
                    source TEXT,
                    used_count INTEGER DEFAULT 0
                )
            ''')
            conn.commit()
    except Exception as e:
        st.error(f"Ошибка БД при инициализации: {e}")

def sanitize_item(item):
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

# --- КОМБИНАТОРНЫЙ ГЕНЕРАТОР ---
COMBINATOR_PROPERTIES = [
    "беспроводной", "автоматический", "сенсорный", "складной", "портативный", 
    "аккумуляторный", "магнитный", "умный", "силиконовый", "гибкий", 
    "ультразвуковой", "компактный", "многофункциональный", "водонепроницаемый"
]

COMBINATOR_PRODUCTS = [
    "светильник", "органайзер", "держатель", "очиститель", "дозатор", "щетка", 
    "чехол", "подставка", "диспенсер", "массажер", "фонарик", "аэратор", 
    "пылесос", "увлажнитель", "компрессор", "вакууматор", "скрабер"
]

COMBINATOR_PLACES = [
    "для авто", "для кухни", "для ванной", "для спальни", "для шкафа", 
    "для окон", "для обуви", "для гаджетов", "для дома", "для туалета", 
    "для раковины", "для лица", "для путешествий"
]

def generate_combinatorial_query():
    prop = random.choice(COMBINATOR_PROPERTIES)
    prod = random.choice(COMBINATOR_PRODUCTS)
    place = random.choice(COMBINATOR_PLACES)
    return f"{prop} {prod} {place}"

# --- РАБОТА С ПУЛОМ ГИПОТЕЗ ---
def add_queries_to_pool(queries, source="AI"):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            for q in queries:
                q_clean = q.strip().lower()
                if q_clean:
                    c.execute("INSERT OR IGNORE INTO query_pool (query, source) VALUES (?, ?)", (q_clean, source))
            conn.commit()
    except Exception as e:
        st.error(f"Ошибка добавления фраз в БД: {e}")

def get_query_from_pool():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT id, query FROM query_pool ORDER BY used_count ASC, RANDOM() LIMIT 1")
            row = c.fetchone()
            if row:
                q_id, query = row
                c.execute("UPDATE query_pool SET used_count = used_count + 1 WHERE id = ?", (q_id,))
                conn.commit()
                return query
    except Exception:
        pass
    return generate_combinatorial_query()

def get_pool_stats():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("SELECT COUNT(*), SUM(CASE WHEN source='AI' THEN 1 ELSE 0 END) FROM query_pool")
            total, ai_count = c.fetchone()
            return total or 0, ai_count or 0
    except Exception:
        return 0, 0

# --- GEMINI AI GENERATOR ---
def generate_ai_queries_gemini(api_key, count=30):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.6-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Сгенерируй {count} поисковых запросов для поиска физических трендовых товаров для дропшиппинга (для Prom.ua).
    Ориентировочная розничная цена: до 500 грн.
    
    ИСКЛЮЧИТЬ: одежду, обувь, лекарства, продукты питания, сложную габаритную электронику.
    ПРЕДПОЧТЕНИЕ: товары с WOW-эффектом, решение бытовых проблем, недорогие девайсы для дома, авто, кухни, ванной, организации пространства, ухода.
    
    Верни СТРОГО JSON-массив строк без какого-либо дополнительного текста или разметки.
    Пример: ["сенсорный ночник для шкафа", "магнитный держатель кабеля", "мини вакууматор пакетов", "щетка для жалюзи"]
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    # 2 попытки с увеличенным таймаутом (10 сек сопряжение, 60 сек чтение)
    for attempt in range(2):
        try:
            res = requests.post(url, headers=headers, json=payload, timeout=(10, 60))
            if res.status_code == 200:
                data = res.json()
                text_response = data["candidates"][0]["content"]["parts"][0]["text"]
                queries = json.loads(text_response)
                if isinstance(queries, list):
                    return queries
            else:
                st.error(f"Ошибка Gemini API: {res.status_code} - {res.text}")
                break
        except requests.exceptions.Timeout:
            if attempt == 0:
                time.sleep(1)
                continue
            st.error("⏳ Таймаут: Gemini API не ответил за 60 секунд. Попробуйте еще раз.")
        except Exception as e:
            st.error(f"Ошибка запроса к AI: {e}")
            break
            
    return []

def extract_graph_queries(products, top_n=5):
    if not products:
        return []
    raw_text = " ".join([p["Название"] for p in products]).lower()
    words = re.findall(r'\b[a-ua-яєії0-9]{4,}\b', raw_text)
    stop_words = {'для', 'над', 'под', 'під', 'или', 'або', 'при', 'пластиковый', 'набор', 'штук', 'грн', 'товар', 'авто', 'дому'}
    filtered = [w for w in words if w not in stop_words and not w.isdigit()]
    most_common = [w[0] for w in Counter(filtered).most_common(top_n)]
    
    graph_queries = []
    for word in most_common:
        graph_queries.append(f"{word} {random.choice(COMBINATOR_PLACES)}")
    return graph_queries

# --- ИНИЦИАЛИЗАЦИЯ ---
init_db()
st.session_state["favorites"] = load_favorites_db()

if "default_query" not in st.session_state:
    st.session_state["default_query"] = generate_combinatorial_query()

if "results" not in st.session_state:
    st.session_state["results"] = []

# --- СТИЛИ CSS ---
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

    div[data-testid="stImage"] img {
        border-radius: 8px;
        transition: transform 0.25s ease-in-out, box-shadow 0.25s ease-in-out;
        cursor: zoom-in;
        object-fit: contain;
    }
    div[data-testid="stImage"] img:hover {
        transform: scale(2.2);
        position: relative;
        z-index: 9999;
        box-shadow: 0px 10px 25px rgba(0, 0, 0, 0.35);
    }
</style>
""", unsafe_allow_html=True)

st.title("📊 MySales Trend: Smart Product Research Engine")

# --- САЙДБАР ---
with st.sidebar:
    st.header("🤖 Smart Query Engine")
    
    total_q, ai_q = get_pool_stats()
    st.caption(f"🧠 В пуле гипотез: **{total_q}** фраз (из них AI: {ai_q})")
    
    c_side1, c_side2 = st.columns(2)
    with c_side1:
        if st.button("🎲 Сгенерировать гипотезу", use_container_width=True):
            st.session_state["default_query"] = get_query_from_pool()
            st.rerun()
            
    with c_side2:
        if st.button("🧩 Комбинатор", use_container_width=True):
            st.session_state["default_query"] = generate_combinatorial_query()
            st.rerun()

    with st.expander("✨ Настройки Gemini AI"):
        default_api_key = ""
        try:
            if "GEMINI_API_KEY" in st.secrets:
                default_api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            pass
        if not default_api_key:
            default_api_key = os.getenv("GEMINI_API_KEY", "")

        gemini_api_key = st.text_input(
            "Gemini API Key:", 
            value=default_api_key, 
            type="password", 
            help="Получить бесплатно на aistudio.google.com"
        )
        
        if st.button("🚀 Наполнить пул через AI (+30 фраз)"):
            if not gemini_api_key:
                st.warning("Введите Gemini API Key или сохраните его в .streamlit/secrets.toml!")
            else:
                with st.spinner("AI генерирует новые поисковые фразы..."):
                    new_q = generate_ai_queries_gemini(gemini_api_key, count=30)
                    if new_q:
                        add_queries_to_pool(new_q, source="AI")
                        st.success(f"Добавлено {len(new_q)} новых гипотез в пул!")
                        st.rerun()

    st.markdown("---")
    query = st.text_input("Поисковый запрос:", value=st.session_state["default_query"])

    pages_count = st.slider("Страниц для сбора:", 1, 10, 3)
    
    st.header("💰 Фильтр по цене")
    price_filter_enabled = st.checkbox("Ограничение цены", value=True)
    min_price_input = st.number_input("Мин. цена (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. цена (грн):", min_value=0, value=500, step=50)

    st.header("🚫 Черный список")
    exclude_keywords = st.text_input("Исключить слова (через запятую):", "")
    exclude_sellers = st.text_input("Исключить продавцов:", "")

# --- ЗАПУСК СКАНА ---
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    start_scan = st.button("🚀 Запустить сканирование", type="primary", use_container_width=True)

if start_scan:
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,uk-UA,uk;q=0.8,en-US;q=0.7,en;q=0.6"
    })
    
    products = []
    progress_bar = st.progress(0)
    status_box = st.empty()
    
    stop_words_filter = [w.strip().lower() for w in exclude_keywords.split(",") if w.strip()]
    stop_sellers_filter = [s.strip().lower() for s in exclude_sellers.split(",") if s.strip()]
    
    encoded_query = quote(query)

    for page in range(1, pages_count + 1):
        status_box.info(f"⏳ Сканирование страницы {page} из {pages_count} по запросу: **{query}**...")
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
                            src = ""
                            srcset = img_el.get("srcset", "")
                            if srcset:
                                candidates = [item.strip().split(" ")[0] for item in srcset.split(",") if item.strip()]
                                if candidates:
                                    src = candidates[-1]
                            
                            if not src:
                                src = img_el.get("data-src") or img_el.get("src") or img_el.get("data-lazy-src") or ""

                            if src:
                                if src.startswith("//"):
                                    src = "https:" + src
                                src = re.sub(r'_w\d+_h\d+_', '_w640_h640_', src)
                                img_url = src

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
        time.sleep(0.8)
        
    status_box.empty()
    st.session_state["results"] = products
    st.rerun()

st.markdown("---")

# --- ВКЛАДКИ ---
tab_list, tab_fav, tab_analytics, tab_seo = st.tabs([
    f"📋 Найдено товаров ({len(st.session_state['results'])})", 
    f"⭐ Избранное в БД ({len(st.session_state['favorites'])})",
    "📊 Аналитика ниши", 
    "🔍 SEO & Ключевые слова"
])

# === ВКЛАДКА 1: НАЙДЕННЫЕ ТОВАРЫ ===
with tab_list:
    if not st.session_state["results"]:
        st.info("💡 Нажмите **'🚀 Запустить сканирование'** или кнопку **'🎲 Сгенерировать гипотезу'** в меню слева.")
    else:
        graph_ideas = extract_graph_queries(st.session_state["results"])
        if graph_ideas:
            st.markdown("##### 🕸️ Скрытый граф товаров (смежные гипотезы из результатов):")
            g_cols = st.columns(len(graph_ideas))
            for idx, idea in enumerate(graph_ideas):
                with g_cols[idx]:
                    if st.button(f"🔍 {idea}", key=f"graph_btn_{idx}", use_container_width=True):
                        st.session_state["default_query"] = idea
                        st.rerun()

        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            search_filter = st.text_input("🔍 Быстрый фильтр по результатам:", placeholder="Введите слово...")
        with f_col2:
            sort_option = st.selectbox("Сортировка:", ["По умолчанию", "Сначала дешевле", "Сначала дороже", "По продавцу"])

        df = pd.DataFrame(st.session_state["results"])
        view_df = df.copy()
        
        if search_filter:
            view_df = view_df[view_df["Название"].str.contains(search_filter, case=False, na=False)]
        
        if sort_option == "Сначала дешевле":
            view_df = view_df.sort_values(by="Цена", ascending=True)
        elif sort_option == "Сначала дороже":
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
                    msg_raw = f"Здравствуйте! Подскажите, пожалуйста, работаете ли вы по дропшиппингу? Если да, дайте свои контакты для связи (Telegram/Viber). Товар: {item['Ссылка']}"

                    b_col1, b_col2 = st.columns([1, 1.2])
                    
                    with b_col1:
                        is_in_fav = any(f["Ссылка"] == item["Ссылка"] for f in st.session_state["favorites"])
                        btn_label = "✅ В избранном" if is_in_fav else "⭐ В избранное"
                        
                        if st.button(btn_label, key=f"fav_btn_{row_idx}_{item['Ссылка'][-10:]}"):
                            if is_in_fav:
                                remove_favorite_db(item["Ссылка"])
                                st.toast("Удалено из БД", icon="🗑️")
                            else:
                                add_favorite_db(item)
                                st.toast("Сохранено в БД! ⭐", icon="✅")
                            st.session_state["favorites"] = load_favorites_db()
                            st.rerun()

                    with b_col2:
                        st.link_button("🤝 К продавцу", target_url, use_container_width=True)

                    st.caption("Текст для продавца:")
                    st.code(msg_raw, language=None)

                with col_price:
                    st.markdown(f"### {item['Цена']} грн")

                with col_seller:
                    if item["Ссылка_поставщика"]:
                        st.markdown(f"**Продавец:** [{item['Поставщик']}]({item['Ссылка_поставщика']})")
                    else:
                        st.markdown(f"**Продавец:** {item['Поставщик']}")
                
                st.markdown('</div>', unsafe_allow_html=True)

# === ВКЛАДКА 2: ИЗБРАННОЕ ===
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
        st.info("В базе данных пока нет сохраненных товаров. Нажимайте **'⭐ В избранное'** возле товаров.")
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
            st.warning("⚠️ Выбрано более 3-х товаров.")
        
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
