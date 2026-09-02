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
from datetime import date

# 1. Настройка страницы
st.set_page_config(page_title="MySales Trend - Prom Analyzer Pro", page_icon="📊", layout="wide")

# --- База данных SQLite ---
DB_NAME = "mysales_trend.db"

# --- ШАБЛОНЫ СООБЩЕНИЙ ДЛЯ ПРОДАВЦОВ ---
VENDOR_MESSAGE_TEMPLATES = [
    "Добрий день! Підкажіть, будь ласка, чи співпрацюєте ви за системою дропшипінгу? Товар: {link}",
    "Вітаю! Зацікавив ваш товар. Чи є у вас можливість співпраці по дропшипінгу? Товар: {link}",
    "Доброго дня! Хотів би уточнити, чи працюєте ви з продавцями по дропшипінгу? Посилання: {link}",
    "Вітаю 🙂 Розглядаю ваші товари для продажу. Чи відправляєте замовлення напряму покупцю? {link}",
    "Добрий день! Скажіть, будь ласка, чи можна з вами працювати без закупівлі товару наперед, під замовлення клієнта? {link}",
    "Доброго дня! Цікавить співпраця з вашим магазином. Чи маєте умови для дропшиперів? {link}",
    "Вітаю! Підкажіть щодо співпраці: чи можете відправляти товар моїм клієнтам від мого імені? Товар: {link}",
    "Добрий день 🙂 Чи розглядаєте ви партнерство по дропшипінгу для ваших товарів? {link}",
    "Вітаю! Хочу додати декілька ваших позицій у продаж. Чи працюєте з партнерами за моделлю дропшипінгу? {link}",
    "Доброго дня! Підкажіть, які у вас є варіанти співпраці для продавців без власного складу? Посилання: {link}"
]

REGEX_XML = r'https?://[^\s<>"]+\.(?:xml|yml)'
REGEX_TG = r'(?:https?://)?(?:t\.me|telegram\.me)/[a-zA-Z0-9_]+'
REGEX_PHONE = r'(?:\+?38)?0\d{9}'
B2B_KEYWORDS = ['постачальник', 'поставщик', 'співпраця', 'сотрудничество', 'дропшипінг', 'дропшипинг', 'xml', 'yml', 'гурт', 'опт', 'фід', 'фид', 'дистриб']

def get_random_vendor_message(link):
    return random.choice(VENDOR_MESSAGE_TEMPLATES).format(link=link)

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
            c.execute('''
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE,
                    card_info TEXT,
                    track_returns INTEGER DEFAULT 1,
                    return_fee REAL DEFAULT 150.0
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS shipments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    vendor_id INTEGER,
                    order_date TEXT,
                    ttn TEXT,
                    city TEXT,
                    nova_poshta_branch TEXT,
                    address TEXT,
                    client_name TEXT,
                    phone TEXT,
                    item_code TEXT,
                    cod_price REAL,
                    qty INTEGER,
                    drop_price REAL,
                    status TEXT,
                    FOREIGN KEY(vendor_id) REFERENCES vendors(id)
                )
            ''')
            # Миграции для уже существующей базы данных
            c.execute("PRAGMA table_info(shipments)")
            existing_columns = {row[1] for row in c.fetchall()}

            if "city" not in existing_columns:
                c.execute("ALTER TABLE shipments ADD COLUMN city TEXT")
            if "nova_poshta_branch" not in existing_columns:
                c.execute("ALTER TABLE shipments ADD COLUMN nova_poshta_branch TEXT")
            conn.commit()
    except Exception as e:
        st.error(f"Ошибка БД при инициализации: {e}")

# --- ФУНКЦИИ БД ДЛЯ ВЗАИМОРАСЧЕТОВ ---
def get_all_vendors():
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("SELECT id, name, card_info, track_returns, return_fee FROM vendors ORDER BY id ASC")
        return c.fetchall()

