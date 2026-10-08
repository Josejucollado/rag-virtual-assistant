# Relación de ejercicios de programación en Bash

## Relación de ejercicios de programación en Bash.

Sistemas Operativos

<!-- image -->

| Anonimizar un nombre en un texto......................................................................................2         |
|---------------------------------------------------------------------------------------------------------------------------------|
| Backup incremental............................................................................................................3 |
| Índice invertido de palabras................................................................................................4   |
| Índice invertido de n-grams................................................................................................ 5   |

<!-- image -->

## Anonimizar un nombre en un texto

Escribe un shell script llamado anonimizar_nombre.sh que recibe varios argumentos: una cadena de texto entre comillas (un nombre), otra cadena de texto (un apodo) y una lista de ficheros ordinarios. Para cada fichero recibido crea un fichero, con el mismo nombre y pero terminado en _ anonimo.txt , con una copia del fichero original pero donde se haya sustituido el texto del primer argumento, por el texto del segundo argumento.

## Asegúrate de comprobar las siguientes condiciones:

- Si el programa no recibe 3 o más argumentos debe escribir cual es la sintaxis correcta de la orden.
- Sólo procesa los ficheros ordinarios que tienen permiso de lectura y extensión ' . txt '.
- Por cada fichero procesado, crea un fichero con una copia del contenido original pero sustituyendo el nombre dado como primer argumento por el apodo indicado en el segundo argumento.
- El nuevo fichero creado tendrá el mismo nombre pero acabará con la cadena ' _anonimo.txt '.
- Escribe el número de ficheros procesados.

## Ejemplos de llamadas:

## $ ./anonimozar_nombre.sh

ERROR: Debes pasar al menos 3 argumentos: dos cadenas de texto y una lista de ficheros

SINTAXIS: ./anonimizar_nombre.sh nombre apodo fich1.txt fich2.txt ...

## $ ./anonimozar_nombre.sh 'Pedro Perez' ANONIMO1 fich1.txt fich2.txt Analizando fich1.txt ...

Se ha generado el fichero fich1_anonimo.txt

Analizando fich2.txt

ERROR: fich2.txt no tiene permisos de lectura

Se han procesado 1 ficheros.

## Backup incremental

Escribe un shell script llamado backup_inc.sh que recibe como argumentos tres nombres de directorios ( dir1 , dir2 y dir3 ). El script creará una copia de todos los ficheros del directorio dir1 en el directorio dir3 . Si el fichero que se va a copiar existe en dir2 y tienen la misma fecha, en lugar de copiarlo se creará un enlace duro en dir3 del archivo que existe en dir2 .

Asegúrate de realizar las siguientes acciones y comprobaciones:

- Si el programa no recibe 3 argumentos debe escribir cual es la sintaxis correcta de la orden y finalizar.
- Comprueba que dir1 y dir2 son directorios y tiene permitido el acceso a ellos (permisos de lectura y ejecución).
- Si el directorio dir3 existe, genera un mensaje de error indicándolo y finaliza.
- Si el directorio dir3 no existe, lo crea.
- Para cada archivo que exista en dir1 :
- Si no tiene permisos de lectura o es una carpeta, lo descarta y no realiza copia.
- Si no existe un archivo con el mismo nombre en dir2 , realiza una copia en dir3 .
- Si existe un archivo con el mismo nombre en dir2 , pero es más antiguo que el existente en dir1 , realiza una copia en dir3 .
- Si existe un archivo con el mismo nombre en dir2 y es más nuevo o igual que el existente en dir1 , realiza un enlace duro del archivo existente en dir2 en el directorio dir3 con el mismo nombre.
- Antes de finalizar indica cuantos archivos ha copiado, cuantos ha enlazado y cuantos a descartado.

## Ejemplos de llamadas:

## $ ./backup_inc.sh

ERROR: Debes pasar como argumento 3 nombres de directorios SINTAXIS: ./backup_inc.sh dir1 dir2 dir3

- $ ./backup_inc.sh ~/MisFotos backup/fotos/enero backup/fotos/febrero Realizando copia de seguridad de ~/MisFotos ...

Se han copiado 13 ficheros en backup/fotos/febrero. Se han enlazado 34 ficheros existentes en backup/fotos/enero. Se han descartado 3 archivos o directorios.

## Índice invertido de palabras

