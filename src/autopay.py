import random
from seleniumbase import SB
from .models import TrainRideRecord


def _human_delay(sb, min_s=0.5, max_s=1.8):
    """Pausa aleatoria que simula comportamiento humano."""
    sb.sleep(round(random.uniform(min_s, max_s), 2))


def _check_and_solve_captcha(sb):
    """Si aparece un captcha en la página, intenta resolverlo automáticamente."""
    try:
        sb.cdp.gui_click_captcha()
    except Exception:
        pass


def compra_trenes(train: TrainRideRecord, email: str, password: str, localizador: str, tg_handler=None, chat_id=None) -> tuple[bool, str]:
    """Inicia sesión y formaliza un viaje con el bono en una misma sesión de navegador."""
    try:
        with SB(uc=True, headless=False, ad_block=True) as sb:
            # 1. Login en la misma sesión del navegador
            sb.activate_cdp_mode("https://venta.renfe.com/vol/loginParticular.do")
            sb.sleep(2)  # Espera inicial para que cargue completamente
            _check_and_solve_captcha(sb)

            _human_delay(sb)
            sb.type('input[name="userId"]', email)
            _human_delay(sb, 0.3, 0.8)
            sb.type('input[name="password"]', password)
            _human_delay(sb)

            try:
                sb.click('button:contains("Aceptar")')
                _human_delay(sb, 0.5, 1.0)
            except Exception:
                pass

            sb.click('button:contains("Entrar")')
            _human_delay(sb, 2.0, 3.5)
            _check_and_solve_captcha(sb)

            # Esperamos a que aparezca o la vista de éxito o la de OTP
            try:
                print("Esperando OTP")
                sb.wait_for_element(
                    'span.rf-search-alternative__links-link[title="Compra tu billete"], #idBotonValDispositivo', timeout=40
                )
            except Exception:
                pass  # Si da timeout, continuará e intentará con is_element_visible

            # Si el botón del OTP está visible, solicitamos código por Telegram
            if sb.is_element_visible("#idBotonValDispositivo"):
                if tg_handler and chat_id:
                    otp_code = tg_handler.request_otp(chat_id, timeout=180)  # 3 mins para insertar
                    if otp_code:
                        _human_delay(sb)
                        sb.type("#codigoValidaLogin2F", otp_code)
                        _human_delay(sb, 0.5, 1.2)
                        sb.click("#idBotonValDispositivo")
                        sb.wait_for_element_visible(
                            'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
                        )
                    else:
                        return False, "Se agotó el tiempo de espera (3 min) para recibir el código OTP de Renfe."
                else:
                    return False, "Renfe solicita código de verificación OTP, pero no hay Telegram configurado (introduce tu Chat ID en Configuración) para introducilo."
            else:
                sb.wait_for_element_visible(
                    'span.rf-search-alternative__links-link[title="Compra tu billete"]', timeout=40
                )

            # 2. Ir a la página de bonos y seleccionar el abono
            sb.open("https://venta.renfe.com/vol/myPassesCard.do")
            sb.sleep(2)
            _check_and_solve_captcha(sb)
            _human_delay(sb)
            sb.click(f"a[id^='new{localizador.strip()}']")
            _human_delay(sb, 1.0, 2.0)

            # 3. Seleccionar trayecto (IDA o VUELTA)
            trenes_ida = sb.get_attribute("#journeyStationOriginDescription", "placeholder").split(" - ")
            es_ida = trenes_ida[0] in train.origin.upper()
            if not es_ida:
                sb.click("#journeyStationDestin")
                _human_delay(sb)

            # 4. Fecha y buscar trenes
            sb.type("#fecha1", train.departure_time.strftime("%d/%m/%Y"))
            _human_delay(sb, 0.5, 1.0)
            sb.click('button:contains("Siguiente")')
            sb.sleep(3)
            _check_and_solve_captcha(sb)

            # 5. Seleccionar el tren por hora de salida
            hora_objetivo = train.departure_time.strftime("%H.%M")
            _human_delay(sb)
            sb.click(f"//tr[td[@data-label='Salida' and normalize-space()='{hora_objetivo}']]//button[contains(@class,'btn-purple')]")
            _human_delay(sb, 0.8, 1.5)
            sb.click('button:contains("Siguiente")')
            sb.sleep(10)

            return True, f"Formalización del trayecto {train.origin}-{train.destination} realizada con éxito"
    except Exception as e:
        print(e)
        return False, f"No se pudo completar la compra: {e}"