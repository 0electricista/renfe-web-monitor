import os
import time
import threading
import asyncio
from datetime import date
from rich.console import Console
from win11toast import toast
from telegram import Bot
from src.cli import main
from src.validators import validate_station


# =================== CONFIGURACIÓN ===================
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icon.png")

# Inicializamos el bot y el event loop de Telegram
loop = asyncio.new_event_loop()
threading.Thread(target=loop.run_forever, daemon=True).start()

# ASCII logo
ascii_art = (
    "\033[95m    ____             ____           ____        __ \n"
    "   / __ \\___  ____  / __/__        / __ )____  / /_\n"
    "  / /_/ / _ \\/ __ \\/ /_/ _ \\______/ __  / __ \\/ __/\n"
    " / _, _/  __/ / / / __/  __/_____/ /_/ / /_/ / /_  \n"
    "/_/ |_|\\___/_/ /_/_/  \\___/     /_____/\\____/\\__/  \n"
    "                                                   \033[0m"
)


# =================== FUNCIONES AUXILIARES ===================

def añadir_estacion(label):
            while True:
                nombre = input(f"Escribe el nombre de la estación de {label}: ")
                valid = validate_station(nombre)
                if valid.is_valid:
                    añadir_favorita = input("¿Quieres añadirla como estación favorita? (S/N): ")
                    if añadir_favorita.lower() == "s":
                        añadir_estacion_favorita(nombre)
                    return nombre
                print(valid.error_message)

def añadir_estacion_favorita(nombre):
    '''
    '''
    try:
        with open("estaciones.txt","a+", encoding='utf-8') as f:
            f.write(nombre+"\n")
    except IOError as e:
        print(f"Error al escribir en el fichero: {e}")

def mostrar_estaciones_favoritas():
    '''
    Muestra las estaciones favoritas del usuario
    '''
    estaciones_favoritas = []
    with open("estaciones.txt","a+", encoding='utf-8') as f:
        f.seek(0)
        for linea in f:
            estaciones_favoritas.append(linea.strip())
    for indice,estacion in enumerate(estaciones_favoritas):
        print(f"[{indice}] {estacion}")
    return estaciones_favoritas

def configurar_telegram():
    """Pide al usuario los datos del bot y los guarda en token.txt."""
    print("🔹 Configurando bot de Telegram...")

    token = input("Introduce el TOKEN del bot: ").strip()
    chat_id = input("Introduce tu CHAT_ID: ").strip()

    with open("token.txt", "w", encoding="utf-8") as f:
        f.write(f"{token}\n{chat_id}\n")

    print("✅ Bot de Telegram configurado correctamente.")
    return token, chat_id


def cargar_token():
    """Carga el token y chat_id desde token.txt o permite configurarlo."""
    if not os.path.exists("token.txt") or os.path.getsize("token.txt") == 0:
        print("⚠️ No tienes configurado el bot de Telegram.")
        opcion = input("¿Deseas configurarlo ahora? (S/N): ").strip().lower()
        if opcion == "s":
            return configurar_telegram()
        else:
            with open("token.txt", "w", encoding="utf-8") as f:
                f.write("N\n")
            print("🔕 Bot de Telegram desactivado.")
            print("Si deseas configurarlo más tarde, borra el archivo token.txt")
            time.sleep(5)
            return None, None

    # Leer token existente
    with open("token.txt", "r", encoding="utf-8") as f:
        lineas = [line.strip() for line in f.readlines() if line.strip()]

    if not lineas or lineas[0] == "N":
        print("🔕 Bot de Telegram desactivado.")
        return None, None

    if len(lineas) >= 2:
        token, chat_id = lineas[0], lineas[1]
        print("✅ Bot de Telegram cargado correctamente.")
        return token, chat_id

    # Si el archivo está corrupto o incompleto
    print("⚠️ Archivo token.txt inválido. Reconfigurando...")
    return configurar_telegram()



def notificar_windows(titulo, cuerpo):
    """Muestra una notificación en Windows sin bloquear."""
    def _notify():
        try:
            toast(title=titulo, body=cuerpo, icon=ICON_PATH, duration="short")
        except Exception as e:
            print(f"Error toast: {e}")

    threading.Thread(target=_notify, daemon=True).start()


def enviar_telegram(mensaje: str):
    """Envía un mensaje por Telegram en segundo plano."""
    async def _enviar():
        try:
            await bot.send_message(chat_id=CHAT_ID, text=mensaje)
        except Exception as e:
            print(f"Error Telegram: {e}")

    asyncio.run_coroutine_threadsafe(_enviar(), loop)


