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
                    supplier_el = b.select_one('[data-qaid="company_name"]') or b.select_one('[data-qaid="company_link"]')
                    img_el = b.select_one('img')
                    sales_el = b.select_one('[data-qaid="rating_info"]') or b.select_one('[data-qaid="reviews_count"]')
                    
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
                        
                        # Парсинг картинки
                        img_url = ""
                        if img_el:
                            img_url = img_el.get("src") or img_el.get("data-src") or ""
                            if img_url.startswith("//"):
                                img_url = "https:" + img_url

                        supplier = supplier_el.text.strip() if supplier_el else "Продавец не указан"
                        sales_info = sales_el.text.strip() if sales_el else "Нет отзывов"

                        products.append({
                            "Название": name,
                            "Цена (грн)": price,
                            "Поставщик": supplier,
                            "Рейтинг/Отзывы": sales_info,
                            "Картинка": img_url,
                            "Ссылка": full_link
                        })
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(0.3)
        
    st.session_state["results"] = products

# Отображение результатов
if "results" in st.session_state and st.session_state["results"]:
    data = st.session_state["results"]
    df = pd.DataFrame(data)
    
    st.markdown("---")
    c1, c2, c3 = st.columns(3)
    c1.metric("Найдено позиций", len(df))
    c2.metric("Средняя цена", f"{int(df['Цена (грн)'].mean()):,} грн".replace(",", " "))
    c3.metric("Диапазон цен", f"{df['Цена (грн)'].min()} - {df['Цена (грн)'].max()} грн")
    st.markdown("---")
    
    # Визуализация карточек (3 карточки в ряд)
    cols = st.columns(3)
    for idx, item in enumerate(data):
        with cols[idx % 3]:
            with st.container(border=True):
                if item["Картинка"]:
                    st.image(item["Картинка"], use_column_width=True)
                
                st.markdown(f"**[{item['Название']}]({item['Ссылка']})**")
                st.markdown(f"### {item['Цена (грн)']} грн")
                st.write(f"🏢 **Продавец:** {item['Поставщик']}")
                st.caption(f"⭐ **Состояние/Отзывы:** {item['Рейтинг/Отзывы']}")

    st.markdown("---")
    csv_data = df.to_csv(index=False).encode('utf-8-sig')
    st.download_button(
        label="📥 Скачать CSV-отчет",
        data=csv_data,
        file_name=f"prom_report.csv",
        mime="text/csv"
    )
elif "results" in st.session_state:
    st.error("Товары не найдены. Попробуйте изменить фильтры или поисковый запрос.")
