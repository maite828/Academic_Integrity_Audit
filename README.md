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

La app permite:

- subir un documento Word `.docx`;
- subir opcionalmente un CSV de resultados;
- subir opcionalmente un ZIP con salidas crudas `.txt`;
- subir opcionalmente un ZIP con documentos `.docx` para similitud local;
- ejecutar la auditoria;
- descargar ZIP, HTML, Markdown y JSON.

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
