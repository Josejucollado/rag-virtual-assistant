# Problemas tema 1 SSOO

## Relación de problemas sobre el tema 1 de teoría

1. De las siguientes operaciones indique aquellas que cree que sólo pueden realizarse en modo supervisor
- a) Cambiar la fecha del sistema.
- b) Leer/escribir de un disco magnético a nivel pista/sector.
- c) Provocar una interrupción software.
- d) Provocar una interrupción hardware.
- e) Deshabilitar interrupciones.
2. Explique las diferencias entre los conceptos de proceso y programa.
3. En un sistema multiusuario varios usuarios desean ejecutar simultáneamente el mismo programa. ¿Podría haber un único proceso para soportar esta situación?
4. ¿Es imprescindible que el dispatcher y las rutinas de servicio a interrupción estén cargadas en memoria principal? Justifique su respuesta.
5. Los conceptos multiprogramación y proceso, ¿mantienen alguna relación de dependencia?
6. ¿Las RSI realizan por completo el procesamiento implicado por la ocurrencia de una interrupción? ¿Por qué?
7. ¿Qué implicaciones supone el adoptar una técnica de multiprogramación?
8. ¿De qué manera la distinción entre modo supervisor y modo usuario actúa como forma rudimentaria del sistema de protección?
9. ¿Cuáles son las funciones principales de un S.O.?

## Soluciones

1. a) Modo supervisor, pues implica la interacción con un dispositivo del ordenador. En un entorno multiusuario cambiar la fecha del sistema no debe ser una tarea arbitraria que sea realizada por cualquiera. La fecha del sistema interviene en las distintas partes del sistema, y es común a todos los usuarios y procesos. Se utiliza, por ejemplo, para anotar la fecha de creación de los ficheros o para programar el momento de ejecución de algunos procesos.
- b) Modo supervisor. El sistema operativo es el encargado de interaccionar directamente con los dispositivos (como las unidades de disco). Piense en un sistema multiusuario: la posibilidad de acceder directamente al disco permitiría a un usuario modificar sectores (zonas del disco) asignados a ficheros de otros usuarios.
- c) Modo usuario y supervisor. Una interrupción software es el mecanismo que tienen los programas para invocar al sistema operativo y solicitar alguno de sus servicios. Si no se pudieran realizar desde el modo usuario los procesos nunca podrían hacer peticiones al sistema operativo.
- d) Ninguno. Una interrupción hardware únicamente la puede provocar el hardware. Cuando hablamos de modo usuario/supervisor estamos suponiendo la ejecución de instrucciones por parte de la CPU en alguno de estos modos.

- e) Modo supervisor. Deshabilitar interrupciones es una de las tareas más críticas de un sistema. Al desactivar las interrupciones éstas no son atendidas. El S.O. llama al dispatcher como consecuencia de la ocurrencia de algunas interrupciones. Un proceso de usuario que deshabilitara las interrupciones podría paralizar el sistema si no las habilita.
2. Un programa viene constituido por una secuencia de instrucciones, es una entidad estática; representa una actividad en potencia. Un proceso es un programa en ejecución, lleva asociado unos valores concretos para sus variables, una pila de ejecución, una zona de memoria donde se almacena, unos valores de los registros del procesador, etc.
3. No. Se puede mantener en memoria una sola copia del código del programa, como se verá en los temas de gestión de memoria. Sin embargo, se necesita crear dos procesos. Observe que para cada uno de los programas ejecutados por un usuario el S.O. necesitará un lugar distinto donde almacenar sus variables, su pila o su contexto (contador de programa, acumulador, etc).
4. En la práctica es imprescindible. Las RSI y el dispatcher son invocados con una frecuencia muy elevada. Deben de tener un código corto para que no se decremente el uso del procesador por parte de los procesos de usuario. Si cada vez que son invocadas hubiera que esperar a que se cargara su código de disco se ralentizaría enormemente la velocidad de ejecución de los procesos.
5. 5.
6. No, las RSI se ejecutan con las interrupciones total o parcialmente deshabilitadas. No es conveniente que esta situación se prolongue para que el sistema pueda atender nuevas interrupciones. Por ello, las RSI se diseñan para realizar el mínimo posible del procesamiento de la interrupción, y dejar que el resto lo desempeñe otra parte del S.O. que se ejecuta con las interrupciones habilitadas.