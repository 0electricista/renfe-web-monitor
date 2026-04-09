"""Módulo de gestión del bot de Telegram para Renfe Web Monitor.

Responsabilidades:
- Enviar ofertas de compra con botones inline al usuario.
- Manejar las respuestas del usuario (comprar / pasar).
- Gestionar una cola thread-safe de compras pendientes.
- Controlar timeouts de ofertas (5 minutos).
- Garantizar que solo haya una compra activa a la vez.
"""

import queue
import threading
import time
from datetime import datetime, timedelta

import telebot
from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.models import TrainRideRecord

OFFER_TIMEOUT = timedelta(minutes=5)


class TelegramHandler:
    """Gestiona la comunicación bidireccional con Telegram para ofertas de autocompra."""

    def __init__(self, token: str):
        self.bot = telebot.TeleBot(token)

        self._purchase_queue = queue.Queue()

        # Ofertas activas: callback_id -> {train_id, chat_id, train, label, timestamp}
        self._active_offers = {}

        # Mapeo train_id <-> callback_id (callback_data de Telegram tiene límite de 64 bytes)
        self._train_to_callback = {}
        self._next_callback_id = 0

        # Solo una compra activa a la vez (protección de bono)
        self._compra_en_proceso = False

        self._lock = threading.Lock()
        
        # Cola para esperar por OTPs
        self._waiting_for_otp = {}

        self._register_handlers()
        self._start_polling()
        self._start_purchase_worker()

    # ─── Handlers del bot ───────────────────────────────────────────

    def _register_handlers(self):
        @self.bot.message_handler(commands=["id", "start"])
        def cmd_id(message):
            self.bot.reply_to(message, f"{message.chat.id}")

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("buy_"))
        def handle_buy(call):
            self._on_buy(call, call.data[4:])

        @self.bot.callback_query_handler(func=lambda call: call.data.startswith("skip_"))
        def handle_skip(call):
            self._on_skip(call, call.data[5:])

        @self.bot.message_handler(func=lambda message: True, content_types=['text'])
        def handle_text(message):
            chat_id = str(message.chat.id)
            text = message.text.strip()
            
            if chat_id in self._waiting_for_otp:
                # Comprobar que el text es de 6 dígitos (condición habitual de OTP)
                if len(text) == 6 and text.isdigit():
                    self._waiting_for_otp[chat_id].put(text)
                    self.bot.reply_to(message, "✅ Código recibido. Intentando validar...")
                else:
                    self.bot.reply_to(message, "⚠️ El código debe ser de 6 dígitos. Inténtalo de nuevo:")

    def _on_buy(self, call, callback_id):
        with self._lock:
            offer = self._active_offers.get(callback_id)

            if not offer:
                self.bot.answer_callback_query(call.id, "⏰ Oferta no disponible")
                return

            if datetime.now() - offer["timestamp"] > OFFER_TIMEOUT:
                self._remove_offer(callback_id)
                self.bot.answer_callback_query(call.id, "⏰ Oferta expirada (5 min)")
                return

            if self._compra_en_proceso:
                self.bot.answer_callback_query(
                    call.id, "⚠️ Ya hay una compra en proceso. Espera."
                )
                return

            # Encolar compra
            self._compra_en_proceso = True
            train = offer["train"]
            self._purchase_queue.put({
                "train_id": offer["train_id"],
                "train": train,
                "chat_id": str(offer["chat_id"]),
                "email": offer.get("email"),
                "password": offer.get("password"),
                "localizador": offer.get("localizador"),
            })
            self._remove_offer(callback_id)

        # Feedback al usuario (fuera del lock)
        self.bot.answer_callback_query(call.id, "✅ Compra iniciada")
        self._remove_inline_keyboard(call)
        self.bot.send_message(
            call.message.chat.id,
            f"⏳ Procesando compra del tren de las {train.departure_time.strftime('%H:%M')}...",
        )

    def _on_skip(self, call, callback_id):
        with self._lock:
            self._remove_offer(callback_id)

        self.bot.answer_callback_query(call.id, "👍 Descartado")
        self._remove_inline_keyboard(call)
        self.bot.send_message(
            call.message.chat.id,
            "❌ Descartado. Se te ofrecerá de nuevo si sigue disponible.",
        )

    # ─── API Pública ────────────────────────────────────────────────

    def enviar_oferta(self, chat_id: str, train_id: str, train: TrainRideRecord, label: str, email: str = None, password: str = None, localizador: str = None):
        """Envía oferta de compra con botones inline. No duplica ofertas activas."""
        with self._lock:
            if train_id in self._train_to_callback:
                existing_cb = self._train_to_callback[train_id]
                existing = self._active_offers.get(existing_cb)
                if existing and datetime.now() - existing["timestamp"] < OFFER_TIMEOUT:
                    return  # Oferta aún activa
                self._remove_offer(existing_cb)

            cb_id = str(self._next_callback_id)
            self._next_callback_id += 1

            self._active_offers[cb_id] = {
                "train_id": train_id,
                "chat_id": chat_id,
                "train": train,
                "label": label,
                "timestamp": datetime.now(),
                "email": email,
                "password": password,
                "localizador": localizador
            }
            self._train_to_callback[train_id] = cb_id

        keyboard = InlineKeyboardMarkup()
        keyboard.row(
            InlineKeyboardButton("🛒 Comprar", callback_data=f"buy_{cb_id}"),
            InlineKeyboardButton("❌ Pasar", callback_data=f"skip_{cb_id}"),
        )

        msg = (
            f"🚨 <b>¡Tren disponible!</b>\n\n"
            f"🚆 <b>{label}</b> | {train.train_type}\n"
            f"📍 {train.origin} → {train.destination}\n"
            f"🕒 {train.departure_time.strftime('%H:%M')} → {train.arrival_time.strftime('%H:%M')}\n"
            f"💰 {train.price:.2f}€\n\n"
            f"⏰ Oferta válida durante 5 minutos."
        )

        try:
            self.bot.send_message(chat_id, msg, parse_mode="HTML", reply_markup=keyboard)
        except Exception as e:
            print(f"⚠️ Error enviando oferta Telegram: {e}")

    def tiene_oferta_activa(self, train_id: str) -> bool:
        """True si el tren tiene una oferta activa no expirada."""
        with self._lock:
            cb_id = self._train_to_callback.get(train_id)
            if cb_id is None:
                return False
            offer = self._active_offers.get(cb_id)
            if offer is None:
                return False
            if datetime.now() - offer["timestamp"] > OFFER_TIMEOUT:
                self._remove_offer(cb_id)
                return False
            return True



    def completar_compra(self):
        """Marca la compra activa como completada, permitiendo nuevas compras."""
        with self._lock:
            self._compra_en_proceso = False

    def enviar_mensaje(self, chat_id: str, mensaje: str) -> bool:
        """Envía un mensaje de texto plano al usuario."""
        try:
            self.bot.send_message(chat_id, mensaje, parse_mode="HTML")
            return True
        except Exception:
            return False

    def request_otp(self, chat_id: str, timeout: int = 180) -> str | None:
        """Solicita el código OTP al usuario por Telegram y bloquea la ejecución hasta recibirlo o agotar el tiempo."""
        self.enviar_mensaje(
            chat_id, 
            "🔐 <b>Se requiere código de verificación (OTP)</b> para iniciar sesión en Renfe.\n\nPor favor, escribe el código de 6 dígitos que has recibido en tu móvil o correo:"
        )
        self._waiting_for_otp[chat_id] = queue.Queue()
        try:
            return self._waiting_for_otp[chat_id].get(timeout=timeout)
        except queue.Empty:
            return None
        finally:
            self._waiting_for_otp.pop(chat_id, None)

    def limpiar_ofertas_expiradas(self):
        """Elimina ofertas que hayan superado el timeout de 5 minutos."""
        with self._lock:
            expired = [
                cb_id for cb_id, offer in self._active_offers.items()
                if datetime.now() - offer["timestamp"] > OFFER_TIMEOUT
            ]
            for cb_id in expired:
                self._remove_offer(cb_id)

    # ─── Utilidades internas ────────────────────────────────────────

    def _remove_offer(self, callback_id: str):
        """Elimina una oferta (llamar con self._lock adquirido)."""
        offer = self._active_offers.pop(callback_id, None)
        if offer:
            self._train_to_callback.pop(offer["train_id"], None)

    def _remove_inline_keyboard(self, call):
        """Elimina los botones inline del mensaje original."""
        try:
            self.bot.edit_message_reply_markup(
                call.message.chat.id, call.message.message_id, reply_markup=None
            )
        except Exception:
            pass

    def _start_polling(self):
        """Arranca el polling del bot en un hilo daemon.

        Si otra instancia ya está haciendo polling (error 409), esta instancia
        espera con backoff largo y reintenta. Todas las instancias pueden ENVIAR
        mensajes; solo una puede recibir callbacks de botones inline.
        """
        def _loop():
            while True:
                try:
                    self.bot.infinity_polling(timeout=20, long_polling_timeout=20)
                except Exception as e:
                    error_msg = str(e)
                    if "409" in error_msg or "Conflict" in error_msg:
                        # Otra instancia está haciendo polling — esperar más tiempo
                        time.sleep(30)
                    else:
                        print(f"⚠️ Error en el bot (reintentando en 5s): {e}")
                        time.sleep(5)

        threading.Thread(target=_loop, daemon=True).start()

    def _start_purchase_worker(self):
        """Arranca el hilo en segundo plano que procesa las compras independiente de Streamlit."""
        def worker():
            from src import autopay
            while True:
                compra = self._purchase_queue.get()  # Bloqueante
                chat_id = compra["chat_id"]
                train = compra["train"]
                email = compra["email"]
                password = compra["password"]
                localizador = compra["localizador"]

                if not email or not password:
                    self.enviar_mensaje(chat_id, "❌ No hay credenciales configuradas. Inicia sesión en la web primero.")
                    self.completar_compra()
                    continue
                if not localizador:
                    self.enviar_mensaje(chat_id, "❌ No hay localizador de abono configurado.")
                    self.completar_compra()
                    continue

                try:
                    exito, mensaje = autopay.compra_trenes(train, email, password, localizador, self, chat_id)
                    emoji = "✅" if exito else "❌"
                    self.enviar_mensaje(chat_id, f"{emoji} {mensaje}")
                except Exception as e:
                    self.enviar_mensaje(chat_id, f"❌ Error en la compra: {e}")
                finally:
                    self.completar_compra()

        threading.Thread(target=worker, daemon=True).start()
