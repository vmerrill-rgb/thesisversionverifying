# Validación estadística: Índice de Dalton, Chile 2002-2026

## 1. Entorno y parámetros

- Python 3.13.5 | numpy 2.3.3 | pandas 2.3.2 | scipy 1.17.0 | Windows-11-10.0.26300-SP0
- Semilla fija: 20261007 | B(cluster) = 1000, B(período) = 1000, B(medición) = 1000, alpha = 0.05

## 2. Diagnóstico ETL

- filas_totales: 2574
- filas_duplicadas_Id_Period: 0
- anchos_IC_negativos: 522
- anchos_IC_cero: 0
- quant_parties_inconsistente: 0
- filas_con_ideologia_sin_partido: 1

Cobertura por período:

```
           n_total  n_validos   pct
Period                             
Periodo_1      429        121  28.2
Periodo_2      429        123  28.7
Periodo_3      429        123  28.7
Periodo_4      429        121  28.2
Periodo_5      429        163  38.0
Periodo_6      429        157  36.6
```

## 3. Construcción

D_t = sqrt(sum_p s_p ((y_p - ybar)/R)^2), con y_p centroide partidario de dim_ideology, s_p proporción de legisladores con estimación válida (NO cuota oficial de escaños), R = 1.7358 (mitad del rango global, fijo).

## 4. Resultados — atribución 'salida'

### Dalton por período

```
   Period  n_legisladores  n_partidos  dalton
Periodo_1             121          11  0.2562
Periodo_2             123          11  0.2756
Periodo_3             123          12  0.3206
Periodo_4             121          15  0.2682
Periodo_5             162          20  0.3896
Periodo_6             157          19  0.3847
```

### Diferencias consecutivas (cluster bootstrap por legislador)

```
           comparacion  dalton_t  dalton_t1   delta  se_cluster  ic95_low  ic95_high  p_bootstrap  p_holm  significativo_5pct
Periodo_1 -> Periodo_2    0.2562     0.2756  0.0194      0.0118   -0.0048     0.0433       0.1259  0.2517               False
Periodo_2 -> Periodo_3    0.2756     0.3206  0.0451      0.0152    0.0167     0.0756       0.0040  0.0160                True
Periodo_3 -> Periodo_4    0.3206     0.2682 -0.0524      0.0149   -0.0827    -0.0229       0.0040  0.0160                True
Periodo_4 -> Periodo_5    0.2682     0.3896  0.1214      0.0168    0.0907     0.1543       0.0020  0.0100                True
Periodo_5 -> Periodo_6    0.3896     0.3847 -0.0049      0.0225   -0.0484     0.0374       0.8032  0.8032               False
```

### Contraste confirmatorio post-reforma 2018

- media(D, Periodo_5-6) - media(D, Periodo_1-4): delta = 0.1070, IC95 = [0.0811, 0.1359], p = 0.0020

### Quiebres exploratorios (Wald + sup-Wald bootstrap)

```
               quiebre   delta  se_cluster    wald  p_bootstrap  p_holm
Periodo_1 -> Periodo_2  0.0194      0.0118  2.7023       0.1129  0.2258
Periodo_2 -> Periodo_3  0.0451      0.0152  8.7422       0.0060  0.0180
Periodo_3 -> Periodo_4 -0.0524      0.0149 12.4438       0.0020  0.0080
Periodo_4 -> Periodo_5  0.1214      0.0168 51.9185       0.0010  0.0050
Periodo_5 -> Periodo_6 -0.0049      0.0225  0.0467       0.8621  0.8621
```
- sup-Wald = 51.919, p = 0.0010

## 4. Resultados — atribución 'unico'

### Dalton por período

```
   Period  n_legisladores  n_partidos  dalton
Periodo_1              95           7  0.2720
Periodo_2              97           7  0.2928
Periodo_3              99           8  0.3422
Periodo_4             101          10  0.2938
Periodo_5             119          13  0.3978
Periodo_6             102          12  0.4021
```

### Diferencias consecutivas (cluster bootstrap por legislador)

```
           comparacion  dalton_t  dalton_t1   delta  se_cluster  ic95_low  ic95_high  p_bootstrap  p_holm  significativo_5pct
Periodo_1 -> Periodo_2    0.2720     0.2928  0.0208      0.0134   -0.0056     0.0459       0.1379  0.2757               False
Periodo_2 -> Periodo_3    0.2928     0.3422  0.0494      0.0171    0.0142     0.0793       0.0100  0.0300                True
Periodo_3 -> Periodo_4    0.3422     0.2938 -0.0484      0.0155   -0.0771    -0.0168       0.0020  0.0100                True
Periodo_4 -> Periodo_5    0.2938     0.3978  0.1041      0.0195    0.0649     0.1412       0.0020  0.0100                True
Periodo_5 -> Periodo_6    0.3978     0.4021  0.0042      0.0292   -0.0493     0.0621       0.9530  0.9530               False
```

