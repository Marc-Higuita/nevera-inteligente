"""Asistente de la nevera: inventario, recetas e intérprete de comandos (texto y voz).

Lo usan las dos páginas, así una pregunta o una orden funciona igual en Monitoreo y en Despensa.
"""
import io
import unicodedata
from datetime import datetime, timedelta

import streamlit as st

from estilo import AZUL, html, ic
from mqtt_utils import ZONA, enviar_orden, leer_estado

# Días aproximados que dura cada alimento en la nevera (ajústalos a tus clases)
DURACION_DIAS = {
    "leche": 5, "huevos": 21, "queso": 14, "yogur": 10, "jamon": 5,
    "carne": 2, "pollo": 2, "fruta": 7, "manzana": 20, "banano": 5,
    "verdura": 5, "tomate": 7, "lechuga": 5, "zanahoria": 21,
    "naranja": 14, "limon": 21, "fresa": 4, "pina": 5, "pimenton": 7, "pepino": 7,
    "brocoli": 5, "coliflor": 7, "repollo": 14, "champinon": 5, "calabacin": 7, "maiz": 4,
    "agua": 60, "gaseosa": 30, "mantequilla": 30, "pescado": 2, "arepa": 5, "uvas": 7,
    "mango": 5, "aguacate": 4, "cebolla": 30, "papa": 30, "jugo": 7, "salsa": 30, "pizza": 3, "helado": 60, "salchicha": 7, "pan": 4, "pasta": 3,
}
# Ícono (Material Symbols) para cada alimento
ICONOS = {
    "leche": "water_full", "yogur": "icecream", "queso": "lunch_dining", "huevos": "egg",
    "jamon": "lunch_dining", "carne": "kebab_dining", "pollo": "set_meal", "fruta": "nutrition",
    "manzana": "nutrition", "banano": "nutrition", "verdura": "eco", "tomate": "eco",
    "lechuga": "eco", "zanahoria": "eco", "naranja": "nutrition", "limon": "nutrition",
    "fresa": "nutrition", "pina": "nutrition", "granada": "nutrition", "pimenton": "eco",
    "pepino": "eco", "brocoli": "eco", "coliflor": "eco", "repollo": "eco", "champinon": "eco",
    "calabacin": "eco", "maiz": "eco", "ahuyama": "eco", "agua": "water_bottle",
    "gaseosa": "local_drink", "vino": "wine_bar", "cerveza": "sports_bar", "pizza": "local_pizza",
    "helado": "icecream", "salchicha": "kebab_dining", "hamburguesa": "lunch_dining",
    "bebida": "local_drink", "taza": "coffee", "recipiente": "rice_bowl", "dona": "donut_large",
    "torta": "cake", "sandwich": "lunch_dining", "copa": "wine_bar",
    "pan": "bakery_dining", "mantequilla": "breakfast_dining", "pescado": "set_meal",
    "arepa": "bakery_dining", "uvas": "nutrition", "mango": "nutrition", "aguacate": "nutrition",
    "cebolla": "eco", "papa": "eco", "jugo": "local_drink", "salsa": "liquor", "pasta": "ramen_dining", "sopa": "soup_kitchen",
}
CLASES_VACIAS = {"nada", "vacio", "fondo", "ninguno"}


def mensaje_lcd(linea1: str, linea2: str = "") -> bool:
    """Envía dos líneas a la LCD 16x2 (sin tildes, que la pantalla no puede mostrar)."""
    def limpio(t):
        t = unicodedata.normalize("NFD", t)
        return "".join(c for c in t if unicodedata.category(c) != "Mn").encode("ascii", "ignore").decode()[:16]
    return enviar_orden("MENSAJE:" + limpio(linea1).ljust(16) + limpio(linea2))


def sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


# ---------- Inventario compartido ----------
@st.cache_resource
def inventario():
    """Lista compartida de alimentos: dicts {alimento, fecha con zona horaria}."""
    return datos_de_ejemplo()


# Alimentos precargados para la demostración: (nombre, hace cuántos días se guardó)
EJEMPLO = [("Leche", 4), ("Huevos", 6), ("Manzana", 3), ("Queso", 2),
           ("Pollo", 2), ("Tomate", 1), ("Yogur", 9), ("Zanahoria", 0)]


def datos_de_ejemplo():
    ahora = datetime.now(ZONA)
    return [{"alimento": n, "fecha": ahora - timedelta(days=d, hours=1)} for n, d in EJEMPLO]


def agregar(alimento: str, notificar: bool = True):
    alimento = alimento.strip().capitalize()
    inventario().append({"alimento": alimento, "fecha": datetime.now(ZONA)})
    if notificar:
        mensaje_lcd(f"+ {alimento}", "Agregado")   # aparece en la LCD de la nevera
    return f"{alimento} se agregó al inventario."


