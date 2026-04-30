import seleniumbase
from seleniumbase import Driver, SB
from .models import TrainRideRecord
import time
import os
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from pathlib import Path
import stat

def compra_trenes(train: TrainRideRecord, email: str, password: str, localizador: str, tg_handler=None, chat_id=None) -> tuple[bool, str]:
    BASE_DIR = Path(__file__).resolve().parent.parent
    extension_path = str(BASE_DIR / "assets" / "Buster")
    """Inicia sesión y formaliza un viaje con el bono en una misma sesión de navegador."""
    def fix_driver_permissions():
        """Fuerza permisos de ejecución en los drivers descargados por SeleniumBase."""
        driver_dir = os.path.join(os.path.dirname(seleniumbase.__file__), "drivers")
        
        if not os.path.exists(driver_dir):
            return
            
        for driver_file in os.listdir(driver_dir):
            driver_path = os.path.join(driver_dir, driver_file)
            if os.path.isfile(driver_path):
                # Otorga permisos de ejecución (equivalente a chmod +x)
                st = os.stat(driver_path)
                os.chmod(driver_path, st.st_mode | stat.S_IEXEC)

    # Ejecuta esta función ANTES de importar o instanciar el Driver
    fix_driver_permissions()
    driver = Driver(
        headless2=True,
        extension_dir=extension_path,
        uc=True,
        use_chromium=True,
    )
    try:
        # 1. Login en la misma sesión del navegador
        driver.get("https://venta.renfe.com/vol/loginParticular.do")
        driver.type('input[name="userId"]', email)
        driver.type('input[name="password"]', password)
        driver.click('button:contains("Aceptar")')
        driver.click('button:contains("Entrar")')
        # Esperamos a que aparezca o la vista de éxito o la de OTP
        try:
            driver.wait_for_element_visible('iframe[title*="recaptcha"]', timeout=10)
            print("Esperando captcha")
            # 2. Salto al frame usando el selector CSS del título
            driver.switch_to_frame('iframe[title*="recaptcha"]')
            # 3. Espera específica a que Buster inyecte el botón de "solver"
            driver.execute_script("window.scrollTo(0, 500);")
            time.sleep(1)
            driver.execute_script("window.scrollTo(0, 0);")
            # 1. Obtenemos la lista de frames desde el contexto principal
            driver.switch_to.default_content()
            iframes = driver.find_elements(By.TAG_NAME, 'iframe')
            for frame in iframes:
                time.sleep(1)
                print("Captcha")
                try:
                    # Volvemos siempre al inicio antes de probar un nuevo frame
                    driver.switch_to.default_content()
                    driver.switch_to.frame(frame)
                    
                    # Buscamos el contenedor que tiene el Shadow Root
                    shadow_parents = driver.find_elements(By.CLASS_NAME, 'button-holder.help-button-holder')
                    
                    for parent in shadow_parents:
                        if parent.is_displayed():
                            # Usamos ActionChains para hacer un clic físico en el centro del div
                            actions = ActionChains(driver)
                            actions.move_to_element(parent).click().perform()
                            print("Clic realizado en el contenedor del solver.")
                            # Salimos del bucle si ya lo encontramos
                            break 
                except Exception as e:
                    continue

            # Al terminar, vuelve siempre al contenido principal
            driver.switch_to.default_content()
        except Exception as e:
            print("Todo mal",e)
            pass
        try:
            print("Esperando OTP")
            driver.wait_for_element(
                'span.rf-search-alternative__links-link[title="Compra tu billete"], #idBotonValDispositivo', timeout=40
            )
        except Exception:
            pass # Si da timeout, continuará e intentará con los asserts o is_element_visible

        # Si el botón del OTP está visible, solicitamos código por Telegram
        if driver.is_element_visible("#idBotonValDispositivo"):
            if tg_handler and chat_id:
                otp_code = tg_handler.request_otp(chat_id, timeout=180) # 3 mins para insertar
                if otp_code:
                    driver.type("#codigoValidaLogin2F", otp_code)
                    driver.click("#idBotonValDispositivo")
                    driver.wait_for_element_visible(
                        'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
                    )
                else:
                    return False, "Se agotó el tiempo de espera (3 min) para recibir el código OTP de Renfe."
            else:
                return False, "Renfe solicita código de verificación OTP, pero no hay Telegram configurado (introduce tu Chat ID en Configuración) para introducilo."
        else:
            driver.wait_for_element_visible(
                'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
            )

        # 2. Ir a la página de bonos y seleccionar el abono
        driver.get("https://venta.renfe.com/vol/myPassesCard.do")
        driver.js_click(f"a[id^='new{localizador.strip()}']")

        # 3. Seleccionar trayecto (IDA o VUELTA)
        trenes_ida = driver.get_attribute("#journeyStationOriginDescription", "placeholder").split(" - ")
        es_ida = trenes_ida[0] in train.origin.upper()
        if not es_ida:
            driver.click("#journeyStationDestin")

        # 4. Fecha y buscar trenes
        driver.type("#fecha1", train.departure_time.strftime("%d/%m/%Y"))
        driver.click('button:contains("Siguiente")')

        # 5. Seleccionar el tren por hora de salida
        hora_objetivo = train.departure_time.strftime("%H.%M")
        driver.js_click(f"//tr[td[@data-label='Salida' and normalize-space()='{hora_objetivo}']]//button[contains(@class,'btn-purple')]")
        driver.js_click('button:contains("Siguiente")')
        time.sleep(10)

        return True, f"Formalización del trayecto {train.origin}-{train.destination} realizada con éxito"
    except Exception as e:
        print(e)
        return False, f"No se pudo completar la compra: {e}"
    finally:
        driver.quit()