Escribe un shell script llamado indice_palabras.sh que recibe varios argumentos: un nombre de fichero, un número y una lista de ficheros ordinarios. El script deberá generar un fichero, con el nombre introducido como primer parámetro, que contenga un listado de palabras junto con el fichero donde aparecen. Dicho listado tendrá una línea por cada palabra y nombre de fichero (ejemplo: 'palabra fichero1'), y las líneas no podrán repetirse.

Asegúrate de realizar las siguientes acciones y comprobaciones:

- Si el programa no recibe 3 o más argumentos debe escribir cual es la sintaxis correcta de la orden y finalizar.
- Sólo procesa los ficheros ordinarios que tienen permiso de lectura y extensión ' . txt '.
- Para cada fichero procesado, leerá el fichero palabra a palabra y añadirá al fichero índice una línea con la palabra y el nombre del fichero analizado.
- Sólo se añadirán las palabras que tengan una longitud igual o mayor al número dado como segundo argumento.
- Asegúrate de que el fichero final se llama como el primer parámetro y que no tiene ninguna pareja (palabra fichero) repetida.
- Escribe el número total de ficheros procesados.

## NOTAS:

- La orden mktemp crea un fichero temporal vacío y devuelve el nombre de dicho fichero.
- Se pueden quitar líneas repetidas de un fichero con la siguiente orden: sort -u ficherotemp > ficheroindice

## Ejemplos de llamadas:

```
$ ./indice_palabras.sh ERROR: Debes pasar al menos 3 argumentos: un nombre de fichero, un número y una lista de ficheros SINTAXIS: ./indice_palabras.sh fich num fich1.txt fich2.txt ... $ ./indice_palabras.sh indice.csv 4 *.txt Analizando fich1.txt ... Analizando fich2.txt ... Analizando fich3.txt ... ERROR: El fichero fich3.txt no es un fichero ordinario o no tiene permisos de lectura. Se han procesado 2 ficheros.
```

## Índice invertido de n-grams

Escribe un shell script llamado indice_ngrams.sh que recibe varios argumentos: un nombre de fichero, un número y una lista de ficheros ordinarios. El script deberá generar un fichero, con el nombre introducido como primer parámetro, que contenga un listado de n-grams junto con el fichero donde aparecen. Dicho listado tendrá una línea por cada n-gram y nombre de fichero (ejemplo: 'ngram fichero1'), y las líneas no podrán repetirse.

Los n-grams se calculan a partir de una palabra y el número dado como segundo argumento, por ejemplo, para la palabra ' botijo ' y el número 4 se generan los siguientes 4-grams: ' boti ', ' otij ' y ' tijo '.

Asegúrate de realizar las siguientes acciones y comprobaciones:

- Si el programa no recibe 3 o más argumentos debe escribir cual es la sintaxis correcta de la orden y finalizar.
- Sólo procesa los ficheros ordinarios que tienen permiso de lectura.
- Para cada fichero procesado, leerá el fichero palabra a palabra y añadirá al fichero índice una línea por cada n-gram generado de cada palabra junto con el nombre del fichero analizado.
- Los n-grams serán del tamaño indicado como segundo argumento. Si la palabra no tiene tamaño suficiente para generar un n-gram , dicha palabra se desestima.
- Asegúrate de que el fichero final se llama como el primer parámetro y que no tiene ninguna pareja (ngram fichero) repetida.
- Escribe el número total de ficheros procesados y el número total de líneas del fichero generado.

## NOTAS:

- La orden mktemp crea un fichero temporal vacío y devuelve el nombre de dicho fichero.
- Se pueden quitar líneas repetidas de un fichero con la siguiente orden: sort -u ficherotemp > ficheroindice

## Ejemplos de llamadas:

```
$ ./indice_ngrams.sh ERROR: Debes pasar al menos 3 argumentos: un nombre de fichero, un número y una lista de ficheros SINTAXIS: ./indice_ngrams.sh fich num fich1 fich2 ... $ ./indice_ngrams.sh indice.csv 4 *.txt Analizando fich1.txt ... Analizando fich2.txt ... Analizando fich3.txt ... ERROR: El fichero fich3.txt no es un fichero ordinario o no tiene permisos de lectura.
```

| Se han   | procesado 2 ficheros.   |
|----------|-------------------------|