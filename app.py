"""
Renfe Web Monitor — Aplicación principal (Streamlit).

Monitoriza la disponibilidad de trenes en Renfe y permite la autocompra
de billetes mediante un bot de Telegram con interacción por botones inline.
"""
import json
import math
import time
from datetime import datetime, time as dt_time, timedelta

import pandas as pd
import pytz
import streamlit as st
import extra_streamlit_components as stx

from src.models import TrainRideRecord
from src.scraper import Scraper
from src.models import StationRecord
from src.telegram_handler import TelegramHandler
from src import autopay


# ================================================================
#  CONSTANTES
# ================================================================

SPAIN_TZ = pytz.timezone("Europe/Madrid")
TOKEN = st.secrets["TELEGRAM_TOKEN"]


# ================================================================
#  CONFIGURACIÓN DE PÁGINA
# ================================================================

st.set_page_config(page_title="Renfe Web Monitor", page_icon="🚆", layout="wide")
cookie_manager = stx.CookieManager(key="renfebot_cookies")


# ================================================================
#  INICIALIZACIÓN DEL BOT DE TELEGRAM (singleton via cache)
# ================================================================

@st.cache_resource
def _init_telegram():
    return TelegramHandler(TOKEN)

tg_handler = _init_telegram()


# ================================================================
#  FUNCIONES AUXILIARES
# ================================================================

@st.cache_data
def load_stations() -> dict:
    """Carga el diccionario nombre → código de estaciones desde el JSON."""
    try:
        with open("assets/stations.json", "r", encoding="utf-8") as f:
            return {name: info["cdgoEstacion"] for name, info in json.load(f).items()}
    except Exception:
        return {}


def get_train_id(train: TrainRideRecord) -> str:
    """Genera un ID único para un tren: 'HH:MM-TIPO-ORIGEN-DESTINO'."""
    return (
        f"{train.departure_time.strftime('%H:%M')}-{train.train_type}"
        f"-{train.origin}-{train.destination}"
    )


def trigger_browser_notification(title: str, body: str):
    """Lanza una notificación del navegador vía JavaScript."""
    js = f"""
    <script>
        (function() {{
            if (Notification.permission !== "granted") Notification.requestPermission();
            new Notification("{title}", {{ body: "{body}"}});
        }})();
    </script>
    """
    st.html(js, unsafe_allow_javascript=True)


def request_notification_perms():
    """Solicita permisos de notificación del navegador."""
    st.html(
        '<script>if(Notification.permission==="default")Notification.requestPermission();</script>',
        unsafe_allow_javascript=True
    )


def invertir_estaciones():
    """Intercambia origen y destino y reinicia la búsqueda."""
    st.empty()
    st.session_state["searching"] = True
    st.session_state["first_run"] = True
    st.session_state["known"] = set()
    st.session_state["selected_trains"] = set()
    st.session_state["origin"], st.session_state["dest"] = (
        st.session_state.get("dest"),
        st.session_state.get("origin"),
    )


# ================================================================
#  DIÁLOGOS
# ================================================================

@st.dialog("🤖 Guía de Configuración Telegram")
def mostrar_ayuda_telegram():
    st.markdown("""
    1. Accede al bot [@RenfeWebMonitorBot](https://t.me/RenfeWebMonitor_bot).  
    2. Haz clic en "Iniciar" o envía `/start`.  
    3. El bot te responderá con tu **Chat ID**.  
    4. Copia ese número y pégalo en el campo "Chat ID".  
    5. Guarda y prueba la conexión.  
    """)


# ================================================================
#  RENDERIZADO DE TABLAS DE TRENES
# ================================================================

