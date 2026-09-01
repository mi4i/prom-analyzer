import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time

st.set_page_config(page_title="Prom Analyzer", page_icon="📊", layout="wide")

st.title("📊 Prom.ua Product Analyzer")
st.caption("Быстрый экспресс-анализ товаров и цен на Prom.ua")

query = st.text_input("Поисковый запрос:", "беспроводные наушники")
pages_count = st.slider("Количество страниц для сбора:", 1, 5, 1)

if st.button("Запустить аналитическое сканирование", type="primary"):
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
                    
                    if name_el and price_el:
                        name = name_el.text.strip()
                        raw_price = price_el.text.strip()
                        digits = "".join(c for c in raw_price if c.isdigit())
                        price = int(digits) if digits else 0
                        
                        href = link_el.get("href", "") if link_el else ""
                        full_link = f"https://prom.ua{href}" if href.startswith("/") else href
                        
                        products.append({
                            "Название": name,
                            "Цена (грн)": price,
                            "Ссылка": full_link
                        })
        except Exception as e:
            st.warning(f"Ошибка загрузки страницы {page}: {e}")
        
        progress_bar.progress(page / pages_count)
        time.sleep(0.3)
        
    if products:
        df = pd.DataFrame(products)
        
        c1, c2, c3 = st.columns(3)
        c1.metric("Найдено позиций", len(df))
        c2.metric("Средняя цена", f"{int(df['Цена (грн)'].mean()):,} грн".replace(",", " "))
        c3.metric("Диапазон цен", f"{df['Цена (грн)'].min()} - {df['Цена (грн)'].max()} грн")
        
        st.dataframe(df, use_container_width=True)
        
        csv_data = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="Загрузить CSV",
            data=csv_data,
            file_name=f"prom_{query}.csv",
            mime="text/csv"
        )
    else:
        st.error("Данные не получены. Возможно, Prom временно ограничил запросы с публичного IP Cloud-сервера.")
