# Aquí va el modelo de Teachable Machine

1. Entra a https://teachablemachine.withgoogle.com → **Proyecto de imagen** → modelo estándar.
2. Crea una clase por alimento (por ejemplo: `Leche`, `Huevos`, `Manzana`, `Queso`)
   y una clase **`Nada`** con fotos del fondo sin ningún alimento.
3. En cada clase toma unas 50–100 fotos con la cámara (distintos ángulos y luz).
4. Clic en **Entrenar modelo**.
5. **Exportar modelo** → pestaña **TensorFlow** → **Keras** → Descargar.
6. Descomprime el zip y copia aquí estos dos archivos:
   - `keras_model.h5`
   - `labels.txt`

Usa los nombres de los alimentos como aparecen en `DURACION_DIAS` dentro de
`paginas/despensa.py` (o agrega los tuyos allí) para que la app calcule cuántos días duran.
