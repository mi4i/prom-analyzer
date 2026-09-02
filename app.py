import io
from datetime import datetime
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Реестр заказов", layout="wide")

st.title("📦 Реестр заказов")

# Пример данных (замените на ваш источник данных / запрос из БД)
if "shipments" not in st.session_state:
    st.session_state.shipments = [
        {
            "Дата заказа": "20.08",
            "ТТН": "20451516066312",
            "Адрес": "Київ",
            "Клиент": "Сорокин Дмитрий",
            "№ телеф.": "067 113 70 77",
            "код Товара": "21010",
            "количе ство": 1,
            "наложка": 850,
            "сумма наложки": 850,
            "medley ціна": 160,
            "ваша маржа": 663,
            "статус": "відмова",
        },
        {
            "Дата заказа": "21.08",
            "ТТН": "20451516500538",
            "Адрес": "Камянское",
            "Клиент": "Сергей Иванов",
            "№ телеф.": "0963309566",
            "код Товара": "21015",
            "количе ство": 50,
            "наложка": 1550,
            "сумма наложки": 1550,
            "medley ціна": 185,
            "ваша маржа": 374.25,
            "статус": "отримано",
        },
    ]

df = pd.DataFrame(st.session_state.shipments)

st.subheader("Текущие записи")
st.dataframe(df, use_container_width=True)


# Функция генерации полноценного .xlsx файла в памяти
def generate_excel(df_to_export):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_to_export.to_excel(writer, index=False, sheet_name="Реестр")
    return buffer.getvalue()


# Блок экспорта
st.markdown("---")
st.subheader("📥 Экспорт в Excel")

excel_bytes = generate_excel(df)

st.download_button(
    label="📥 Скачать реестр (.xlsx)",
    data=excel_bytes,
    file_name=f"shipments_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    use_container_width=True,
)
