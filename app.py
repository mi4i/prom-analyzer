import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="Prom Analyzer", page_icon="📊", layout="wide")

st.title("📊 Prom.ua Product Analyzer")

# Боковая панель для фильтров
with st.sidebar:
    st.header("⚙️ Параметры поиска")
    query = st.text_input("Поисковый запрос:", "беспроводные наушники")
    pages_count = st.slider("Количество страниц:", 1, 5, 1)
    
    st.header("💰 Фильтр по цене")
    price_filter_enabled = st.checkbox("Включить фильтрацию по цене", value=False)
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
                    
                    # Извлечение данных продавца и ссылки на его магазин
                    supplier_el = b.select_one('[data-qaid="company_link"]') or b.select_one('[data-qaid="company_name"]')
                    
                    if name_el and price_el:
                        name = name_el.text.strip()
                        raw_price = price_el.text.strip()
                        digits = "".join(c for c in raw_price if c.isdigit())
                        price = int(digits) if digits else 0
                        
                        # Фильтрация по цене
                        if price_filter_enabled:
                            if min_price_input > 0 and price < min_price_input:
                                continue
                            if max_price_input > 0 and price > max_price_input:
                                continue

                        # Ссылка на товар
                        href = link_el.get("href", "") if link_el else ""
                        full_link = f"https://prom.ua{href}" if href.startswith("/") else href
                        
                        # Парсинг продавца и ссылки на его каталог
                        supplier_name = "Продавец не указан"
                        supplier_link = ""
                        if supplier_el:
                            supplier_name = supplier_el.text.strip()
                            s_href = supplier_el.get("href", "") if supplier_el.name == "a" else ""
                            if not s_href and supplier_el.parent and supplier_el.parent.name == "a":
                                s_href = supplier_el.parent.get("href", "")
                            if s_href:
                                supplier_link = f"https://prom.ua{s_href}" if s_href.startswith("/") else s_href

                        # Парсинг картинки
                        img_url = ""
                        if img_el:
                            img_url = img_el.get("src") or img_el.get("data-src") or ""
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url

                        sales_info = sales_el.text.strip() if sales_el else "Нет отзывов"

                        products.append({
                            "Название": name,
                            "Цена (грн)": price,
                            "Поставщик": supplier_name,
                            "Ссылка_поставщика": supplier_link,
                            "Рейтинг/Отзывы": sales_info,
                            "Картинка": img_url,
                            "Ссылка": full_link
                        })
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(0.3)
        
    st.session_state["results"] = products

# Отображение результатов в виде таблицы
if "results" in st.session_state and st.session_state["results"]:
    data = st.session_state["results"]
    df = pd.DataFrame(data)
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Найдено позиций", len(df))
    c2.metric("Средняя цена", f"{int(df['Цена (грн)'].mean()):,} грн".replace(",", " "))
    c3.metric("Диапазон цен", f"{df['Цена (грн)'].min()} - {df['Цена (грн)'].max()} грн")
    st.markdown("---")
    
    # Шапка горизонтальной таблицы
    h_col1, h_col2, h_col3, h_col4, h_col5 = st.columns([1, 4, 2, 1.5, 2])
    with h_col1:
        st.markdown("**Фото**")
    with h_col2:
        st.markdown("**Товар**")
    with h_col3:
        st.markdown("**Продавец**")
    with h_col4:
        st.markdown("**Цена**")
    with h_col5:
        st.markdown("**Отзывы / Рейтинг**")
    
    st.divider()

    # Строки таблицы
    for item in data:
        row_col1, row_col2, row_col3, row_col4, row_col5 = st.columns([1, 4, 2, 1.5, 2])
        
        # 1. Фотография (миниатюра 70px)
        with row_col1:
            if item["Картинка"] and item["Картинка"].startswith("http"):
                try:
                    st.image(item["Картинка"], width=70)
                except Exception:
                    st.caption("🖼️ N/A")
            else:
                st.caption("🖼️ N/A")
                
        # 2. Название со ссылкой
        with row_col2:
            st.markdown(f"[{item['Название']}]({item['Ссылка']})")
            
        # 3. Продавец со ссылкой на каталог магазина
        with row_col3:
            if item["Ссылка_поставщика"]:
                st.markdown(f"[{item['Поставщик']}]({item['Ссылка_поставщика']})")
            else:
                st.write(item["Поставщик"])
                
        # 4. Цена
        with row_col4:
            st.markdown(f"**{item['Цена (грн)']} грн**")
            
        # 5. Рейтинг / Отзывы
        with row_col5:
            st.caption(item["Рейтинг/Отзывы"])
            
        st.divider()

    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Скачать CSV-отчет",
        data=csv_data,
        file_name="prom_report.csv",
        mime="text/csv"
    )
elif "results" in st.session_state:
    st.error("Товары не найдены. Попробуйте изменить фильтры или поисковый запрос.")