def elegir_estacion(label):
    """Selecciona una estación con validación."""
    os.system('cls')
    print(f"\n{ascii_art}\n")
    estaciones_favoritas = mostrar_estaciones_favoritas()
    if not estaciones_favoritas:
        print("No tienes estaciones favoritas añadidas")
        return añadir_estacion(label)
    else:
        print(f"[{len(estaciones_favoritas)}] Elegir otra estación")
        seleccion = int(input(f"Elige la estación de {label} de entre las favoritas (número): "))
        if seleccion == len(estaciones_favoritas):
           return añadir_estacion(label)
        else:
            return estaciones_favoritas[seleccion]
              
           


def buscar_y_mostrar_trayecto(ciudad, destino, fecha, mes, hora, minutos, seen, trayecto_label):
    """Ejecuta la búsqueda, imprime la salida y lanza una notificación si hay novedades."""
    print(f"\033[31m{trayecto_label}\033[0m")

    consola = Console(record=True)
    with consola.capture() as captura:
        trains = main(
            origin=ciudad,
            destination=destino,
            departure_date=f"{mes}/{fecha}/{date.today().year}",
            from_time=f"{hora}:{minutos}",
            console=consola,
        )

    texto = captura.get()
    print(texto)

    if not trains:
        return

    # Filtrar solo trenes disponibles (igual que en CLI)
    trenes_dispo = [
        f"🚆 {t.train_type} | {t.departure_time.strftime('%H:%M')} → {t.arrival_time.strftime('%H:%M')} | {t.duration / 60:.1f}h | {t.price:.2f}€"
        for t in trains if t.available
    ]

    if not trenes_dispo:
        return

    nuevos = "\n".join(trenes_dispo)

    # Si hay nuevos resultados (por texto completo)
    if texto.strip() and texto not in seen:
        seen[0] = texto

        notificar_windows("RenfeBot", f"Nueva actualización en el trayecto {ciudad}-{destino}")
        if TOKEN is not None:
            mensaje = f"🚄 Nuevos trenes {ciudad}-{destino}:\n{nuevos}"
            enviar_telegram(mensaje)



# =================== LÓGICA PRINCIPAL ===================
def main_loop():
    os.system("cls")
        
    ciudad = elegir_estacion("salida")
    destino = elegir_estacion("destino")

    os.system("cls")
    print(ascii_art)
    print(f"\nTrayecto {ciudad} - {destino}")

    fecha = input("Día salida: ")
    mes_ida = input("Mes salida: ")
    hora_salida = input("Hora salida (horas): ")
    minutos_salida = input("Minutos salida: ")

    iv = input("¿Deseas buscar ida y vuelta? (S/N): ").lower()

    if iv == 's':
        os.system("cls")
        print(ascii_art)
        print(f"Trayecto {destino} - {ciudad}")
        ciudad_vuelta = destino
        destino_vuelta = ciudad
        fecha_vuelta = input("Día vuelta: ")
        mes_vuelta = input("Mes vuelta: ")
        hora_salida_vuelta = input("Hora salida (horas): ")
        minutos_vuelta = input("Minutos salida: ")

    os.system("cls")
    print(ascii_art)

    while True:
        try:
            actualizar = float(input("Actualizar el buscador de trenes cada (segundos): "))
            break
        except ValueError:
            print("Valor no válido")

    # Sets para almacenar resultados ya vistos
    seen = [0]
    seen_vuelta = [0]

    console = Console()

    while True:
        try:
            console.clear()
            print(ascii_art, "\n")

            buscar_y_mostrar_trayecto(ciudad, destino, fecha, mes_ida, hora_salida, minutos_salida, seen, "TRAYECTO IDA")

            if iv == "s":
                buscar_y_mostrar_trayecto(
                    ciudad_vuelta,
                    destino_vuelta,
                    fecha_vuelta,
                    mes_vuelta,
                    hora_salida_vuelta,
                    minutos_vuelta,
                    seen_vuelta,
                    "TRAYECTO VUELTA",
                )

            time.sleep(actualizar)

        except KeyboardInterrupt:
            print("\n\033[93mBúsqueda interrumpida por el usuario.\033[0m")
            break

        except Exception as e:
            print(f"\033[91mError: {e}\033[0m")
            time.sleep(5)


# =================== EJECUCIÓN ===================

if __name__ == "__main__":
    TOKEN,CHAT_ID = cargar_token()
    if TOKEN is not None:
        bot = Bot(token=TOKEN)          
    main_loop()
