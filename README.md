# Academic Integrity Audit

Herramienta local para auditoria academica, originalidad y trazabilidad experimental.

La propuesta no intenta afirmar "plagio confirmado" ni replicar Turnitin. Su enfoque es
explicable y trazable:

- calidad academica del documento;
- riesgo heuristico de estilo generico;
- evidencia experimental reproducible;
- similitud interna y local entre documentos;
- dashboard HTML, informe Markdown, CSV y JSON.

## Instalacion local

Desde la carpeta del proyecto:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

## Encender la app visual

La forma mas robusta en cualquier terminal:

```bash
scripts/run_local.sh
```

Apaga con `Ctrl+C`.

Arranque en segundo plano:

```bash
scripts/start_local.sh
```

Abre:

```text
http://localhost:8501
```

Para apagar:

```bash
scripts/stop_local.sh
```

Tambien puedes usar Make:

```bash
make run
make app
make stop
```

## Uso visual

### Flujo principal

Para la mayoria de usuarios, el flujo debe ser simple:

1. Subir un documento Word `.docx`.
2. Pulsar `Analizar documento`.
3. Revisar el dashboard.
4. Descargar el informe en ZIP, HTML, Markdown o JSON.

Con solo el `.docx`, la herramienta ya genera:

- riesgo heuristico de estilo generico;
- calidad academica estimada;
- auditoria por secciones;
- parrafos prioritarios;
- informe Markdown;
- dashboard HTML;
- CSV/JSON de resultados.

## Revision con IA local

La app puede anadir una capa de revision con un modelo local mediante Ollama. Esta
funcionalidad es opcional y gratuita: no requiere API keys, no usa servicios de pago y
no sube documentos a plataformas externas.

Cuando se activa, el modelo produce:

- riesgo estimado de uso intensivo de IA;
- riesgo estimado de plagio/originalidad;
- calidad academica estimada por modelo;
- motivos explicativos;
- recomendaciones de mejora;
- preguntas que podria hacer un profesor para verificar autoria y comprension.

### Requisitos

1. Tener Ollama instalado y arrancado en el ordenador.
2. Tener descargado al menos un modelo local.

La forma automatica recomendada:

```bash
scripts/setup_ai_local.sh llama3.1
```

Tambien:

```bash
make setup-ai
```

Este comando:

- instala Ollama con Homebrew si no existe;
- arranca Ollama como servicio local;
- comprueba que responde en `http://127.0.0.1:11434`;
- descarga el modelo indicado si falta.

Ejemplos de modelos gratuitos que se pueden probar:

```bash
ollama pull llama3.1
ollama pull mistral
ollama pull qwen2.5
```

En la app visual:

1. Abre la barra lateral.
2. Activa `Revision con IA local (Ollama)`.
3. Indica el modelo, por ejemplo `llama3.1`.
4. Mantiene la URL por defecto si Ollama esta en el mismo ordenador:

```text
http://127.0.0.1:11434
```

En CLI:

```bash
.venv/bin/academic-audit audit documento.docx \
  --ai-model llama3.1 \
  --out-dir audit_output_ai
```

Para que `scripts/run_local.sh` prepare tambien la IA antes de abrir la app:

```bash
ACADEMIC_AUDIT_SETUP_AI=1 scripts/run_local.sh
```

Puedes cambiar el modelo:

```bash
ACADEMIC_AUDIT_SETUP_AI=1 ACADEMIC_AUDIT_MODEL=mistral scripts/run_local.sh
```

### Limites importantes

Los porcentajes del modelo son estimaciones explicables, no pruebas definitivas.

- `Riesgo uso IA` no confirma que el texto haya sido escrito por IA.
- `Riesgo plagio/originalidad` no sustituye una busqueda externa tipo Turnitin.
- Si no se aporta corpus local, el modelo no puede saber si el texto existe en internet.
- La salida debe usarse como ayuda de revision, no como veredicto automatico.

La ventaja del modulo local es que aporta interpretacion y preguntas de defensa sin
enviar documentos fuera del ordenador.

### Opciones avanzadas