def quitar(alimento: str):
    buscado = sin_tildes(alimento)
    for i, item in enumerate(inventario()):
        if sin_tildes(item["alimento"]) == buscado:
            inventario().pop(i)
            mensaje_lcd(f"- {item['alimento']}", "Retirado")
            return f"{item['alimento']} se retiró del inventario."
    return f"{alimento.capitalize()} no está en el inventario."


def resumen_inventario():
    items = inventario()
    if not items:
        return "El inventario está vacío."
    nombres = ", ".join(i["alimento"] for i in items)
    return f"En la nevera hay: {nombres}."


# ---------- Intérprete de comandos (voz y texto usan el mismo) ----------
def buscar_en_inventario(f: str):
    """Devuelve (nombre, cantidad, días restantes) del alimento mencionado en la frase, o None."""
    grupos = {}
    for item in inventario():
        clave = sin_tildes(item["alimento"])
        g = grupos.setdefault(clave, {"nombre": item["alimento"], "cantidad": 0, "restantes": 999})
        g["cantidad"] += 1
        g["restantes"] = min(g["restantes"], dias_restantes(item))
    for clave, g in grupos.items():
        singular = clave[:-1] if clave.endswith("s") else clave
        if clave in f or singular in f:
            return g["nombre"], g["cantidad"], g["restantes"]
    return None


def interpretar(frase: str) -> str:
    f = sin_tildes(frase)
    palabras = f.split()
    if not palabras:
        return "No se recibió ningún comando."

    # Mensaje directo para la pantalla: "escribe en la pantalla hola" / "mensaje: hola"
    for inicio in ("mensaje:", "mensaje ", "escribe en la pantalla ", "pantalla:"):
        if f.startswith(inicio):
            texto = frase.strip()[len(inicio):].strip(" :")
            mensaje_lcd(texto[:16], texto[16:32])
            return f"Listo, la pantalla de la nevera muestra: {texto[:32]}."

    # Puerta (simulación)
    if "puerta" in f and any(p in f for p in ("abre", "abrir")):
        enviar_orden("PUERTA_ABRIR")
        return "Abrí la puerta. La temperatura empezará a subir."
    if "puerta" in f and any(p in f for p in ("cierra", "cerrar")):
        enviar_orden("PUERTA_CERRAR")
        return "Cerré la puerta."

    # Vencimientos: "cuándo vence la leche", "revisar fecha leche", "cuánto dura el queso"
    if any(p in f for p in ("vence", "vencimiento", "fecha", "caduca", "dura", "revisa", "queda")):
        encontrado = buscar_en_inventario(f)
        if encontrado:
            nombre, cantidad, restantes = encontrado
            unidades = f" ({cantidad} unidades)" if cantidad > 1 else ""
            if restantes <= 0:
                mensaje_lcd(nombre, "REVISAR fecha")
                return f"{nombre}{unidades}: ya cumplió su tiempo en la nevera. Revisa su estado antes de consumirlo."
            queda = "le queda 1 día" if restantes == 1 else f"le quedan {restantes} días"
            mensaje_lcd(nombre, f"Vence en {restantes} d")
            consejo = " Conviene consumirlo pronto." if restantes <= 2 else ""
            return f"{nombre}{unidades}: {queda} aproximadamente.{consejo}"
        mencionado = next((k for k in list(DURACION_DIAS) + [sin_tildes(n) for n in ICONOS] if k in f), None)
        if mencionado:
            mensaje_lcd(mencionado.capitalize(), "No registrado")
            return f"No encontré {mencionado} en el inventario de la nevera."
        if any(p in f for p in ("vence", "vencimiento", "caduca")):
            urgentes = sorted(((dias_restantes(i), i["alimento"]) for i in inventario()))[:3]
            if not urgentes:
                return "No hay alimentos registrados."
            lista = ", ".join(f"{n} ({max(d, 0)} d)" for d, n in urgentes)
            return f"Lo que vence primero: {lista}."

    if "alarma" in f and any(p in f for p in ("silencia", "calla", "apaga")):
        enviar_orden("SILENCIAR")
        return "Alarma silenciada."
    if "temperatura" in f and any(p in f for p in ("sube", "subir", "aumenta", "mas alta")):
        enviar_orden("OBJETIVO_MAS")
        return "Subí un grado la temperatura objetivo."
    if "temperatura" in f and any(p in f for p in ("baja", "bajar", "disminuye", "mas fria", "enfria")):
        enviar_orden("OBJETIVO_MENOS")
        return "Bajé un grado la temperatura objetivo."
    if any(p in f for p in ("enfriamiento", "compresor", "frio")):
        if any(p in f for p in ("apaga", "deten", "para ")):
            enviar_orden("COMPRESOR_OFF")
            return "Enfriamiento apagado."
        if "automatico" in f:
            enviar_orden("MODO_AUTO")
            return "Enfriamiento en modo automático."
        if any(p in f for p in ("enciende", "prende", "activa", "mas")):
            enviar_orden("COMPRESOR_ON")
            return "Enfriamiento encendido."
    if "temperatura" in f:
        d = leer_estado().ultimo
        if d:
            return f"Temperatura actual: {d['temp']:.1f} grados. Puerta {'abierta' if d['puerta'] else 'cerrada'}."
        return "Aún no hay datos de la nevera."
    if any(p in f for p in ("que hay", "inventario", "lista")):
        return resumen_inventario()
    if any(p in f for p in ("receta", "cocino", "cocinar", "preparo")):
        sug = sugerir_recetas(inventario(), n=1)
        if not sug:
            return "No tengo recetas para los alimentos registrados."
        _, receta, _, urgentes, _ = sug[0]
        extra = ""
        if urgentes:
            verbo = "vence" if len(urgentes) == 1 else "vencen"
            extra = f" Así aprovechas {' y '.join(urgentes)}, que {verbo} pronto."
        mensaje_lcd("Receta:", receta["nombre"])
        return f"Te sugiero {receta['nombre']}.{extra} " + " ".join(receta["pasos"])

    verbos_agregar = ("agrega", "agregar", "anade", "anadir", "guarda", "guardar", "mete", "compre")
    verbos_quitar = ("saca", "sacar", "quita", "quitar", "elimina", "borra", "comi", "se acabo")
    for v in verbos_quitar:
        if f.startswith(v) or f" {v} " in f" {f} ":
            resto = f.split(v, 1)[1].replace("el ", "").replace("la ", "").replace("los ", "").replace("las ", "").strip()
            return quitar(resto) if resto else "Indica qué alimento deseas retirar."
    for v in verbos_agregar:
        if f.startswith(v) or f" {v} " in f" {f} ":
            resto = f.split(v, 1)[1].strip()
            for articulo in ("un ", "una ", "unos ", "unas ", "el ", "la ", "los ", "las "):
                if resto.startswith(articulo):
                    resto = resto[len(articulo):]
            return agregar(resto) if resto else "Indica qué alimento deseas agregar."

    return ("No reconocí el comando. Prueba con: cuándo vence la leche, baja la temperatura, "
            "abre la puerta, agrega huevos, qué puedo cocinar o silencia la alarma.")