def add_vendor(name, card_info="", track_returns=1, return_fee=150.0):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO vendors (name, card_info, track_returns, return_fee) VALUES (?, ?, ?, ?)",
                  (name, card_info, track_returns, return_fee))
        conn.commit()

def update_vendor_settings(vendor_id, card_info, track_returns, return_fee):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE vendors SET card_info = ?, track_returns = ?, return_fee = ? WHERE id = ?",
                  (card_info, int(track_returns), return_fee, vendor_id))
        conn.commit()

def get_shipments_by_vendor(vendor_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            SELECT id, order_date, ttn, city, nova_poshta_branch, address, client_name, phone,
                   item_code, cod_price, qty, drop_price, status
            FROM shipments WHERE vendor_id = ? ORDER BY id DESC
        ''', (vendor_id,))
        return c.fetchall()

def add_shipment_db(
    vendor_id, order_date, ttn, city, nova_poshta_branch, address,
    client_name, phone, item_code, cod_price, qty, drop_price, status
):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute('''
            INSERT INTO shipments (
                vendor_id, order_date, ttn, city, nova_poshta_branch, address,
                client_name, phone, item_code, cod_price, qty, drop_price, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            vendor_id, str(order_date), ttn, city, nova_poshta_branch, address,
            client_name, phone, item_code, cod_price, qty, drop_price, status
        ))
        conn.commit()

def update_shipment_status_db(shipment_id, new_status):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("UPDATE shipments SET status = ? WHERE id = ?", (new_status, shipment_id))
        conn.commit()

def delete_shipment_db(shipment_id):
    with sqlite3.connect(DB_NAME) as conn:
        c = conn.cursor()
        c.execute("DELETE FROM shipments WHERE id = ?", (shipment_id,))
        conn.commit()

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
        "Ссылка": str(d.get("Ссылка", "")),
        "is_b2b": bool(d.get("is_b2b", False)),
        "xml_feeds": list(d.get("xml_feeds", [])),
        "tg_contacts": list(d.get("tg_contacts", [])),
        "phones": list(d.get("phones", []))
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

def extract_core_product_name(title):
    eng_matches = re.findall(r'[A-Za-z0-9]{2,}(?:\s+[A-Za-z0-9]+)*', title)
    eng_words = [m.strip() for m in eng_matches if len(m.strip()) > 2]
    if eng_words:
        return " ".join(eng_words[:3])
    
    stop_words = {'для', 'та', 'з', 'и', 'в', 'на', 'посуду', 'прибирання', 'насадками', 'штук', 'шт', 'комплект', 'универсальный', 'універсальна'}
    words = re.findall(r'\b[a-ua-яєії0-9]{3,}\b', title.lower())
    filtered = [w for w in words if w not in stop_words]
    
    if filtered:
        return " ".join(filtered[:3])
    
    return title[:30]

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

# Создание демо-поставщика, если база пустая
if not get_all_vendors():
    add_vendor("Миша (Drop Supply)", "4874 0700 5387 1529", 1, 150.0)

if "default_query" not in st.session_state:
    st.session_state["default_query"] = generate_combinatorial_query()

if "results" not in st.session_state:
    st.session_state["results"] = []