Las subidas adicionales no son necesarias para un ensayo normal. Estan pensadas para
trabajos con experimentos, practicas tecnicas, TFG/TFM, articulos o proyectos donde
hay datos externos que justifican los resultados.

#### CSV de resultados experimentales

Usalo cuando el trabajo tenga una tabla de resultados generada por un experimento.
Por ejemplo:

```text
results/summary/satellite_results.csv
```

La app lo usa para revisar trazabilidad experimental:

- numero de filas del experimento;
- planificadores, metodos o sistemas comparados;
- problemas, datasets o instancias evaluadas;
- ejecuciones resueltas o fallidas;
- completitud de metricas;
- campos ausentes como tiempo, coste, nodos, acciones o errores.

No intenta inventar metricas. Si el CSV no tiene un dato, el informe lo trata como
ausente.

#### ZIP con salidas crudas `.txt`

Usalo cuando tengas logs, salidas de terminal o respuestas originales de herramientas.
Por ejemplo:

```text
results/raw/*.txt
```

Como la app web no puede leer carpetas locales completas directamente desde el
navegador, esas salidas se suben comprimidas en un ZIP.

La app no interpreta todos los logs en profundidad. Su funcion principal es comprobar
que existen evidencias crudas asociadas al experimento. Esto ayuda a distinguir entre:

- una tabla final sin respaldo;
- una tabla final respaldada por salidas originales trazables.

Esta opcion es util para auditoria academica porque permite documentar que los
resultados no son solo una tabla redactada a mano.

#### ZIP con corpus local de documentos `.docx`

Usalo si quieres comparar el documento principal contra otros documentos locales.
Por ejemplo:

```text
corpus/
  entrega_v1.docx
  entrega_v2.docx
  trabajos_referencia.docx
```

La app busca similitud textual local entre parrafos. Esto puede servir para detectar:

- reutilizacion excesiva entre versiones;
- autocopia;
- coincidencias con documentos de referencia;
- fragmentos que requieren cita o revision.

El resultado no significa "plagio confirmado". Significa "coincidencia textual que
conviene revisar".

### Recomendacion de usabilidad

Para mantener el producto simple:

- usuario normal: subir solo `.docx`;
- usuario con experimento: anadir CSV;
- auditoria fuerte de experimento: anadir CSV + ZIP de logs;
- revision de originalidad local: anadir ZIP con corpus `.docx`.

## Uso basico

```bash
.venv/bin/academic-audit audit ../MEMORIA/Actividad3_RPA_Satellite_entrega_borrador/Paper_RPA_Actividad3_Satellite_revisado_v6.docx \
  --results-csv ../MEMORIA/Actividad3_RPA_Satellite_entrega_borrador/results/summary/satellite_results.csv \
  --raw-dir ../MEMORIA/Actividad3_RPA_Satellite_entrega_borrador/results/raw \
  --out-dir audit_output_v6
```

## Similitud local

Compara el documento objetivo contra otros `.docx` de una carpeta:

```bash
.venv/bin/academic-audit audit documento.docx --corpus-dir carpeta_con_docs --out-dir audit_output
```

## Docker

Para moverlo a otro ordenador con Docker instalado:

```bash
docker compose up --build
```

Abre:

```text
http://localhost:8501
```

Para apagar:

```bash
docker compose down
```

Los resultados quedan en:

```text
runs/
```

Si usas Docker y Ollama esta instalado en el ordenador anfitrion, en la app usa esta
URL de Ollama:

```text
http://host.docker.internal:11434
```

## Salidas

- `dashboard.html`: visualizacion principal.
- `quality_audit_report.md`: informe textual.
- `audit_summary.json`: resumen estructurado.
- `paragraph_audit.csv`: auditoria por parrafo.
- `section_audit.csv`: auditoria por seccion.
- `similarity_matches.csv`: coincidencias locales detectadas.

## Posicionamiento

Frente a herramientas externas de similitud, esta propuesta se puede vender como
auditoria academica privada y explicable. No sube documentos a servicios externos y
puede funcionar con repositorios locales, rubricas, resultados experimentales y
evidencias crudas.