def responder(texto: str):
    """Muestra la respuesta y la lee en voz alta (salida multimodal)."""
    html(f'<div class="card" style="display:flex;gap:.8rem;align-items:center;padding:1rem 1.2rem">'
         f'<span class="icono-circ" style="background:#E8EFFF;color:{AZUL}">{ic("graphic_eq")}</span>'
         f'<div style="font-weight:600">{texto}</div></div>')
    try:
        from gtts import gTTS
        audio = io.BytesIO()
        gTTS(texto, lang="es", tld="com.mx").write_to_fp(audio)
        st.audio(audio.getvalue(), format="audio/mp3", autoplay=True)
    except Exception:
        pass   # si no hay internet para la voz, al menos queda el texto



# ---------- Recetas anti-desperdicio ----------
RECETAS = [
    {"nombre": "Arepa con huevo", "min": 20, "icono": "egg_alt", "ingredientes": ["Arepa", "Huevos"],
     "pasos": ["Asa las arepas hasta que estén doradas.", "Fríe o revuelve los huevos con sal.",
               "Abre la arepa y rellénala con el huevo."]},
    {"nombre": "Huevos pericos", "min": 15, "icono": "skillet", "ingredientes": ["Huevos", "Tomate", "Cebolla"],
     "pasos": ["Sofríe el tomate y la cebolla picados.", "Agrega los huevos batidos con sal.",
               "Revuelve a fuego medio hasta que cuajen."]},
    {"nombre": "Batido de banano", "min": 5, "icono": "blender", "ingredientes": ["Banano", "Leche"],
     "pasos": ["Pela y trocea el banano.", "Licúa con la leche fría.", "Sirve de inmediato."]},
    {"nombre": "Arroz con leche", "min": 40, "icono": "rice_bowl", "ingredientes": ["Leche"],
     "pasos": ["Cocina el arroz en agua hasta que ablande.", "Agrega la leche, azúcar y canela.",
               "Cocina a fuego bajo hasta que espese."]},
    {"nombre": "Salpicón de frutas", "min": 10, "icono": "nutrition",
     "ingredientes": ["Manzana", "Banano", "Fresa", "Naranja", "Mango"],
     "pasos": ["Pica todas las frutas en cubos.", "Mézclalas en un recipiente.",
               "Agrega jugo de naranja y sirve frío."]},
    {"nombre": "Ensalada fresca", "min": 10, "icono": "eco",
     "ingredientes": ["Lechuga", "Tomate", "Pepino", "Zanahoria"],
     "pasos": ["Lava y pica las verduras.", "Mezcla en un recipiente.", "Aliña con limón, sal y aceite."]},
    {"nombre": "Sándwich de jamón y queso", "min": 10, "icono": "lunch_dining",
     "ingredientes": ["Pan", "Jamón", "Queso"],
     "pasos": ["Arma el sándwich con jamón y queso.", "Caliéntalo en sartén o sanduchera.",
               "Sirve cuando el queso esté derretido."]},
    {"nombre": "Pollo guisado", "min": 45, "icono": "set_meal", "ingredientes": ["Pollo", "Tomate", "Cebolla", "Papa"],
     "pasos": ["Dora las presas de pollo.", "Agrega el hogao de tomate y cebolla.",
               "Incorpora las papas y cocina tapado 30 minutos."]},
    {"nombre": "Sopa de verduras", "min": 35, "icono": "soup_kitchen",
     "ingredientes": ["Zanahoria", "Papa", "Brócoli", "Cebolla"],
     "pasos": ["Pica todas las verduras.", "Cocínalas en agua con sal y cebolla.",
               "Sirve caliente con cilantro."]},
    {"nombre": "Tortilla de verduras", "min": 20, "icono": "skillet",
     "ingredientes": ["Huevos", "Pimentón", "Cebolla", "Tomate"],
     "pasos": ["Sofríe las verduras picadas.", "Vierte los huevos batidos encima.",
               "Cocina tapado hasta que cuaje y dóblala."]},
    {"nombre": "Yogur con frutas", "min": 5, "icono": "icecream", "ingredientes": ["Yogur", "Fresa", "Banano", "Manzana"],
     "pasos": ["Pica la fruta.", "Sirve el yogur en un vaso.", "Agrega la fruta y granola si tienes."]},
    {"nombre": "Guacamole", "min": 10, "icono": "nutrition", "ingredientes": ["Aguacate", "Tomate", "Cebolla", "Limón"],
     "pasos": ["Machaca el aguacate.", "Agrega tomate y cebolla picados.", "Sazona con limón y sal."]},
    {"nombre": "Bistec a caballo", "min": 30, "icono": "kebab_dining", "ingredientes": ["Carne", "Tomate", "Cebolla", "Huevos"],
     "pasos": ["Asa la carne con sal y pimienta.", "Prepara un hogao de tomate y cebolla.",
               "Sirve con el hogao y un huevo frito encima."]},
    {"nombre": "Pasta con salsa y queso", "min": 20, "icono": "ramen_dining", "ingredientes": ["Pasta", "Salsa", "Queso"],
     "pasos": ["Cocina la pasta en agua con sal.", "Calienta la salsa.", "Mezcla y gratina con queso."]},
    {"nombre": "Limonada natural", "min": 5, "icono": "local_drink", "ingredientes": ["Limón"],
     "pasos": ["Exprime los limones.", "Licúa con agua, hielo y azúcar.", "Cuela y sirve."]},
]