if "trigger_auto_scan" not in st.session_state:
    st.session_state["trigger_auto_scan"] = False

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

    .b2b-card {
        padding: 14px;
        border: 2px solid #635BFF;
        border-radius: 10px;
        background-color: #F8F7FF;
        margin-bottom: 12px;
    }

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
    st.header("🏢 B2B Пресеты (Поставщики)")
    st.caption("Быстрый поиск дистрибьюторов на Prom.ua:")
    
    b2b_c1, b2b_c2 = st.columns(2)
    with b2b_c1:
        if st.button("🤝 Закупкашипінг постачальник", use_container_width=True):
            st.session_state["default_query"] = "дропшипінг постачальник"
            st.rerun()
        if st.button("📦 Опт та дропшипінг", use_container_width=True):
            st.session_state["default_query"] = "опт та дропшипінг"
            st.rerun()
            
    with b2b_c2:
        if st.button("💼 Закупкашипінг співпраця", use_container_width=True):
            st.session_state["default_query"] = "дропшипінг співпраця"
            st.rerun()
        if st.button("📄 XML фід дропшипінг", use_container_width=True):
            st.session_state["default_query"] = "xml фід дропшипінг"
            st.rerun()

    st.markdown("---")
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
    
    deep_b2b_scan = st.checkbox(
        "🔍 Глубокий поиск B2B-контактов (заходить в карточки за XML/Telegram)", 
        value=True,
        help="При обнаружении B2B-объявления парсер перейдет на страницу товара и извлечет XML-фиды, Telegram и телефоны."
    )

    st.header("💰 Фильтр по цене")
    price_filter_enabled = st.checkbox("Ограничение цены (авто-отключается для B2B)", value=True)
    min_price_input = st.number_input("Мин. цена (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. цена (грн):", min_value=0, value=500, step=50)

    st.header("🚫 Черный список")
    exclude_keywords = st.text_input("Исключить слова (через запятую):", "")
    exclude_sellers = st.text_input("Исключить продавцов:", "")

# --- ЗАПУСК СКАНА ---
col_btn1, col_btn2 = st.columns([1, 3])
with col_btn1:
    start_scan = st.button("🚀 Запустить сканирование", type="primary", use_container_width=True)

if st.session_state["trigger_auto_scan"]:
    start_scan = True
    st.session_state["trigger_auto_scan"] = False

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
                        
                        if not name:
                            continue

                        name_lower = name.lower()
                        is_b2b = (price <= 5 and price > 0) or price == 0 or any(kw in name_lower for kw in B2B_KEYWORDS)

                        if price_filter_enabled and not is_b2b:
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

                        xml_feeds = []
                        tg_contacts = []
                        phones = []

                        block_html = str(b)
                        xml_feeds.extend(re.findall(REGEX_XML, block_html, re.IGNORECASE))
                        tg_contacts.extend(re.findall(REGEX_TG, block_html, re.IGNORECASE))
                        phones.extend(re.findall(REGEX_PHONE, block_html))

                        if deep_b2b_scan and is_b2b and full_link:
                            try:
                                d_res = session.get(full_link, timeout=4)
                                if d_res.status_code == 200:
                                    d_text = d_res.text
                                    xml_feeds.extend(re.findall(REGEX_XML, d_text, re.IGNORECASE))
                                    tg_contacts.extend(re.findall(REGEX_TG, d_text, re.IGNORECASE))
                                    phones.extend(re.findall(REGEX_PHONE, d_text))
                            except Exception:
                                pass

                        xml_feeds = sorted(list(set(xml_feeds)))
                        tg_contacts = sorted(list(set(tg_contacts)))
                        phones = sorted(list(set(phones)))

                        products.append({
                            "Название": name,
                            "Цена": price,
                            "Поставщик": supplier_name,
                            "Ссылка_поставщика": supplier_link,
                            "Статус": sales_info,
                            "Картинка": img_url,
                            "Ссылка": full_link,
                            "is_b2b": is_b2b,
                            "xml_feeds": xml_feeds,
                            "tg_contacts": tg_contacts,
                            "phones": phones
                        })
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(0.8)
        
    status_box.empty()
    st.session_state["results"] = products
    st.rerun()

st.markdown("---")

# --- РАЗДЕЛЕНИЕ ТОВАРОВ И B2B ---
all_results = st.session_state["results"]
b2b_items = [p for p in all_results if p.get("is_b2b")]
regular_items = [p for p in all_results if not p.get("is_b2b")]

# --- ВКЛАДКИ ---
tab_list, tab_b2b, tab_fav, tab_shipments, tab_analytics, tab_seo = st.tabs([
    f"📋 Найдено товаров ({len(regular_items)})", 
    f"🏢 B2B Поставщики ({len(b2b_items)})",
    f"⭐ Избранное в БД ({len(st.session_state['favorites'])})",
    "📦 Отправки и Взаиморасчеты",
    "📊 Аналитика ниши", 
    "🔍 SEO & Ключевые слова"
])

