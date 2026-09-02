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

# 1. Налаштування сторінки
st.set_page_config(page_title="MySales Trend - Prom Analyzer Pro", page_icon="📊", layout="wide")

# --- База даних SQLite ---
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
        st.error(f"Помилка БД при ініціалізації: {e}")

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
        st.error(f"Не вдалося зберегти в БД: {e}")

def remove_favorite_db(link):
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM favorites WHERE link = ?", (link,))
            conn.commit()
    except Exception as e:
        st.error(f"Не вдалося видалити з БД: {e}")

def clear_favorites_db():
    try:
        with sqlite3.connect(DB_NAME) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM favorites")
            conn.commit()
    except Exception as e:
        st.error(f"Не вдалося очистити БД: {e}")

# --- КОМБІНАТОРНИЙ ГЕНЕРАТОР ---
COMBINATOR_PROPERTIES = [
    "безпровідний", "автоматичний", "сенсорний", "складний", "портативний", 
    "акумуляторний", "магнітний", "розумний", "силіконовий", "гнучкий", 
    "ультразвуковий", "компактний", "багатофункціональний", "водонепроникний"
]

COMBINATOR_PRODUCTS = [
    "світильник", "органайзер", "тримач", "очисник", "дозатор", "щітка", 
    "чохол", "підставка", "диспенсер", "масажер", "ліхтарик", "аератор", 
    "пилосос", "зволожувач", "компресор", "вакууматор", "скрабер"
]

COMBINATOR_PLACES = [
    "для авто", "для кухні", "для ванної", "для спальні", "для шафи", 
    "для вікон", "для взуття", "для гаджетів", "для дому", "для туалету", 
    "для раковини", "для обличчя", "для подорожей"
]

def generate_combinatorial_query():
    prop = random.choice(COMBINATOR_PROPERTIES)
    prod = random.choice(COMBINATOR_PRODUCTS)
    place = random.choice(COMBINATOR_PLACES)
    return f"{prop} {prod} {place}"

