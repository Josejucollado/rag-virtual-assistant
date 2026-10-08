# Problemas tema 5 y 6 Memoria

## Temas 6 y 7

- 1) Un  sistema  de  memoria  paginada  utiliza  registros  asociativos  para  mantener  las  entradas  de  las tablas  de  páginas  a  las  que  se  ha  hecho  referencia  hace  menos  tiempo.  Si  las  tablas  de  páginas  se mantienen normalmente en memoria, y el tiempo  de acceso a memoria es de 1 microsegundo, ¿cuál será el tiempo de acceso efectivo si el 85% de las referencias a memoria encuentran sus entradas en los  registros  asociativos?  ¿Cuál  será  el  tiempo  de  acceso  efectivo  si  este  ratio  es  sólo  del  50%?. Compare  e stos  resultados  con  el  tiempo  de  acceso  efectivo  que  se  obtendría  si  no  se  utilizaran registros asociativos. (El tiempo que dura la consulta de los registros asociativos es 60 nanosegundos).
- 2) Un  sistema  paginado  tiene  una  memoria  física  de  256  MB,  un  tamaño de palabra de 4 bytes, y direcciones  virtuales  de  32  bits.  De  estos  32  bits  los  22  de  la  izquierda  constituyen  el  número  de página y los 10 de la derecha el desplazamiento dentro de la página, como se observa en la figura:

| Dirección virtual            | Dirección virtual          |
|------------------------------|----------------------------|
| Número de página ← 22 bits → | Desplazamiento ← 10 bits → |

Según lo anterior, y teniendo en cuenta que se direcciona a nivel de palabra

- a) ¿Qué tamaño tiene cada página?
- b) ¿Cuál es el tamaño del espacio de direccionamiento virtual?
- c) ¿En cuántos marcos de página se divide la memoria física?
- d) ¿Qué tamaño deberá tener el campo Número de Marco de la tabla de páginas?
- e) Si un proceso tiene la tabla de páginas que se muestra abajo, donde el campo Válido indica si la  página  está  (el  campo  valdrá  1)  o  no  (0)  en  memoria  principal,  ¿  qué  direcciones  físicas estarán asociadas a las direcciones virtuales 950 y 3572?
- 3) Un sistema de segmentación paginada utiliza registros asociativos para mantener las entradas de las tablas  de  páginas  a  las  que  se  ha  hecho  referencia  hace  menos  tiempo.  Si  las  tablas  de  páginas  se mantiene normalmente en memoria, y el tiempo de acceso a memoria es de 1 microsegundo, ¿cuál será el tiempo de acceso efectivo si el 85% de las referencias a memoria encuentran sus entradas en los  registros  asociativos?  (El  tiempo  que  dura  la  consulta  de  los  registros  asociativos  es  60 nanosegundos).
- 4) En un sistema de particiones dinámicas con intercambio tenemos 3 procesos que tienen la misma prioridad y que llevan el mismo tiempo en memoria principal, se debe elegir a uno para desplazarlo a disco, ¿cuál de los tres elegiría si el primero está en estado bloqueado, el segundo en estado listo y el tercero en ejecución? Conteste también a lo siguiente:

| Marco   |   Válido |
|---------|----------|
| 7308    |        1 |
| -       |        0 |
| 24      |        1 |
| -       |        0 |
| 10500   |        1 |
| 23004   |        1 |