# === ВКЛАДКА 1: НАЙДЕННЫЕ ТОВАРЫ ===
with tab_list:
    if not regular_items:
        st.info("💡 Нажмите **'🚀 Запустить сканирование'** или используйте кнопки слева.")
    else:
        graph_ideas = extract_graph_queries(regular_items)
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
            search_filter = st.text_input("🔍 Быстрый фильтр по результатам:", placeholder="Введите слово...", key="filter_reg")
        with f_col2:
            sort_option = st.selectbox("Сортировка:", ["По умолчанию", "Сначала дешевле", "Сначала дороже", "По продавцу"], key="sort_reg")

        df = pd.DataFrame(regular_items)
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
                    
                    msg_key = f"vendor_msg_{row_idx}_{hash(item['Ссылка'])}"
                    if msg_key not in st.session_state:
                        st.session_state[msg_key] = get_random_vendor_message(item['Ссылка'])

                    b_col1, b_col2, b_col3 = st.columns([1, 1, 1.3])
                    
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

                    with b_col3:
                        core_name = extract_core_product_name(item["Название"])
                        if st.button(f"🔎 Все продавцы ({core_name})", key=f"find_all_{row_idx}_{item['Ссылка'][-10:]}", use_container_width=True):
                            st.session_state["default_query"] = core_name
                            st.session_state["trigger_auto_scan"] = True
                            st.rerun()

                    st.caption("Текст сообщения (можно редактировать прям тут):")
                    txt_col, btn_col = st.columns([4, 1])
                    
                    with btn_col:
                        if st.button("🔄 Сменить вопрос", key=f"rand_msg_{row_idx}_{item['Ссылка'][-10:]}", use_container_width=True):
                            st.session_state[msg_key] = get_random_vendor_message(item['Ссылка'])
                            st.rerun()

                    with txt_col:
                        st.text_area(
                            label="Сообщение продавцу", 
                            key=msg_key, 
                            height=75, 
                            label_visibility="collapsed"
                        )

                with col_price:
                    st.markdown(f"### {item['Цена']} грн")

                with col_seller:
                    if item["Ссылка_поставщика"]:
                        st.markdown(f"**Продавец:** [{item['Поставщик']}]({item['Ссылка_поставщика']})")
                    else:
                        st.markdown(f"**Продавец:** {item['Поставщик']}")
                
                st.markdown('</div>', unsafe_allow_html=True)

