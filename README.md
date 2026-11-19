# Proyecto RAG · Normativa académica del programa de Administración de Sistemas Informáticos

**Curso:** Sistemas Inteligentes Computacionales  
**Profesor:** Néstor Darío Duque Méndez  
**Autores:** Manuela Gama Peña · Franklin Libreros  
**Universidad Nacional de Colombia — Sede Manizales**

Sistema de generación aumentada por recuperación (RAG) que responde preguntas sobre el programa de Administración de Sistemas Informáticos, su normativa, su calendario y su proceso de matrícula. Recupera fragmentos con localizador verificable, responde en español con citas `[F#]` y se abstiene cuando la evidencia es insuficiente.

## Resultados del protocolo

| Config. | Cobertura | Corrección | Citas | Abstención | Costo 9 preguntas |
|---|---:|---:|---:|---:|---:|
| R0 · Base | 4/6 | 3/6 | 4/5 | 3/3 | USD 0,003032 |
| R1 · Fragmentación | 3/6 | 3/6 | 5/5 | 3/3 | USD 0,002076 |
| R2 · Híbrida | **5/6** | **4/6** | **6/6** | **3/3** | USD 0,003044 |
| C0 · Sin RAG | — | 2/6 | no aplica | 3/3 | USD 0,000647 |
| E1 · Otro embedding | 3/6 | 2/6 | 4/4 | 3/3 | USD 0,003047 |
| E2 · Otro LLM | 4/6 | 3/6 | 4/5 | 3/3 | USD 0,007118 |

Las 54 corridas (36 principales + 18 de experimentos) se ejecutaron con llamadas reales a OpenRouter, sin errores de API. La configuración recomendada es **R2**: fragmentos 400/60, búsqueda híbrida densa + TF-IDF con fusión RRF, k=6, embeddings multilingües y GPT-4o-mini.

## Requisitos

- Python 3.12 (probado en Windows 11; también funciona en Linux/Colab).
- Conexión a Internet para descargar modelos de Hugging Face y llamar a OpenRouter.
- Una clave de OpenRouter.
- Dependencias de `requirements.txt`: `pymupdf`, `python-docx`, `sentence-transformers`, `numpy`, `faiss-cpu`, `scikit-learn`, `tiktoken`, `openai`, `python-dotenv`, `pandas`, `matplotlib`, `tabulate`, `jupyter`.

## Instalación

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

Edite `.env` y escriba su clave:

```dotenv
OPENROUTER_API_KEY=sk-or-v1-...
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
OPENROUTER_MODEL=openai/gpt-4o-mini
OPENROUTER_MODEL_ALTERNO=google/gemini-2.5-flash
TEMPERATURA=0.0
MAX_TOKENS_SALIDA=500
```

> **Nunca** suba `.env` al repositorio ni lo incluya en la carpeta de entrega. `.gitignore` ya lo excluye. Si una clave se compartió en un chat o en un archivo público, rótela antes de usarla.

## Ejecución

```powershell
python -m src.main ingesta
python -m src.main indexar --configs R0,R1,E1
python -m src.main consultar --config R2 --pregunta "¿Cuándo inician las clases del segundo periodo de 2026?"
python -m src.main evaluar --configs R0,R1,R2,C0
python -m src.main experimentos
python scripts/evaluar_manualmente.py
python -m src.main metricas
python -m src.figuras
```

La evaluación es reanudable: cada corrida se guarda en `resultados/corridas.jsonl`. Si una llamada falla, se registra el error y puede repetirse sin duplicar las corridas ya completadas.

El cuaderno `Proyecto_RAG.ipynb` reproduce el flujo completo y solicita la clave con `getpass` o desde los secretos de Colab; no la escribe en el archivo.

## Corpus

`data/documentos_fuente/` contiene seis archivos públicos en dos formatos:

| Archivo | Formato real | Contenido |
|---|---|---|
| `calendario-academico-pregrado.pdf` | PDF | Calendario académico 2026 |
| `estatuto_estudiantil.pdf` | PDF | Estatuto Estudiantil |
| `faq_estudiantil.md` | DOCX | Preguntas frecuentes del programa |
| `InstructivoMatriula.pdf` | PDF | Instructivo de matrícula |
| `MallaCurricularAcuerdo05del2023.pdf` | PDF | Malla curricular |
| `programa_admon_sistemas..pdf` | PDF | Ficha del programa |