- a) ¿Permite el intercambio aumentar el número de procesos existentes?
- b) ¿Permite  el  intercambio  aumentar  el  tamaño  del  espacio  de  direccionamiento  lógico  de  los procesos?
- c) ¿Provoca el intercambio una disminución en la velocidad de ejecución de los procesos?
- d) ¿Los procesos de usuario son conscientes de su existencia?
- 5) Suponga que se tiene un sistema de segmentación paginada con registros asociativos para mantener las entradas de la tabla de segmentos a las que se ha hecho referencia de forma más reciente. Si las tablas de páginas se mantienen normalmente en memoria, y el tiempo de acceso a memoria es de 1 microsegundo,  ¿cuál  será  el  tiempo  de  acceso  efectivo  si  el  85%  de  la  referencias  a  memoria encuentran sus entradas en los registros asociativos? (El tiempo que dura la consulta de los registros asociativos es 60 nanosegundos).
- 6) ¿Es más sencillo compartir un módulo reentrante en un sistema de segmentación que en uno de paginación? ¿Por qué?
- 7) Sea un sistema de paginación bajo demanda en el que no existe  memoria asociativa. El tiempo de acceso a memoria es de 0,5 microsegundos. Servir un fallo de página lleva: a) 8 milisegundos si existe un marco vacío o, si no existiendo, la página reemplazada no ha sido modificada durante su estancia en memoria principal, o b) 20 milisegundos si no existe un marco vacío y la página reemplazada fue modificada durante su estancia en memoria. La probabilidad de que una página haya sido modificada durante su estancia en memoria principal es del 70%. ¿Cuál es la tasa de fallos de página máxima para lograr un tiempo de acceso efectivo inferior o igual a 2 microsegundos?
- 8) Para la siguiente secuencia de referencias a páginas de un proceso: 1,2,3,4,1,2,5,1,2,3,4,5. Calcule el número de fallos de página que produce suponiendo que se aplica el algoritmo de reemplazo FIFO, el proceso no tiene ninguna página en memoria, se sigue una política de reemplazo local y el número de marcos de página asignadas al proceso es de:
- a) 3 marcos
- b) 4 marcos

¿Se corresponde el resultado obtenido con la idea intuitiva de que disminuirá el número de fallos de página al aumentar el tamaño de memoria asignado al proceso?

- 9) Calcule el número de fallos de página que produce la secuencia de referencias del ejercicio anterior suponiendo que se aplica el algoritmo de reemplazo óptimo, el proceso no tiene ninguna página en memoria, se sigue una política de reemplazo local y el proceso tiene asignados 3 marcos.
- 10) ¿Cuándo ocurre un fallo de página? Describa las acciones que emprende el sistema operativo cuando tiene lugar un fallo de este tipo.
- 11) ¿Por qué una política de reemplazo de páginas global puede ser más susceptible a la hiperpaginación que una política local?
- 12) En un sistema de paginación, un proceso realiza la siguiente serie de referen cias a páginas: 16, 11, 15, 17, 17, 17, 17, 15, 11, 16, 12, 13, 14, 11, 12, 13, 14, 14. Inicialmente el proceso no tiene asignado ningún marco. Calcule los conjuntos de trabajo del proceso para una ventana de tamaño

- a) 5
- b) 8

Si  un  proceso  tuviera  asignadas  en  todo  momento  (y  únicamente)  las  páginas  que  constituyen  su conjunto de trabajo, ¿cuántos fallos de página se producirían? ¿Para qué sirve la política del conjunto de trabajo? ¿Qué dificultades conlleva su implantación?

- 13) ¿Cuál es la causa de la hiperpaginación? ¿Cómo puede detectar el sistema operativo que se está dando este fenómeno?, y una vez detectado ¿qué puede hacer para eliminarlo?

## Soluciones

- 1) Se tiene un sistema paginado con registros asociativos para mejorar el tiempo de acceso a memoria efectivo. Dada una dirección virtual primero se busca el marco correspondiente a la página lógica en los registros asociativos, si se falla se acudirá a la tabla de páginas.

El tiempo de acceso a memoria si tiene éxito la búsqueda en los registros asociativos es:

```
T1 = Tiempo acceso a los registros + Tiempo de acceso a memoria = 60 ns + 1000 ns = 1060 ns
```

El tiempo de acceso a memoria si no tiene éxito la búsqueda en los registros asociativos es:

```
T2 = T. acceso a los registros + T. acceso a la tabla páginas + T. acceso a memoria = 60ns + 1000 ns +1000 ns = 2060 ns
```

El  tiempo  de  acceso  a  memoria  efectivo  para  un  éxito  del  85%  en  la  búsqueda  en  los  registros asociativos = T 3 = 0. 85 * T 1 + 0.15 * T 2 = 1210 ns

Y para un éxito del 50 % = T 4 =0. 5 * T 1 + 0.5 * T 2 = 1560 ns

Realicemos ahora la comparación:

Tiempo de acceso a memoria sin registros asociativos = T 5 = 1000 ns + 1000 ns = 2000 ns

85%) T5 - T 3 = 2000 ns - 1210 ns = 790 ns ⇒ Una mejora del 39,5 % (790/2000*100)

