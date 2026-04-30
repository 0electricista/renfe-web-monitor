from seleniumbase import SB
from .models import TrainRideRecord
import time
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from pathlib import Path


def compra_trenes(train: TrainRideRecord, email: str, password: str, localizador: str, tg_handler=None, chat_id=None) -> tuple[bool, str]:
    BASE_DIR = Path(__file__).resolve().parent.parent
    extension_path = str(BASE_DIR / "assets" / "Buster")
    result = (False, "Error desconocido")

    with SB(
        headless2=True,
        extension_dir=extension_path,
        use_chromium=True,
    ) as sb:
        try:
            # 1. Login en la misma sesión del navegador
            sb.open("https://venta.renfe.com/vol/loginParticular.do")
            sb.type('input[name="userId"]', email)
            sb.type('input[name="password"]', password)
            sb.click('button:contains("Aceptar")')
            sb.click('button:contains("Entrar")')
            # Esperamos a que aparezca o la vista de éxito o la de OTP
            try:
                sb.wait_for_element_visible('iframe[title*="recaptcha"]', timeout=10)
                print("Esperando captcha")
                # 2. Salto al frame usando el selector CSS del título
                sb.switch_to_frame('iframe[title*="recaptcha"]')
                # 3. Espera específica a que Buster inyecte el botón de "solver"
                sb.execute_script("window.scrollTo(0, 500);")
                time.sleep(1)
                sb.execute_script("window.scrollTo(0, 0);")
                # 1. Obtenemos la lista de frames desde el contexto principal
                sb.switch_to_default_content()
                iframes = sb.driver.find_elements(By.TAG_NAME, 'iframe')
                for frame in iframes:
                    time.sleep(1)
                    print("Captcha")
                    try:
                        # Volvemos siempre al inicio antes de probar un nuevo frame
                        sb.switch_to_default_content()
                        sb.driver.switch_to.frame(frame)

                        # Buscamos el contenedor que tiene el Shadow Root
                        shadow_parents = sb.driver.find_elements(By.CLASS_NAME, 'button-holder.help-button-holder')

                        for parent in shadow_parents:
                            if parent.is_displayed():
                                # Usamos ActionChains para hacer un clic físico en el centro del div
                                actions = ActionChains(sb.driver)
                                actions.move_to_element(parent).click().perform()
                                print("Clic realizado en el contenedor del solver.")
                                # Salimos del bucle si ya lo encontramos
                                break
                    except Exception as e:
                        continue

                # Al terminar, vuelve siempre al contenido principal
                sb.switch_to_default_content()
            except Exception as e:
                print("Todo mal", e)
                pass
            try:
                print("Esperando OTP")
                sb.wait_for_element(
                    'span.rf-search-alternative__links-link[title="Compra tu billete"], #idBotonValDispositivo', timeout=40
                )
            except Exception:
                pass # Si da timeout, continuará e intentará con los asserts o is_element_visible

            # Si el botón del OTP está visible, solicitamos código por Telegram
            if sb.is_element_visible("#idBotonValDispositivo"):
                print("Aqui llega")
                if tg_handler and chat_id:
                    otp_code = tg_handler.request_otp(chat_id, timeout=180) # 3 mins para insertar
                    if otp_code:
                        sb.type("#codigoValidaLogin2F", otp_code)
                        sb.click("#idBotonValDispositivo")
                        sb.wait_for_element_visible(
                            'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
                        )
                    else:
                        result = (False, "Se agotó el tiempo de espera (3 min) para recibir el código OTP de Renfe.")
                        return result
                else:
                    result = (False, "Renfe solicita código de verificación OTP, pero no hay Telegram configurado (introduce tu Chat ID en Configuración) para introducilo.")
                    return result
            else:
                sb.wait_for_element_visible(
                    'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
                )

            # 2. Ir a la página de bonos y seleccionar el abono
            sb.open("https://venta.renfe.com/vol/myPassesCard.do")
            sb.js_click(f"a[id^='new{localizador.strip()}']")

            # 3. Seleccionar trayecto (IDA o VUELTA)
            trenes_ida = sb.get_attribute("#journeyStationOriginDescription", "placeholder").split(" - ")
            es_ida = trenes_ida[0] in train.origin.upper()
            if not es_ida:
                sb.click("#journeyStationDestin")

            # 4. Fecha y buscar trenes
            sb.type("#fecha1", train.departure_time.strftime("%d/%m/%Y"))
            sb.click('button:contains("Siguiente")')

            # 5. Seleccionar el tren por hora de salida
            hora_objetivo = train.departure_time.strftime("%H.%M")
            sb.js_click(f"//tr[td[@data-label='Salida' and normalize-space()='{hora_objetivo}']]//button[contains(@class,'btn-purple')]")
            sb.js_click('button:contains("Siguiente")')
            time.sleep(10)

            result = (True, f"Formalización del trayecto {train.origin}-{train.destination} realizada con éxito")
        except Exception as e:
            print(e)
            result = (False, f"No se pudo completar la compra: {e}")

    return result