# === ВКЛАДКА 2: B2B ПОСТАВЩИКИ И XML-ФИДЫ ===
with tab_b2b:
    if not b2b_items:
        st.info("ℹ️ B2B-объявления и поставщики не найдены. Воспользуйтесь **B2B-пресетами** в сайдбаре слева.")
    else:
        st.subheader(f"🏢 Найдено B2B-предложений: {len(b2b_items)}")
        
        for b_idx, b_item in enumerate(b2b_items):
            with st.container():
                st.markdown('<div class="b2b-card">', unsafe_allow_html=True)
                bc_img, bc_info, bc_contacts = st.columns([1, 4, 3])
                
                with bc_img:
                    st.image(b_item["Картинка"], use_container_width=True)
                    
                with bc_info:
                    st.markdown(f"### 🤝 [{b_item['Название']}]({b_item['Ссылка']})")
                    if b_item["Ссылка_поставщика"]:
                        st.markdown(f"**Поставщик:** [{b_item['Поставщик']}]({b_item['Ссылка_поставщика']})")
                    else:
                        st.markdown(f"**Поставщик:** {b_item['Поставщик']}")
                    
                    price_display = f"{b_item['Цена']} грн" if b_item['Цена'] > 0 else "Уточняйте / Договорная"
                    st.caption(f"Указанная цена/депозит: **{price_display}**")

                    is_in_fav = any(f["Ссылка"] == b_item["Ссылка"] for f in st.session_state["favorites"])
                    btn_fav_b2b = "✅ В избранном" if is_in_fav else "⭐ Сохранить поставщика"
                    if st.button(btn_fav_b2b, key=f"fav_b2b_{b_idx}"):
                        if is_in_fav:
                            remove_favorite_db(b_item["Ссылка"])
                            st.toast("Удалено из БД", icon="🗑️")
                        else:
                            add_favorite_db(b_item)
                            st.toast("Поставщик сохранен в БД! ⭐", icon="✅")
                        st.session_state["favorites"] = load_favorites_db()
                        st.rerun()

                with bc_contacts:
                    st.markdown("#### 🔗 Фиды и контакты")
                    
                    if b_item["xml_feeds"]:
                        st.markdown("**📄 XML / YML Фиды выгрузки:**")
                        for xml_link in b_item["xml_feeds"]:
                            st.markdown(f"- [`{xml_link[:50]}...`]({xml_link})")
                    else:
                        st.caption("📄 XML-фид в описании не найден")

                    if b_item["tg_contacts"]:
                        st.markdown("**💬 Telegram контакты/каналы:**")
                        for tg in b_item["tg_contacts"]:
                            tg_url = tg if tg.startswith("http") else f"https://{tg}"
                            st.markdown(f"- [Telegram Manager/Channel ↗]({tg_url})")

                    if b_item["phones"]:
                        st.markdown(f"**📞 Телефоны:** {', '.join(b_item['phones'])}")
                        
                st.markdown('</div>', unsafe_allow_html=True)

# === ВКЛАДКА 3: ИЗБРАННОЕ ===
with tab_fav:
    c_fav_head, c_fav_clear = st.columns([4, 1])
    with c_fav_head:
        st.subheader("⭐ Сохраненные товары и поставщики в SQLite БД")
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
                if f_item.get("is_b2b"):
                    st.markdown("`🏢 B2B Поставщик`")
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

