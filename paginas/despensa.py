"""Ambiente 2: despensa inteligente (cámara, voz, texto y respuesta hablada)."""
import io
import unicodedata
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
from PIL import Image

from estilo import AMBAR, AZUL, GRIS, ROJO, VERDE, barra_superior, encabezado, estado, html, ic, lcd_virtual
import streamlit.components.v1 as components

from asistente import (DURACION_DIAS, ICONOS, agregar, datos_de_ejemplo, dias_restantes, interpretar, inventario,
                       quitar, responder, resumen_inventario, sin_tildes, sugerir_recetas)
from mqtt_utils import BROKER_WS, TOPIC_CMD, TOPIC_INV, ZONA, enviar_orden, leer_estado

barra_superior(leer_estado().conectado)
encabezado("Despensa", "Registra alimentos con la cámara o la voz y controla su vida útil.", "shopping_basket")

CARPETA_MODELO = Path(__file__).resolve().parent.parent / "modelo"

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
        entrada_texto = procesador(text=textos, return_tensors="pt", padding=True)
        torch.set_num_threads(2)
        return modelo, procesador, entrada_texto, clases
    except Exception as e:
        return f"{type(e).__name__}: {e}"   # texto del error, para mostrarlo en pantalla


def reconocer(imagen: Image.Image):
    """Devuelve (alimento o None, confianza)."""
    import torch

    modelo, procesador, entrada_texto, clases = cargar_modelo()
    with torch.no_grad():
        entrada_imagen = procesador(images=imagen.convert("RGB"), return_tensors="pt")
        salida = modelo(**entrada_texto, pixel_values=entrada_imagen["pixel_values"])
        probs = salida.logits_per_image.softmax(dim=-1)[0].tolist()
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


def panel_recetas():
    sugerencias = sugerir_recetas(inventario())
    if not sugerencias:
        html(f"""
        <div class="card" style="text-align:center;padding:2.2rem">
          {ic('menu_book', 44, GRIS)}
          <div class="valor" style="font-size:1.15rem;margin-top:.6rem">Sin recetas sugeridas</div>
          <div class="etiqueta">Registra alimentos en el inventario para recibir ideas.</div>
        </div>""")
        return
    st.markdown("##### Recetas sugeridas para aprovechar primero lo que está por vencer")
    cols = st.columns(3, gap="medium")
    for i, (_, receta, tiene, urgentes, disponibles) in enumerate(sugerencias):
        chips = ""
        for ing in receta["ingredientes"]:
            clave = sin_tildes(ing)
            if ing in urgentes:
                chips += estado(f"{ing} · vence pronto", "#9A5B00", "#FFF4E0") + " "
            elif ing in tiene:
                chips += estado(ing, "#11804F", "#E7F7EF") + " "
            else:
                chips += estado(ing, GRIS, "#F1F4FA") + " "
        aviso = (f'<div class="etiqueta" style="margin-top:.5rem;color:#9A5B00;font-weight:600">'
                 f'Aprovecha: {", ".join(urgentes)}</div>') if urgentes else ""
        with cols[i % 3]:
            html(f"""
            <div class="card" style="margin-bottom:.4rem">
              <div class="titulo"><span class="icono-circ" style="background:#E8EFFF;color:{AZUL}">{ic(receta['icono'])}</span>{receta['nombre']}</div>
              <div class="etiqueta">{receta['min']} minutos · {len(tiene)} de {len(receta['ingredientes'])} ingredientes</div>
              <div style="margin-top:.6rem;line-height:2">{chips}</div>
              {aviso}
            </div>""")
            with st.expander("Preparación"):
                for n, paso in enumerate(receta["pasos"], 1):
                    st.markdown(f"{n}. {paso}")
                if st.button("Leer receta", icon=":material/volume_up:", key=f"leer-{i}"):
                    responder(f"{receta['nombre']}. " + " ".join(receta["pasos"]))


@st.fragment(run_every=2)
def pantalla_nevera():
    """Réplica en vivo de la LCD: muestra la confirmación de cada alimento registrado."""
    d = leer_estado().ultimo or {}
    html(f'<div class="card"><div class="titulo">{ic("developer_board")}Pantalla de la nevera</div>'
         f'{lcd_virtual(d.get("lcd1", "Sin conexión"), d.get("lcd2", ""), apagada=not d)}'
         f'<div class="etiqueta" style="margin-top:.6rem">Al agregar o sacar un alimento, la nevera lo confirma aquí.</div></div>')


