# renfe-bot


## Descripción

Renfe-bot es un bot de Telegram diseñado para ayudar a los usuarios a comprar
billetes de tren de Renfe, el principal operador ferroviario de España. El bot
monitorea la disponibilidad de billetes, especialmente en situaciones en las que
están agotados y solo se vuelven a estar disponibles cuando alguien cancela su
reserva. Notifica rápidamente a los usuarios cuando hay billetes disponibles
para comprar. El bot ahora admite una interfaz de chatbot de Telegram para una
interacción mejorada con el usuario.

Este fork de Renfe-bot implementa una nueva CLI que se conecta directamente con un bot de Telegram, además
implementa notificaciones en Windows mediante ```win11toast```. Por último, este fork permite guardar
**estaciones favoritas**, para agilizar los procesos de búsqueda.



## Como utilizar el bot

### Opción A: Correrlo normalmente en tu ordenador

#### Requisitos

Las dependencias requeridas para ejecutar este proyecto están incluidas en el
archivo `requirements.txt`. Para instalar los requisitos, usa el siguiente
comando:

```bash
pip install -r requirements.txt
```

#### Instalación

Sigue los siguientes pasos para instalar y configurar el Renfe-bot:

1. Asegúrate de tener Python con versión >= 3.12, si no instálalo desde Google
2. Descarga a partir de releases o clona este repositorio en tu máquina local.
3. Instala las dependencias requeridas utilizando el comando mencionado en la
   sección 'Requisitos'.
4. Ejecuta el bot ejecutándolo (`python repeat.py`) en el directorio raíz
   del proyecto.
5. Cualquier dato requerido, como la clave API, se solicitará cuando ejecutes el
   bot por primera vez.
6. Las estaciones favoritas se guardan. Si quieres borrarla, ve al archivo estaciones.txt y borra el nombre de las estaciones. No dejes un vacío.
7. NO INTRODUZCAS ESTACIONES NUEVAS (a no ser que sepas el nombre exacto de la estación o lo hayas mirado en stations.json)
8. Disfrutalo.

#### Creación bot de Telegram
1. Necesitas una cuenta de Telegram
2. Entra aquí y sigue las instrucciones: https://telegram.me/BotFather. Asegúrate de copiar el token.
3. Luego entra aquí: ```https://api.telegram.org/bot{pega_aqui_tu_token_y_quita_las_llaves}/getUpdates``` pegando tu token donde pone que lo pongas
4. Envíale un mensaje a tu bot en Telegram, y vuelve a la página de antes (api.telegram...).
5. Verás algo parecido a "message":{"message_id":X,"from":{"id":NUMEROSDEID..."
6. Copia el número (sin comillas) que aparezca en id (NUMEROSDEID), y ese es el CHAT_ID



## Uso

Para usar el necesitarás ejecutar `python repeat.py`. Necesitarás
proporcionar datos como las estaciones de origen y destino, y las fechas. El bot
monitoreará la disponibilidad de billetes y te notificará inmediatamente cuando
haya un billete disponible para tu viaje a partir de Telegram o con una notificación en Windows.

## Contribuciones

Este proyecto es de código abierto y las contribuciones son muy bienvenidas. Si
deseas contribuir al proyecto, por favor sigue estos pasos:

1. Haz un fork del repositorio.
2. Crea una nueva rama para tus cambios.
3. Realiza tus cambios.
4. Envía tus cambios a tu fork.
5. Envía una pull request con una descripción de los cambios.

Antes de fusionar, todos los cambios serán probados para asegurar que funcionan
correctamente. Las contribuciones no se limitan a cambios de código; abrir
problemas o proporcionar sugerencias son igualmente valiosos.

## Licencia

Este proyecto está licenciado bajo los términos de la [Licencia
MIT](https://opensource.org/license/mit/).

La Licencia MIT es una licencia permisiva que permite la reutilización de
software dentro del software propietario siempre que todas las copias del
software licenciado incluyan una copia de los términos de la Licencia MIT y el
aviso de derechos de autor.

Esto significa que eres libre de usar, copiar, modificar, fusionar, publicar,
distribuir, sublicenciar y/o vender copias del software, siempre que incluyas la
atribución necesaria y proporciona una copia de la licencia MIT.

Puedes ver el texto completo de la licencia en el archivo LICENSE.
