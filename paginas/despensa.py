"""Ambiente 2: despensa inteligente (cámara, voz, texto y respuesta hablada)."""
import io
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from estilo import AMBAR, AZUL, GRIS, ROJO, VERDE, barra_superior, encabezado, estado, html, ic
from mqtt_utils import ZONA, enviar_orden, leer_estado

barra_superior(leer_estado().conectado)
encabezado("Despensa", "Registra alimentos con la cámara o la voz y controla su vida útil.", "shopping_basket")

CARPETA_MODELO = Path(__file__).resolve().parent.parent / "modelo"

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
    "pan": "bakery_dining", "mantequilla": "breakfast_dining", "pescado": "set_meal",
    "arepa": "bakery_dining", "uvas": "nutrition", "mango": "nutrition", "aguacate": "nutrition",
    "cebolla": "eco", "papa": "eco", "jugo": "local_drink", "salsa": "liquor", "pasta": "ramen_dining", "sopa": "soup_kitchen",
}
CLASES_VACIAS = {"nada", "vacio", "fondo", "ninguno"}


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


def agregar(alimento: str):
    alimento = alimento.strip().capitalize()
    inventario().append({"alimento": alimento, "fecha": datetime.now(ZONA)})
    enviar_orden(f"MENSAJE:+ {alimento}")       # aparece en la LCD de la nevera
    return f"{alimento} se agregó al inventario."


def quitar(alimento: str):
    buscado = sin_tildes(alimento)
    for i, item in enumerate(inventario()):
        if sin_tildes(item["alimento"]) == buscado:
            inventario().pop(i)
            enviar_orden(f"MENSAJE:- {item['alimento']}")
            return f"{item['alimento']} se retiró del inventario."
    return f"{alimento.capitalize()} no está en el inventario."


def resumen_inventario():
    items = inventario()
    if not items:
        return "El inventario está vacío."
    nombres = ", ".join(i["alimento"] for i in items)
    return f"En la nevera hay: {nombres}."


# ---------- Intérprete de comandos (voz y texto usan el mismo) ----------
def interpretar(frase: str) -> str:
    f = sin_tildes(frase)
    palabras = f.split()
    if not palabras:
        return "No se recibió ningún comando."

    if "alarma" in f and any(p in f for p in ("silencia", "calla", "apaga")):
        enviar_orden("SILENCIAR")
        return "Alarma silenciada."
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

    return ("No reconocí el comando. Prueba con: agrega leche, saca los huevos, "
            "qué hay en la nevera, enciende el enfriamiento o silencia la alarma.")


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


# ---------- Reconocimiento de alimentos ----------
# Se usa CLIP (OpenAI), un modelo que compara la imagen con descripciones en texto.
# Por eso puede reconocer cualquier alimento de esta lista sin entrenamiento previo.
# Para agregar un alimento basta con añadir una línea: "Nombre": ["descripción en inglés", ...]
CATALOGO = {
    "Leche": ["a carton of milk", "a bottle of milk", "a glass of milk", "a bag of milk"],
    "Huevos": ["eggs", "a carton of eggs", "chicken eggs"],
    "Queso": ["a block of cheese", "sliced cheese", "fresh white cheese"],
    "Yogur": ["a cup of yogurt", "a bottle of drinkable yogurt"],
    "Mantequilla": ["a stick of butter", "butter"],
    "Jamón": ["sliced ham", "a package of ham"],
    "Carne": ["raw red meat", "beef steak"],
    "Pollo": ["raw chicken", "chicken breast"],
    "Pescado": ["raw fish", "fish fillet"],
    "Salchicha": ["sausages", "hot dog sausages"],
    "Arepa": ["arepas", "a corn arepa"],
    "Manzana": ["an apple", "red apples", "a green apple"],
    "Banano": ["a banana", "a bunch of bananas"],
    "Naranja": ["an orange fruit", "oranges"],
    "Limón": ["a lime", "a lemon"],
    "Fresa": ["strawberries"],
    "Uvas": ["grapes"],
    "Piña": ["a pineapple"],
    "Mango": ["a mango"],
    "Aguacate": ["an avocado"],
    "Tomate": ["a tomato", "tomatoes"],
    "Zanahoria": ["a carrot", "carrots"],
    "Lechuga": ["lettuce", "a head of lettuce"],
    "Cebolla": ["an onion", "onions"],
    "Papa": ["potatoes"],
    "Pimentón": ["a bell pepper"],
    "Pepino": ["a cucumber"],
    "Brócoli": ["broccoli"],
    "Pan": ["bread", "a loaf of bread"],
    "Agua": ["a bottle of water"],
    "Gaseosa": ["a can of soda", "a bottle of soda"],
    "Jugo": ["a box of juice", "a bottle of juice"],
    "Salsa": ["a bottle of ketchup", "a jar of sauce"],
    "Helado": ["a tub of ice cream", "ice cream"],
    "Nada": ["a person", "a face", "a room", "an empty table", "a wall", "an empty refrigerator shelf"],
}