# =====================================================================
tab_cam, tab_voz, tab_inv, tab_rec = st.tabs([":material/photo_camera: Cámara",
                                              ":material/mic: Voz y texto",
                                              ":material/inventory_2: Inventario",
                                              ":material/menu_book: Recetas"])

# ---------- Cámara ----------
def html_escaner():
    ruta = Path(__file__).resolve().parent.parent / "componentes" / "escaner.html"
    return (ruta.read_text(encoding="utf-8").replace("__TOPIC_CMD__", TOPIC_CMD)
            .replace("__TOPIC_INV__", TOPIC_INV).replace("__BROKER_WS__", BROKER_WS))


with tab_cam:
    origen = st.segmented_control("Origen de la imagen", ["Escáner en vivo", "Cámara", "Subir foto", "Enlace"],
                                  default="Escáner en vivo", label_visibility="collapsed")
    if origen == "Escáner en vivo":
        components.html(html_escaner(), height=640, scrolling=False)
        st.caption("Detección en tiempo real con TensorFlow.js (COCO-SSD). Para leche, huevos, queso y "
                   "otros productos sin categoría propia, usa la opción Cámara.")
    izq, der = st.columns([1.2, 1], gap="large")
    imagen = None
    with izq:
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
        elif origen == "Cámara":
            foto = st.camera_input("Ubica el alimento frente a la cámara y toma la foto")
            if foto is not None:
                imagen = Image.open(foto)
        if imagen is not None and origen != "Cámara":
            st.image(imagen, use_container_width=True)

    with der:
        if origen == "Escáner en vivo":
            pass
        elif imagen is None:
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
            ("list_alt", "Qué hay en la nevera"), ("event", "Cuándo vence la leche"), ("menu_book", "Qué puedo cocinar"),
            ("device_thermostat", "Cuál es la temperatura"), ("thermostat", "Baja la temperatura"),
            ("ac_unit", "Enciende el enfriamiento"), ("notifications_off", "Silencia la alarma"),
        ]
        filas = "".join(
            f'<div style="display:flex;align-items:center;gap:.7rem;padding:.55rem 0;border-bottom:1px solid #F1F4FA">'
            f'<span class="icono-circ" style="width:34px;height:34px;background:#F1F4FA;color:#14161F">{ic(i, 18)}</span>'
            f'<span style="font-weight:600">{t}</span></div>'
            for i, t in comandos
        )
        html(f'<div class="card"><div class="titulo">{ic("record_voice_over")}Comandos disponibles</div>{filas}</div>')
        st.write("")
        pantalla_nevera()

# ---------- Inventario ----------
@st.fragment(run_every=4)
def panel_inventario():
    # Alimentos registrados desde el escáner en vivo (llegan por MQTT)
    pendientes = leer_estado().pendientes
    while pendientes:
        agregar(pendientes.popleft(), notificar=False)
    items = inventario()
    cab1, cab2, cab3 = st.columns([2, 1, 1], vertical_alignment="center")
    n_tipos = len({sin_tildes(i["alimento"]) for i in items})
    cab1.markdown(f"#### {len(items)} producto{'s' if len(items) != 1 else ''} · {n_tipos} tipo{'s' if n_tipos != 1 else ''}")
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
        # Agrupa los alimentos repetidos: cantidad y fecha del más antiguo
        grupos = {}
        for item in items:
            clave = sin_tildes(item["alimento"])
            if clave not in grupos:
                grupos[clave] = {"alimento": item["alimento"], "fecha": item["fecha"], "cantidad": 0}
            grupos[clave]["cantidad"] += 1
            grupos[clave]["fecha"] = min(grupos[clave]["fecha"], item["fecha"])
        tiles, urgentes = [], []
        for item in grupos.values():
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
            cantidad_txt = f' <span style="color:#6B7185;font-weight:600">×{item["cantidad"]}</span>' if item["cantidad"] > 1 else ""
            tiles.append(
                f'<div class="tile">{ic(ICONOS.get(nombre, "kitchen"), 40, color)}'
                f'<div class="nom">{item["alimento"]}{cantidad_txt}</div>'
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


with tab_inv:
    panel_inventario()

with tab_rec:
    panel_recetas()
