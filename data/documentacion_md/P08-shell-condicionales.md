# P08-shell-condicionales

## Práctica 8. Programación en Shell.

<!-- image -->

## Ejecución condicional de órdenes.

Autor: Francisco de Asís Conde Rodríguez / Lina García Cabrera Copyright:

<!-- image -->

| Índice.......................................................................................................................................1   |
|--------------------------------------------------------------------------------------------------------------------------------------------------|
| Introducción....................................................................................................................... 2            |
| La estructura condicional if - then - else.............................................................................2                         |
| Condicionales y operadores.................................................................................................3                     |
| Operadores para aplicar a archivos:..................................................................................3                           |
| Operadores para aplicar a números:..................................................................................4                            |
| Operadores para aplicar a cadenas de caracteres:...........................................................5                                     |
| Condiciones compuestas...................................................................................................5                       |
| Comparaciones avanzadas.............................................................................................5                            |
| Ejemplos del uso de condicionales en shell script............................................................ 6                                  |
| Comprobar si se han pasado todos los argumentos..........................................................6                                       |
| Comprobar si existe o no un archivo..................................................................................7                           |
| Comparar cadenas de caracteres......................................................................................8                            |
| Comparar expresiones y números.....................................................................................8                             |
| Ejercicios.............................................................................................................................. 10      |
| Propuestas de bash scripts................................................................................................ 11                    |

<!-- image -->

## Introducción

En ocasiones, un shell script deberá ejecutar un conjunto de órdenes si se da una condición y otro distinto si no se da. Es lo que se denomina ejecución condicional de órdenes.

Como en la mayoría de lenguajes de programación, en la programación de shell scripts existe la estructura if-then-else , que son palabras clave o reservadas del intérprete de órdenes, y que permiten programar la ejecución condicional de órdenes.

En esta sesión de prácticas se estudia esta estructura y cómo se evalúan las expresiones lógicas que nos permitirán construir programas más flexibles y útiles.

## La estructura condicional if - then - else

Si se escribe en un terminal type -a if , el terminal responde:

```
fconde@fconde-VirtualBox:~$ type -a if if es una palabra clave del shell
```

Es decir, if no es una orden, sino que es una palabra clave que indica al intérprete de órdenes que debe interpretar lo que sigue al if como un condicional. La sintaxis correcta para escribir un condicional en shell script es:

```
if [ condicion ] then sentencias si condición verdadera else sentencias si condición falsa fi
```

Si la condición o expresión es distinto de cero (verdadero) se ejecuta la parte then y si es falso se ejecuta la parte else .

Los corchetes [ ] y los espacios que hay entre ellos y la condición son obligatorios . Es un fallo muy común no poner espacio entre el primer corchete y el primer carácter de la condición. Por ejemplo, al ejecutar:

```
if [-d ${HOME}/bin] (El primer corchete [ va pegado a -d sin espacio)
```

el intérprete de órdenes da el error:

```
[-d: no se encontró la orden
```

También es frecuente olvidar el espacio entre el final de la condición y el último corchete ] . Por ejemplo al ejecutar:

```
if [ -d ${HOME}/bin] (El último corchete ] va pegado sin espacio a bin )
```

el intérprete de órdenes da el error:

```
bash: [: falta un `]'
```

Las estructuras condicionales en shell script comienzan con la palabra reservada if y terminan con la palabra reservada fi.

## Condicionales y operadores

Para comparar en Bash se utiliza test o [ . Ambos son totalmente equivalentes, y ambos están implementados, en el propio Bash. En el caso [ , por cuestiones prácticas es obligatorio también utilizar su pareja ] o de otra forma te da error. Esta es la razón para que tenga que estar separado el corchete de la expresión que viene a continuación (debe incluirse un espacio blanco), porque es un comando.

La condición dentro de una instrucción if-then-else , siempre se escribe entre corchetes y entre los corchetes y la condición debe existir un espacio, de lo contrario el intérprete de órdenes dará un error.

Para construir las condiciones, se usan valores, sustituciones de parámetros y operadores.

Por ejemplo:

```
[ -r ${1} ]
```

es una condición sintácticamente bien construída que comprueba si el valor del parámetro posicional 1, es el nombre de un archivo que existe y es legible ( readable ).

En la programación shell, existen muchos operadores que podemos utilizar para construir nuestras condiciones.

## Operadores para aplicar a archivos:

Los ocho primeros son unarios, es decir sólo necesitan un operando que se escribe a continuación del operador:

```
[ operador archivo ]
```

Los dos últimos son binarios, es decir, requieren dos operandos que se escriben uno a cada lado del operador:

```
[ archivo1 operador archivo2 ]
```

- -r Comprueba si lo que va a continuación es el nombre de un archivo que existe y es legible.
- -x Comprueba si el archivo existe y es ejecutable.
- -h Comprueba si el archivo existe y es un enlace simbólico.
- -f Comprueba si el archivo existe y es un fichero regular u ordinario (no es un directorio, ni otro tipo de archivo especial)
- -d Comprueba si el archivo existe y es un directorio.
- -s Comprueba si el archivo existe y no está vacío (su tamaño es mayor que cero).
- -e Comprueba si el archivo existe.
- -O Comprueba si el archivo es propiedad de quien ejecuta el shell script . O es una o mayúscula.
- -G Comprueba si el archivo pertenece al grupo de quien ejecuta el shell script .
- -nt Se coloca entre dos nombres de archivos y devuelve verdadero si el primero tiene fecha de modificación más reciente que el segundo.
- -ot Comprueba si el primer archivo tiene fecha de modificación más antigua que el segundo.

## Operadores para aplicar a números:

Todos ellos son binarios. Es decir, se aplican a dos argumentos que se escriben uno a cada lado del operador.

- -eq Comprueba si los dos números que se pasan como argumentos son iguales.
- -ne Comprueba si los dos números son distintos.
- -ge Comprueba si el primer número es mayor o igual que el segundo.
- -gt Comprueba si el primer número es mayor estricto que el segundo.
- -le Comprueba si el primer número es menor o igual que el segundo.
- -lt Comprueba si el primer número es menor estricto que el segundo.

## Operadores para aplicar a cadenas de caracteres:

Los dos primeros son unarios mientras que los dos últimos son binarios. Además, los dos últimos ( < y > ) requieren dobles corchetes para que se puedan interpretar bien, ya que también son los símbolos que usa el intérprete de órdenes para indicar la redirección.

- -z Indica si la longitud de la cadena que se pasa como argumento es cero (cadena vacía).
- -n Indica si la longitud de la cadena es mayor que cero.
- = Comprueba si las dos cadenas de caracteres son iguales.
- != Comprueba si las dos cadenas de caracteres son distintas.
- < Indica si la primera cadena es menor que la segunda. Hace una comparación lexicográfica (es decir, comparando carácter a carácter). Por ejemplo, la cadena 'adiós' es menor que la cadena 'hola'.
- > Indica si la primera cadena es mayor que la segunda.

## Condiciones compuestas

Se pueden usar condiciones compuestas, por ejemplo comprobar a la vez si un archivo es legible y ejecutable. Para ello se usan los operadores lógicos && ( and ) y || ( or ) para separar dos condiciones simples.

```
[ -r ${file} ] && [ -x ${file} ]
```

También se puede usar el operador unario ! para negar el resultado de una condición.

## Importante:

Como en cualquier lenguaje de programación, si en un shell script no se escribe la sintaxis de las órdenes correctamente se producen errores.

Para aprender a programar shell scripts es necesario estudiar la sintaxis y practicarla con diversos ejemplos hasta que la aprendas.

## Comparaciones avanzadas

También se pueden utilizar dobles corchetes [[ para realizar tus comparaciones. Los dobles corchetes pueden resultar ser una mejora respecto a los simples en ciertas situaciones. Las diferencias entre uno y otro son las siguientes:

- No tienes que utilizar las comillas con las variables, los dobles corchetes trabajan perfectamente con los espacios.
- Con [[ puedes utilizar los operadores || y && , así como < y > para las comparaciones de cadena.
- Puedes utilizar el operador =~ para expresiones regulares 1 ,
- También puedes utilizar comodines como 2

```
Así [ -f "$file" ] es equivalente a [[ -f $file ]] .
```

```
como por ejemplo [[ $respuesta =~ ^s(i)?$ ]]
```

```
por ejemplo en la expresión [[ abc == a* ]]
```

Es posible que te preguntes por la razón para seguir utilizando [ simple corchete en lugar de doble. La cuestión es por compatibilidad. Si utilizas Bash en diferentes equipos es posible que te encuentres alguna incompatibilidad. Así que depende de ti y de dónde lo vayas a utilizar.

## Ejemplos del uso de condicionales en shell script.

## Comprobar si se han pasado todos los argumentos.

Uno de los usos de los condicionales en programas shell script es comprobar si se han pasado todos los argumentos al programa. En aquellos programas que requieran argumentos es muy importante que se compruebe que se han pasado los parámetros posicionales adecuados, ya que un parámetro que no existe siempre se sustituye por la cadena vacía y esto podría causar errores en el programa.

Ejemplo: Escribir un shell script que reciba dos argumentos y comprobar si se han pasado justamente dos argumentos.

1 [[ $respuesta =~ ^s(i)?$ ]] verifica si la variable respuesta contiene exactamente "s" o "si" (sin ningún carácter adicional antes o después). Esta expresión es útil, por ejemplo, para confirmar si un usuario respondió afirmativamente con "s" o "si" pero no coincide con: "sí" , " s

" , "no" , "siempre" . =~ : El operador que compara la cadena en $respuesta con la expresión regular proporcionada. ^ inicio de la línea, $ final de la línea.

2 [[ abc == a* ]] devolvería true porque a* en este caso significa "a seguido de cualquier número de caracteres"

```
(1) (2) (3) #!/bin/bash # Autor: Francisco de Asís Conde Rodríguez # Descripción: Comprueba si al script se le han pasado # justamente dos argumentos. if [ ! ${#} -eq 2 ] then echo "Error, se han pasado ${#} argumento(s)" fi
```

- (1) Como sabemos de la sesión anterior, el parámetro especial # contiene el número de parámetros posicionales que se han pasado al shell script cuando se ejecutó. Por tanto si comprobamos si es distinto de 2, habremos comprobado si a nuestro script se le han pasado, o no, justamente dos argumentos.
- (2) La palabra reservada then tiene que ir escrita en la línea siguiente a la línea donde está la palabra reservada if . Si se escribe en la misma línea se produce un error al interpretar la línea.
- (3) El sangrado es opcional, pero si se incluye, el código es mucho más legible.

## Comprobar si existe o no un archivo

Como administrador del sistema operativo, en muchas ocasiones tendrás que hacer comprobaciones sobre archivos, qué permisos tienen o a quién pertenecen, y en función de esas comprobaciones realizar unas tareas de administración u otras.

Ejemplo: Escribir un shell script que reciba un argumento (el nombre de un archivo ejecutable) y compruebe si ese archivo está en el directorio bin del usuario que ejecuta el shell script y realmente es ejecutable. Si no está debe escribir por pantalla que no existe ese archivo, y si no es ejecutable debe escribir por pantalla que no es ejecutable.

```
(1) #!/bin/bash # Autor: Francisco de Asís Conde Rodríguez # Descripción: Comprueba si un nombre que se pasa como # argumento corresponde a un programa # ejecutable situado en el directorio ~/bin if [ ${#} -ne 1 ] then echo "Error. Se debe pasar un argumento" exit fi if [ ! -e ${HOME}/bin/${1} ] then
```

```
echo No existe el script: ${1} else if [ ! -x ${HOME}/bin/${1} ] then echo ${1} no es un ejecutable fi fi
```

- (1) La variable HOME contiene la ruta completa del directorio base del usuario que ejecuta el script. Fíjate la importancia de siempre usar las llaves {} en la sustitución de parámetros. Si no se usara, la sustitución ${HOME}/bin/${1} sería imposible.

## Comparar cadenas de caracteres.

En shell script , todos los valores se tratan como cadenas de caracteres a menos que se indique lo contrario, por tanto, es muy importante saber escribir condicionales en los que los argumentos de las condiciones sean cadenas.

Ejemplo: Escribir un shell script que reciba exactamente dos argumentos y que compruebe que son distintos. Si no se escriben dos argumentos, o si éstos son iguales debe escribir un error en la pantalla.

```
#!/bin/bash # Autor: Francisco de Asís Conde Rodríguez # Descripción: Comprueba si los dos argumentos que se dan # son iguales. if [ ${#} -ne 2 ] then echo "Error. No se han dado dos argumentos" else if [ ${1} = ${2} ] then echo "Error. Los argumentos son iguales" fi fi
```

La comprobación de la igualdad de argumentos es útil por ejemplo a la hora de renombrar un archivo. En este caso, si el nombre del archivo que se renombra y el nuevo nombre que se quiere dar al archivo son iguales, no se debería ejecutar la orden de renombrar.

## Comparar expresiones y números.

En este script se comprueba el número de argumentos de datos y que los argumentos contengan sólo números.

Ejemplo: Script triangulo.sh al que pasan 3 argumentos y devuelve el tipo de triángulo utilizando las siguientes condiciones:

Escaleno: Un triángulo en el que cada lado tiene una longitud diferente. Isósceles: Un triángulo en el que 2 de sus lados tienen la misma longitud.

Equilátero: Un triángulo en el que todos los lados tienen la misma longitud.

Para saber si una variable es numérica en Shell Script podemos comprobar con una expresión regular si todos sus caracteres son numéricos.

```
[[ "$variable" =~ ^[0-9]+$ ]]
```

Donde indicamos que entre el comienzo ( ^ ) y el final ( $ ) hay una o más veces ( + ) un elemento comprendido en el rango de 0 a 9 ( [0-9] ). Si hacemos esta comprobación en un if , nos devolverá verdadero si todos los caracteres son numéricos y falso si alguno no lo es.

```
#!/bin/bash # Autor/a: Lina García Cabrera # Descripción: Tipo de triángulo: # EQUILÁTERO, ISÓSCELES o ESCALENO. # Se le pasan 3 números, los lados del triángulo y # dice el tipo de triángulo # Comprobar el número de argumentos if [ $# != 3 ] then echo "No has pasado 3 argumentos." echo "Sintaxis: ${0} lado1 lado2 lado3" else # Comprobar que los argumentos son números if [[ "$1" =~ ^[0-9]+$ ]] && [[ "$2" =~ ^[0-9]+$ ]] && [[ "$3" =~ ^[0-9]+$ ]] then # Todos los lados son iguales if [ $1 -eq $2 ] && [ $2 -eq $3 ] && [ $1 -eq $3 ] then echo "El triángulo es EQUILÁTERO" # 2 lados son iguales elif [ $1 -eq $2 ] || [ $2 -eq $3 ] || [ $1 -eq $3 ] then echo "El triángulo es ISÓSCELES" else echo "El triángulo es ESCALENO"
```

```
fi else echo "Alguno de los argumentos no es un número" echo "Sintaxis: ${0} lado1 lado2 lado3" fi fi
```

## Ejercicios

1. Reescribe el shell script :

```
#!/bin/bash # Autor: Francisco de Asís Conde Rodríguez # Descripción: Comprueba si al script se le han pasado # justamente dos argumentos. if [ ! ${#} -eq 2 ] then echo "Error, se han pasado ${#} argumento(s)" fi
```

para que realice la misma comprobación, pero usando otros operadores.

2. Escribe un shell script que compruebe si se le han pasado entre dos y cuatro argumentos. En caso de que no se le hayan pasado ese número de argumentos que escriba un error, y en caso de que sí se le hayan pasado que los escriba por pantalla.
3. Escribe un shell script que reciba exactamente un argumento, un nombre de usuario, y compruebe si en el directorio base de ese usuario existe un archivo llamado .profile . Si no existe, que lo copie del directorio /etc/skel en el directorio del usuario y le dé permisos -rw-r--r--
4. Escribe un shell script que reciba exactamente un argumento que es el nombre de un directorio. A continuación compruebe si ya existe, y si no existe que lo cree. Por último, tanto si existía previamente como si no, que le dé permisos drwx------
5. Escribe un shell script que reciba exactamente dos argumentos que sean cadenas de caracteres y diga si la primera está ordenada alfabéticamente con respecto a la segunda o no.
6. La tarea de escribir un nuevo shell script requiere varios pasos: comprobar si el nombre del script ya existe, escribir el archivo, darle permisos de ejecución y copiarlo al directorio ~/bin . Escribe un shell script que reciba como argumento el nombre de un nuevo shell script que se quiere escribir y simplifique todos esos pasos. NOTA: En el script puedes comprobar si existe alguna orden o script con el nombre pasado

como parámetro con type redirigiendo salida y error a /dev/null. Luego puedes usar el parámetro especial $ ? devuelve el resultado de la última orden (si se ejecutó con o sin errores) para informar que ese nombre ya existe.

## Propuestas de bash scripts

1. Escribe un script bash al que se le pasan 2 argumentos al que llamaremos cpalabra.sh : el nombre de un fichero de texto y una palabra o frase que debe pasarse entre comillas dobles. El script debe comprobar el número de argumentos y que el primer argumento es un fichero y el segundo un texto. El programa cuenta el número de palabras o frases que hay en el fichero de texto que se pasa como argumento. Indicaciones: utiliza las órdenes grep (busca las opción que solo muestra las coincidencias, no la línea completa) y wc .
2. La orden uniq sin argumentos elimina las líneas de texto que están duplicadas sólo si son adyacentes. Escribe una nueva orden que se llamará uniq_all.sh que recibe dos parámetros, 2 nombres de ficheros. Lo que hace es quitar las líneas repetidas de un fichero estén o no consecutivas y lo guarda en el otro fichero. A continuación tienes un ejemplo del contenido de un fichero con líneas repetidas.
3. El comando du sirve para verificar el uso de espacio en disco en un directorio. Escriba una orden llamada queocupa.sh al que se pasan 3 argumentos: un directorio, y una extensión (algo como .jpg, .png) y un número num y muestra los num ficheros que más ocupan con esa extensión. Indicaciones: Utiliza la opción de la orden du que muestra el espacio en Byte, Kilobyte, Megabyte, Gigabyte, Terabyte and Petabyte, usa las órdenes grep , sort (buscar las opciones que ordena numéricamente). El script debe comprobar el número de argumentos, que el primero es un directorio, el segundo un string que comienza por "." y que el tercero es un número.

| Ejemplo de fichero de entrada                                                                                                                                               | Fichero resultado                                                      |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------|
| Julio Lorenzo Pedro Andión Celia Fernández Celia Fernández Juan Fernández Enrique Peña Julio Lorenzo Pedro Andión Celia Fernández Juan Fernández Enrique Peña Julio Lorenzo | Julio Lorenzo Pedro Andión Celia Fernández Juan Fernández Enrique Peña |

4. Escriba una orden llamada masenlaces.sh al que se pasa 2 argumentos: un directorio y un número. Esta orden muestra los n fi cheros o directorios con más enlaces duros de ese directorio. Indicaciones: tail -n +2 : Omite la primera línea de la salida, que suele ser el encabezado en el caso de ls -l (normalmente "total XX"). La opción -n especifica el número de líneas que quieres mostrar, pero el signo + cambia el comportamiento de tail. En lugar de mostrar las últimas n líneas, +2 indica que se deben mostrar todas las líneas comenzando desde la segunda línea. El script debe comprobar el número de argumentos, que el primero es un directorio y el segundo un número.
5. Escriba una orden llamada num_duplicados.sh a la que se pasa 2 argumentos: un número y un fichero. Esta orden busca en un fichero de configuración (por ejemplo, /etc/passwd o /etc/group ) si uno de sus campos numéricos tiene números duplicados. El argumento número hace referencia al campo que debe verificar. El script debe comprobar el número de argumentos, que el primero es un directorio y el segundo un fichero y que se puede leer. Por ejemplo, en el caso de /etc/passwd , en el campo 3 están los UIDs, en el caso de /etc/group , en el campo 3 están los GIDs. Formas de invocarlos sería:

```
./num_duplicados.sh 3 /etc/group ./num_duplicados.sh 3 /etc/passwd
```

Se puede simular un fichero para probarlo en el que se repitan números.