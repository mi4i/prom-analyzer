import streamlit as st
import pandas as pd

# ... ваш код загрузки данных ...

# 1. Сначала определяем или фильтруем view_df
view_df = st.session_state.get("df", pd.DataFrame()) # или ваша переменная с товарами

# 2. Проверяем, что датафрейм не пустой
if not view_df.empty:
    for row_idx, item in view_df.iterrows():
        with st.container():
            st.markdown('<div class="product-card">', unsafe_allow_html=True)
            col_img, col_main, col_price, col_seller = st.columns([1, 4.5, 1.5, 2])
            
            with col_img:
                st.image(item["Картинка"], use_container_width=True)
                
            with col_main:
                st.markdown(f"**[{item['Название']}]({item['Ссылка']})**")
                st.caption(f"{item['Статус']} · [Открыть на Prom.ua ↗]({item['Ссылка']})")
                
                target_url = item["Ссылка_поставщика"] if item["Ссылка_поставщика"] else item["Ссылка"]
                msg_raw = f"Вітаю! Підкажіть, будь ласка, чи працюєте ви по дропшипінгу? Якщо так, дайте свої контакти для зв'язку (Telegram/Viber). Товар: {item['Ссылка']}"

                b_col1, b_col2 = st.columns([1, 1.2])
                
                with b_col1:
                    is_in_fav = any(f["Ссылка"] == item["Ссылка"] for f in st.session_state.get("favorites", []))
                    btn_label = "✅ В избранном" if is_in_fav else "⭐ В избранное"
                    
                    if st.button(btn_label, key=f"fav_btn_{row_idx}_{item['Ссылка'][-10:]}"):
                        # логика добавления/удаления
                        pass

                with b_col2:
                    st.link_button("🤝 К продавцу", target_url, use_container_width=True)

                st.caption("Текст для продавца (нажмите иконку копирования справа):")
                st.code(msg_raw, language=None)

            with col_price:
                st.markdown(f"### {item['Цена']} грн")

            with col_seller:
                supplier_name = item.get("Поставщик", "Не указан")
                if item.get("Ссылка_поставщика"):
                    st.markdown(f"**Продавец:** [{supplier_name}]({item['Ссылка_поставщика']})")
                else:
                    st.markdown(f"**Продавец:** {supplier_name}")
            
            st.markdown('</div>', unsafe_allow_html=True)
else:
    st.info("Список товаров пуст.")