50%) T5 - T 4 = 2000 ns - 1560 ns = 440 ns ⇒ Una mejora del 22 % (440/2000*100)

- 2) 10 palabras. Luego el
- a)  Puesto  que  el  campo  desplazamiento  es  de  10  bits  en  una  página  caben  2 tamaño de página es de 4 KB (2 10 palabras x 4 bytes/palabra).
- b) Puesto que las direcciones son de 32 bits un pro grama puede hacer referencia a 2 32 palabras.
- c) 256 MB : 4 KB/marco = 64 K marcos
- d)  La  memoria  principal  tiene  64  K  marcos,  es  decir,  2 16 marcos.  Luego  se  necesitan  16  bits  para hacer referencia a un marco, y éste deber ser el tamaño del campo número de marco.

```
e) Página lógica de la dirección virtual 950 = 950 div 1024 = 0 Desplazamiento de la dirección virtual 950 dentro de la página-marco = 950 mod 1024 = 950 Marco en que se ubica la página lógica 0 del proceso = 7308 Dirección física = 7308 * 1024 + 950 = 7484342
```

Para la dirección virtual 3572 se tiene que su página lógica es la 3 (3572 div 1024). Puesto que esta página no está en memoria al hacer referencia a la dirección se produce un fallo de página. Cuando se resuelva se podrá calcular la dirección física.

- 4) A  igualdad  de  prioridad  y  tiempo  de  estancia  en  memoria  principal  se  elegiría  al  proceso bloqueado, pues así aumenta la posibilidad de hacer un buen uso del procesador. De entre el proceso listo y el proceso en ejecución quizá sería mejor elegir al primero, pues si se elige al segundo también se necesita efectuar un cambio de proceso.
- a)  Sí,  mediante  el  intercambio  podemos  tener  más  procesos  en  el  sistema  de  los  que  caben  en memoria principal.
- b) No.
- c) Sí, por dos motivos. En primer lugar, porque pueden existir más procesos en el sistema de los que caben en memoria principal, y por tanto, de los que admite un sistema de particiones dinámicas sin intercambio. Al existir más procesos compitiendo por los mismos recursos (CPU, memoria, discos, impresoras,  etc),  la  ejecución  de  los  procesos  se  ralentiza.  En  segundo  lugar,  porque  el  sistema operativo utiliza recursos (en perjuicio de los procesos de usuario) para implantar el intercambio. Por ejemplo,  debe  ejecutar  algoritmos  para  determinar  qué  p rocesos  desplazar  de  memoria  principal  a disco  (y  viceversa),  realizar  operaciones  de  disco,  necesita  un  espacio  en  disco  para  la  zona  de intercambio, etc.
- d) No. Los programadores escriben sus programas de la misma forma. El sistema operativo se encarga de que el intercambio sea transparente al programador.
- 7) Sean

```
T1 = Tiempo de acceso a memoria cuando no hay fallo de página = 0,5 µ s * 2 = 1 µ s T2 = Tiempo de acceso a memoria cuando hay fallo de página = 0.3 * 8000 µ s + 0.7 * 20000 µ s = 16400 µ s
```

En T 2 se realiza la media ponderada del acceso a memoria con fallo de página teniendo en cuenta las circunstancias a) y b). A este tiempo habría que añadirle el microsegundo que se tarda en acceder a la página una vez resuelto el fallo de página. Sin embargo, aquí lo hemos despreciado.

El tiempo de acceso efectivo (T.A.E.) es: (1-p) * T 1 + p * T 2 µ s = 1 + 16399p µ s, donde p es la probabilidad de que ocurra un fallo de página.

Como queremos un T.A.E <= 2 µ s 1 + 16399p µ s <= 2 µ s p <= 1/16399. Luego p debe ser menor de 0,0000609, o lo que es lo mismo, se debe de producir como mucho un fallo de página cada 16399 accesos a memoria.

- 8) En las siguientes matrices la primera fila representa las referencias a memoria. Para la columna i , el elemento  [1, i ]  representa  la  página  a  la  que  se  ha  hecho  referencia,  y  el  resto  de  elementos  de  la

columna la ocupación de los marcos del proceso tras la referencia. Las páginas que producen fallo de página se resaltan en negrita.

a)

b)

