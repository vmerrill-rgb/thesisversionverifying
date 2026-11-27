# Polarización legislativa en Chile, 2010–2026

Integré los cuatro archivos en un flujo reproducible para estimar Dalton y la desviación absoluta media de centroides partidarios (MAD). La ejecución usa la [versión pública de Fábrega en Harvard Dataverse](https://doi.org/10.7910/DVN/FOXOIT); no supone que tus CSV y Excel locales sean idénticos a esa versión. El mayor cambio nacional en las series principales es el aumento de 2014–18 a 2018–22. En cambio, la dirección del cambio posterior depende de cómo se trate a los independientes. El período 2022–26 contiene votaciones solo hasta junio de 2025 ([documentación de la base](https://pmc.ncbi.nlm.nih.gov/articles/PMC12595135/)).

## De los cuatro archivos a una sola base

1. **Fijé el calendario antes de hacer los cruces.** Se preservan `Id`, `Name`, `Period`, `dim_ideology`, `quant_parties` y `party_1` a `party_4`. Se conserva la forma original de `Period` en `Period_fuente`. La fila de análisis es diputado-persona por legislatura, no candidato-comuna ni escaño. Los cruces de auxiliares preservan el número y orden de las filas del archivo long; se rechazan claves duplicadas. Las fechas de inicio y término siguen el [calendario de la Cámara](https://opendata.camara.cl/camaradiputados/WServices/WSLegislativo.asmx/retornarPeriodosLegislativos).

   | Elección | Legislatura que inicia | `Period` | Índice de esta entrega |
   |---|---|---|---|
   | 2009 | 2010–2014 | `Periodo_3` | Sí |
   | 2013 | 2014–2018 | `Periodo_4` | Sí |
   | 2017 | 2018–2022 | `Periodo_5` | Sí |
   | 2021 | 2022–2026 | `Periodo_6` | Sí, con corte en junio de 2025 |
   | 2025 | 2026–2030 | `Periodo_7` | No: sin estimaciones de esa legislatura en esta versión |

   `Periodo_1` y `Periodo_2` se conservan en la base de composición, pero no entran en los índices. El módulo de Excel reconoce `Cargo`, los tres campos de nombre y la geografía por encabezado, no por número de columna. Reduce repeticiones por comuna, marca candidatos ambiguos y nunca une al panel solo por período. Por diseño, una candidatura no reemplaza la geografía de un escaño ni una etiqueta de afiliación legislativa.

2. **Concilié identidades con la fuente de cada variable.** Las matrices de votos y militancias publicadas se enlazan por `Id`–`Period`, con comprobación adicional del nombre. En 2018–22, Pablo Prieto Lorca se reconcilia de `DiputadoId=1064` a `Id=209`, tal como hace el [código de estimación del depósito](https://doi.org/10.7910/DVN/FOXOIT); ambos identificadores quedan visibles. El cruce con los padrones externos se hace por nombre y legislatura, no por igualdad de ID entre sistemas. Cada distrito enlazado conserva su fuente, el nombre publicado y el método.

3. **Separé la codificación original de la variante corregida.** `salida` usa el último `party_n` no vacío; `unico` exige un único campo no vacío y `quant_parties=1`. El [código de enriquecimiento de la base](https://doi.org/10.7910/DVN/FOXOIT) construye `party_n` a partir del orden de aparición de siglas distintas, sin filtrar los tramos por legislatura. Por eso `salida_fechada` usa el último inicio registrado de una afiliación que intersecta la ventana analizada, truncada el 30 de junio de 2025 para `Periodo_6`. `unico_fechado` retiene quienes tienen una sola sigla documentada dentro de esa ventana, no quienes necesariamente militaron en ella todos los días. Ninguna variante reasigna retrospectivamente cada voto a la militancia de la fecha de ese voto. Se marcan empates y solapamientos; si hay dos siglas con el mismo último inicio, la afiliación queda sin resolver.

4. **Reconstruí la geografía de representación.** Usé los distritos de los padrones históricos [2010–14](https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle?inicio=2010-03-11&fin=2014-03-10&periodo=1990-2026&cam=Diputados), [2014–18](https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle?inicio=2014-03-11&fin=2018-03-10&periodo=1990-2026&cam=Diputados), [2018–22](https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle?inicio=2018-03-11&fin=2022-03-10&periodo=1990-2026&cam=Diputados) y [2022–26](https://www.bcn.cl/historiapolitica/corporaciones/periodo_detalle?inicio=2022-03-11&fin=2026-03-10&periodo=1990-2026&cam=Diputados), contrastados con [Cámara Open Data](https://opendata.camara.cl/camaradiputados/pages/diputado/retornarDiputadosXPeriodo.aspx), [Servel, electos de 2017](https://www.servel.cl/wp-content/uploads/2022/12/Candidatos_2017_Electos_14-03-2018.xlsx), el [directorio de la Cámara de junio de 2025](https://www.camara.cl/camara/doc/listado2022.pdf) y fichas individuales. Si dos fuentes asignan distritos distintos, no se elige uno automáticamente. Los distritos se convierten a región con el [esquema histórico de la Ley 18.700](https://nuevo.leychile.cl/servicios/Consulta/Exportar?radioExportar=Normas&exportar_formato=pdf&nombrearchivo=Ley-18700_06-MAY-1988&exportar_con_notas_bcn=True&exportar_con_notas_originales=True&hddResultadoExportar=30082.2011-10-17.0.0%23) y el [esquema posterior a la reforma](https://www.bcn.cl/leychile/Navegar?idNorma=1108229&idParte=9836521). Conservo el distrito y la región asignada; para el panel armonizado uso Biobío y Ñuble como una sola unidad en los cuatro tramos. La región mide representación electoral, no residencia.

5. **Calculé sobre las personas con ideología y partido para cada variante.** Para cada celda se calculan el centroide ideológico de cada grupo \(c_g\), su cuota \(s_g=n_g/n\) y el centroide ponderado \(\mu=\sum_g s_gc_g\). Cada diputado aporta una unidad, incluidos los reemplazantes, sin ponderar por asistencia ni duración en el escaño. `IND` se mantiene como categoría administrativa, no como partido coherente, y se muestra una sensibilidad que lo excluye.

   - **Dalton legislativo**: \(\sqrt{\sum_g s_g(c_g-\mu)^2}/R\). Adapta [Dalton (2008)](https://sites.socsci.uci.edu/~rdalton/archive/CPS2008.pdf) a cuotas de diputados observados, en lugar de votos electorales. El valor `dalton_raw` conserva la dispersión en unidades originales.
   - **MAD entre centroides**: `mad_party` promedia \(\lvert c_g-\bar c\rvert\) con igual peso para cada grupo, donde \(\bar c\) es la media no ponderada de centroides. `mad_party_normalized` divide por \(R\). También se entrega el MAD ponderado alrededor de \(\mu\), que responde a la dispersión entre grupos desde la perspectiva del diputado promedio. Ninguno es la mediana de desviaciones absolutas.
   - **Escala común**: \(R=1.735836\), la mitad del rango observado \([-1.929184,\ 1.542487]\) en los cuatro períodos objetivo. Los extremos también son los de toda la edición pública ([Dataverse](https://doi.org/10.7910/DVN/FOXOIT)). La escala es común a períodos, regiones y modos; no se renormaliza en cada celda. Si hay menos de dos grupos, Dalton y MAD se dejan sin estimar: un cero algebraico no mostraría una comparación entre grupos.

## Conciliación y resultados nacionales

La cuadrícula long de la [edición pública](https://doi.org/10.7910/DVN/FOXOIT) contiene 2.574 filas y 429 IDs, con 429 filas nominales en cada período. Las filas vacías de ideología no representan ausencias; es la matriz de cada período, no la cuadrícula long, la que define la cobertura observada. Los conjuntos de IDs con punto ideológico y con fila en la matriz coinciden exactamente en los cuatro tramos. Los 564 casos objetivo también quedaron enlazados a un distrito; esto verifica el universo publicado, no que la edición incluya todo diputado o voto posible hasta el fin de cada legislatura.

| Período | Escaños nominales | Personas en matriz y con ideología | Con distrito | Sin partido posicional | Partido distinto con fechas¹ |
|---|---:|---:|---:|---:|---:|
| 2010–14 | 120 | 123 | 123 | 0 | 18 |
| 2014–18 | 120 | 121 | 121 | 0 | 12 |
| 2018–22 | 155 | 163 | 163 | 1 | 26 |
| 2022–26, corte jun. 2025 | 155 | 157 | 157 | 0 | 4 |

¹ Entre quienes tienen partido en ambas reglas. Cálculos sobre [Dataverse](https://doi.org/10.7910/DVN/FOXOIT); escaños según la [ley histórica](https://nuevo.leychile.cl/servicios/Consulta/Exportar?radioExportar=Normas&exportar_formato=pdf&nombrearchivo=Ley-18700_06-MAY-1988&exportar_con_notas_bcn=True&exportar_con_notas_originales=True&hddResultadoExportar=30082.2011-10-17.0.0%23) y la [ley reformada](https://www.bcn.cl/leychile/Navegar?idNorma=1108229&idParte=9836521). Una legislatura puede acumular más personas que escaños simultáneos; por ejemplo, el [listado 2022–26 de la Cámara](https://www.camara.cl/camara/doc/listado2022.pdf) registra los reemplazos de Mercedes Bulnes y Tomás de Rementería. En 2018–22, la variante fechada también recupera `IND` para Prieto, el único punto sin partido posicional.

Las cuotas suman uno en cada celda, los conteos partidarios suman el total de la muestra y la varianza poblacional total se reconcilia exactamente como varianza entre grupos más varianza dentro de grupos, dentro de tolerancia numérica. Ordené las cotas invertidas sin cambiar los puntos: 121 y 157 intervalos dinámicos en 2014–18 y 2022–26, respectivamente, y 121 y 163 intervalos del modelo bayesiano en 2014–18 y 2018–22, respectivamente, en el [archivo de estimaciones](https://doi.org/10.7910/DVN/FOXOIT). Se conservaron las cotas originales y se comprobó que los 564 puntos dinámicos objetivo quedan contenidos tras ordenarlas. No se usó la mera disponibilidad de esas cotas para seleccionar los puntos.

| Período | Dalton posicional `salida` | Dalton `salida_fechada` | MAD no ponderado normalizado, fechado | Dalton fechado sin `IND` |
|---|---:|---:|---:|---:|
| 2010–14 | 0,3206 | 0,3311 | 0,2490 | 0,3394 |
| 2014–18 | 0,2682 | 0,2718 | 0,2125 | 0,2861 |
| 2018–22 | 0,3896 | 0,4081 | 0,3452 | 0,4315 |
| 2022–26, corte jun. 2025 | 0,3847 | 0,3850 | 0,3027 | 0,4474 |

Cálculos sobre [Dataverse](https://doi.org/10.7910/DVN/FOXOIT). De 2014–18 a 2018–22, Dalton fechado sube **0,1363**, y el aumento también aparece en la codificación original, en las variantes de partido único y al excluir `IND`. El último cambio va de −0,0231 con `IND` a +0,0159 sin ellos, con 43 independientes excluidos del último período frente a 21 del anterior. Esto identifica sensibilidad a la definición y composición de la muestra, no un efecto atribuible a los independientes. Para una tesis, usaría la serie fechada como principal y mostraría `salida` y la exclusión de `IND` en la misma tabla.

## Qué regiones usar y qué hacer con las pequeñas

**Recomiendo siete unidades para un panel regional directo y balanceado**: Valparaíso, Metropolitana, O’Higgins, Maule, Biobío y Ñuble, La Araucanía y Los Lagos. Es el conjunto máximo que cumple simultáneamente, en los cuatro períodos, al menos ocho personas, cobertura de al menos 85% de las personas mapeadas, dos grupos con al menos dos personas cada uno y un cambio máximo de 0,12 en Dalton al retirar cualquier diputado. Exijo que cada retiro siga permitiendo estimar el índice. Estos son umbrales de publicación descriptiva, no criterios de significancia.

| Período | Personas en el panel común | % de la muestra nacional | Dalton al reunir sus diputados² |
|---|---:|---:|---:|
| 2010–14 | 97 | 78,9% | 0,3219 |
| 2014–18 | 94 | 77,7% | 0,2668 |
| 2018–22 | 128 | 78,5% | 0,4090 |
| 2022–26, corte jun. 2025 | 123 | 78,3% | 0,3951 |

² Se vuelven a estimar los centroides con los diputados reunidos; no es el promedio de siete Dalton regionales. Cálculos con las estimaciones de [Dataverse](https://doi.org/10.7910/DVN/FOXOIT) y las asignaciones de distrito documentadas en el cruce adjunto.

- **Por qué no recortar por desviación estándar ideológica**: esa desviación contiene parte del fenómeno que se quiere medir. Una región diversa puede tener datos sólidos, y una homogénea puede tener solo dos personas. Prefiero clasificar por tamaño, cobertura, replicación de cada grupo y sensibilidad a observaciones individuales. Para otro uso inferencial, conviene fijar esa regla antes de mirar la variable dependiente.
- **Qué unidades quedan fuera**: Arica y Parinacota, Tarapacá, Aysén y Magallanes tienen entre 2 y 4 personas por período; Antofagasta, Atacama y Los Ríos, entre 4 y 5. Coquimbo llega a 6–7, pero solo en 2014–18 tiene dos grupos con al menos dos legisladores. El perfil flexible (mínimo 6, cobertura 85%, máximo 0,16) retiene las mismas siete unidades; el estricto (10, 95%, 0,08) retiene cuatro. Como ejemplo de fragilidad, en Tarapacá 2022–26 hay tres personas, tres grupos y un cambio de hasta 0,495 al retirar una de ellas. Cálculos sobre [Dataverse](https://doi.org/10.7910/DVN/FOXOIT) y el cruce con el [directorio de la Cámara](https://www.camara.cl/camara/doc/listado2022.pdf).
- **Qué mostrar si necesitas todas las regiones**: reporta el índice directo con advertencia o déjalo fuera de la tabla principal, y muestra aparte una versión que combina el centroide local de cada grupo con el centroide del mismo grupo en el resto del país. Se mantienen las cuotas locales; la referencia externa pesa \(4/(n_g+4)\) cuando existe. Si no existe, se conserva el centroide local y se publica qué cuota sí tuvo referencia. También se entrega un proxy solo con centroides externos cuando todos los grupos tienen referencia, y un MAD de diputados respecto a su propio grupo fuera de la región. Son medidas diferentes: sirven como sensibilidad o como exposición a la composición partidaria, no como reemplazos indistinguibles del Dalton regional.
- **Implicación para la tesis**: el panel directo tiene 28 celdas y solo siete unidades geográficas. Úsalo para comparar trayectorias, no para obtener precisión aparente replicando el índice a nivel comuna. Si el modelo exige cobertura completa, distingue el proxy de composición del índice local y evalúa cuánto cambia la conclusión con cada definición.

## Validación estadística y límites de interpretación

- **Convergencia entre modelos**: dentro de cada período, `dim_ideology` y W-NOMINATE tienen Spearman de 0,816 a 0,898; frente al modelo bayesiano, de 0,841 a 0,901. Se calculan sobre pares completos de la [base publicada](https://doi.org/10.7910/DVN/FOXOIT). Esto respalda ordenamientos intraperíodo similares, no igualdad de escalas ni invariancia temporal.
- **Cambios de composición**: restringí los contrastes a los mismos IDs en pares consecutivos. Entre 2014–18 y 2018–22 se mantiene un aumento de 0,0971 con 63 presentes en ambos; para 2022–26, el contraste entre 65 continuos es −0,1339. En los continuos, la correlación de rango entre períodos es de 0,814 a 0,912, pero cambia su desviación estándar. La prueba no separa cambios de conducta, agenda de votación y métrica latente ([metodología de estimación de Fábrega](https://pmc.ncbi.nlm.nih.gov/articles/PMC12595135/)).
- **Remuestreo de composición**: 3.999 réplicas multinomiales a nivel de ID. Cada persona recibe el mismo peso aleatorio en todos sus períodos para preservar su dependencia. Condicionalmente a las ubicaciones ideológicas, el rango y los partidos publicados, los percentiles 2,5–97,5 del cambio fechado son \([-0,0870;\,-0,0280]\), \([0,1004;\,0,1713]\) y \([-0,0686;\,0,0256]\) en los tres pares sucesivos calculados con la [edición pública](https://doi.org/10.7910/DVN/FOXOIT). Son un diagnóstico de sensibilidad a la composición, no intervalos que propaguen la incertidumbre del modelo de ideología ni intervalos para una población electoral. El promedio 2018–26 menos 2010–18, +0,0951, es descriptivo.
- **Qué retiré**: pruebas de quiebre tipo Chow o pseudo-sup-Wald con solo cuatro períodos; remuestreo independiente por período que ignora diputados repetidos; simulación de errores ideológicos independientes a partir de cotas marginales; y correlación entre Dalton crudo y normalizado con escala fija, que es mecánica. No hay identificación causal de la reforma de escaños en estas comparaciones. Para estimar incertidumbre del índice latente harían falta extracciones conjuntas del modelo o reestimaciones que preserven la dependencia, y para una interpretación causal harían falta un diseño y supuestos aparte.

## Revisión de asistencia

Reproduje el cálculo del notebook: `Asistencia = (Afirmativo + En_Contra) / Total_Votaciones`. También reproduje el denominador de 3.393 y los cinco primeros cocientes guardados para 2022–26 al cruzar sus nombres con la [matriz pública](https://dataverse.harvard.edu/api/access/datafile/11752366?format=original). Las categorías de cada diputado suman las columnas de votación, y los conteos de período suman personas por votaciones.

| Período | Votaciones incluidas | Media binaria | P10 / mediana / P90 | Media con abstenciones |
|---|---:|---:|---:|---:|
| 2010–14 | 3.082 | 75,15% | 64,12% / 76,35% / 87,11% | 77,29% |
| 2014–18 | 3.267 | 77,35% | 64,62% / 77,99% / 90,33% | 80,97% |
| 2018–22 | 3.520 | 77,54% | 58,70% / 81,62% / 90,91% | 81,16% |
| 2022–26, corte jun. 2025 | 3.393 | 77,59% | 58,07% / 80,78% / 92,22% | 81,66% |

Cálculos sobre las [matrices de Fábrega](https://doi.org/10.7910/DVN/FOXOIT). El casillero vacío o `NA` no distingue ausencia de estar fuera del ejercicio del cargo. La fracción binaria está por debajo de 10% para una persona en 2014–18 y dos en 2022–26 en las [matrices públicas](https://doi.org/10.7910/DVN/FOXOIT). Una fracción así puede reflejar menos tiempo de exposición y no es evidencia de baja asistencia oficial. Para medirla como tal se necesitan fechas efectivas por diputado, fechas por votación y una fuente que distinga elegibilidad, dispensas y asistencia. No ponderé los índices con este cociente.

## Reproducción y archivos

```bash
python -m pip install -r requirements.txt
python -m unittest -v
python indices_diputados_chile.py --publico --out mi_reproduccion
```

El cálculo público reconoce la geografía adjunta solo si el archivo long coincide byte por byte con la edición fijada. El programa descarga nueve archivos de [Dataverse](https://doi.org/10.7910/DVN/FOXOIT), verifica SHA-256 y registra las entradas y la semilla en `manifiesto.json`. Se puede reutilizar la descarga mediante `--cache`; usa una carpeta de salida nueva o vacía. Se probaron siete casos unitarios e integrados, incluido un Excel de prueba con la estructura aportada, y dos ejecuciones de la versión pública con la misma configuración produjeron archivos idénticos.

| Archivo | Para qué sirve |
|---|---|
| `base_composicion.csv`, `conciliacion_periodos.csv`, `incidencias_identidad.csv` | Panel completo, denominadores y discrepancias de clave. Si incidencias solo tiene encabezado, no hubo diferencias de conjuntos en los cruces comprobados. |
| `indices_nacionales.csv`, `partidos_nacionales.csv`, `sensibilidad_sin_IND.csv` | Cuatro atribuciones, Dalton, MAD, dispersión y tamaño de cada grupo. |
| `indices_regionales.csv`, `soporte_partido_region.csv` | Índices directos, proxies, diagnósticos de soporte y alertas por grupo y región. |
| `panel_regional_comun.csv`, `indices_pool_panel_comun.csv`, `sensibilidad_soporte_regional.csv` | Selección de unidades y sensibilidad a umbrales. |
| `contrastes_dalton.csv`, `continuos_escala_diagnostico.csv`, `convergencia_modelos_por_periodo.csv` | Diferencias, sensibilidad de composición y concordancia entre modelos. |
| `asistencia_por_periodo.csv` | Conteos por código, denominadores y distribución de los cocientes. |
| `distritos_diputados_2010_2026.csv`, `reconstruir_distritos.py` | Cruce con evidencia por fila y código auxiliar para reconstruirlo desde los padrones. |

Para bases locales, sustituye el insumo que corresponda con `--ideologia ARCHIVO`, `--matriz 2010=ARCHIVO`, `--militancia 2010=ARCHIVO` o `--geografia ARCHIVO`. Las opciones de matrices y militancias se repiten por período. `--publico` puede completar los demás insumos desde el depósito; omítelo para una ejecución solo local. Para auditar las candidaturas, usa `--eleccion 2013=ARCHIVO` y/o `--eleccion 2025=ARCHIVO`; el programa espera `Votación por comuna` con encabezado en la fila 7 de Excel, modificable en la CLI. Un enlace electoral se reporta como candidatura vinculada, no como prueba de que ganó. El archivo 2025 queda en `Periodo_7` y no rellena ideología ni geografía del `Periodo_6`.

Para reauditar el cruce territorial no necesitas volver a descargar los padrones: el CSV identifica la evidencia por fila. Si quieres regenerarlo, `reconstruir_distritos.py` recibe por `--raw` una carpeta con el texto de los cuatro listados BCN (`bcn2010.txt`, `bcn2014.txt`, `bcn2018.txt`, `bcn2022.txt`), los XML históricos de la Cámara (`roster6.xml`, `roster8.xml`) y el Excel oficial de electos de 2017 (`servel2017.xlsx`). Pásale `--ideologia` con el CSV long y `--out` con el nombre del cruce nuevo; la extracción de texto del PDF de la Cámara de 2022–26 entra por la entrada estándar. Dado que esos directorios pueden actualizarse o cambiar de formato, compara el nuevo cruce con el adjunto antes de sustituirlo.

Queda pendiente contrastar tus dos Excel efectivos, `2013_11_Diputados_Datos_Eleccion.xlsx` y `2025_11_Diputados_Datos_Eleccion_v2.xlsx`, y el CSV long o las matrices locales si son ediciones distintas. El esquema electoral se probó con un libro sintético; no se verificaron ni se imputaron datos de esos archivos no adjuntados.