@st.cache_resource(show_spinner="Cargando modelo de reconocimiento (solo la primera vez)…")
def cargar_modelo():
    """Carga CLIP y precalcula las descripciones de todos los alimentos."""
    try:
        import torch
        from transformers import CLIPModel, CLIPProcessor

        nombre = "openai/clip-vit-base-patch32"
        modelo = CLIPModel.from_pretrained(nombre).eval()
        procesador = CLIPProcessor.from_pretrained(nombre)
        textos, clases = [], []
        for clase, frases in CATALOGO.items():
            for frase in frases:
                textos.append(f"a photo of {frase}")
                clases.append(clase)
        with torch.no_grad():
            entrada = procesador(text=textos, return_tensors="pt", padding=True)
            emb = modelo.get_text_features(**entrada)
            emb = emb / emb.norm(dim=-1, keepdim=True)
        return modelo, procesador, emb, clases
    except Exception as e:
        return f"{type(e).__name__}: {e}"   # texto del error, para mostrarlo en pantalla


def reconocer(imagen: Image.Image):
    """Devuelve (alimento o None, confianza)."""
    import torch

    modelo, procesador, emb_textos, clases = cargar_modelo()
    with torch.no_grad():
        entrada = procesador(images=imagen.convert("RGB"), return_tensors="pt")
        emb = modelo.get_image_features(**entrada)
        emb = emb / emb.norm(dim=-1, keepdim=True)
        probs = (100 * emb @ emb_textos.T).softmax(dim=-1)[0].tolist()
    total = {}
    for clase, p in zip(clases, probs):
        total[clase] = total.get(clase, 0) + p
    mejor = max(total, key=total.get)
    return (None if mejor == "Nada" else mejor), total[mejor]