def render_train_table(
    trains: list,
    header: str,
    origin_name: str,
    selectable: bool = False,
    show_direction: bool = False,
):
    """
    Renderiza una tabla de trenes.

    Args:
        trains: Lista de TrainRideRecord.
        header: Título de la sección ("Ida", "Vuelta", etc.).
        origin_name: Estación de origen (para determinar IDA/VUELTA).
        selectable: Si True, muestra checkboxes "Monitorizar".
        show_direction: Si True, muestra columna "Trayecto".
    """
    col_txt, col_btn = st.columns([0.8, 0.2])
    with col_txt:
        st.subheader(f"{header} ({len(trains)})")
    with col_btn:
        st.write("")
        st.link_button("🛒 Ir a Renfe", "https://venta.renfe.com/vol/home.do", width="stretch")

    if not trains:
        st.info("No hay trenes disponibles.")
        return

    # Preparar filas
    rows = []
    for t in trains:
        is_out = t.origin.upper() == origin_name.upper()
        tid = f"{get_train_id(t)}_{'I' if is_out else 'V'}"
        row = {
            "Salida": t.departure_time.strftime("%H:%M"),
            "Llegada": t.arrival_time.strftime("%H:%M"),
            "Precio": t.price,
            "Tipo": t.train_type,
        }
        if show_direction:
            row["Trayecto"] = "IDA" if is_out else "VUELTA"
        if selectable:
            row["Monitorizar"] = tid in st.session_state.get("selected_trains", set())
            row["_id_interno"] = tid
        rows.append(row)

    df = pd.DataFrame(rows)

    if selectable:
        _render_selectable_table(df, header, show_direction)
    else:
        st.dataframe(df, width="stretch", hide_index=True)


def _render_selectable_table(df: pd.DataFrame, header: str, show_direction: bool):
    """Tabla editable con checkboxes de monitorización dentro de un formulario."""
    with st.form(key=f"form_{header}"):
        disabled_cols = ["Salida", "Llegada", "Precio", "Tipo"]
        if show_direction:
            disabled_cols.append("Trayecto")

        edited_df = st.data_editor(
            df,
            column_config={
                "Monitorizar": st.column_config.CheckboxColumn(
                    "Monitorizar", default=False, width="small"
                ),
                "_id_interno": None,
            },
            disabled=disabled_cols,
            hide_index=True,
            key=f"editor_{header}",
            width="stretch",
        )

        if st.form_submit_button("💾 Guardar Selección"):
            selected = set(edited_df[edited_df["Monitorizar"] == True]["_id_interno"])
            all_ids = set(edited_df["_id_interno"])

            if "selected_trains" not in st.session_state:
                st.session_state["selected_trains"] = set()

            st.session_state["selected_trains"].difference_update(all_ids)
            st.session_state["selected_trains"].update(selected)
            st.success("¡Selección actualizada!")


# ================================================================
#  PROCESAMIENTO DE COMPRAS PENDIENTES
# ================================================================

def process_pending_purchases():
    """Consume la cola de compras del TelegramHandler y lanza autopay."""
    compras = tg_handler.obtener_compras_pendientes()

    for compra in compras:
        chat_id = compra["chat_id"]
        train = compra["train"]

        tg_handler.enviar_mensaje(
            chat_id,
            f"🔄 Iniciando compra del tren de las {train.departure_time.strftime('%H:%M')}...",
        )

        try:
            email = cookie_manager.get("email")
            password = cookie_manager.get("password")
            if not email or not password:
                tg_handler.enviar_mensaje(
                    chat_id,
                    "❌ No hay credenciales configuradas. Inicia sesión en la web primero.",
                )
                continue

            localizador = st.session_state.get("localizador", "") or cookie_manager.get("local") or ""
            if not localizador:
                tg_handler.enviar_mensaje(
                    chat_id,
                    "❌ No hay localizador de abono configurado.",
                )
                continue

            exito, mensaje = autopay.compra_trenes(train, email, password, localizador)
            emoji = "✅" if exito else "❌"
            tg_handler.enviar_mensaje(chat_id, f"{emoji} {mensaje}")

        except Exception as e:
            tg_handler.enviar_mensaje(chat_id, f"❌ Error en la compra: {e}")

        finally:
            tg_handler.completar_compra()


# ================================================================
#  CARGA DE DATOS
# ================================================================

stations_map = load_stations()
station_names = sorted(stations_map.keys())
cookie_chat_id = cookie_manager.get(cookie="tg_chat_id")


# ================================================================
#  SIDEBAR
# ================================================================

