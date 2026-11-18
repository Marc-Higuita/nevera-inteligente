"""Ambiente 2: despensa inteligente (cámara, voz, texto y respuesta hablada)."""
import io
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image, ImageOps

from estilo import encabezado
from mqtt_utils import enviar_orden, leer_estado

encabezado("🥕 Despensa inteligente", "Muéstrale tus alimentos a la cámara o díselos por voz")

CARPETA_MODELO = Path(__file__).resolve().parent.parent / "modelo"

# Días aproximados que dura cada alimento en la nevera (ajústalos a tus clases)
DURACION_DIAS = {
    "leche": 5, "huevos": 21, "queso": 14, "yogur": 10, "jamon": 5,
    "carne": 2, "pollo": 2, "fruta": 7, "manzana": 20, "banano": 5,
    "verdura": 5, "tomate": 7, "lechuga": 5, "zanahoria": 21,
}
CLASES_VACIAS = {"nada", "vacio", "fondo", "ninguno"}


def sin_tildes(texto: str) -> str:
    texto = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in texto if unicodedata.category(c) != "Mn").strip()


# ---------- Inventario compartido ----------
@st.cache_resource
def inventario():
    return []   # lista de dicts {alimento, fecha}


def agregar(alimento: str):
    alimento = alimento.strip().capitalize()
    inventario().append({"alimento": alimento, "fecha": datetime.now()})
    enviar_orden(f"MENSAJE:+ {alimento}")       # aparece en la LCD de la nevera
    return f"Listo, agregué {alimento} a la nevera."


def quitar(alimento: str):
    buscado = sin_tildes(alimento)
    for i, item in enumerate(inventario()):
        if sin_tildes(item["alimento"]) == buscado:
            inventario().pop(i)
            enviar_orden(f"MENSAJE:- {item['alimento']}")
            return f"Saqué {item['alimento']} del inventario."
    return f"No encontré {alimento} en la nevera."


def resumen_inventario():
    items = inventario()
    if not items:
        return "La nevera está vacía."
    nombres = ", ".join(i["alimento"] for i in items)
    return f"En la nevera hay: {nombres}."


# ---------- Intérprete de comandos (voz y texto usan el mismo) ----------
def interpretar(frase: str) -> str:
    f = sin_tildes(frase)
    palabras = f.split()
    if not palabras:
        return "No escuché nada."

    if "alarma" in f and any(p in f for p in ("silencia", "calla", "apaga")):
        enviar_orden("SILENCIAR")
        return "Silencié la alarma."
    if any(p in f for p in ("enfriamiento", "compresor", "frio")):
        if any(p in f for p in ("apaga", "deten", "para ")):
            enviar_orden("COMPRESOR_OFF")
            return "Apagué el enfriamiento."
        if "automatico" in f:
            enviar_orden("MODO_AUTO")
            return "El enfriamiento quedó en automático."
        if any(p in f for p in ("enciende", "prende", "activa", "mas")):
            enviar_orden("COMPRESOR_ON")
            return "Encendí el enfriamiento."
    if "temperatura" in f:
        d = leer_estado().ultimo
        if d:
            return f"La nevera está a {d['temp']:.1f} grados y la puerta está {'abierta' if d['puerta'] else 'cerrada'}."
        return "Todavía no tengo datos de la nevera."
    if any(p in f for p in ("que hay", "inventario", "lista")):
        return resumen_inventario()

    verbos_agregar = ("agrega", "agregar", "anade", "anadir", "guarda", "guardar", "mete", "compre")
    verbos_quitar = ("saca", "sacar", "quita", "quitar", "elimina", "borra", "comi", "se acabo")
    for v in verbos_quitar:
        if f.startswith(v) or f" {v} " in f" {f} ":
            resto = f.split(v, 1)[1].replace("el ", "").replace("la ", "").replace("los ", "").replace("las ", "").strip()
            return quitar(resto) if resto else "¿Qué alimento saco?"
    for v in verbos_agregar:
        if f.startswith(v) or f" {v} " in f" {f} ":
            resto = f.split(v, 1)[1].strip()
            for articulo in ("un ", "una ", "unos ", "unas ", "el ", "la ", "los ", "las "):
                if resto.startswith(articulo):
                    resto = resto[len(articulo):]
            return agregar(resto) if resto else "¿Qué alimento agrego?"

    return ("No entendí. Prueba con: 'agrega leche', 'saca los huevos', "
            "'qué hay en la nevera', 'enciende el enfriamiento' o 'silencia la alarma'.")


def responder(texto: str):
    """Muestra la respuesta y la lee en voz alta (salida multimodal)."""
    st.success(texto)
    try:
        from gtts import gTTS
        audio = io.BytesIO()
        gTTS(texto, lang="es", tld="com.mx").write_to_fp(audio)
        st.audio(audio.getvalue(), format="audio/mp3", autoplay=True)
    except Exception:
        pass   # si no hay internet para la voz, al menos queda el texto


