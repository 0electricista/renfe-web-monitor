# 🚄 Renfe Web Monitor

[![Streamlit App](https://img.shields.io/badge/-Streamlit-FF4B4B?style=flat&logo=streamlit&logoColor=white)](https://renfe-monitor.streamlit.app/)
[![Python](https://img.shields.io/badge/Python-3.12%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**La forma más fácil de encontrar billetes de tren.** Olvídate de refrescar la página de Renfe constantemente. Este monitor busca por ti y te avisa visualmente cuando alguien libera un asiento. 

---

## 🚀 Empezar ahora

No necesitas instalar nada en tu ordenador. Usa la versión web accesible desde cualquier navegador:

> **[👉 HAZ CLICK AQUÍ PARA ABRIR EL MONITOR WEB](https://renfe-monitor.streamlit.app/)**

### ¿Cómo funciona?
1. **Entra al enlace** de arriba.
2. Selecciona tu **Origen**, **Destino** y la **Fecha** del viaje.
3. Deja la pestaña abierta mientras haces otras cosas. El sistema se actualizará solo.

---

## ✨ Características Principales

* **🖥️ Interfaz Visual (Web):** Olvídate de comandos complicados. Una interfaz gráfica limpia y fácil de usar.
* **🔔 Notificaciones Nativas (Windows):** Si usas la versión de escritorio, recibirás avisos directamente en el centro de notificaciones de Windows 10/11.
* **⚡ Búsqueda Rápida:** Filtra trenes por hora de salida.
* **📱 Telegram (Opcional):** Posibilidad de integración con Telegram para recibir alertas en el móvil.

---

## 💻 Ejecución en local

Si prefieres ejecutar el programa en tu propio ordenador para tener **notificaciones nativas de Windows** o mayor control, sigue estos pasos:

### Requisitos Previos
* Tener [Python 3.12](https://www.python.org/downloads/) o superior instalado.

### Instalación

1. Descarga el código fuente: [Descargar ZIP](https://github.com/0electricista/renfe-web-monitor/archive/refs/tags/v1.4.zip) y descomprímelo en un lugar accesible.
2. Abre una terminal en la carpeta descargada y ejecuta:

   ```bash
   pip install -r requirements.txt
   ```
   En Windows puedes utilizar el clic derecho y darle a "Abrir en Terminal".
### Modos de Uso Local

**Opción A: Interfaz Gráfica**  
Ejecuta este comando en la terminal para abrir la versión web en tu propio PC:

```bash
streamlit run app.py
```

**Opción B: Monitor de Fondo (Windows)**  
Si quieres dejarlo corriendo en segundo plano buscando billetes repetidamente y que te avise con una notificación:

```bash
python repeat.py
```

*La primera vez te pedirá los datos de búsqueda y guardará tus estaciones favoritas.*

---

#### 🤖 Creación bot de Telegram (opcional)
1. Necesitas una cuenta de Telegram
2. Entra aquí y sigue las instrucciones: https://telegram.me/BotFather. Asegúrate de copiar el token.
3. Luego entra aquí: ```https://api.telegram.org/bot{pega_aqui_tu_token_y_quita_las_llaves}/getUpdates``` pegando tu token donde pone que lo pongas
4. Envíale un mensaje a tu bot en Telegram, y vuelve a la página de antes (api.telegram...).
5. Verás algo parecido a ```"message":{"message_id":X,"from":{"id":NUMEROSDEID..."```
6. Copia el número (sin comillas) que aparezca en id ```(NUMEROSDEID)```, y ese es el CHAT_ID

  
*La versión web ya incopora un bot para todos, sin embargo, en local, debes crearlo tu y sustituir el valor del TOKEN en ```app.py``` por el tuyo*

---



## 🛠️ CLI Original

Este proyecto mantiene la compatibilidad con la CLI original para su uso en scripts o servidores.

```bash
# Búsqueda puntual
python src/cli.py -o Madrid -d Barcelona --departure_date 01/01/2025
```

**Argumentos extra disponibles:**

* `--from_time HH:MM`: Filtra los resultados para mostrar solo trenes que salen después de una hora específica.

---

## 📄 Créditos y Licencia

Este proyecto es un fork de **Renfe-bot**.

* **Core & Scraping:** [emartinez-dev](https://github.com/emartinez-dev) (Lógica original de scraping y estructura base).
* **Web UI & Windows Notifications:** [0electricista](https://github.com/0electricista) (Implementación de Streamlit, Win11Toast y mejoras visuales).

Este proyecto está bajo la **Licencia MIT**. Eres libre de usarlo, modificarlo y compartirlo.
