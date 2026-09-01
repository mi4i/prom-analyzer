import json
from urllib.parse import quote
from bs4 import BeautifulSoup
import cloudscraper
from google import genai
from google.genai import types
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Prom.ua Analytics", layout="wide", page_icon="📊"
)
st.title("📊 Поиск и AI-анализ товаров Prom.ua")

# 1. Авторизация Gemini API
api_key = None
if "GEMINI_API_KEY" in st.secrets:
  api_key = st.secrets["GEMINI_API_KEY"]
else:
  api_key = st.sidebar.text_input(
      "Введите ваш Gemini API Key:", type="password"
  )

if not api_key:
  st.warning(
      "⚠️ Пожалуйста, введите ваш API Key от Google AI Studio в меню слева!"
  )
  st.stop()

client = genai.Client(api_key=api_key)


# 2. Функция парсинга с использованием cloudscraper
def scrape_prom_items(query, limit=10):
  scraper = cloudscraper.create_scraper(
      browser={"browser": "chrome", "platform": "windows", "desktop": True}
  )
  url = f"https://prom.ua/ua/search?search_term={quote(query)}"

  try:
    response = scraper.get(url, timeout=15)
    if response.status_code != 200:
      st.error(
          f"Prom.ua вернул статус {response.status_code}. Защита маркетплейса"
          " блокирует запрос."
      )
      return []

    soup = BeautifulSoup(response.text, "html.parser")
    products = []

    # Поиск элементов товаров
    cards = soup.find_all("div", {"data-qaid": "product_presence"}, limit=limit)

    for card in cards:
      parent = card.find_parent("article") or card.find_parent(
          "div", class_=True
      )
      if not parent:
        parent = card.parent

      title_elem = parent.find("a", {"data-qaid": "product_name"})
      price_elem = parent.find("span", {"data-qaid": "product_price"})
      store_elem = parent.find("a", {"data-qaid": "company_name"})

      if title_elem and price_elem:
        title = title_elem.text.strip()
        price_raw = (
            price_elem.text.encode("ascii", "ignore")
            .decode("utf-8")
            .replace(" ", "")
        )
        try:
          price = int("".join(filter(str.isdigit, price_raw)))
        except ValueError:
          price = 0

        store = store_elem.text.strip() if store_elem else "Н/Д"
        link = title_elem.get("href", "")
        if not link.startswith("http"):
          link = "https://prom.ua" + link

        products.append(
            {"title": title, "price": price, "store": store, "link": link}
        )

    return products
  except Exception as e:
    st.error(f"Ошибка при подключении к Prom.ua: {e}")
    return []


# 3. AI-анализ Gemini
def analyze_with_ai(product):
  prompt = (
      f"Проанализируй товар для коммерческих продаж/дропшиппинга:"
      f" {json.dumps(product, ensure_ascii=False)}.\n"
      "Верни СТРОГО JSON с двумя полями:\n"
      '1. "score": число от 0 до 100 (маркетинговый потенциал спроса и маржи)\n'
      '2. "verdict": краткое объяснение оценки (1 предложение)'
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


# 4. Интерфейс
search_query = st.text_input(
    "Введите поисковый запрос на Prom.ua:", placeholder="Например: автотовары"
)

if st.button("🔎 Найти и проанализировать") and search_query:
  with st.spinner("Загружаем свежие товары с Prom.ua..."):
    items = scrape_prom_items(search_query)

  if not items:
    st.warning("Товары не найдены или Prom.ua заблокировал IP сервера.")
  else:
    with st.spinner("Анализируем товары с помощью Gemini AI..."):
      analyzed_items = []
      for item in items:
        res = analyze_with_ai(item)
        item.update(res)
        analyzed_items.append(item)

      df = pd.DataFrame(analyzed_items)
      st.success(f"Успешно проанализировано товаров: {len(df)}")

      st.dataframe(
          df[["score", "title", "price", "store", "verdict", "link"]],
          column_config={
              "score": st.column_config.ProgressColumn(
                  "Сигнал AI", min_value=0, max_value=100, format="%d/100"
              ),
              "title": "Наименование товара",
              "price": st.column_config.NumberColumn(
                  "Цена", format="%d грн"
              ),
              "store": "Продавец",
              "verdict": "Вывод Gemini AI",
              "link": st.column_config.LinkColumn("Ссылка"),
          },
          use_container_width=True,
          hide_index=True,
      )
