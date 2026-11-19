# Métricas de evaluación

Generado: 2026-11-18 21:45

Corridas registradas: **54**. Evaluación manual disponible: **sí**.

## Resumen por configuración

| configuracion   |   n |   evidencia_recuperada_6 |   evidencia_contexto_6 |   correccion_6 |   correccion_pct | respaldo_citas   |   respaldo_citas_pct |   abstencion_3 |   abstencion_detectada_3 |   falsas_abstenciones_6 |   tiempo_medio_s |   tiempo_mediana_s |   tiempo_p95_s |   tokens_prompt_medio |   costo_total_usd |   errores |
|:----------------|----:|-------------------------:|-----------------------:|---------------:|-----------------:|:-----------------|---------------------:|---------------:|-------------------------:|------------------------:|-----------------:|-------------------:|---------------:|----------------------:|------------------:|----------:|
| C0              |   9 |                      nan |                    nan |              2 |             33.3 | no aplica        |                  nan |              3 |                        0 |                       0 |            1.553 |              1.477 |          2.02  |                 148.8 |          0.000647 |         0 |
| E1              |   9 |                        3 |                      3 |              2 |             33.3 | 4/4              |                  100 |              3 |                        3 |                       3 |            1.337 |              1.214 |          1.899 |                2169.7 |          0.003047 |         0 |
| E2              |   9 |                        4 |                      4 |              3 |             50   | 4/5              |                   80 |              3 |                        3 |                       2 |            1.452 |              1.045 |          3.598 |                2289.2 |          0.007118 |         0 |
| R0              |   9 |                        4 |                      4 |              3 |             50   | 4/5              |                   80 |              3 |                        3 |                       3 |            2.772 |              1.56  |          8.992 |                2166   |          0.003032 |         0 |
| R1              |   9 |                        3 |                      3 |              3 |             50   | 5/5              |                  100 |              3 |                        3 |                       3 |            1.258 |              1.192 |          1.676 |                1386.8 |          0.002076 |         0 |
| R2              |   9 |                        5 |                      5 |              4 |             66.7 | 6/6              |                  100 |              3 |                        3 |                       1 |            1.344 |              1.318 |          1.783 |                2069.7 |          0.003044 |         0 |

## Definiciones

- **Cobertura de evidencia (recuperada / contexto):** preguntas respondibles cuyos pasajes necesarios aparecen en los fragmentos recuperados y, además, quedan dentro del contexto enviado al LLM. Se reporta sobre 6.
- **Corrección:** respuestas correctas y completas frente a la referencia, sobre 6. Una respuesta parcial o una abstención cuenta como incorrecta.
- **Respaldo de citas:** proporción de respuestas sustantivas RAG cuyas afirmaciones centrales están respaldadas por los pasajes citados.
- **Abstención apropiada:** preguntas sin respuesta documental en las que el sistema reconoce que no puede responder y no añade una respuesta sin respaldo, sobre 3.

## Nota metodológica

La cobertura, la abstención detectada, las citas y los tiempos son cálculos automáticos. La corrección y el respaldo de citas se diligenciaron tras leer cada respuesta y contrastarla con la referencia y los fragmentos citados; por eso el informe puede auditar cada fila de `tabla_resultados.csv`.