# --- РОБОТА З ПУЛОМ ГІПОТЕЗ ---
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
        st.error(f"Помилка додавання фраз до БД: {e}")

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
    # ИСПРАВЛЕНО: заменено gemini-1.5-flash-latest -> gemini-1.5-flash
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    headers = {"Content-Type": "application/json"}
    
    prompt = f"""
    Сгенеруй {count} пошукових запитів українською мовою для пошуку фізичних трендових товарів для дропшипінгу в Україні (для Prom.ua).
    Орієнтовна роздрібна ціна: до 500 грн.
    
    ВИКЛЮЧИТИ: одяг, взуття, ліки, продукти харчування, складну габаритну електроніку.
    ПЕРЕВАГА: товари з WOW-ефектом, розв'язання побутових проблем, недорогі девайси для дому, авто, кухні, ванної, організації простору, догляду.
    
    Поверни СТРОГО JSON-масив рядків без будь-якого додаткового тексту чи размітки.
    Приклад: ["сенсорний нічник для шафи", "магнітний тримач кабелю", "міні вакууматор пакетів", "щітка для жалюзі"]
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=20)
        if res.status_code == 200:
            data = res.json()
            text_response = data["candidates"][0]["content"]["parts"][0]["text"]
            queries = json.loads(text_response)
            if isinstance(queries, list):
                return queries
        else:
            st.error(f"Помилка Gemini API: {res.status_code} - {res.text}")
    except Exception as e:
        st.error(f"Не вдалося згенерувати через AI: {e}")
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

# --- ІНІЦІАЛІЗАЦІЯ ---
init_db()
st.session_state["favorites"] = load_favorites_db()

if "default_query" not in st.session_state:
    st.session_state["default_query"] = generate_combinatorial_query()

if "results" not in st.session_state:
    st.session_state["results"] = []

# --- СТИЛІ CSS ---
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
    st.caption(f"🧠 В пулі гіпотез: **{total_q}** фраз (з них AI: {ai_q})")
    
    c_side1, c_side2 = st.columns(2)
    with c_side1:
        if st.button("🎲 Згенерувати гіпотезу", use_container_width=True):
            st.session_state["default_query"] = get_query_from_pool()
            st.rerun()
            
    with c_side2:
        if st.button("🧩 Комбінатор", use_container_width=True):
            st.session_state["default_query"] = generate_combinatorial_query()
            st.rerun()

    with st.expander("✨ Налаштування Gemini AI"):
        # Спроба отримати ключ із secrets.toml або змінних оточення
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
            help="Отримати безкоштовно на aistudio.google.com"
        )
        
        if st.button("🚀 Наповнити пул через AI (+30 фраз)"):
            if not gemini_api_key:
                st.warning("Введіть Gemini API Key або збережіть його в .streamlit/secrets.toml!")
            else:
                with st.spinner("AI генерує нові пошукові фрази..."):
                    new_q = generate_ai_queries_gemini(gemini_api_key, count=30)
                    if new_q:
                        add_queries_to_pool(new_q, source="AI")
                        st.success(f"Додано {len(new_q)} нових гіпотез у пул!")
                        st.rerun()

    st.markdown("---")
    query = st.text_input("Пошуковий запит:", value=st.session_state["default_query"])

    pages_count = st.slider("Сторінок для збору:", 1, 10, 3)
    
    st.header("💰 Фільтр за ціною")
    price_filter_enabled = st.checkbox("Обмеження ціни", value=True)
    min_price_input = st.number_input("Мін. ціна (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. ціна (грн):", min_value=0, value=500, step=50)

    st.header("🚫 Чорний список")
    exclude_keywords = st.text_input("Виключити слова (через кому):", "")
    exclude_sellers = st.text_input("Виключити продавців:", "")

# --- ЗАПУСК СКАНИРОВАНИЯ ---
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    start_scan = st.button("🚀 Запустити сканування", type="primary", use_container_width=True)

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
        status_box.info(f"⏳ Сканування сторінки {page} з {pages_count} за запитом: **{query}**...")
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

                        supplier_name = supplier_el.text.strip() if supplier_el else "Продавець не вказаний"
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

                        sales_info = sales_el.text.strip() if sales_el else "В наявності"

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
            st.warning(f"Помилка завантаження сторінки {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(0.8)
        
    status_box.empty()
    st.session_state["results"] = products
    st.rerun()

st.markdown("---")

# --- ВКЛАДКИ ---
tab_list, tab_fav, tab_analytics, tab_seo = st.tabs([
    f"📋 Знайдено товарів ({len(st.session_state['results'])})", 
    f"⭐ Обране в БД ({len(st.session_state['favorites'])})",
    "📊 Аналітика ніші", 
    "🔍 SEO & Ключові слова"
])

# === ВКЛАДКА 1: ЗНАЙДЕНІ ТОВАРИ ===
with tab_list:
    if not st.session_state["results"]:
        st.info("💡 Натисніть **'🚀 Запустити сканування'** або кнопку **'🎲 Згенерувати гіпотезу'** в меню ліворуч.")
    else:
        graph_ideas = extract_graph_queries(st.session_state["results"])
        if graph_ideas:
            st.markdown("##### 🕸️ Скритий граф товарів (суміжні гіпотези з результатів):")
            g_cols = st.columns(len(graph_ideas))
            for idx, idea in enumerate(graph_ideas):
                with g_cols[idx]:
                    if st.button(f"🔍 {idea}", key=f"graph_btn_{idx}", use_container_width=True):
                        st.session_state["default_query"] = idea
                        st.rerun()

        f_col1, f_col2 = st.columns([2, 1])
        with f_col1:
            search_filter = st.text_input("🔍 Швидкий фільтр в результатах:", placeholder="Введіть слово...")
        with f_col2:
            sort_option = st.selectbox("Сортування:", ["За замовчуванням", "Спочатку дешевші", "Спочатку дорожчі", "За продавцем"])

        df = pd.DataFrame(st.session_state["results"])
        view_df = df.copy()
        
        if search_filter:
            view_df = view_df[view_df["Название"].str.contains(search_filter, case=False, na=False)]
        
        if sort_option == "Спочатку дешевші":
            view_df = view_df.sort_values(by="Цена", ascending=True)
        elif sort_option == "Спочатку дорожчі":
            view_df = view_df.sort_values(by="Цена", ascending=False)
        elif sort_option == "За продавцем":
            view_df = view_df.sort_values(by="Поставщик")

        for row_idx, item in view_df.iterrows():
            with st.container():
                st.markdown('<div class="product-card">', unsafe_allow_html=True)
                col_img, col_main, col_price, col_seller = st.columns([1, 4.5, 1.5, 2])
                
                with col_img:
                    st.image(item["Картинка"], use_container_width=True)
                    
                with col_main:
                    st.markdown(f"**[{item['Название']}]({item['Ссылка']})**")
                    st.caption(f"{item['Статус']} · [Відкрити на Prom.ua ↗]({item['Ссылка']})")
                    
                    target_url = item["Ссылка_поставщика"] if item["Ссылка_поставщика"] else item["Ссылка"]
                    msg_raw = f"Вітаю! Підкажіть, будь ласка, чи працюєте ви по дропшипінгу? Якщо так, дайте свої контакти для зв'язку (Telegram/Viber). Товар: {item['Ссылка']}"

                    b_col1, b_col2 = st.columns([1, 1.2])
                    
                    with b_col1:
                        is_in_fav = any(f["Ссылка"] == item["Ссылка"] for f in st.session_state["favorites"])
                        btn_label = "✅ В обраному" if is_in_fav else "⭐ В обране"
                        
                        if st.button(btn_label, key=f"fav_btn_{row_idx}_{item['Ссылка'][-10:]}"):
                            if is_in_fav:
                                remove_favorite_db(item["Ссылка"])
                                st.toast("Видалено з БД", icon="🗑️")
                            else:
                                add_favorite_db(item)
                                st.toast("Збережено в БД! ⭐", icon="✅")
                            st.session_state["favorites"] = load_favorites_db()
                            st.rerun()

                    with b_col2:
                        st.link_button("🤝 До продавця", target_url, use_container_width=True)

                    st.caption("Текст для продавця:")
                    st.code(msg_raw, language=None)

                with col_price:
                    st.markdown(f"### {item['Цена']} грн")

                with col_seller:
                    if item["Ссылка_поставщика"]:
                        st.markdown(f"**Продавець:** [{item['Поставщик']}]({item['Ссылка_поставщика']})")
                    else:
                        st.markdown(f"**Продавець:** {item['Поставщик']}")
                
                st.markdown('</div>', unsafe_allow_html=True)

# === ВКЛАДКА 2: ОБРАНЕ ===
with tab_fav:
    c_fav_head, c_fav_clear = st.columns([4, 1])
    with c_fav_head:
        st.subheader("⭐ Збережені товари в SQLite БД")
    with c_fav_clear:
        if st.session_state["favorites"]:
            if st.button("🧹 Очистити БД"):
                clear_favorites_db()
                st.session_state["favorites"] = []
                st.rerun()

    if not st.session_state["favorites"]:
        st.info("У базі даних поки немає збережених товарів. Натискайте **'⭐ В обране'** біля товарів.")
    else:
        fav_df = pd.DataFrame(st.session_state["favorites"])
        st.write("Відмітьте галочками **до 3-х кращих товарів** для запуску в рекламу:")
        
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
                st.caption(f"Продавець: {f_item['Поставщик']} | Ціна: {f_item['Цена']} грн")
            with f_c4:
                if st.button("🗑️ Видалити", key=f"del_fav_{f_idx}"):
                    remove_favorite_db(f_item["Ссылка"])
                    st.session_state["favorites"] = load_favorites_db()
                    st.rerun()
            st.markdown("---")

        if len(selected_for_ads) > 3:
            st.warning("⚠️ Вибрано більше 3-х товарів.")
        
        if selected_for_ads:
            st.subheader("🚀 Ваша трійка для рекламного тесту")
            top_df = pd.DataFrame(selected_for_ads)
            st.dataframe(top_df[["Название", "Цена", "Поставщик", "Ссылка"]], use_container_width=True)

# === ВКЛАДКА 3: АНАЛІТИКА ===
with tab_analytics:
    if st.session_state["results"]:
        df_an = pd.DataFrame(st.session_state["results"])
        st.subheader("📈 Розподіл цін у ніші")
        fig_hist = px.histogram(df_an, x="Цена", nbins=20, title="Гістограма цін",
                                labels={"Цена": "Ціна (грн)", "count": "Кількість"},
                                color_discrete_sequence=['#635BFF'])
        st.plotly_chart(fig_hist, use_container_width=True)
    else:
        st.info("Спочатку запустіть сканування товарів.")

# === ВКЛАДКА 4: SEO ===
with tab_seo:
    if st.session_state["results"]:
        df_seo = pd.DataFrame(st.session_state["results"])
        st.subheader("🔑 Популярні ключові слова")
        raw_text = " ".join(df_seo["Название"].tolist()).lower()
        words = re.findall(r'\b[a-ua-яєії0-9]{3,}\b', raw_text)
        stop_words = {'для', 'над', 'под', 'під', 'или', 'або', 'при', 'пластиковый', 'набор', 'шт', 'грн'}
        filtered_words = [w for w in words if w not in stop_words and not w.isdigit()]
        word_counts = Counter(filtered_words).most_common(15)
        seo_df = pd.DataFrame(word_counts, columns=["Слово", "Частота"])
        st.dataframe(seo_df, use_container_width=True)
    else:
        st.info("Спочатку запустіть сканування товарів.")
