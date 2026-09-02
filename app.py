# === ВКЛАДКА 4: 📦 ОТПРАВКИ И ВЗАИМОРАСЧЕТЫ С ПОСТАВЩИКАМИ ===
with tab_shipments:
    st.subheader("📦 Модуль учета отправок и взаиморасчетов по наложенным платежам")
    
    vendors_list = get_all_vendors()
    
    col_v1, col_v2 = st.columns([3, 1])
    with col_v1:
        vendor_options = {f"{v[1]} (ID: {v[0]})": v for v in vendors_list}
        selected_v_label = st.selectbox(" Выберите поставщика:", list(vendor_options.keys()))
        selected_vendor = vendor_options[selected_v_label]
        v_id, v_name, v_card, v_track_returns, v_return_fee = selected_vendor

    with col_v2:
        with st.popover("➕ Новый поставщик"):
            new_v_name = st.text_input("Имя/Название поставщика:")
            new_v_card = st.text_input("Реквизиты/Карта:")
            new_v_returns = st.checkbox("Учитывать возвраты на себя", value=True)
            new_v_fee = st.number_input("Логистика отказа (грн):", value=150.0, step=10.0)
            if st.button("Сохранить поставщика", type="primary"):
                if new_v_name:
                    add_vendor(new_v_name, new_v_card, 1 if new_v_returns else 0, new_v_fee)
                    st.success("Поставщик добавлен!")
                    st.rerun()

    # --- НАСТРОЙКИ И ФАЙЛОВЫЕ ОПЕРАЦИИ (ЭКСПОРТ / ИМПОРТ) ---
    col_exp1, col_exp2 = st.columns([1, 1])
    
    with col_exp1:
        with st.expander(f"⚙️ Настройки учета: {v_name}", expanded=False):
            st.markdown("**Параметры списания логистики и реквизиты:**")
            track_returns_val = st.checkbox(
                "Вести учет возвратов/отказов", 
                value=bool(v_track_returns),
                help="Если включено — при отказе покупателя логистика сгорает из вашей маржи. Если отключено — поставщик берет логистику на себя."
            )
            return_fee_val = st.number_input(
                "Стоимость отказа (грн):", 
                value=float(v_return_fee), 
                step=10.0,
                disabled=not track_returns_val
            )
            card_info_val = st.text_input("Карта/Реквизиты поставщика:", value=v_card or "")

            if st.button("💾 Сохранить настройки поставщика"):
                update_vendor_settings(v_id, card_info_val, track_returns_val, return_fee_val)
                st.toast("Настройки поставщика обновлены! ✅", icon="⚙️")
                st.rerun()

    with col_exp2:
        with st.expander("📂 Экспорт и Импорт данных (Excel / CSV)", expanded=False):
            st.markdown("**Экспорт:** Скачать текущий реестр поставщика в CSV (Excel)")
            
            raw_shipments_exp = get_shipments_by_vendor(v_id)
            if raw_shipments_exp:
                exp_data = []
                for s in raw_shipments_exp:
                    s_id, o_date, ttn, addr, c_name, ph, code, cod, q, drop, st_val = s
                    t_cod = cod * q
                    t_drop = drop * q
                    if st_val == "отримано":
                        mrg = t_cod - t_drop
                    elif st_val == "відмова":
                        mrg = -v_return_fee if v_track_returns else 0.0
                    else:
                        mrg = 0.0

                    exp_data.append({
                        "Дата заказа": o_date,
                        "ТТН": ttn,
                        "Адрес / Город": addr,
                        "Клиент": c_name,
                        "Телефон": ph,
                        "Код товара": code,
                        "Количество": q,
                        "Наложка за 1 шт": cod,
                        "Сумма наложки": t_cod,
                        "Дроп цена за 1 шт": drop,
                        "Себестоимость": t_drop,
                        "Маржа": mrg,
                        "Статус": st_val
                    })
                df_exp = pd.DataFrame(exp_data)
                csv_bytes = df_exp.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig')
                st.download_button(
                    label=f"📥 Скачать CSV ({v_name})",
                    data=csv_bytes,
                    file_name=f"shipments_{v_name}_{date.today()}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            else:
                st.caption("Нет данных для экспорта.")

            st.markdown("---")
            st.markdown("**Импорт:** Загрузить ТТН из файла (CSV или XLSX)")
            uploaded_file = st.file_uploader("Выберите файл для импорта:", type=["csv", "xlsx"])
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        imp_df = pd.read_csv(uploaded_file)
                    else:
                        imp_df = pd.read_excel(uploaded_file)

                    st.dataframe(imp_df.head(3), use_container_width=True)
                    
                    if st.button("🚀 Импортировать в базу", type="primary"):
                        count_added = 0
                        for _, row in imp_df.iterrows():
                            # Автоматическое определение колонок
                            i_date = str(row.get("Дата заказа", row.get("Дата", date.today())))
                            i_ttn = str(row.get("ТТН", row.get("ttn", "")))
                            i_addr = str(row.get("Адрес / Город", row.get("Адрес", row.get("Address", ""))))
                            i_client = str(row.get("Клиент", row.get("Client", "")))
                            i_phone = str(row.get("Телефон", row.get("Phone", "")))
                            i_code = str(row.get("Код товара", row.get("Код", "2101")))
                            i_cod = float(row.get("Наложка за 1 шт", row.get("Наложка", 0.0)))
                            i_qty = int(row.get("Количество", row.get("Кол-во", 1)))
                            i_drop = float(row.get("Дроп цена за 1 шт", row.get("Дроп", 0.0)))
                            i_status = str(row.get("Статус", "новий")).lower()

                            if i_ttn and i_ttn != "nan":
                                add_shipment_db(v_id, i_date, i_ttn, i_addr, i_client, i_phone, i_code, i_cod, i_qty, i_drop, i_status)
                                count_added += 1
                        
                        st.success(f"Успешно импортировано {count_added} записей!")
                        st.rerun()
                except Exception as e:
                    st.error(f"Ошибка при импорте файла: {e}")

    st.markdown("---")

    # --- ПОЛУЧЕНИЕ И РАСЧЕТ ОТПРАВОК ---
    raw_shipments = get_shipments_by_vendor(v_id)
    
    total_delivered_margin = 0.0
    total_refusal_loss = 0.0
    count_delivered = 0
    count_refused = 0
    count_in_transit = 0

    shipment_rows = []
    for s in raw_shipments:
        s_id, order_date, ttn, address, client_name, phone, item_code, cod_price, qty, drop_price, status = s
        
        total_cod = qty * cod_price
        total_drop = qty * drop_price
        
        # Расчет маржи в зависимости от статуса и настроек поставщика
        if status == "отримано":
            margin = total_cod - total_drop
            total_delivered_margin += margin
            count_delivered += 1
        elif status == "відмова":
            margin = -v_return_fee if v_track_returns else 0.0
            total_refusal_loss += abs(margin)
            count_refused += 1
        else:
            margin = 0.0
            count_in_transit += 1

        shipment_rows.append({
            "id": s_id,
            "order_date": order_date,
            "ttn": ttn,
            "address": address,
            "client_name": client_name,
            "phone": phone,
            "item_code": item_code,
            "cod_price": cod_price,
            "qty": qty,
            "total_cod": total_cod,
            "drop_price": drop_price,
            "total_drop": total_drop,
            "margin": margin,
            "status": status
        })

    net_final_margin = total_delivered_margin - total_refusal_loss

    # --- СВОДНЫЕ КАРТОЧКИ БАЛАНСА ---
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric("Чистая маржа к выплате", f"{net_final_margin:,.2f} грн")
    with m_col2:
        st.metric("Успешно забрано (Отримано)", f"{total_delivered_margin:,.2f} грн", f"{count_delivered} ТТН")
    with m_col3:
        st.metric("Убыток от отказов", f"-{total_refusal_loss:,.2f} грн", f"{count_refused} отказов", delta_color="inverse")
    with m_col4:
        st.metric("В процессе / В дороге", f"{count_in_transit} ТТН")

    if v_card:
        st.caption(f"💳 **Реквизиты для перевода / сверки с {v_name}:** `{v_card}`")

    st.markdown("---")

    # --- ФОРМА ДОБАВЛЕНИЯ НОВОЙ ОТПРАВКИ ---
    with st.expander("➕ Добавить новую отправку (ТТН)", expanded=False):
        with st.form("add_shipment_form", clear_on_submit=True):
            f_col1, f_col2, f_col3, f_col4 = st.columns(4)
            with f_col1:
                in_date = st.date_input("Дата заказа:", value=date.today())
                in_ttn = st.text_input("№ ТТН:")
                in_address = st.text_input("Город / Адрес:")
            with f_col2:
                in_client = st.text_input("ФИО Клиента:")
                in_phone = st.text_input("№ Телефона:")
                in_code = st.text_input("Код / Артикул товара:", value="2101")
            with f_col3:
                in_cod = st.number_input("Наложка за 1 шт (грн):", value=550.0, step=10.0)
                in_qty = st.number_input("Количество (шт):", min_value=1, value=1)
                in_drop = st.number_input("Дроп-цена за 1 шт (грн):", value=185.0, step=10.0)
            with f_col4:
                in_status = st.selectbox("Статус отправки:", ["в дорозі", "отримано", "відмова", "новий"])
                st.write("")
                st.write("")
                btn_add_order = st.form_submit_button("Сохранить отправку", type="primary", use_container_width=True)

            if btn_add_order:
                if in_ttn:
                    add_shipment_db(v_id, in_date, in_ttn, in_address, in_client, in_phone, in_code, in_cod, in_qty, in_drop, in_status)
                    st.success("Отправка успешно сохранена в базу!")
                    st.rerun()
                else:
                    st.warning("Укажите номер ТТН!")

    # --- ТАБЛИЦА УЧЕТА И ИЗМЕНЕНИЯ СТАТУСОВ ---
    if not shipment_rows:
        st.info("Пока нет зафиксированных отправок для этого поставщика. Нажмите **'➕ Добавить новую отправку'** выше.")
    else:
        st.markdown("### 📋 Реестр отправок")
        
        status_options = ["в дорозі", "отримано", "відмова", "новий"]
        
        # Шапка таблицы
        h_c1, h_c2, h_c3, h_c4, h_c5, h_c6, h_c7, h_c8, h_c9 = st.columns([1, 1.3, 1.8, 1.2, 1, 1, 1, 1.3, 0.5])
        h_c1.caption("**Дата**")
        h_c2.caption("**ТТН**")
        h_c3.caption("**Клиент**")
        h_c4.caption("**Код**")
        h_c5.caption("**Наложка**")
        h_c6.caption("**Дроп**")
        h_c7.caption("**Маржа**")
        h_c8.caption("**Статус**")
        h_c9.caption("**Уд.**")

        st.markdown("---")

        for row in shipment_rows:
            r_c1, r_c2, r_c3, r_c4, r_c5, r_c6, r_c7, r_c8, r_c9 = st.columns([1, 1.3, 1.8, 1.2, 1, 1, 1, 1.3, 0.5])
            
            r_c1.write(f"{row['order_date']}")
            r_c2.write(f"**{row['ttn']}**")
            r_c3.write(f"{row['client_name']}\n`{row['phone']}`")
            r_c4.write(f"{row['item_code']} (x{row['qty']})")
            r_c5.write(f"{row['total_cod']} грн")
            r_c6.write(f"{row['total_drop']} грн")
            
            # Цветовая индикация маржи
            if row["margin"] > 0:
                r_c7.markdown(f"**<span style='color:green;'>+{row['margin']:,.1f} грн</span>**", unsafe_allow_html=True)
            elif row["margin"] < 0:
                r_c7.markdown(f"**<span style='color:red;'>{row['margin']:,.1f} грн</span>**", unsafe_allow_html=True)
            else:
                r_c7.write("0 грн")

            # Выпадающий список прямого изменения статуса
            cur_idx = status_options.index(row["status"]) if row["status"] in status_options else 0
            new_st = r_c8.selectbox("", status_options, index=cur_idx, key=f"st_sel_{row['id']}", label_visibility="collapsed")
            
            if new_st != row["status"]:
                update_shipment_status_db(row["id"], new_st)
                st.toast(f"Статус ТТН {row['ttn']} изменен на '{new_st}'", icon="🔄")
                st.rerun()

            if r_c9.button("❌", key=f"del_ship_{row['id']}"):
                delete_shipment_db(row["id"])
                st.rerun()