# === ВКЛАДКА 4: 📦 ОТПРАВКИ И ВЗАИМОРАСЧЕТЫ С ПОСТАВЩИКАМИ ===
with tab_shipments:
    st.subheader("📦 Модуль учета отправок и взаиморасчетов по наложенным платежам")
    
    vendors_list = get_all_vendors()
    
    col_v1, col_v2 = st.columns([3, 1])
    with col_v1:
        vendor_options = {f"{v[1]} (ID: {v[0]})": v for v in vendors_list}
        selected_v_label = st.selectbox(" Выберите поставщика:", list(vendor_options.keys()))
        selected_vendor = vendor_options[selected_v_label]
        v_id, v_name, v_card, v_track_returns, v_return_fee = selected_vendor

    with col_v2:
        with st.popover("➕ Новый поставщик"):
            new_v_name = st.text_input("Имя/Название поставщика:")
            new_v_card = st.text_input("Реквизиты/Карта:")
            new_v_returns = st.checkbox("Учитывать возвраты на себя", value=True)
            new_v_fee = st.number_input("Логистика отказа (грн):", value=150.0, step=10.0)
            if st.button("Сохранить поставщика", type="primary"):
                if new_v_name:
                    add_vendor(new_v_name, new_v_card, 1 if new_v_returns else 0, new_v_fee)
                    st.success("Поставщик добавлен!")
                    st.rerun()

    # --- НАСТРОЙКИ УЧЕТА ПОСТАВЩИКА ---
    with st.expander(f"⚙️ Настройки учета и реквизиты: {v_name}", expanded=False):
        st.markdown("**Параметры списания логистики и реквизиты:**")
        cfg_col1, cfg_col2, cfg_col3 = st.columns([2, 1.5, 2.5])
        
        with cfg_col1:
            track_returns_val = st.checkbox(
                "Вести учет возвратов/отказов", 
                value=bool(v_track_returns),
                help="Если включено — при отказе покупателя логистика сгорает из вашей маржи. Если отключено — поставщик берет логистику на себя."
            )
        with cfg_col2:
            return_fee_val = st.number_input(
                "Стоимость отказа (грн):", 
                value=float(v_return_fee), 
                step=10.0,
                disabled=not track_returns_val
            )
        with cfg_col3:
            card_info_val = st.text_input("Карта/Реквизиты поставщика:", value=v_card or "")

        if st.button("💾 Сохранить настройки поставщика"):
            update_vendor_settings(v_id, card_info_val, track_returns_val, return_fee_val)
            st.toast("Настройки поставщика обновлены! ✅", icon="⚙️")
            st.rerun()

    st.markdown("---")

    # --- ПОЛУЧЕНИЕ И РАСЧЕТ ОТПРАВОК ---
    raw_shipments = get_shipments_by_vendor(v_id)
    
    total_delivered_margin = 0.0
    total_refusal_loss = 0.0
    count_delivered = 0
    count_refused = 0
    count_in_transit = 0

    shipment_rows = []
    for s in raw_shipments:
        (
            s_id, order_date, ttn, city, nova_poshta_branch, address,
            client_name, phone, item_code, cod_price, qty, drop_price, status
        ) = s
        
        total_cod = qty * cod_price
        total_drop = qty * drop_price
        
        # Расчет маржи в зависимости от статуса и настроек поставщика
        if status in ("получено", "отримано"):
            margin = total_cod - total_drop
            total_delivered_margin += margin
            count_delivered += 1
        elif status in ("отказ", "відмова"):
            margin = -v_return_fee if v_track_returns else 0.0
            total_refusal_loss += abs(margin)
            count_refused += 1
        else:
            margin = 0.0
            count_in_transit += 1

        shipment_rows.append({
            "id": s_id,
            "order_date": order_date,
            "ttn": ttn,
            "city": city or "",
            "nova_poshta_branch": nova_poshta_branch or "",
            "address": address or "",
            "client_name": client_name,
            "phone": phone,
            "item_code": item_code,
            "cod_price": cod_price,
            "qty": qty,
            "total_cod": total_cod,
            "drop_price": drop_price,
            "total_drop": total_drop,
            "margin": margin,
            "status": status
        })

    net_final_margin = total_delivered_margin - total_refusal_loss

    # --- СВОДНЫЕ КАРТОЧКИ БАЛАНСА ---
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Чистая маржа к выплате", f"{net_final_margin:,.2f} грн")
    with m_col2:
        st.metric("Успешно получено", f"{total_delivered_margin:,.2f} грн", f"{count_delivered} ТТН")
    with m_col3:
        st.metric("Убыток от отказов", f"-{total_refusal_loss:,.2f} грн", f"{count_refused} отказов", delta_color="inverse")
    with m_col4:
        st.metric("В процессе / В дороге", f"{count_in_transit} ТТН")

    if v_card:
        st.caption(f"💳 **Реквизиты для перевода / сверки с {v_name}:** `{v_card}`")

    st.markdown("---")

    # --- ФОРМА ДОБАВЛЕНИЯ НОВОЙ ОТПРАВКИ ---
    with st.expander("➕ Добавить новую отправку (ТТН)", expanded=False):
        with st.form("add_shipment_form", clear_on_submit=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                in_date = st.date_input("Дата заказа:", value=date.today())
                in_ttn = st.text_input("№ ТТН:")
                in_city = st.text_input("Город:")
                in_np_branch = st.text_input("Отделение Новой почты №:")

            with f_col2:
                in_address = st.text_input("Адрес / примечание:")
                in_client = st.text_input("ФИО клиента:")
                in_phone = st.text_input("№ телефона:")
                in_code = st.text_input("Код / Артикул товара:", value="2101")

            with f_col3:
                in_cod = st.number_input("Наложка за 1 шт (грн):", value=550.0, step=10.0)
                in_qty = st.number_input("Количество (шт):", min_value=1, value=1)
                in_drop = st.number_input(
                    "Закупочная цена за 1 шт (грн):",
                    min_value=0.0,
                    value=185.0,
                    step=10.0
                )

            with f_col4:
                in_status = st.selectbox(
                    "Статус отправки:",
                    ["в дороге", "получено", "отказ", "новый"]
                )
                st.write("")
                st.write("")
                btn_add_order = st.form_submit_button(
                    "Сохранить отправку",
                    type="primary",
                    use_container_width=True
                )

            if btn_add_order:
                if in_ttn:
                    add_shipment_db(
                        v_id,
                        in_date,
                        in_ttn,
                        in_city,
                        in_np_branch,
                        in_address,
                        in_client,
                        in_phone,
                        in_code,
                        in_cod,
                        in_qty,
                        in_drop,
                        in_status
                    )
                    st.success("Отправка успешно сохранена в базу!")
                    st.rerun()
                else:
                    st.warning("Укажите номер ТТН!")

    # --- ТАБЛИЦА УЧЕТА И ИЗМЕНЕНИЯ СТАТУСОВ ---
    if not shipment_rows:
        st.info("Пока нет зафиксированных отправок для этого поставщика. Нажмите **'➕ Добавить новую отправку'** выше.")
    else:
        st.markdown("### 📋 Реестр отправок")
        
        status_options = ["в дороге", "получено", "отказ", "новый"]
        
        # Шапка таблицы
        h_c1, h_c2, h_c3, h_c4, h_c5, h_c6, h_c7, h_c8, h_c9, h_c10, h_c11 = st.columns(
            [0.9, 1.2, 1.1, 0.9, 1.7, 1, 1, 1, 1, 1.2, 0.45]
        )
        h_c1.caption("**Дата**")
        h_c2.caption("**ТТН**")
        h_c3.caption("**Город**")
        h_c4.caption("**НП №**")
        h_c5.caption("**Клиент**")
        h_c6.caption("**Код**")
        h_c7.caption("**Наложка**")
        h_c8.caption("**Закупка**")
        h_c9.caption("**Маржа**")
        h_c10.caption("**Статус**")
        h_c11.caption("**Уд.**")

        st.markdown("---")

        for row in shipment_rows:
            r_c1, r_c2, r_c3, r_c4, r_c5, r_c6, r_c7, r_c8, r_c9 = st.columns([1, 1.3, 1.8, 1.2, 1, 1, 1, 1.3, 0.5])
            
            r_c1.write(f"{row['order_date']}")
            r_c2.write(f"**{row['ttn']}**")
            r_c3.write(f"{row['client_name']}\n`{row['phone']}`")
            r_c4.write(f"{row['item_code']} (x{row['qty']})")
            r_c5.write(f"{row['total_cod']} грн")
            r_c6.write(f"{row['total_drop']} грн")
            
            # Цветовая индикация маржи
            if row["margin"] > 0:
                r_c7.markdown(f"**<span style='color:green;'>+{row['margin']:,.1f} грн</span>**", unsafe_allow_html=True)
            elif row["margin"] < 0:
                r_c7.markdown(f"**<span style='color:red;'>{row['margin']:,.1f} грн</span>**", unsafe_allow_html=True)
            else:
                r_c7.write("0 грн")

            # Выпадающий список прямого изменения статуса
            cur_idx = status_options.index(row["status"]) if row["status"] in status_options else 0
            new_st = r_c8.selectbox("", status_options, index=cur_idx, key=f"st_sel_{row['id']}", label_visibility="collapsed")
            
            if new_st != row["status"]:
                update_shipment_status_db(row["id"], new_st)
                st.toast(f"Статус ТТН {row['ttn']} изменен на '{new_st}'", icon="🔄")
                st.rerun()

            if r_c9.button("❌", key=f"del_ship_{row['id']}"):
                delete_shipment_db(row["id"])
                st.rerun()

# === ВКЛАДКА 5: АНАЛИТИКА ===
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

# === ВКЛАДКА 6: SEO ===
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
