import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="Prom Analyzer", page_icon="📊", layout="wide")

# Стилизация интерфейса в стиле личного кабинета аналитики
st.markdown("""
<style>
    /* Шапка таблицы */
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
    
    /* Карточка товара */
    .product-row {
        display: flex;
        align-items: flex-start;
        padding: 16px;
        border-left: 1px solid #EAE6F8;
        border-right: 1px solid #EAE6F8;
        border-bottom: 1px solid #EAE6F8;
        background-color: #FFFFFF;
    }
    .product-row:hover {
        background-color: #FBFBFE;
    }

    /* Колонки */
    .col-product { flex: 3.5; display: flex; gap: 16px; }
    .col-price { flex: 1; font-weight: 700; font-size: 1.1rem; color: #111827; padding-top: 4px; }
    .col-store { flex: 1.5; padding-top: 4px; }

    /* Предотвращение размытия и растягивания картинки */
    .product-img {
        width: 85px;
        height: 85px;
        object-fit: contain;
        border-radius: 8px;
        border: 1px solid #F0F0F5;
        background: #FFFFFF;
        flex-shrink: 0;
    }

    /* Тексты и ссылки */
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

    /* Теги/кнопки */
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

st.title("📊 Prom.ua Product Analyzer")

with st.sidebar:
    st.header("⚙️ Параметры поиска")
    query = st.text_input("Поисковый запрос:", "беспроводные наушники")
    pages_count = st.slider("Количество страниц:", 1, 5, 1)
    
    st.header("💰 Фильтр по цене")
    price_filter_enabled = st.checkbox("Включить фильтрацию", value=False)
    min_price_input = st.number_input("Мин. цена (грн):", min_value=0, value=0, step=50)
    max_price_input = st.number_input("Макс. цена (грн):", min_value=0, value=5000, step=50)

if st.button("Запустить сканирование", type="primary"):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }
    
    products = []
    progress_bar = st.progress(0)
    
    for page in range(1, pages_count + 1):
        url = f"https://prom.ua/ua/search?search_term={query}&page={page}"
        try:
            res = requests.get(url, headers=headers, timeout=10)
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

                        href = link_el.get("href", "") if link_el else ""
                        full_link = f"https://prom.ua{href}" if href.startswith("/") else href
                        
                        supplier_name = "Продавец не указан"
                        supplier_link = ""
                        if supplier_el:
                            supplier_name = supplier_el.text.strip()
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
        time.sleep(0.3)
        
    st.session_state["results"] = products

if "results" in st.session_state and st.session_state["results"]:
    data = st.session_state["results"]
    df = pd.DataFrame(data)
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Найдено позиций", len(df))
    c2.metric("Средняя цена", f"{int(df['Цена'].mean()):,} грн".replace(",", " "))
    c3.metric("Диапазон цен", f"{df['Цена'].min()} - {df['Цена'].max()} грн")
    st.markdown("---")
    
    # Шапка таблицы
    st.markdown("""
    <div class="table-header">
        <div class="col-product">ТОВАР</div>
        <div class="col-price">ЦЕНА</div>
        <div class="col-store">МАГАЗИН</div>
    </div>
    """, unsafe_allow_html=True)
    
    # Генерация карточек товаров
    html_content = ""
    for item in data:
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
    st.markdown("<br>", unsafe_allow_html=True)
    
    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Скачать CSV-отчет",
        data=csv_data,
        file_name="prom_report.csv",
        mime="text/csv"
    )
elif "results" in st.session_state:
    st.error("Товары не найдены.")
