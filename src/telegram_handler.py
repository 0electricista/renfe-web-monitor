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

        self._register_handlers()
        self._start_polling()

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

    def enviar_oferta(self, chat_id: str, train_id: str, train: TrainRideRecord, label: str):
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

    def obtener_compras_pendientes(self) -> list:
        """Vacía la cola y devuelve las compras pendientes."""
        compras = []
        while not self._purchase_queue.empty():
            try:
                compras.append(self._purchase_queue.get_nowait())
            except queue.Empty:
                break
        return compras

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