with st.sidebar:
    st.header("⚙️ Configuración")
    request_notification_perms()

    # ── Telegram ──
    st.subheader("🤖 Telegram (opcional)")

    default_chat = cookie_chat_id if cookie_chat_id else ""

    with st.expander("Configurar Credenciales", expanded=not default_chat):
        tg_chat_id = st.text_input("Chat ID", value=default_chat)

        c1, c2 = st.columns(2)
        if c1.button("💾 Guardar Chat ID"):
            cookie_manager.set(
                "tg_chat_id", tg_chat_id,
                expires_at=datetime.now(SPAIN_TZ) + timedelta(days=30),
                key="set_chat",
            )
            st.success("Guardado.")
            time.sleep(1)
            st.rerun()

        if c2.button("🗑️ Borrar Chat ID"):
            cookie_manager.delete("tg_chat_id", key="delete_chat")
            st.success("Borradas.")
            time.sleep(1)
            st.rerun()

        if c1.button("🔔 Probar Conexión"):
            if tg_handler.enviar_mensaje(tg_chat_id, "🔔 ¡RenfeBot conectado!"):
                st.toast("Conexión correcta", icon="✅")
            else:
                st.error("Error. Revisa ID.")

        if c2.button("📩 Obtener Chat ID"):
            mostrar_ayuda_telegram()

    st.divider()

    # ── Estaciones ──
    origin_name = st.selectbox(
        "📍 Origen", station_names, index=None, placeholder="Origen", key="origin"
    )
    dest_options = [s for s in station_names if s != origin_name]
    dest_name = st.selectbox(
        "🏁 Destino", dest_options, index=None, placeholder="Destino", key="dest"
    )
    st.button("Invertir", on_click=invertir_estaciones, width="stretch")

    st.divider()

    # ── Fechas y horarios ──
    trip_type = st.radio("Tipo", ["Solo Ida", "Ida y Vuelta"], horizontal=True)
    d1, d2 = st.columns(2)
    dept_date = d1.date_input("Fecha Ida", datetime.today(), min_value=datetime.today())
    min_time_out = d1.time_input("Hora Ida", dt_time(6, 0))

    ret_date, min_time_ret = None, dt_time(0, 0)
    if trip_type == "Ida y Vuelta":
        ret_date = d2.date_input("Fecha Vuelta", dept_date, min_value=dept_date)
        min_time_ret = d2.time_input("Hora Vuelta", dt_time(16, 0))

    st.divider()

    # ── Controles de búsqueda ──
    desactivar = st.checkbox("❌ Desactivar la búsqueda automática")
    refresh_rate = (
        st.number_input("Refresca cada (s)", 5, 60, 30) if not desactivar else 1
    )

    if st.button("🔎 BUSCAR", type="primary", width="stretch"):
        st.empty()
        st.session_state["searching"] = True
        st.session_state["first_run"] = True
        st.session_state["known"] = set()
        st.session_state["selected_trains"] = set()
        st.rerun()

    if st.button("⏹️ PARAR"):
        st.session_state["searching"] = False
        st.rerun()


# ================================================================
#  PANTALLA PRINCIPAL
# ================================================================

st.title("🚆 Renfe Web Monitor")

# ── Página de inicio (sin búsqueda activa) ──
if not st.session_state.get("searching"):
    with st.expander("ℹ️ ¿Qué es Renfe Web Monitor?", expanded=True):
        st.markdown("""
        **Renfe Web Monitor** monitorea la disponibilidad de billetes de tren.
        Detecta cuando alguien cancela y el billete vuelve a estar disponible,
        **notificándote inmediatamente** vía navegador o Telegram.

        Con la función de **autocompra**, recibes ofertas interactivas en Telegram
        y puedes comprar el billete con un solo clic usando tu bono de Renfe.

        **IMPORTANTE**: La pestaña del navegador debe estar abierta para que funcione.
        """)

    with st.expander("🔍 Funcionalidades", expanded=True):
        st.markdown("""
        1️⃣ Búsquedas automáticas de trayectos sin recargar la página.  
        2️⃣ Monitorización de trenes específicos con opción de autocompra **SOLO CON BONO**.  
        3️⃣ Notificaciones por Telegram con botones para comprar o descartar.  
        """)

    with st.expander("❔ Configuración de Telegram", expanded=not default_chat):
        st.markdown("""
        1. Accede a [@RenfeWebMonitorBot](https://t.me/RenfeWebMonitor_bot).  
        2. Envía `/start` y copia tu **Chat ID**.  
        3. Pégalo en la configuración de la barra lateral.  
        """)

    with st.expander("🛒 Configuración de autocompra", expanded=True):
        st.markdown("Permite la autocompra de billetes mediante bonos de Renfe.")
        default_mail = cookie_manager.get("email")
        default_password = cookie_manager.get("password")
        default_local = cookie_manager.get("local")
        email = st.text_input("Email Renfe", value=default_mail or "")
        password = st.text_input("Contraseña Renfe", type="password", value=default_password or "")
        localizador = st.text_input("Localizador del Abono", value=default_local or "")
        if st.button("Iniciar sesión", width="stretch"):
            st.session_state["localizador"] = localizador
            # Persistir credenciales en cookies del navegador AL FINAL
            # (cookie_manager.set provoca rerun de Streamlit)
            if not cookie_manager.get("email"):
                cookie_manager.set(
                    "email", email,
                    expires_at=datetime.now(SPAIN_TZ) + timedelta(days=30),
                    key="set_email",
                )
                cookie_manager.set(
                    "password", password,
                    expires_at=datetime.now(SPAIN_TZ) + timedelta(days=30),
                    key="set_password",
                )
                cookie_manager.set(
                    "local", localizador,
                    expires_at=datetime.now(SPAIN_TZ) + timedelta(days=30),
                    key="set_localizador",
                )
            if email and password and localizador:
                st.success("Sesión iniciada con éxito")
            else:
                st.error("Faltan datos")


