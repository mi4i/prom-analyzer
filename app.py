import json
from bs4 import BeautifulSoup
from google import genai
from google.genai import types
import pandas as pd
import requests
import streamlit as st

# Настройки страницы Streamlit
st.set_page_config(page_title="Prom Analytics", layout="wide")

st.title("📊 Поиск и анализ товаров Prom.ua")

# 1. Получение API-ключа (из Secrets сервера или из ввода пользователем)
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

# Инициализация клиента Gemini
client = genai.Client(api_key=api_key)


# 2. Функция анализа товара через Gemini API
def analyze_with_ai(product):
  prompt = (
      f"Проанализируй товар для дропшиппинга/товарного бизнеса:"
      f" {json.dumps(product, ensure_ascii=False)}.\n"
      "Верни JSON с полями:\n"
      "- score: число от 0 до 100 (потенциал успешности продаж)\n"
      "- verdict: короткий вывод (1 предложение, почему поставлен такой балл)"
  )
  try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        ),
    )
    return json.loads(response.text)
  except Exception as e:
    return {"score": 50, "verdict": f"Ошибка ИИ-анализа: {str(e)}"}


# 3. Функция получения товаров (демо-список)
def get_prom_items(query):
  return [
      {
          "title": "Гель для прання Deluxe Enzo 4л",
          "price": 269,
          "orders": 40,
          "reviews": 0,
          "store": "Інтернет-магазин О.К.",
      },
      {
          "title": "Туалетний папір Papela Comfort 16р",
          "price": 176,
          "orders": 20,
          "reviews": 5,
          "store": "Все для дому",
      },
      {
          "title": "Епілятор IPL для обличчя",
          "price": 4899,
          "orders": 10,
          "reviews": 2,
          "store": "Кардинал",
      },
      {
          "title": "Лесинка для собак",
          "price": 1589,
          "orders": 0,
          "reviews": 0,
          "store": "Майстерня Меблі Стиль",
      },
  ]


# 4. Форма и вывод результатов
query = st.text_input("Поисковый запрос на Prom.ua:", value="домашние товары")

if st.button("🔎 Найти и проанализировать"):
  with st.spinner("Собираем товары и запрашиваем аналитику у Gemini AI..."):
    raw_items = get_prom_items(query)
    final_items = []

    for item in raw_items:
      analysis = analyze_with_ai(item)
      item.update(analysis)
      final_items.append(item)

    df = pd.DataFrame(final_items)

    st.success("Анализ завершен!")

    # Таблица результатов
    st.dataframe(
        df[["score", "title", "price", "orders", "store", "verdict"]],
        column_config={
            "score": st.column_config.ProgressColumn(
                "Сигнал", min_value=0, max_value=100, format="%d/100"
            ),
            "title": "Товар",
            "price": "Цена (грн)",
            "orders": "Заказы",
            "store": "Магазин",
            "verdict": "Анализ Gemini AI",
        },
        use_container_width=True,
    )