### Contraste confirmatorio post-reforma 2018

- media(D, Periodo_5-6) - media(D, Periodo_1-4): delta = 0.0997, IC95 = [0.0677, 0.1321], p = 0.0020

### Quiebres exploratorios (Wald + sup-Wald bootstrap)

```
               quiebre   delta  se_cluster    wald  p_bootstrap  p_holm
Periodo_1 -> Periodo_2  0.0208      0.0134  2.4180       0.1229  0.2458
Periodo_2 -> Periodo_3  0.0494      0.0171  8.3314       0.0050  0.0150
Periodo_3 -> Periodo_4 -0.0484      0.0155  9.7611       0.0010  0.0050
Periodo_4 -> Periodo_5  0.1041      0.0195 28.5192       0.0010  0.0050
Periodo_5 -> Periodo_6  0.0042      0.0292  0.0209       0.8841  0.8841
```
- sup-Wald = 28.519, p = 0.0010

## 5. Dispersión cruda por legislador

```
           comparacion  p_brown_forsythe  p_fligner_killeen    p_bf_holm    p_fk_holm
Periodo_1 -> Periodo_2      4.905224e-01       7.485932e-01 9.810448e-01 1.000000e+00
Periodo_2 -> Periodo_3      1.081224e-02       1.558953e-02 3.243673e-02 6.235812e-02
Periodo_3 -> Periodo_4      4.992307e-03       3.195160e-02 1.996923e-02 9.585479e-02
Periodo_4 -> Periodo_5      1.747424e-09       2.529898e-10 8.737118e-09 1.264949e-09
Periodo_5 -> Periodo_6      6.266403e-01       5.620494e-01 9.810448e-01 1.000000e+00
```
- Global Brown-Forsythe p = 3.71e-18; Fligner-Killeen p = 2.34e-20

## 6. Robustez

### Solo legisladores continuos

```
           comparacion  n_continuos  delta_continuos  ic95_low  ic95_high  p_bootstrap  p_holm
Periodo_1 -> Periodo_2           78          -0.0019   -0.0211     0.0162       0.7932  0.7932
Periodo_2 -> Periodo_3           78           0.0186   -0.0137     0.0533       0.2498  0.4995
Periodo_3 -> Periodo_4           79          -0.0841   -0.1107    -0.0517       0.0020  0.0100
Periodo_4 -> Periodo_5           63           0.0873    0.0516     0.1246       0.0020  0.0100
Periodo_5 -> Periodo_6           65          -0.1106   -0.1424    -0.0752       0.0020  0.0100
```

### Normalización fija vs variable

- R fijo = 1.7358; R variable: media = 1.6808 (sd 0.0685); corr(Dalton fijo, Dalton variable) = 1.000

## 7. Salvedades de validación


1. Serie de período corta (K=6): no se aplican tests asintóticos de quiebres
   (Chow, CUSUM, Andrews). Toda la inferencia es bootstrap a nivel de
   legislador; el sup-Wald es un diagnóstico de muestra finita recalibrado
   por remuestreo, y el contraste post-2018 es el único pre-especificado.
2. s_p es la proporción de legisladores CON estimación válida, no la cuota
   oficial de escaños. Como la cobertura varía entre períodos
   (~28% vs ~38%), si el missingness correlaciona con partido/ideología el
   Dalton de períodos con menor cobertura está sesgado (riesgo MNAR).
3. Dependencia panel: los deltas usan cluster bootstrap por Id (legislador),
   que respeta la correlación de diputados que continúan entre períodos; el
   bootstrap independiente se reporta como cota optimista.
4. Error de medición: sigma_i = |IC_high - IC_low|/3.92 asume IC ~95% normal;
   los intervalos con cotas invertidas (conteo en sección 2) usan el valor
   absoluto del ancho.
5. Atribución partidaria: 'salida' usa switchers; 'unico' los excluye. Si los
   resultados difieren entre atribuciones, la conclusión no es robusta al
   criterio de asignación de partido.
6. Permutación de etiquetas de período NO se usa como test principal: los
   períodos difieren institucional y composicionalmente, violando el
   supuesto de intercambiabilidad del test de permutación.
7. Multiplicidad: Holm sobre las 5 comparaciones adyacentes y sobre los
   contrastes de dispersión por pares.
