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