# ---------- Modelo de Teachable Machine ----------
@st.cache_resource
def cargar_modelo():
    ruta_modelo = CARPETA_MODELO / "keras_model.h5"
    ruta_labels = CARPETA_MODELO / "labels.txt"
    if not ruta_modelo.exists() or not ruta_labels.exists():
        return None, None, "Falta el modelo: sube keras_model.h5 y labels.txt a la carpeta modelo/."
    try:
        from tensorflow.keras.layers import DepthwiseConv2D
        from tensorflow.keras.models import load_model

        class DepthwiseConv2DCompat(DepthwiseConv2D):
            # Teachable Machine guarda un parámetro 'groups' que Keras nuevo no acepta
            def __init__(self, *args, **kwargs):
                kwargs.pop("groups", None)
                super().__init__(*args, **kwargs)

        modelo = load_model(str(ruta_modelo), compile=False,
                            custom_objects={"DepthwiseConv2D": DepthwiseConv2DCompat})
    except Exception as e:
        return None, None, f"No se pudo cargar el modelo: {e}"
    etiquetas = []
    for linea in ruta_labels.read_text(encoding="utf-8").splitlines():
        partes = linea.strip().split(" ", 1)     # formato "0 Leche"
        if partes and partes[0]:
            etiquetas.append(partes[-1])
    return modelo, etiquetas, None


def clasificar(imagen: Image.Image, modelo, etiquetas):
    imagen = ImageOps.fit(imagen.convert("RGB"), (224, 224), Image.Resampling.LANCZOS)
    arreglo = (np.asarray(imagen, dtype=np.float32) / 127.5) - 1
    pred = modelo.predict(arreglo[np.newaxis, ...], verbose=0)[0]
    i = int(np.argmax(pred))
    return etiquetas[i], float(pred[i])


# =====================================================================
tab_cam, tab_voz, tab_inv = st.tabs(["📷 Cámara", "🎙️ Voz y texto", "📋 Inventario"])

# ---------- Cámara ----------
with tab_cam:
    st.markdown("Muéstrale un alimento a la cámara y la app lo reconoce.")
    modelo, etiquetas, error = cargar_modelo()
    foto = st.camera_input("Toma una foto del alimento")

    if foto is not None:
        if modelo is None:
            st.warning(error)
            manual = st.text_input("Mientras tanto, escribe qué alimento es:")
            if st.button("Agregar", key="manual") and manual:
                responder(agregar(manual))
        else:
            clase, confianza = clasificar(Image.open(foto), modelo, etiquetas)
            if sin_tildes(clase) in CLASES_VACIAS:
                st.info("No veo ningún alimento. Acércalo a la cámara.")
            else:
                st.markdown(f"### Veo: **{clase}**  ({confianza:.0%} de seguridad)")
                st.progress(confianza)
                if confianza < 0.6:
                    st.caption("No estoy muy segura. Prueba con mejor luz o más cerca.")
                c1, c2 = st.columns(2)
                if c1.button(f"➕ Guardar {clase}", use_container_width=True):
                    responder(agregar(clase))
                if c2.button(f"➖ Sacar {clase}", use_container_width=True):
                    responder(quitar(clase))

# ---------- Voz y texto ----------
with tab_voz:
    st.markdown(
        "Habla o escribe. Ejemplos: *agrega leche*, *saca los huevos*, "
        "*qué hay en la nevera*, *cuál es la temperatura*, *silencia la alarma*."
    )
    audio = st.audio_input("Graba tu comando de voz")
    # Solo procesa cada grabación una vez (si no, se repite en cada recarga)
    huella = hash(audio.getvalue()) if audio is not None else None
    if audio is not None and st.session_state.get("ultimo_audio") != huella:
        st.session_state["ultimo_audio"] = huella
        try:
            import speech_recognition as sr
            reconocedor = sr.Recognizer()
            with sr.AudioFile(audio) as fuente:
                datos = reconocedor.record(fuente)
            frase = reconocedor.recognize_google(datos, language="es-CO")
            st.markdown(f"🗣️ Escuché: **{frase}**")
            responder(interpretar(frase))
        except Exception as e:
            st.error(f"No pude entender el audio ({type(e).__name__}). Intenta de nuevo o escríbelo.")

    with st.form("texto", clear_on_submit=True):
        frase = st.text_input("…o escribe tu comando")
        if st.form_submit_button("Enviar") and frase:
            responder(interpretar(frase))

# ---------- Inventario ----------
with tab_inv:
    items = inventario()
    with st.expander("⏩ Simular el paso del tiempo (para la demo)"):
        dias_extra = st.slider("Días que han pasado", 0, 15, 0)

    if not items:
        st.info("La nevera está vacía. Agrega alimentos con la cámara o con la voz.")
    else:
        ahora = datetime.now() + timedelta(days=dias_extra)
        filas = []
        for item in items:
            dias = (ahora - item["fecha"]).days
            duracion = DURACION_DIAS.get(sin_tildes(item["alimento"]), 7)
            restantes = duracion - dias
            if restantes <= 0:
                estado = "🔴 Revisar / posiblemente vencido"
            elif restantes <= 2:
                estado = "🟡 Consumir pronto"
            else:
                estado = "🟢 Bien"
            filas.append({"Alimento": item["alimento"],
                          "Guardado": item["fecha"].strftime("%d/%m %H:%M"),
                          "Días en la nevera": dias,
                          "Días que le quedan (aprox.)": max(restantes, 0),
                          "Estado": estado})
        df = pd.DataFrame(filas)
        st.dataframe(df, use_container_width=True, hide_index=True)

        urgentes = [f["Alimento"] for f in filas if not f["Estado"].startswith("🟢")]
        if urgentes:
            st.warning("Consume pronto: " + ", ".join(urgentes))

        c1, c2 = st.columns(2)
        if c1.button("🔊 Leer inventario en voz alta", use_container_width=True):
            responder(resumen_inventario())
        if c2.button("🗑️ Vaciar inventario", use_container_width=True):
            items.clear()
            st.rerun()