def imagen_desde_enlace(url: str) -> Image.Image:
    import urllib.request
    pedido = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (NeveraInteligente; proyecto academico EAFIT)", "Accept": "image/*"})
    with urllib.request.urlopen(pedido, timeout=15) as r:
        return Image.open(io.BytesIO(r.read()))


# =====================================================================
tab_cam, tab_voz, tab_inv = st.tabs([":material/photo_camera: Cámara",
                                     ":material/mic: Voz y texto",
                                     ":material/inventory_2: Inventario"])

# ---------- Cámara ----------
with tab_cam:
    izq, der = st.columns([1.2, 1], gap="large")
    imagen = None
    with izq:
        origen = st.segmented_control("Origen de la imagen", ["Cámara", "Subir foto", "Enlace"],
                                      default="Cámara", label_visibility="collapsed")
        if origen == "Subir foto":
            archivo = st.file_uploader("Sube una foto del alimento", type=["jpg", "jpeg", "png", "webp"])
            if archivo is not None:
                imagen = Image.open(archivo)
        elif origen == "Enlace":
            enlace = st.text_input("Pega el enlace de una imagen de internet",
                                   placeholder="https://…/foto.jpg")
            if enlace:
                try:
                    imagen = imagen_desde_enlace(enlace.strip())
                except Exception as e:
                    st.error("No fue posible abrir la imagen. Prueba con otro enlace o descarga la foto "
                             "y usa la opción Subir foto.", icon=":material/link_off:")
                    st.caption(f"Detalle técnico: {type(e).__name__}: {e}")
        else:
            foto = st.camera_input("Ubica el alimento frente a la cámara y toma la foto")
            if foto is not None:
                imagen = Image.open(foto)
        if imagen is not None and origen != "Cámara":
            st.image(imagen, use_container_width=True)

    with der:
        if imagen is None:
            html(f"""
            <div class="card" style="text-align:center;padding:2rem">
              {ic('center_focus_strong', 44, GRIS)}
              <div class="valor" style="font-size:1.15rem;margin-top:.6rem">Reconocimiento de alimentos</div>
              <div class="etiqueta">Toma o sube una foto y el modelo identificará el producto para registrarlo.</div>
              <div style="margin-top:.8rem">{estado(f"Modelo CLIP · {len(CATALOGO) - 1} alimentos", AZUL, "#E8EFFF")}</div>
            </div>""")
        else:
            with st.spinner("Analizando imagen…"):
                recurso = cargar_modelo()
                cargado = not isinstance(recurso, str)
                clase, confianza = reconocer(imagen) if cargado else (None, 0.0)
            if not cargado:
                st.info("El modelo de reconocimiento no está disponible. Escribe el nombre del alimento.",
                        icon=":material/info:")
                st.caption(f"Detalle técnico: {recurso}")
            if clase is None:
                if cargado:
                    st.info("No se identificó un alimento. Acércalo a la cámara o prueba con otra foto.",
                            icon=":material/info:")
                manual = st.text_input("Escribe el nombre del alimento")
                if st.button("Agregar al inventario", icon=":material/add:", type="primary",
                             key="manual") and manual:
                    responder(agregar(manual))
            else:
                icono = ICONOS.get(sin_tildes(clase), "kitchen")
                html(f"""
                <div class="card" style="text-align:center">
                  <span class="icono-circ" style="background:#E8EFFF;color:{AZUL};width:72px;height:72px">{ic(icono, 38)}</span>
                  <div class="etiqueta" style="margin-top:.8rem">Alimento detectado</div>
                  <div class="valor">{clase}</div>
                  <div class="etiqueta">Confianza del modelo: {confianza:.0%}</div>
                </div>""")
                st.progress(min(confianza, 1.0))
                if confianza < 0.4:
                    st.caption("Confianza baja. Mejora la iluminación o acerca el producto.")
                c1, c2 = st.columns(2)
                if c1.button("Agregar", icon=":material/add:", type="primary", use_container_width=True):
                    responder(agregar(clase))
                if c2.button("Retirar", icon=":material/remove:", use_container_width=True):
                    responder(quitar(clase))

# ---------- Voz y texto ----------
with tab_voz:
    izq, der = st.columns([1, 1], gap="large")
    with izq:
        with st.container(border=True):
            st.markdown("**:material/mic: Comando de voz**")
            audio = st.audio_input("Presiona el micrófono y di tu comando")
            # Cada grabación se procesa una sola vez
            huella = hash(audio.getvalue()) if audio is not None else None
            if audio is not None and st.session_state.get("ultimo_audio") != huella:
                st.session_state["ultimo_audio"] = huella
                try:
                    import speech_recognition as sr
                    reconocedor = sr.Recognizer()
                    with sr.AudioFile(audio) as fuente:
                        datos = reconocedor.record(fuente)
                    frase = reconocedor.recognize_google(datos, language="es-CO")
                    st.caption(f"Comando reconocido: “{frase}”")
                    responder(interpretar(frase))
                except Exception:
                    st.error("No fue posible reconocer el audio. Intenta de nuevo o escribe el comando.",
                             icon=":material/mic_off:")

            with st.form("texto", clear_on_submit=True, border=False):
                a, b = st.columns([2.6, 1.4], vertical_alignment="bottom")
                frase = a.text_input("O escribe el comando")
                if b.form_submit_button("Enviar", icon=":material/send:", type="primary",
                                        use_container_width=True) and frase:
                    responder(interpretar(frase))
    with der:
        comandos = [
            ("add_circle", "Agrega leche"), ("remove_circle", "Saca los huevos"),
            ("list_alt", "Qué hay en la nevera"), ("device_thermostat", "Cuál es la temperatura"),
            ("ac_unit", "Enciende el enfriamiento"), ("notifications_off", "Silencia la alarma"),
        ]
        filas = "".join(
            f'<div style="display:flex;align-items:center;gap:.7rem;padding:.55rem 0;border-bottom:1px solid #F1F4FA">'
            f'<span class="icono-circ" style="width:34px;height:34px;background:#F1F4FA;color:#14161F">{ic(i, 18)}</span>'
            f'<span style="font-weight:600">{t}</span></div>'
            for i, t in comandos
        )
        html(f'<div class="card"><div class="titulo">{ic("record_voice_over")}Comandos disponibles</div>{filas}</div>')

# ---------- Inventario ----------
with tab_inv:
    items = inventario()
    cab1, cab2, cab3 = st.columns([2, 1, 1], vertical_alignment="center")
    cab1.markdown(f"#### {len(items)} producto{'s' if len(items) != 1 else ''} registrado{'s' if len(items) != 1 else ''}")
    with cab2.popover("Simular días", icon=":material/calendar_month:", use_container_width=True):
        dias_extra = st.slider("Días transcurridos", 0, 15, 0)
    if cab3.button("Leer inventario", icon=":material/volume_up:", use_container_width=True):
        responder(resumen_inventario())

    if not items:
        html(f"""
        <div class="card" style="text-align:center;padding:2.2rem">
          {ic('inventory_2', 44, GRIS)}
          <div class="valor" style="font-size:1.15rem;margin-top:.6rem">Sin productos registrados</div>
          <div class="etiqueta">Agrega alimentos desde la cámara o con un comando de voz.</div>
        </div>""")
        st.write("")
        if st.button("Cargar inventario de ejemplo", icon=":material/restart_alt:"):
            items[:] = datos_de_ejemplo()
            st.rerun()
    else:
        ahora = datetime.now(ZONA) + timedelta(days=dias_extra)
        tiles, urgentes = [], []
        for item in items:
            nombre = sin_tildes(item["alimento"])
            dias = (ahora - item["fecha"]).days
            restantes = DURACION_DIAS.get(nombre, 7) - dias
            if restantes <= 0:
                chip, color = estado("Revisar", "#B4232A", "#FFF1F1"), ROJO
                urgentes.append(item["alimento"])
            elif restantes <= 2:
                chip, color = estado(f"{restantes} d restantes", "#9A5B00", "#FFF4E0"), AMBAR
                urgentes.append(item["alimento"])
            else:
                chip, color = estado(f"{restantes} d restantes", "#11804F", "#E7F7EF"), VERDE
            tiles.append(
                f'<div class="tile">{ic(ICONOS.get(nombre, "kitchen"), 40, color)}'
                f'<div class="nom">{item["alimento"]}</div>'
                f'<div class="sub">Registrado {item["fecha"].strftime("%d/%m %H:%M")}</div>{chip}</div>'
            )
        html(f'<div class="grid">{"".join(tiles)}</div>')
        if urgentes:
            st.write("")
            st.warning("Consumir pronto: " + ", ".join(urgentes), icon=":material/schedule:")
        st.write("")
        v1, v2, _ = st.columns([1, 1, 2])
        if v1.button("Vaciar inventario", icon=":material/delete:", use_container_width=True):
            items.clear()
            st.rerun()
        if v2.button("Restablecer ejemplo", icon=":material/restart_alt:", use_container_width=True):
            items[:] = datos_de_ejemplo()
            st.rerun()
