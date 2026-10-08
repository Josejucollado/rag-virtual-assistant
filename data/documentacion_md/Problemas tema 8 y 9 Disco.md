# Problemas tema 8 y 9 Disco

## Temas 8 y 9

- 1) A un gestor de disco de un sistema de cabezas móviles le llegan solicitudes de E/S para las pistas 10, 22, 20, 2, 40, 6 y 38, en ese orden. El tiempo que tarda una cabeza móvil en atravesar una pista es 6  milisegundos.  Calcule  el  tiempo  de  búsqueda  necesario  para  satisfacer  las  solicitudes  usando  los siguientes algoritmos:
- a) FCFS
- b) SSTF
- c) SCAN (la cabeza móvil se dirige hacia las pistas exteriores)

Inicialmente la cabeza móvil está situada sobre la pista 20.

- 2) Indique  en  cuál  de  los  cuatro  niveles  de  E/S  (Programas  de  usuario,  rutinas  de  E/S,  gestores  de dispositivos,  rutinas  de  servicio  de  interrupción  de  E/S)  se  realiza  cada  una  de  las  siguientes actividades (justifique su respuesta):
- a) Cálculo de la pista y el sector en una lectura de disco.
- b) Mantenimiento de una caché con los bloques usados recientemente.
- c) Escritura de órdenes en los registros del dispositivo.
- d) Comprobación del permiso de un usuario para usar un dispositivo.
- e) Conversión de enteros binarios a ASCII para imprimirlos.
- 3) Un vendedor de licencias de sistemas operativos monousuarios que visitaba una universidad del suroeste de Amsterdam comentó durante su presentación comercial que su compañía había dedicado un gran esfuerzo a optimizar la velocidad de sus versiones de UNIX. Como ejemplo mencionó que su gestor de disco utilizaba  el  algoritmo  SCAN.  Un  estudiante,  Pepe  Manitas,  se  quedó  muy impresionado y decidió comprar uno. Lo instaló en su ordenador personal y escribió un programa que leía 10.000 bloques distribuidos aleatoriamente por todo el disco. Para su sorpresa, la velocidad que obtuvo era idéntica a la que cabría esperar de un algoritmo primero en llegar, primero en servirse. ¿Le había mentido el vendedor?
- 4) En un entorno de monoprogramación, ¿son útiles las planificaciones de disco distintas de la FCFS?
- 5) ¿Qué  es  la  'independencia  del  dispositivo'?  ¿Cómo  podemos  organizar  el  sistema  de  E/S  para alcanzar este objetivo?
- 6) Suponga un sistema con discos de cabezas móviles y con 200 pistas, numeradas desde la 0 hasta la 199. Actualmente se está sirviendo una solicitud en la pista 143, y la solicitud atendida previamente era relavita a la pista 125. Si la cola de solicitudes es: 147, 91, 177, 94, 150, 102, 175, 130. ¿Cuál es el movimiento  de  cabeza  total  necesario  para  satisfacer  estas  solicitudes  con  los  algoritmos  de planificación de disco: FCFS, SSTF, SCAN, C-SCAN?
- 7) Cuando  la  longitud  media  de  la  cola  de  solicitudes  es  pequeña,  todos  los  algoritmos  de planificación  de  disco  tienen  un  rendimiento  similar  a  la  planificación FCFS. Explique por qué es cierta dicha afirmación.

## Soluciones

- 1) a) Las solicitudes se atienden por orden de llegada. Esto implica que la cabeza móvil debe recorrer (10 + 12 + 2 + 18 + 38 + 34 + 32) pistas, es decir, 146 pistas. En estos recorridos dedica un total de (146 pistas * 6 ms/pista) ms, es decir, 876 ms.
- b) Las solicitudes se atienden en el orden: 20, 22, 10, 6, 2, 38, 40. Esto implica que la cabeza móvil debe recorrer (0 + 2 + 12 + 4 + 4 + 36 + 2) pistas, es decir, 60 pistas. En  estos recorridos dedica un total de (60 pistas * 6 ms/pista) ms, es decir, 360 ms.
- c) Las solicitudes se atienden en el orden: 20, 22, 38, 40, 10, 6, 2. Esto implica que la cabeza móvil debe recorrer (0 + 2 + 16 + 2 + 30 + 4 + 4) pistas, es decir, 58 pistas. En estos recorridos dedica un total de (58 pistas * 6 ms/pista) ms, es decir, 348 ms.
4. 2 ) a) Gestor de dispositivo. Es la única parte del software de E/S que entiende de parámetros físicos.
- b) Rutinas de E/S. Si existe buffering son las encargadas de implementarlo.
- c) Gestor de dispositivo. Por lo mismo que a).
- d) Rutinas de E/S.
- e) Programas de usuario. Los procedimientos de biblioteca de los lenguajes de programación ofrecen la posibilidad de dar formato a la salida de datos. Un ejemplo de función de  este tipo es fprintf de la biblioteca estándar de E/S de C.
- 3) No necesariamente. Un programa UNIX que solicita 10000 lecturas de bloque hace sus solicitudes una  a  una.  Al  realizar  una  solicitud  se  bloquea  hasta  que  ésta  sea  completada.  Como  el  sistema operativo tan sólo ve una solicitud a la vez no tiene oportunidad de hacer ninguna optimización, las procesa  en  el  orden  de  llegada.  Pepe  Manitas  debería  haber  ejecutado  concurrentemente  varios programas que realizaran las lecturas de disco para comprobar la eficacia del algoritmo SCAN.
- 4) No.  Los  algoritmos  de  planificación  tienen  como  uno  de  sus  objetivos  el  reducir  el  tiempo  de búsqueda  medio  (movimiento  del  brazo).  Para  ello  reordenan  la  cola  de  solicitudes  de  cara  a aprovechar mejor el desplazamiento del brazo. En un sistema de monoprogramación tan sólo existe un proceso de usuario. Por lo tanto es el único que realiza solicitudes del disco, y como hasta que no se resuelva una solicitud no se devuelve el control al proceso, como mucho existe una solicitud de disco en un momento. Resulta pues absurdo reordenar las solicitudes, ya que en todo instante a lo sumo existe una.