def dias_restantes(item, dias_extra=0):
    ahora = datetime.now(ZONA) + timedelta(days=dias_extra)
    dias = (ahora - item["fecha"]).days
    return DURACION_DIAS.get(sin_tildes(item["alimento"]), 7) - dias


def sugerir_recetas(items, n=6):
    """Ordena las recetas: primero las que usan alimentos por vencer."""
    disponibles = {}
    for item in items:
        clave = sin_tildes(item["alimento"])
        r = dias_restantes(item)
        disponibles[clave] = min(r, disponibles.get(clave, r))
    resultado = []
    for receta in RECETAS:
        tiene = [i for i in receta["ingredientes"] if sin_tildes(i) in disponibles]
        if not tiene:
            continue
        urgentes = [i for i in tiene if disponibles[sin_tildes(i)] <= 2]
        puntaje = (len(tiene) / len(receta["ingredientes"])) + 1.5 * len(urgentes)
        resultado.append((puntaje, receta, tiene, urgentes, disponibles))
    resultado.sort(key=lambda x: -x[0])
    return resultado[:n]




def transcribir(audio, clave: str):
    """Convierte una grabación de st.audio_input en texto (una sola vez por grabación)."""
    if audio is None:
        return None
    huella = hash(audio.getvalue())
    if st.session_state.get(clave) == huella:
        return None
    st.session_state[clave] = huella
    try:
        import speech_recognition as sr
        reconocedor = sr.Recognizer()
        with sr.AudioFile(audio) as fuente:
            datos = reconocedor.record(fuente)
        return reconocedor.recognize_google(datos, language="es-CO")
    except Exception:
        st.error("No fue posible reconocer el audio. Intenta de nuevo o escribe la pregunta.",
                 icon=":material/mic_off:")
        return None