|   1 |   2 |   3 |   4 | 1   | 2   |   5 |   1 |   2 |   3 |   4 |   5 |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
|   1 |   1 |   1 |   1 |     |     |   5 |   5 |   5 |   5 |   4 |   4 |
|     |   2 |   2 |   2 |     |     |   2 |   1 |   1 |   1 |   1 |   5 |
|     |     |   3 |   3 |     |     |   3 |   3 |   2 |   2 |   2 |   2 |
|     |     |     |   4 |     |     |   4 |   4 |   4 |   3 |   3 |   3 |

Para 3 marcos ocurren 9 fallos y para  4 marcos 10. El resultado obtenido no se corresponde con la idea intuitiva de que al asignar más memoria a un proceso disminuirá su número de fallos de página. Esto se debe a que si se utiliza el algoritmo FIFO para reemplazar las páginas de un proceso no  se verifica el siguiente principio: el conjunto de páginas en memoria que tiene un proceso al que se le han asignado n marcos es un subconjunto del conjunto de páginas en memoria que tendría si se le hubiesen asignado n + 1 marcos .

9)

|   1 |   2 |   3 |   4 | 1   | 2   |   5 | 1   | 2   |   3 |   4 | 5   |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
|   1 |   1 |   1 |   1 |     |     |   1 |     |     |   3 |   4 |     |
|     |   2 |   2 |   2 |     |     |   2 |     |     |   2 |   2 |     |
|     |     |   3 |   4 |     |     |   5 |     |     |   5 |   5 |     |

Se producen 7 fallos de página. En los dos últimos fallos de página, ante la igualdad de méritos para ser víctima, se elige a una página aleatoriamente.

12)

|   1 |   2 |   3 |   4 |   1 |   2 |   5 | 1   | 2   |   3 |   4 | 5   |
|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|-----|
|   1 |   1 |   1 |   4 |   4 |   4 |   5 |     |     |   5 |   5 |     |
|     |   2 |   2 |   2 |   1 |   1 |   1 |     |     |   3 |   3 |     |
|     |     |   3 |   3 |   3 |   2 |   2 |     |     |   2 |   4 |     |

|   Referencias | Conjunto de trabajo para ∆ = 5   | Conjunto de trabajo para ∆ = 8   |
|---------------|----------------------------------|----------------------------------|
|            16 | { 16 } *                         | { 16 } *                         |
|            11 | { 11, 16 } *                     | { 11, 16 } *                     |
|            15 | { 15, 11, 16 } *                 | { 15, 11, 16 } *                 |
|            17 | { 17, 15, 11, 16 } *             | { 17, 15, 11, 16 } *             |
|            17 | { 17, 15, 11, 16 }               | { 17, 15, 11, 16 }               |
|            17 | { 17, 15, 11 }                   | { 17, 15, 11, 16 }               |
|            17 | { 17, 15 }                       | { 17, 15, 11, 16 }               |
|            15 | { 15, 17 }                       | { 15, 17, 11, 16 }               |
|            11 | { 11, 15, 17 } *                 | { 11, 15, 17 }                   |
|            16 | { 16, 11, 15, 17 } *             | { 16, 11, 15, 17 } *             |
|            12 | { 12, 16, 11, 15, 17 } *         | { 12, 16, 11, 15, 17 } *         |
|            13 | { 13, 12, 16, 11, 15 } *         | { 13, 12, 16, 11, 15, 17 } *     |

|   14 | { 14, 13, 12, 16, 11 } *   | { 14, 13, 12, 16, 11, 15, 17 }   |
|------|----------------------------|----------------------------------|
|   11 | { 11, 14, 13, 12, 16 }     | { 11, 14, 13, 12, 16, 15, 17 }   |
|   12 | { 12, 11, 14, 13 }         | { 12, 11, 14, 13, 16, 15 }       |
|   13 | { 13, 12, 11, 14 }         | { 13, 12, 11, 14, 16 }           |
|   14 | { 14, 13, 12, 11 }         | { 14, 13, 12, 11, 16 }           |
|   14 | { 14, 13, 12, 11 }         | { 14, 13, 12, 11 }               |

Los asteriscos denotan las referencias que provocan fallos de página. Con ∆ = 5 se producen 9 fallos de página, y con ∆ = 8 se producen 8 fallos de página.