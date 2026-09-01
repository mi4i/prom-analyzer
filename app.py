import json
from urllib.parse import quote
from bs4 import BeautifulSoup
from curl_cffi import requests
from google import genai
from google.genai import types
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="mySalesTrend — Prom & AI Analytics",
    layout="wide",
    page_icon="⚡",
)

st.title("⚡ mySalesTrend: Умный поиск и AI-анализ Prom.ua")

# 1. Авторизация и пароль
if "APP_PASSWORD" in st.secrets:
  user_pass = st.sidebar.text_input("Пароль доступа:", type="password")
  if user_pass != st.secrets["APP_PASSWORD"]:
    st.error("🔒 Введите пароль для работы с сервисом.")
    st.stop()

api_key = st.secrets.get(
    "GEMINI_API_KEY"
) or st.sidebar.text_input("Gemini API Key:", type="password")
if not api_key:
  st.warning("⚠️ Укажите GEMINI_API_KEY в Secrets или в меню слева.")
  st.stop()

client = genai.Client(api_key=api_key)

# 2. Настройки фильтрации (как в mySalesTrend)
st.sidebar.header("🎯 Параметры отбора")
min_price = st.sidebar.number_input("Цена от, грн:", min_value=0, value=0)
max_price = st.sidebar.number_input("Цена до, грн:", min_value=0, value=700)
min_orders = st.sidebar.selectbox(
    "Минимум заказов:",
    options=[0, 1, 10, 20, 50, 100],
    index=2,  # По умолчанию от 10 заказов
)
max_items = st.sidebar.selectbox(
    "Сколько проверить:",
    options=[30, 60, 100],
    format_func=lambda x: f"До {x} товаров",
)
only_in_stock = st.sidebar.checkbox("Только в наличии", value=True)
sort_mode = st.sidebar.selectbox(
    "Режим отбора:",
    options=["popular", "ads"],
    format_func=lambda x: (
        "Самые покупаемые" if x == "popular" else "Перспективные для рекламы"
    ),
)


# 3. Функция многостраничного парсинга Prom.ua
def scrape_prom_multipage(query, min_p, max_p, min_ord, in_stock, target_count):
  products = []
  seen_titles = set()
  page = 1

  # Формируем URL с фильтрами Prom.ua
  base_url = f"https://prom.ua/ua/search?search_term={quote(query)}"
  if max_p > 0:
    base_url += f"&price_local__lte={max_p}"
  if min_p > 0:
    base_url += f"&price_local__gte={min_p}"
  if in_stock:
    base_url += "&presence_option=in_stock"

  headers = {
      "Accept": (
          "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
      ),
      "Accept-Language": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
      "Referer": "https://prom.ua/",
  }

  while len(products) < target_count and page <= 3:
    url = f"{base_url}&page={page}"
    try:
      response = requests.get(
          url, impersonate="chrome120", timeout=15, headers=headers
      )
      if response.status_code != 200:
        break

      soup = BeautifulSoup(response.text, "html.parser")
      cards = soup.select(
          'div[data-qaid="product_presence"], article, div[data-qaid="product_block"]'
      )

      if not cards:
        break

      for card in cards:
        parent = card.find_parent("article") or card

        title_elem = parent.select_one(
            'a[data-qaid="product_name"], a[data-qaid="product_link"]'
        )
        price_elem = parent.select_one(
            'span[data-qaid="product_price"], [data-qaid="price_span"]'
        )
        store_elem = parent.select_one('a[data-qaid="company_name"]')
        orders_elem = parent.select_one('[data-qaid="orders_count"]')

        if title_elem and price_elem:
          title = title_elem.text.strip()
          if title in seen_titles:
            continue

          # Парсинг цены
          price_raw = (
              price_elem.text.encode("ascii", "ignore")
              .decode("utf-8")
              .replace(" ", "")
          )
          try:
            price = int("".join(filter(str.isdigit, price_raw)))
          except ValueError:
            price = 0

          # Парсинг количества заказов
          orders = 0
          if orders_elem:
            try:
              orders = int("".join(filter(str.isdigit, orders_elem.text)))
            except ValueError:
              orders = 0

          # Проверка фильтров
          if min_ord > 0 and orders < min_ord:
            continue
          if max_p > 0 and price > max_p:
            continue
          if min_p > 0 and price < min_p:
            continue

          seen_titles.add(title)
          store = store_elem.text.strip() if store_elem else "Н/Д"
          link = title_elem.get("href", "")
          if not link.startswith("http"):
            link = "https://prom.ua" + link

          products.append({
              "title": title,
              "price": price,
              "orders": orders,
              "store": store,
              "link": link,
          })

          if len(products) >= target_count:
            break

      page += 1
    except Exception as e:
      st.error(f"Ошибка сбора данных: {e}")
      break

  return products


# 4. Анализ через Gemini 2.0 Flash
def analyze_with_ai(product, mode):
  prompt = (
      f"Проанализируй товар для дропшиппинга/товарки (Режим: {mode}):"
      f" {json.dumps(product, ensure_ascii=False)}.\n"
      "Верни JSON с 2 полями:\n"
      '1. "score": число от 0 до 100 (маркетинговый потенциал)\n'
      '2. "verdict": 1 короткое предложение о перспективах продаж'
  )
  try:
    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)
  except Exception as e:
    return {"score": 50, "verdict": f"Ошибка AI: {str(e)}"}


# 5. Главный интерфейс
search_query = st.text_input(
    "Поисковый запрос на Prom.ua:",
    placeholder="Например: детские игрушки, товары для кухни, автокомпрессор",
)

if st.button("🔎 Найти лучшие товары") and search_query:
  with st.spinner("Сканируем страницы Prom.ua и отбираем товары..."):
    items = scrape_prom_multipage(
        query=search_query,
        min_p=min_price,
        max_p=max_price,
        min_ord=min_orders,
        in_stock=only_in_stock,
        target_count=max_items,
    )

  if not items:
    st.warning(
        "Товары не найдены. Попробуйте уменьшить 'Минимум заказов' или расширить"
        " диапазон цен."
    )
  else:
    with st.spinner("Проводим AI-анализ найденных позиций..."):
      analyzed_items = []
      for item in items:
        res = analyze_with_ai(item, sort_mode)
        item.update(res)
        analyzed_items.append(item)

      df = pd.DataFrame(analyzed_items)
      df = df.sort_values(
          by="orders" if sort_mode == "popular" else "score", ascending=False
      )

      st.success(f"Найдено и проанализировано подходящих товаров: {len(df)}")

      st.dataframe(
          df[["score", "title", "price", "orders", "store", "verdict", "link"]],
          column_config={
              "score": st.column_config.ProgressColumn(
                  "Сигнал AI", min_value=0, max_value=100, format="%d/100"
              ),
              "title": "Товар",
              "price": st.column_config.NumberColumn(
                  "Цена", format="%d грн"
              ),
              "orders": st.column_config.NumberColumn("Заказы"),
              "store": "Магазин",
              "verdict": "Анализ Gemini AI",
              "link": st.column_config.LinkColumn("Ссылка на Prom"),
          },
          use_container_width=True,
          hide_index=True,
      )
