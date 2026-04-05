# pip install seleniumbase
from seleniumbase import Driver
from .models import TrainRideRecord
import time

def compra_trenes(train: TrainRideRecord, email: str, password: str, localizador: str) -> tuple[bool, str]:
    """Inicia sesión y formaliza un viaje con el bono en una misma sesión de navegador."""
    driver = Driver(uc=True, headless=False)
    try:
        # 1. Login en la misma sesión del navegador
        driver.get("https://venta.renfe.com/vol/loginParticular.do")
        driver.type('input[name="userId"]', email)
        driver.type('input[name="password"]', password)
        driver.click('button:contains("Aceptar")')
        driver.click('button:contains("Entrar")')
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
