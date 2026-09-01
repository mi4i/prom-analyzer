def add_favorite_db(item):
    # Преобразуем Pandas Series в чистый Python dict
    if hasattr(item, "to_dict"):
        item_dict = item.to_dict()
    else:
        item_dict = dict(item)
    
    # Приводим данные к базовым типам Python (str, int), чтобы json.dumps не падал
    clean_dict = {
        "Название": str(item_dict["Название"]),
        "Цена": int(item_dict["Цена"]),
        "Поставщик": str(item_dict["Поставщик"]),
        "Ссылка_поставщика": str(item_dict["Ссылка_поставщика"]),
        "Статус": str(item_dict["Статус"]),
        "Картинка": str(item_dict["Картинка"]),
        "Ссылка": str(item_dict["Ссылка"])
    }

    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO favorites (link, data) VALUES (?, ?)", 
              (clean_dict["Ссылка"], json.dumps(clean_dict, ensure_ascii=False)))
    conn.commit()
    conn.close()
