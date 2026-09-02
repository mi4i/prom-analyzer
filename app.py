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
    
    # Retry-логика: 2 попытки с увеличенным таймаутом (10 сек на коннект, 60 сек на чтение)
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
                time.sleep(1) # Пауза перед повторной попыткой
                continue
            st.error("⏳ Таймаут: Gemini API не ответил за 60 секунд. Попробуйте еще раз позже.")
        except Exception as e:
            st.error(f"Ошибка запроса к AI: {e}")
            break
            
    return []