`faq_estudiantil.md` es en realidad un DOCX: el cargador detecta el formato por los primeros bytes (`PK`), no por la extensión. Los localizadores son página en PDF y sección/párrafo en DOCX.

## Configuraciones

| ID | Cambio | Chunk | k | Búsqueda | Embeddings | LLM |
|---|---|---:|---:|---|---|---|
| R0 | Base | 400/60 | 6 | Densa | Multilingüe MiniLM-L12 | GPT-4o-mini |
| R1 | Fragmentación | 200/30 | 6 | Densa | Multilingüe MiniLM-L12 | GPT-4o-mini |
| R2 | Recuperación | 400/60 | 6 | Híbrida RRF | Multilingüe MiniLM-L12 | GPT-4o-mini |
| C0 | Sin RAG | — | 0 | — | — | GPT-4o-mini |
| E1 | Otro embedding | 400/60 | 6 | Densa | all-MiniLM-L6-v2 | GPT-4o-mini |
| E2 | Otro LLM | 400/60 | 6 | Densa | Multilingüe MiniLM-L12 | Gemini 2.5 Flash |

Todas las comparaciones fijan corpus, preguntas, temperatura (0,0), límite de salida (500 tokens), plantilla de instrucciones y límite de contexto (3.500 tokens).

## Paquete de evaluación

- `data/preguntas_evaluacion.json`: 9 preguntas con respuesta esperada, evidencia y criterios.
- `data/hipotesis.json`: H1–H5 registradas antes de las corridas finales.
- `resultados/corridas.jsonl`: registro completo de las 54 corridas.
- `resultados/tabla_resultados.csv`: tabla plana con métricas automáticas.
- `resultados/evaluacion_manual.csv`: corrección, citas, abstención y notas por corrida.
- `resultados/resumen_configuraciones.csv`: resumen por configuración.
- `resultados/metricas_evaluacion.md`: métricas y definiciones.
- `resultados/revision_respuestas.md`: las 54 respuestas completas para auditoría.
- `resultados/figuras/`: figuras del informe.

## Informe

`informe/Informe_Proyecto_RAG.docx` contiene portada, caso de uso, corpus, arquitectura, configuraciones, preguntas, hipótesis, resultados, análisis, recomendación, limitaciones, declaración de uso de IA, referencias y anexos con las 54 corridas, los prompts y la lista de verificación del enunciado.

## Limitaciones principales

- Nueve preguntas y un solo corpus: los resultados son descriptivos, no inferenciales.
- La valoración de corrección, citas y abstención fue manual, realizada por los autores; no hubo doble anotación independiente.
- M1 (documentos de matrícula + Artículo 13) no se resolvió en ninguna configuración. Requiere metadatos por artículo o descomposición de la consulta.
- El detector automático de abstención no reconoce todas las fórmulas; C0 usa «no tengo acceso» y el detector lo marca como 0/3 aunque la revisión manual lo valore 3/3.
- El proveedor no expone semilla; a temperatura 0,0 la variación es baja, pero no hay reproducibilidad bit a bit.
- La extracción de tablas del calendario puede alterar el orden de lectura.

## Estructura

```text
proyecto_rag/
  data/
    documentos_fuente/
    preguntas_evaluacion.json
    hipotesis.json
  src/
    config.py, carga_documentos.py, procesamiento_texto.py, embeddings.py
    base_vectorial.py, recuperacion.py, generacion_respuestas.py
    evaluacion.py, experimentos.py, figuras.py, main.py
  scripts/
    crear_notebook.py, revisar_respuestas.py, evaluar_manualmente.py
    generar_informe.py
  resultados/
  informe/
  Proyecto_RAG.ipynb
  requirements.txt
  .env.example
  README.md
```

## Uso de inteligencia artificial

Se utilizó un asistente de IA integrado en OpenCode como apoyo para programar, depurar, redactar y revisar la consistencia del informe. Todas las respuestas se contrastaron con el corpus y se valoraron manualmente en `evaluacion_manual.csv`; las 54 corridas son reales y no se inventaron resultados. La declaración completa está en la sección 12 del informe.