# ── Búsqueda activa ──
if st.session_state.get("searching"):
    if not origin_name or not dest_name:
        st.error("⚠️ Selecciona origen y destino.")
        st.stop()

    origin = StationRecord(name=origin_name, code=stations_map[origin_name])
    dest = StationRecord(name=dest_name, code=stations_map[dest_name])
    departure_dt = datetime.combine(dept_date, min_time_out)
    return_dt = datetime.combine(ret_date, min_time_ret) if ret_date else None

    try:
        with st.spinner(f"Monitorizando... ({refresh_rate}s)"):
            all_trains = Scraper(origin, dest, departure_dt, return_dt).get_trainrides()

        if not all_trains:
            st.warning("⚠️ Sin resultados")
        else:
            # ── Clasificar trenes disponibles ──
            outbound, returning, current_ids = [], [], set()

            for t in all_trains:
                if not t.available:
                    continue

                is_out = t.origin.upper() == origin_name.upper()
                tid = get_train_id(t) + ("_I" if is_out else "_V")
                label = "IDA" if is_out else "VUELTA"

                # Filtrar por hora mínima y tipo de trayecto
                if is_out and t.departure_time.time() >= min_time_out:
                    outbound.append(t)
                elif not is_out and trip_type != "Solo Ida" and t.departure_time.time() >= min_time_ret:
                    returning.append(t)
                else:
                    continue

                current_ids.add(tid)
                is_new = tid not in st.session_state.get("known", set())
                is_monitored = tid in st.session_state.get("selected_trains", set())

                # ── Autocompra: enviar oferta Telegram para trenes monitorizados ──
                if is_monitored and tg_chat_id:
                    if is_new or not tg_handler.tiene_oferta_activa(tid):
                        tg_handler.enviar_oferta(tg_chat_id, tid, t, label)

                # ── Notificación browser para trenes nuevos no monitorizados ──
                elif is_new and not st.session_state.get("first_run"):
                    trigger_browser_notification(
                        "¡Novedades!",
                        f"Tren {label} {t.departure_time.strftime('%H:%M')} ({t.price}€)",
                    )

            # ── Procesar compras pendientes de Telegram ──
            process_pending_purchases()

            # ── Limpiar ofertas expiradas (timeout 5 min) ──
            tg_handler.limpiar_ofertas_expiradas()

            # ── Actualizar estado ──
            st.session_state["known"] = current_ids
            st.session_state["first_run"] = False

            # ── Renderizar tablas ──
            all_priced = [t for t in all_trains if not math.isnan(t.price)]

            if trip_type != "Solo Ida":
                t1, t2, t3 = st.tabs(["IDA", "VUELTA", "HORARIOS"])
                with t1:
                    render_train_table(outbound, "Ida", origin_name)
                with t2:
                    render_train_table(returning, "Vuelta", origin_name)
                with t3:
                    render_train_table(
                        all_priced, "Todos los trenes", origin_name,
                        selectable=True, show_direction=True,
                    )
            else:
                t1, t2 = st.tabs(["IDA", "HORARIOS"])
                with t1:
                    render_train_table(outbound, "Ida", origin_name)
                with t2:
                    render_train_table(
                        all_priced, "Todos los trenes", origin_name,
                        selectable=True, show_direction=True,
                    )

            # ── Timestamp ──
            now_str = datetime.now(SPAIN_TZ).strftime("%H:%M:%S")
            if not desactivar:
                st.caption(f"Actualizado: {now_str}. Próxima en {refresh_rate}s.")
            else:
                st.caption(f"Última actualización: {now_str}.")

    except Exception as e:
        st.error(f"Error: {e}")

    if not desactivar:
        time.sleep(refresh_rate)
        st.rerun()
