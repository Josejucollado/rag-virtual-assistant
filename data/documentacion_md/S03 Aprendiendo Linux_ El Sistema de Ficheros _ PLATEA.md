# S03 Aprendiendo Linux_ El Sistema de Ficheros _ PLATEA

## Aprendiendo Linux: El Sistema de Ficheros

Sitio:

PLATEA (Plataforma de Enseñanza y Aprendizaje de la Universidad de Jaén)

Curso:

24/25 Sistemas operativos (13312037-2425,74018016- 2425)

Libro:

Aprendiendo Linux: El Sistema de Ficheros

Imprimido por:

Díaz Galiano, Manuel Carlos

Día:

viernes, 10 de enero de 2025, 00:04

## Descripción

nombres de ficheros, tipos de ficheros en linux, camino, ruta o trayectoria absoluta y relativa, diferencia entre directorio base y directorio de trabajo, listado largo, permisos en directorios y ficheros, cambiar permisos en formato simbólico o en formato octal con chmod, permisos preestablecidos umask, setuid, setgid, Sticky bit

## Tabla de contenidos

## 1. Introducción

- 1.1. Nombres de ficheros
- 1.2. Trayectorias de ficheros (paths)
- 1.3. Directorios base

## 2. Listado de ficheros con ls

- 2.1. Opciones de la línea de órdenes
- 2.2. Interpretación del formato largo
- 2.3. Comodines en las trayectorias de ficheros
3. Cambio de directorio de trabajo
4. Presentación del directorio de trabajo
5. La jerarquía de directorios de UNIX
6. Permisos
- 6.1. Permisos especiales de ficheros y directorios
- 6.2. Permisos de directorios
- 6.3. Establecimiento de permisos de acceso
- 6.4. Ejemplos

## 7. Ejercicios propuestos

## 1. Introducción

Autores: Lina García Cabrera, Francisco Martínez del Río, Pedro Sánchez Sánchez

Copyright:

<!-- image -->

Este material está sometido a las condiciones de una Licencia Creative Commons Attribution-Noncommercial-No Derivative Works 3.0.

En este capítulo se utilizan algunos programas que puedes descargar desde aquí:

- [cambia](https://platea.ujaen.es/pluginfile.php/453769/mod_book/chapter/19464/cambia)
- [consultar.c](https://platea.ujaen.es/pluginfile.php/453769/mod_book/chapter/19464/consultar.c)

El sistema de ficheros de UNIX consta de un conjunto de ficheros. Hay tres tipos de ficheros:

- Ficheros ordinarios , que contienen datos.
- Directorios , que contienen información sobre un conjunto de ficheros. Se emplean para localizar un fichero a partir de su trayectoria o ruta ( path ).
- Ficheros especiales , se utilizan para representar un dispositivo físico real como una impresora, una unidad de cinta o un terminal, utilizado para operaciones de entrada/salida (I/O). Los ficheros de dispositivos suelen estar en el directorio /dev .También tienen otros propósitos.

En los sistemas UNIX hay dos tipos de archivos especiales de dispositivo, archivos especiales de caracteres y archivos especiales de bloque :

- Cuando un archivo especial de caracteres se utiliza para la entrada/salida (I/O) del dispositivo, los datos se transfieren un carácter a la vez. Este tipo de acceso se llama acceso de dispositivo crudo ( raw device access ). Los terminales son dispositivos de carácter.
- En la salida de formato largo de ls -l /dev ,  los archivos de caracteres especiales están marcados conel símbolo de la " c ".
- Cuando se utiliza un archivo especial de bloque para la Entrada/Salida (I/O) del dispositivo, los datos se transfieren en grandes bloques de tamaño fijo. Este tipo de acceso se denomina acceso de dispositivo en bloque.  Los discos son dispositivos de bloque.
- En la salida de formato largo de ls -l /dev , los archivos especiales de bloque están marcados con el símbolo " b ".

Al igual que la mayoría de los sistemas operativos modernos UNIX organiza su sistema de ficheros como una jerarquía de directorios , la cual muchas veces se denomina árbol, aunque casi siempre se dibuja como un árbol invertido. En la parte superior de la jerarquía está un directorio especial: root (raíz) .

Un directorio puede incluir ficheros normales y subdirectorios. UNIX considera a un subdirectorio como un fichero de tipo especial. Si se presenta el contenido de un directorio, se mostrarán los subdirectorios junto con los demás ficheros.

<!-- image -->

## 1.1. Nombres de ficheros

Un nombre de fichero designa a un fichero dentro de un directorio, y consta de un máximo de 14 caracteres en la mayoría de los sistemas System V y un máximo de 255 caracteres en casi todos los sistemas basados en Berkeley.

El nombre de un fichero puede contener cualquier carácter distinto de '/' , aunque algunos caracteres como '-' y (espacio) causan problemas por su significado especial en la línea de órdenes. Casi siempre son caracteres seguros las letras (mayúsculas o minúsculas), los dígitos y los caracteres especiales (+=_: ).

Por convención, un punto al principio de un nombre de fichero indica un fi chero de iniciación (también se llama fi chero oculto ) u otro fichero de apoyo para un programa en particular. Los listados de directorios normalmente no incluyen los ficheros cuyos nombres comienzan por punto (se ocultan a menos que se acompañe la orden de algún parámetro, por ejemplo ls -a ). Los archivos ocultos se utilizan para ejecutar algunos scripts o para almacenar la configuración de algunos servicios en su host. Además, los ficheros con punto reciben un trato especial durante la expansión con comodines .

Los nombres de ficheros distinguen entre mayúsculas y minúsculas , de forma que datos , Datos y DATOS nombran tres ficheros distintos.

## Buenos Consejos para nombrar archivos en Linux

Para evitar que se produzcan problemas con las rutas, caminos o trayectorias de los archivos, sigue estos buenos consejos:

- Nombrar todos sus archivos en minúsculas por defecto.
- En lugar de utilizar un espacio, utilice un ( _ ).
- Usar tipos de archivo consistentes, siempre lo mismo. Por ejemplo, todos los archivos deben llevar la extensión del programa que lo genera.
- Sólo caracteres alfanuméricos, puntos, subrayados y guiones y no uses símbolos como "%", "$", etc.
- Mantén los nombres de los archivos cortos y descriptivos.

## 1.2. Trayectorias de ficheros (paths)

Una trayectoria, camino o ruta de fichero designa a un fichero dentro de la jerarquía de ficheros, y consta de una secuencia de nombres de fichero separados por diagonales (/). Hay dos tipos de trayectorias: las absolutas y las relativas.

Las trayectorias absolutas comienzan con una diagonal; no así las trayectorias relativas.

Trayectorias absolutas . Se puede hacer referencia a un fichero en cualquier parte del árbol especificando su trayectoria absoluta. Ésta especifica la secuencia de subdirectorios que se debe recorrer para llegar de la raíz al fichero . La diagonal que siempre inicia una trayectoria absoluta designa al directorio raíz.

Por ejemplo, UNIX interpreta la trayectoria /usr/humberto/ranas de la siguiente manera:

1. De la raíz, pasar al subdirectorio de nombre usr .
2. De este directorio pasar al subdirectorio de nombre humberto .
3. En este subdirectorio escoger el fichero denominado ranas (el cual podría ser un subdirectorio).

Trayectorias relativas . Cada proceso tiene un directorio denominado directorio actual o directorio de trabajo (forma parte del BCP o descriptor de proceso, esa información se almacena en esa estructura de datos), el cual puede servir como punto de partida para las trayectorias de fichero. La orden pwd ( p rint w orking d irectory) presenta el directorio de trabajo del usuario o directorio actual, es decir, el directorio de trabajo de su proceso de shell . Una trayectoria que no comienza con '/' se denomina trayectoria relativa , y es relativa al directorio de trabajo .

Así pues, si el directorio de trabajo es /usr/humberto , la trayectoria relativa

viajes/ciudad.datos/jakarta

corresponde a la trayectoria absoluta

/usr/humberto/viajes/ciudad.datos/jakarta

El caso más común y sencillo de trayectoria relativa es un nombre de fichero. Este nombre de fichero se refiere al fichero en el directorio actual.

Las notaciones '.' y '..' .

El padre de un directorio d (distinto del directorio raíz) es el directorio que está inmediatamente arriba de d en la jerarquía. El directorio actual se denomina '.' y su padre se llama '..', de manera que se pueden usar trayectorias para subir o bajar por la jerarquía.

Por ejemplo, si el directorio actual es /usr/humberto , como en el ejemplo anterior, '..' se refiere a /usr , '.. / ..' se refiere a la raíz, y '. . /lara ' se refiere a /usr/lara . El directorio raíz es un caso especial, ya que es su propio padre; así, '/..' se refiere a la raíz, lo mismo que '/'.

- . ( punto simple) denota el directorio actual en la ruta.
- .. (dos puntos) indica el directorio principal, es decir, un nivel superior.

## ¿Cuál debe utilizar? ¿Ruta relativa o ruta absoluta?

Para ser sinceros, no hay una respuesta directa a esta pregunta. Realmente depende de la situación.

Si estás muy abajo en la jerarquía de directorios y tienes que moverte un nivel hacia arriba o hacia abajo, el uso de la ruta relativa será más fácil.

Supongamos que estás en el directorio /home/nombredeusuario/programación/proyecto/interfaz/src/header

y tienes que acceder a algo en el directorio /home/nombredeusuario/programación/proyecto/interfaz/bin.

El uso de la ruta relativa le ahorrará escribir todos esos largos nombres de directorios y puede usar simplemente

.. / .. /bin

Pero si tienes que acceder a algo en el directorio

/usr/bin desde el directorio /home/username/programming/project/interface/src/header,

usar algo como ../../../../../usr/bin

no será algo inteligente. Usar la ruta absoluta es lo más sensato en este caso.

Otro caso es el uso de las rutas en scripts o programas . Cuando estés seguro de la ubicación, utiliza la ruta absoluta .

¿Cuál sería la ruta absoluta o relativa para mostrar para mostrar el contenido de mi_script.sh ?

<!-- image -->

¿Cuál sería la ruta absoluta o relativa para mostrar para cambiarte al directorio marco ?

<!-- image -->

## 1.3. Directorios base

Todo usuario tiene un directorio base ( home directory ). La trayectoria absoluta de ese directorio varía de acuerdo con el sistema, pero su último componente generalmente es el nombre del usuario. En System V, el directorio base del usuario usuario casi siempre es el directorio /usr/usuario , y en BSD UNIX normalmente es /u/usuario . Otros sistemas usan /home/usuario o /u/instalación/usuario , donde instalación es el nombre del ordenador anfitrión. El directorio base de un usuario se guarda en la variable de entorno HOME. Puede mostrar el valor del variable HOME, ejecutando  echo $HOME. En los próximos ejemplos seguiremos el convencionalismo de que los directorios base son subdirectorios de /usr .

Los directorios base son muy importantes, por lo que hay una notación especial que reconocen todos los shells de UNIX, con la excepción del shell Bourne: el metacarácter '~' al inicio de una trayectoria se refiere al directorio base del usuario actual , mientras que ' ~ ' se refiere al directorio base del usuario usuario .

Si el directorio base en un sistemas Unix es /usr/nombredeusuario. Entonces, para el usuario humberto ' ~/helado ' se refiere a /usr/humberto/helado y  para el usuario zelda' ~/galletas ' se refiere a /usr/zelda/galletas . Es útil hacer referencias a los directorios de otras personas cuando se trabaja en un proyecto en grupo, o se tiene acceso a información que otra persona hizo de acceso público; en estos casos la notación ' ~ ' hace que las cosas sean más fáciles,

por ejemplo

```
$ echo ~ /home/administrador
```

- $ ls ~/publico Produce un resultado a equivalente a ls /home/alumno/publico

y permite consultar el directorio publico del usuario alumno tecleando menos (se supone que el usuario que ha ejecutado esa orden es alumno ).

## 2. Listado de ficheros con ls

A lo largo de las prácticas hemos utilizado muchas veces esta orden. En esta sección la estudiaremos con algo más de detalle.

La orden ls lista

- un conjunto de ficheros,
- el contenido de un directorio,
- el contenido de un árbol de directorios
- o cualquier combinación de los anteriores.

Puede emplearse para ver si existen ficheros o para examinar sus características.

Su sintaxis es:

## $ ls [opciones] nombre ...

Esta orden lista los directorios y ficheros especificados en nombre ..., y el estilo del listado lo determinan las opciones o el valor por omisión. Dos conjuntos de opciones especialmente útiles son -CF y -l . La opción -l ya la conocemos y la orden

## $ ls -CF nombre ...

lista los ficheros en formato de columna e indica cuáles son directorios o ficheros ejecutables.

Cada nombre en nombre ... es un directorio o un fichero; los nombres sucesivos se separan con espacios. Si se omite nombre ..., se considera como '.' (el directorio actual). Se pueden usar metacaracteres mágicos (comodines) para especificar varios ficheros (ver la sección 2.3). Los elementos que se listarán se determinan de la siguiente manera:

- Si un nombre designa un fichero que no es un directorio, se presenta ese fichero.
- Si el nombre designa un directorio, se listan los ficheros del directorio.
- Si no hay ningún fichero con ese nombre, no se lista nada.

Se excluyen los ficheros y directorios cuyos nombres comienzan con punto, a menos que se especifique la opción -a . Un ejemplo de utilización de ls es:

## $ ls -Fl -a .. harpo

Esta orden lista dos conjuntos de ficheros: aquellos en el directorio padre del directorio actual y aquellos en harpo . Si harpo es un subdirectorio del directorio actual, se listan los ficheros en dicho subdirectorio; si harpo es un fichero del directorio actual, sólo se lista el fichero; y si harpo no está en el directorio actual, no se lista nada por harpo . Las opciones de listado que se aplican son -F , -l y -a .

## 2.1. Opciones de la línea de órdenes

La orden ls puede producir dos tipos de listados: corto y largo.

- El listado corto , que se presenta por omisión, incluye el nombre de cada fichero y la demás información que se solicite de forma explícita;
- el listado largo incluye los permisos de fichero e información adicional. La opción -l genera un listado largo, si no está presente se obtiene un listado corto. A continuación comentamos las opciones más útiles.

Las opciones que siguen afectan al conjunto de ficheros que se incluyen en el listado:

- -a Lista todos los ficheros, incluyendo aquellos cuyo nombre comienza con punto o que se encuentran en un directorio cuyo nombre comienza con punto.
- -d Si un nombre de la línea de órdenes designa un directorio, sólo se lista el nombre del directorio y no su contenido . Se puede usar esta opción junto con -l para ver el estado de un directorio.
- -R Lista los subdirectorios de forma recursiva. En otras palabras, para cada subdirectorio que ls encuentra lista los ficheros de ese subdirectorio y de cada uno de los subdirectorios que contiene directa o indirectamente. El listado muestra la organización de los subdirectorios.
- -f Esta opción sólo se aplica a directorios y hace que ls liste todos los ficheros que contiene el directorio en el orden en que se almacenaron. Esta opción anula las opciones -l , -t , -s y -r (si se especifican) e implica la opción -a para los ficheros que contiene el directorio.

Las opciones que siguen afectan a la información relacionada con los ficheros que se presentan en un listado, sea largo o corto:

- -F Coloca una '/' después de cada fichero que es un directorio y un '*' después de cada fichero ejecutable.
- -i Muestra el número de nodo i de cada fichero (veremos los nodos i en teoría, es un estructura de datos con las propiedades y forma de localizar el contenido del fichero).
- -s Muestra el tamaño en bloques de cada fichero, incluyendo los bloques indirectos (bloques que contienen punteros a otros bloques).

Las opciones siguientes controlan la distribución de un listado corto :

- -C Produce una salida de varias columnas, con las entradas clasificadas de forma vertical.
- -x Produce una salida de varias columnas, con las entradas clasificadas de forma horizontal.
- -m Lista los ficheros a lo ancho de la página, separando los ficheros sucesivos con comas. Esta opción no está disponible en algunos sistemas.

Las opciones que siguen afectan al orden de presentación de los ficheros :

- -t Lista los nombres en orden cronológico, comenzando por los más recientes (a menos que se invierta el orden con -r ). Para la clasificación se utiliza la hora de la última modificación, a menos que se especifique la opción -u .
- -r Lista los ficheros en orden alfabético inverso si no existe la opción -t , y en orden cronológico de más antiguo a más nuevo si está presente la opción -t .

Las opciones que se presentan a continuación afectan a la hora asociada a cada fichero, y la hora afecta al orden de los ficheros si se ha especificado la opción -t ; también aparece en los listados largos incluso si no se ha especificado -t . Por omisión, la hora es la de la última modificación.

- -u Usa la hora del último acceso al fichero.
- -c Usa la hora de la última modificación del nodo i del fichero, específicamente, el momento en que se creó el fichero o la última vez que se modificaron sus permisos. Si están presentes tanto -u como -c , -u controla la hora.

## 2.2. Interpretación del formato largo

La orden ls produce un listado largo si se especifica la opción -l . A continuación se presenta un ejemplo del contenido de un directorio listado con las opciones -lF :

```
total 48 drwxrwxr-x  3 ciclo muses 176 Mar 19 12:06 ./ drwxrwxr-x 13 ciclo muses 944 Feb 16 19:39 ../ drwxr-xr-x  2 ciclo muses  48 Apr  4 11:54 dl/ -rwxr-xr-x  1 root  other   3 Apr 11 12:05 loockup* lrwxrwxrwx  1 ciclo muses   9 Mar 23 09:38 mark -> tmp/marvin -rw-r--r--  3 ciclo mail    4 Apr  3 11:02 news prw-r--r--  1 lara  muses   0 Apr 11 11:09 tubo
```

El listado se interpreta de la siguiente manera:

- El primer carácter de la línea indica el tipo de fichero:
- Fichero ordinario
- d Directorio
- l Enlace simbólico (lo veremos en el siguiente tema)
- b Dispositivo de bloques , transmiten datos en bloques (paquetes) y por esa razón son usados a menudo para la transmisión paralela de datos. Estos dispositivos utilizan el Buffer de datos del sistema operativo.
- c Dispositivo de caracteres , transmiten solo un Bit o solo un Byte a la vez, es decir, utilizan la transmisión serial de datos, sin usar buffer.
- p Interconexión (tuberías, cauce en inglés pipe ) con nombre. Las tuberías sin nombre tienen asociado un fichero en memoria principal, por lo tanto, son temporales y se eliminan cuando no están siendo usados ni por productores ni por consumidores. Permiten la comunicación entre el proceso que crea un cauce y procesos hijos tras la creación de la tubería. Las tuberías con nombre el cauce se crea en el sistema de archivos, y por lo tanto no tienen carácter temporal. Se manejan mediante llamadas al sistema ( open , close , read y write ) como el resto de ficheros del sistema. Permiten la comunicación entre los procesos que usen dicha tubería, aunque no exista una conexión jerárquica entre ellos.

La entrada de un enlace simbólico muestra su nombre en el directorio actual y el nombre del fichero con el que está enlazado.

- Las nueve letras siguientes indican los permisos del fichero como veremos en este mismo tema.
- El elemento que sigue indica cuántos enlaces duros tiene ese fichero (lo veremos también en el siguiente tema). Un directorio dir generalmente tiene varios enlaces, ya que cada uno de sus subdirectorios incluye una entrada para dir como directorio padre y esta entrada cuenta como enlace a dir .
- Los dos elementos que siguen indican el usuario y el grupo propietarios del fichero . El grupo usualmente es el del usuario, pero no es obligatorio que así sea.

- El elemento que sigue muestra el tamaño del fichero en caracteres .  En la parte superior se presenta el número total de bloques de disco ocupados por los ficheros del listado; en el ejemplo se ha ejecutado con la opción -a y se incluyen también los bloques que ocupan . y .., en este caso los 7 ficheros del listado ocupan 48 bloques.
- Los dos elementos que siguen indican la fecha y la hora de la última modificación del fichero . Si se usó la opción -u , se presenta la hora del último acceso; si se empleó la opción -c , aparece la hora de la última modificación del nodo i (ver las descripciones de estas opciones en la sección anterior).
- El último elemento muestra el nombre. Si hay una '/' después del nombre del fichero, indica que se trata de un directorio; un '*' indica un fichero ejecutable (y corresponde a una x en los permisos de usuario).

## 2.3. Comodines en las trayectorias de ficheros

Como vimos en el primer tema los shells permiten hacer referencia a un conjunto de ficheros usando una trayectoria de fichero que contenga uno o más comodines. En esta sección estudiaremos rigurosamente los tipos de comodines y su interpretación.

Hay tres notaciones para los comodines:

- El carácter * representa cualquier secuencia de cero o más caracteres .
- El carácter ? representa un sólo carácter .
- La construcción [ conjuntoc ] representa cualquier carácter del conjunto conjuntoc . El conjunto conjuntoc se escribe como una secuencia de caracteres y pares de caracteres. Un par de caracteres tiene la forma ' c1-c2 ' y representa los caracteres entre c1 y c2 en el conjunto de caracteres ASCII. Tres pares de caracteres de utilidad especial son ' a-z ' (las letras minúsculas), ' A-Z ' (las letras mayúsculas) y ' 0-9 ' (los dígitos decimales). Si se coloca el símbolo ! antes de la secuencia, indica todos los caracteres que no están en la secuencia (algunos shells no permiten la utilización de ! ). A una '/' en la trayectoria real del fichero debe corresponder una '/' explícita en el patrón. Además, un '.' en la trayectoria real de un fichero que esté al principio de la trayectoria o inmediatamente después de una '/' debe tener un '.' correspondiente en el patrón.

A continuación se presentan algunos ejemplos de los comodines y los ficheros a los que pueden referirse:

| Nombre       | Ficheros                                 |
|--------------|------------------------------------------|
| gn*.l        | gnu.l , gneiss.l , gn.l , pero no gn/x.l |
| ~/.[a-zA-Z]* | ~/.login , ~/.mailrc , pero no ~/login   |
| */hacer*     | uno/hacer , dos/hacer.c , pero no hacer  |
| zz?          | zz1 , zza , pero no zz12                 |
| [A-Z]*[!0-9] | Ala , Mario , pero no rosca o Rosca0     |
| *.[acAC]     | archivo.a , archivo.C , pero no .a       |

Puedes encontrar más información sobre los Caracteres Comodín en Caracteres 'comodín' ¿Qué son los caracteres "comodín"?

## [Caracteres Comodín](https://platea.ujaen.es/mod/url/view.php?id=369674)

Preguntas Frecuentes (Prácticas Sistemas Operativos) .

## 3. Cambio de directorio de trabajo

La orden cd sirve para cambiar el directorio de trabajo. Su sintaxis es:

| $ cd [dir]   |
|--------------|

donde dir es la trayectoria (absoluta o relativa) del nuevo directorio actual. Si se omite dir se cambia el directorio actual al directorio base .

cd es una orden que implementa el shell . Esto es así porque el directorio actual es una propiedad de los procesos. Si el shell creara un hijo para que cambiara de directorio actual sólo se cambiaría en el hijo.

## 4. Presentación del directorio de trabajo

La orden pwd ( P rint W orking D irectory ) envía (muestra) la trayectoria del directorio de trabajo a la salida estándar (normalmente la pantalla).

## 5. La jerarquía de directorios de UNIX

En esta sección vamos a explicar algunos directorios de UNIX que guardan ficheros que forman parte importante del entorno proporcionado por UNIX. Sería útil que el lector explorara dichos directorios con órdenes como:

## $ ls -l /bin | more

<!-- image -->

En teoría los directorios de UNIX pueden tener cualquier nombre. En la práctica los nombres y la utilización de varios directorios de primer y segundo nivel de los sistemas UNIX están firmemente establecidos por la tradición.

- /bin : Contiene ciertos programas, disponibles para todos los usuarios, que forman parte de la distribución normal de UNIX. Generalmente el directorio /bin incluye programas como ls , esenciales para iniciar un sistema y repararlo cuando hay problemas. Los ficheros ejecutables especializados pueden estar en otros directorios, la mayoría de los cuales tienen 'bin' en sus trayectorias ('bin' viene de binary , binario)
- /boot : Contiene todos los ficheros necesarios para que arranque el sistema Linux, incluyendo la imagen binaria del kernel de LINUX. El nombre del fichero del kernel es vmlinux (o vmlinuz), seguido por la información de versión y de edición. Por ejemplo, en Red Hat LINUX 6.1, el kernel se encuentra en el fichero /boot/vmlinux-2.2.5-15 file.
- /dev : Contiene ficheros correspondientes a dispositivos externos, como impresoras ('dev' viene de device , dispositivo). Están divididos en dos grupos: ficheros especiales de caracteres y de bloques. Los primeros corresponden a dispositivos cuya E/S se hace en caracteres como el teclado. Los de bloques llevan a cabo la E/S en términos de bloques de bytes , como el disco duro.
- /etc : Contiene ficheros como el de claves ( /etc/passwd ) que se requieren para la administración del sistema. Es común que se almacenen ficheros de datos y programas en este directorio. Otro fichero que pertenece a /etc es /etc/rc , un fichero de órdenes del shell que se ejecuta tras la inicialización del sistema. También se encuentra aquí /etc/group , que almacena los miembros de cada grupo.

- /home : Contiene los directorios iniciales de los usuarios. En ubuntu es el directorio que contiene los directorios base de los usuarios.
- /lib : Contiene bibliotecas ( libraries ) de subprogramas C compilados, que los programas C pueden llamar y enlazar.
- /lost+found : Contiene todos ficheros del sistema que no están asociados a ningún directorio. Estos ficheros se encuentran ejecutando la orden fsck (comprobación del sistema de ficheros).
- /mnt : Lo utiliza el administrador del sistema para montar temporalmente sistemas de ficheros con la orden mount. Cuando se monta el CD-ROM o la disquetera podemos acceder a sus ficheros desde aquí.
- /opt : Sirve para instalar software adicional. Los programas deben ubicarse en /opt/nombre_paquete/bin , en donde nombre_paquete es el nombre del paquete instalado.
- /proc : Contiene información relativa a los procesos y al sistema.
- /root : Se utiliza en muchos sistemas LINUX como directorio inicial de la cuenta root , está protegido.
- /usr : Generalmente contiene subdirectorios y ficheros que pertenecen a usuarios individuales, sea directa o indirectamente. También contiene subdirectorios importantes que se presentan a continuación. La estructura de subdirectorios de /usr imita parcialmente la estructura de root .
- /usr/bin : Por lo general contiene ficheros ejecutables de utilidad, como el editor vi , que no son indispensables para la operación del sistema. Los ficheros ejecutables locales de su instalación podrían estar en /usr/bin , pero es más probable que estén en otro directorio como /usr/local/bin .
- /usr/lib : Contiene diversas bibliotecas y subdirectorios de bibliotecas especializadas para recursos como el sistema X Windows.
- /usr/src : Contiene los ficheros fuente de UNIX, es decir, el texto de los programas C del sistema UNIX. Estos ficheros sólo están disponibles en los sistemas con licencia fuente de UNIX; el acceso a ellos está restringido.
- /usr/include : Contiene ficheros de cabecera para programas C.
- /usr/adm : Contiene información contable, ficheros de diagnóstico generados en el momento de una avería del sistema e información similar requerida por los administradores del sistema.
- /usr/spool : Contiene los ficheros de colas de impresión, es decir, ficheros temporales en espera de procesamiento. Incluye los ficheros por imprimirse, bitácoras administrativas, ficheros que se enviarán a otros ordenadores y ficheros recibidos de otros ordenadores que deben ser recogidos por los usuarios. Los ficheros en /usr/spool , a diferencia de los de /tmp (descrito más adelante) siempre se conservan, incluso si el sistema se apaga.
- /usr/tmp : Una alternativa de /tmp , descrito más adelante.
- /usr/ucb : Contiene programas específicos de Berkeley, como vi y mail (incluso en algunos sistemas que no son de Berkeley).
- /tmp : Contiene ficheros temporales, creados por la operación de diversos programas. En algunos sistemas se pierde el contenido de /tmp cuando se apaga el sistema.
- /var : En algunos sistemas BSD UNIX se emplea para almacenar ficheros que cambian de tamaño frecuente y rápidamente, como los ficheros de colas de impresión y los ficheros de bitácora. En estos sistemas /var/adm y /var/spool sustituyen a /usr/adm y /usr/spool .

Esta estructura de directorios generalmente se duplica en otros directorios. Por ejemplo, el usuario chico podría mantener sus programas personales en /usr/chico/bin y los ficheros fuente de estos programas en /usr/chico/src .

## 6. Permisos

Cuando un usuario entra en una sesión, teclea un nombre de usuario, y después confirma que efectivamente es esa persona tecleando una clave. El nombre es la identificación para iniciar la sesión del usuario, o login-id . Pero el sistema en realidad reconoce al usuario por medio de un número , llamado su identificador de usuario o uid ( User IDentifier ). Además, al usuario se le asigna un identificador de grupo o gid ( Group Identifier ), que lo sitúa en una clase de usuarios. En muchos sistemas todos los usuarios ordinarios (a diferencia de aquellos con un nombre de usuario como root ) se ponen en un sólo grupo llamado other ; sin embargo, el sistema del lector podría ser diferente. El sistema de ficheros y, por tanto, el sistema UNIX, determinan, en general, lo que el usuario puede hacer con los ficheros mediante los permisos otorgados a su uid y a su gid .

El fichero /etc/passwd es el "fichero de claves o contraseñas". Contiene toda la información de inicio de sesión de cada usuario. El lector puede descubrir su uid y su gid como lo hace el sistema, buscando su nombre en /etc/passwd :

$ grep groucho /etc/passwd

groucho:gkmbCTrJ=$COM:604:1:Groucho Marx:/usr/groucho:/bin/sh

La orden grep será estudiada más adelante, su función es seleccionar las líneas de un fichero de texto que contienen un patrón de búsqueda (en este caso groucho ). Los campos del fichero de claves están separados por ":", y están ordenados como sigue:

nombre de usuario: clave codificada: uid : gid : varios: directorio base: shell de inicio

El fichero /etc/passwd es un fichero de texto normal, pero el contenido, el orden de aparición de los campos y los separadores son una convención reconocida por los programas que usan la información del fichero.

El campo de shell de inicio está a menudo vacío, lo que quiere decir que se usa el shell por defecto. El campo varios puede contener cualquier información, incluye con frecuencia el nombre completo del usuario.

El sistema operativo decidió permitir al usuario que leyera /etc/passwd , consultando los permisos asociados con el fichero. Existen tres tipos de permisos para cada fichero:

- r (read) leer (es decir, examinar su contenido),
- w (write) escribir (cambiar su contenido, distinto a borrar el fichero) y
- x (execute) ejecutar (ejecutarlo como programa).

Además, se puede aplicar un permiso diferente a cada persona. Como propietario de un fichero , el lector posee un conjunto de permisos de lectura, escritura y ejecución . Su " grupo " tiene otro conjunto. Los demás (a los que llamaremos " otros ") tienen un tercer conjunto.

La opción -l de la orden ls despliega información, entre otras cosas, sobre los permisos:

$ ls -l /etc/passwd

-rw-r--r-- 1 root adm 5115 Aug 30 10:40 /etc/passwd

Esta línea puede interpretarse como sigue: / etc/passwd pertenece al usuario root , del grupo adm , su tamaño es de 5115 bytes, fue modificado por última vez el 30 de Agosto a las 10:40 AM y posee un enlace (hablaremos sobre enlaces más adelante).

La cadena -rw-r--r-- es la manera en que ls representa los permisos del fichero.

- El primer - indica que se trata de un fichero ordinario. Si se tratara de un directorio habría una d en su lugar.
- Los tres caracteres siguientes codifican los permisos de lectura, escritura y ejecución del dueño o propietario del fichero (basados en el uid ). rwsignifica que root (el propietario) puede leer o escribir sobre el fichero, pero no ejecutarlo. Un fichero ejecutable tendría una x en vez de un guión.
- Los tres caracteres siguientes ( r-- ) codifican los permisos del grupo ; en este caso significa que las personas que pertenecen al grupo adm , pueden leer el fichero, pero no escribir en él, ni tampoco ejecutarlo.
- Los tres siguientes (también r-- ) definen los permisos para cualquier otra persona (el resto de los usuarios del sistema que no son el propietario ni los que pertenecen al grupo).

En esta máquina, por lo tanto, sólo root puede cambiar la información de inicio de sesión para un usuario, pero cualquiera puede leer el fichero para descubrirla. Una alternativa razonable sería que el grupo adm (probablemente los administradores del sistema) también tuviera permiso de escritura sobre /etc/passwd.

<!-- image -->

## 6.1. Permisos especiales de ficheros y directorios

Además de los bits de permisos rwx , UNIX tiene otros tipos de permisos de fichero que usan principalmente (pero no exclusivamente) los programadores de sistemas: Sticky Bit, set-uid bit y set-gid bit . Estos 3 permisos especiales pueden modificar la forma en que funciona un directorio o cómo se ejecuta un programa. Se pueden especificar en modo simbólico o numérico

Estos agregan un carácter más al código , a la nomenclatura octal (xxxx), pero no a la simólica (-). Por ejemplo, podrías encontrarte con códigos tipo 4777, rwS, etc. El primer número en octal se utiliza para activar estos permisos, valor octal 1 para sticky bit, valor octal 2 para set-gid bit y valor octal 4 para set-uid bit. Los valores siempre pueden ser -, S, s, t, T, x, pero no varios al a vez.

A continuación describimos algunos de estos permisos.

## El bit set-uid

El bit set-uid otorga a un programa los permisos del propietario, y no los del usuario que lo llama . En un listado este bit aparece como una s en lugar de la x en los permisos del propietario. Se especifica con una s al usar la orden chmod . ()

Normalmente, cuando se llama a un programa y éste tiene acceso a un fichero los privilegios de acceso del programa al fichero son aquellos relacionados con el identificador del usuario que llamó al programa.

Como ejemplo, suponga lo siguiente:

- El usuario groucho es dueño del fichero ejecutable juego .
- El programa juego utiliza el fichero de datos records , que pertenece a groucho .
- El usuario homer ejecuta el programa juego .

Los permisos que se aplicarán a records durante esta ejecución son los de "otros" (ya que homer no es dueño de records ). A menos que groucho otorgue a "otros" el permiso de escritura de records , el programa juego no podrá tener acceso a él. Sin embargo, si confiere dicho permiso de escritura, homer podrá modificar directamente el fichero records y hacer lo que quiera con la información que contenga, utilizándola de manera no contemplada por groucho .

El bit set-uid permite evitar esta situación . Al activarlo en un fichero ejecutable se especifica que durante la ejecución del programa correspondiente los permisos aplicables son los del propietario del programa, no los del usuario que lo llama. Es decir, el bit set-uid confiere permiso al usuario para tener acceso indirecto a un fichero como records , a través de juego, pero no de forma directa.

Por ejemplo, suponga que se añade lo siguiente al ejemplo anterior:

- Los permisos de records para el dueño son rw .
- Los permisos de records para "otros" están desactivados.
- El bit set-uid del fichero juego está activo.

Ahora, cuando homer ejecuta juego , el proceso se comporta como si el usuario fuera groucho , no homer . Por consiguiente, el proceso tiene el permiso de escritura necesario para records , pero homer no puede tener acceso de lectura o escritura a records de forma directa.

El ejemplo clásico de utilización del bit set-uid es la orden passwd . El fichero de claves /etc/passwd pertenece a root (el superusuario, hacer ls -l /etc/passwd ), y el programa passwd debe escribir en él. Los usuarios comunes deben ser capaces de ejecutar el programa passwd para modificar su clave, pero no se les debe permitir que modifiquen el fichero de claves. Entonces, se activa el bit set-uid para el programa passwd (si en su sistema el programa passwd cuelga del directorio /bin ó en el directorio /usr/bin puede hacer ls -l /bin/passwd ó ls -l /usr/bin/passwd para comprobar la activación de dicho bit), con lo cual puede escribir en /etc/passwd a la vez que se niega el permiso a los usuarios comunes.

Algunos sistemas sólo reconocen el bit set-uid cuando aparece en los permisos de un programa compilado, y lo ignoran si aparece en los permisos de un guión de shell . Sin embargo, la utilización del bit set-uid no está limitada al superusuario.

## Diferencia entre la s minúscula y la S mayúscula como bit SUID

¿Recuerdas la definición de SUID? Permite que un archivo se ejecute con los mismos permisos que el propietario del archivo. ¿Pero qué pasa si el archivo no tiene el bit de ejecución establecido en primer lugar? Así:

teamitsfoss:~$ ls -l test.txt -rw-rw-rw- 1 team itsfoss 0 Apr 12 17:51 test.txt

Si se activa el bit SUID, se mostrará una S mayúscula, no una s minúscula:

teamitsfoss:~$ chmod u+s test.txt teamitsfoss:~$ ls -l test.txt

-rwSrw-rw- 1 team itsfoss 0 Apr 12 17:52 test.txt

La bandera S como SUID significa que hay un error que debes investigar. Se quiere que el archivo se ejecute con el mismo permiso que el propietario, pero no hay permiso de ejecución en el archivo. Lo que significa que ni siquiera el propietario puede ejecutar el archivo. El permiso set-uid (también set-gid) está ligado al de ejecución, ambos deben estar activos.

## El bit set-gid

El bit set-gid es parecido al bit set-uid , excepto que se aplica a los permisos de grupo en lugar de a los permisos de usuario. Cuando un programa con el bit set-gid activado tiene acceso a un fichero, el programa utiliza los privilegios de grupo del fichero de programa en lugar de los del grupo del usuario. El bit set-gid también se especifica con s .

## Bit Adhesivo (Sticky bit)

El bit adhesivo, también llamado bandera de eliminación restringida , tiene el valor octal 1 y en modo simbólico está representado por una t dentro de los permisos del otro. Esto se aplica solo a los directorios y no tiene ningún efecto en los archivos normales. En Linux, evita que los usuarios eliminen o cambien el nombre de un archivo en un directorio a menos que sean propietarios de ese archivo o directorio.

Los directorios con el bit adhesivo establecido muestran una t reemplazando la x en los permisos de otros en la salida de ls -l :

## $ ls -ld Sample_Directory/

drwxr-xr-t 2 carol carol 4096 Dec 20 18:46 Sample_Directory/

En el modo octal, los permisos especiales se especifican mediante una notación de 4 dígitos, donde el primer dígito representa el permiso especial para actuar. Por ejemplo, para establecer el bit adhesivo (valor 1 ) para el directorio Another_Directory en modo octal, con permisos 755 , el comando sería:

## $ chmod 1755 Another_Directory

$ ls -ld Another_Directory

drwxr-xr-t 2 carol carol 4,0K Dec 20 18:46 Another_Directory

Este permiso se suele utilizar en el directorio /tmp que funciona como la papelera de los archivos temporales.

teamitsfoss:~$ ls -ld /tmp

drwxrwxrwt 1 root root 512 Apr 12 13:24 /tmp

Como puedes ver, la carpeta /tmp, tiene la letra t en el mismo lugar que esperamos ver x o - para otros permisos. Esto significa que un usuario (excepto root) no puede borrar los archivos temporales creados por otros usuarios en el directorio /tmp.

## 6.2. Permisos de directorios

Los permisos de ficheros se aplican también a los directorios , aunque funcionan de una forma diferente .

El permiso r de un directorio permite averiguar qué hay en un directorio , pero no es suficiente para tener acceso a los ficheros cuyos nombres aparecen en él (para ello también hay que tener el permiso x activado que nos permite atravesarlo). Por ejemplo, no se puede leer el contenido de los ficheros de un directorio si sólo se tiene acceso r debe además tener activado el permiso x .

El permiso w de un directorio es necesario para añadir ficheros o eliminarlos del directorio , pero NO para modificar un fichero que aparece en el directorio (para ello habrá que tener el permiso w del fichero en cuestión). Para editar un fichero debemos poder llegar hasta él y además que éste tenga el permiso de escritura activado.

El permiso x de un directorio permite al usuario operar sobre los nombres del directorio, alcanzar o atravesar dicho directorio pero no le permite saber su contenido. Un directorio puede tener activado el permiso x , esto es, podemos pasar por él pero si no tiene además activado el permiso de lectura no podemos saber su contenido, esto es, no se puede listar su contenido. Sin el permiso x un usuario no puede ni ejecutar ni leer o modificar los ficheros de un directorio porque no se puede situar en ese directorio.

La última parte sobre los directorios puede sonar un poco confusa. Imaginemos, por ejemplo, que tienes un directorio llamado Another_Directory , con los siguientes permisos:

## $ ls -ld Another_Directory/

d--xr-xr-x 2 carol carol 4,0K Dec 20 18:46 Another_Directory

Imagina también que dentro de este directorio tienes un script de shell llamado hello.sh con los siguientes permisos:

-rwxr-xr-x 1 carol carol 33 Dec 20 18:46 hello.sh

Si eres el usuario carol e intentas enumerar el contenido de Another_Directory , recibirás un mensaje de error, ya que su usuario no tiene permiso de lectura para ese directorio:

## $ ls -l Another_Directory/

ls: cannot open directory 'Another_Directory/': Permission denied

Sin embargo, el usuario carol tiene permisos de ejecución, lo que significa que puede entrar o situarse en el directorio. Por lo tanto, el usuario carol puede acceder a los archivos dentro del directorio, siempre que tenga los permisos correctos para el archivo respectivo . En este ejemplo, el usuario tiene permisos completos para el script hello.sh , por lo que puede ejecutar el script, incluso si no puede leer el contenido del directorio que lo contiene. Todo lo que se necesita es el nombre completo del archivo.

$ sh Another_Directory/hello.sh

Hello LPI World!

## 6.3. Establecimiento de permisos de acceso

La orden chmod permite cambiar los permisos de un fichero. Para que pueda funcionar es necesario tener acceso de escritura a los directorios que contienen los ficheros.

El formato de la orden chmod ( change mode , cambiar modo) es:

$ chmod

```
especifmodo fichero ...
```

donde cada fi chero es la trayectoria de un fichero, y especifmodo es

- una lista de cambios de permisos separados por comas, o bien
- un número octal con un máximo de cuatro dígitos.

Cada cambio de permiso tiene tres partes: una o más letras de "quién", un operador, y una o más letras de permiso. Las letras de "quién" son:

- u permiso para el propietario del fichero
- g permiso para el grupo del fichero
- o permiso para todos los demás usuarios
- a permiso para todos los usuarios (equivale a ugo )

Los operadores son:

+ añadir estos permisos
- quitar estos permisos
- = establecer exactamente estos permisos, eliminando todos los demás para las letras "quién" implicadas.

Los permisos son:

- r lectura
- w escritura
- x ejecución
- s asignar set-uid o set-gid .

Cada cambio modifica los permisos de los ficheros en fichero ... de acuerdo con lo que se indique. Si se omiten las letras de "quién", se toma por omisión el valor a , pero los permisos se modifican con el valor umask que veremos en la siguiente subsección.

## Especificación de permisos en octal

Quizás la forma más sencilla de especificar los permisos sea utilizando un número octal de 4 dígitos como máximo. El número octal se obtiene efectuando la suma de los números de la siguiente lista:

- 4000 activar el bit set-uid .
- 2000 activar el bit set-gid .
- 0400 asignar permiso de lectura para el propietario , r--------, 100 000 000.
- 0200 asignar permiso de escritura para el propietario , -w-------, 010 000 000.
- 0100 asignar permiso de ejecución para el propietario , --x------, 001 000 000.
- 0040,0020,0010 asignar permisos de lectura, escritura o ejecución para el grupo .
- 0004,0002,0001 asignar permisos de lectura, escritura o ejecución para otros usuarios .

## Restricciones

- Únicamente el propietario del fichero o el superusuario pueden cambiar los permisos de un fichero.
- Únicamente puede activar el bit s para un grupo un usuario cuyo grupo sea el mismo que el grupo del fichero, y sólo si se permite al grupo la ejecución del fichero.
- El bit s no tiene sentido para el resto de los usuarios o .

## Ejemplos

A continuación se presentan algunos ejemplos de utilización de chmod :

## $ chmod ug+wx,o+x sartre

otorga permisos de escritura y ejecución del fichero sartre al propietario y al grupo de sartre , y permiso de ejecución a los demás usuarios.

## $ chmod +x camus

suponiendo que el valor umask es 0027, confiere al propietario y a todos los usuarios de su grupo el permiso de ejecutar camus , pero no a los demás usuarios, ya que el valor umask elimina todos los permisos de los demás usuarios.

## $ chmod o=wx kafka

asigna los permisos de kafka para que otros usuarios puedan "escribir" y "ejecutar". Los permisos u y g no cambian.

## $ chmod 644 moloko

asigna los permisos de lectura y escritura al propietario de moloko , y el de lectura a los miembros del grupo y demás usuarios.

## Reducción de los permisos para ficheros de nueva creación.

Cuando un programa crea un fichero, especifica un conjunto de permisos para él. Los conjuntos usuales son rw-r--r-- (644 en octal) para ficheros de datos y rwxr-xr-x (755 en octal) para ficheros ejecutables.

Los permisos de este conjunto se reducen después con el valor umask (mascarilla de usuario), que se puede cambiar con la orden umask . Los permisos se calculan realizando la operación AND bit a bit entre el valor de umask , negado bit a bit, y el valor especificado por el programa.

Así pues, si el valor de umask es 002 (permiso de escritura para otros usuarios), aquellos fuera de su grupo no podrán escribir en los ficheros que usted cree, a menos que cambie el modo de los ficheros con chmod o modifique su valor umask . Un valor umask característico es 022, con lo cual se niega el permiso de escritura a todos los usuarios menos usted.

La sintaxis de la orden umask es:

$ umask [n]

donde n es un número octal de tres dígitos que especifica los permisos que se negarán, umask dice los permisos que queremos quitar. Si se omite n , umask muesta el valor umask vigente. Una vez que se ha asignado el valor umask , sigue vigente durante la ejecución de su shell o hasta que se cambie de nuevo.

## Realiza el siguiente ejercicio :

1. Pon una máscara a 000

- $ umask 000

2. Crea un fichero y un directorio

- $ touch fichero

- $ mkdir directorio

3. Mira los permisos que tienen

- $ ls -l

¿Por qué los permisos son diferentes para el fichero y para el directorio?

## 6.4. Ejemplos

En este apartado se pretende aclarar el uso y funcionamiento de los permisos mediante algunos ejemplos. En ellos se utilizarán las siguientes órdenes:

- cat : cuando se utiliza con la sintaxis cat fich , cat intenta abrir el fichero fi ch en modo de sólo lectura. Si tiene permisos para ello lo lee, y muestra su contenido en la salida estándar.
- cambia : su sintaxis de uso es cambia fich c1 c2 . Este programa intenta abrir el fichero fich en modo de lectura y escritura. Si consigue hacerlo cambia en fi ch todas las ocurrencias del carácter c1 por c2 .

- su : cuando se utiliza con la sintaxis su u se ejecuta un intérprete de órdenes con el identificador de usuario, y de grupo, del usuario u . La orden nos pide el password de u. Para más información consultar el manual.
- Para Crear un usuario normal (debe ser administrador del sistema)

Si se ejecuta adduser sin opciones, creará un usuario normal. Veamos un ejemplo:

```
$ sudo adduser nombre_usuario
```

La orden anterior creará un usuario con las siguientes opciones por defecto :

- Se le asigna y creará el directorio de inicio en /home/nombre_usuario .
- Se le asigna la shell /bin/bash .
- Pregunta por su nombre completo y otros datos como el teléfono, etc.
- Se crea el grupo de nombre igual al nombre del usuario.
- Pregunta por la contraseña para asignarle una. Al introducir la contraseña esta no es visible.

Descarga el programa cambia que aparece en Introducción de este tema.

Ejecutemos ahora los ejemplos:

$ cd # Nos desplazamos a nuestro directorio base Aquí es /home/fmartin pero puede ser /home/administrador o el usuario que está haciendo la práctica que tenga cuenta

$ cp ~/Descargas/cambia . # Copiamos cambia a nuestro directorio base

$ mkdir d # Creamos el directorio d $ ls -ld d # Consultamos sus permisos drwxr-xr-x 2 x1111111 alumno 1024 Oct 4 10:40 d $ echo murcielago > d/f # Creamos el fichero d/f con el contenido murciélago $ ls -l d/f # Observamos con qué permisos se creó d/f -rw-r--r-- 1 x1111111 alumno 11 Oct 4 10:42 d/f $ cat d/f # Observamos (leemos) el contenido de d/f murcielago $ cambia d/f a A # Cambiamos las ocurrencias de a por A en d/f $ cat d/f # Comprobamos que los cambios se realizan murcielAgo $ chmod 000 d/f # Cambiamos los permisos de d/f $ ls -l d/f # Observamos los permisos de d/f ---------- 1 x1111111 alumno 11 Oct 4 10:42 d/f $ cat d/f # Ahora no podemos leer d/f cat: d/f: permiso denegado $ cambia d/f e E # Ni modificarlo cambia: no puedo abrir d/f $ chmod 644 d/f # Restablecemos los permisos de d/f $ chmod 100 d # Establecemos los permisos --x------ en d $ cat d/f # Podemos acceder a los ficheros de d si sabemos su nombre murcielAgo $ ls -l d # Pero no consultar su contenido, porque no se puede leer d ls: d: Permiso denegado

```
$ chmod 400 d # Establecemos los permisos r--------- en d $ ls d # Podemos consultar el contenido de d f $ cat d/f #Pero no podemos usar ningún fichero que cuelgue de d cat: d/f: permiso denegado $ chmod 755 d #Se restablecen los permisos originales rwxr-wr-w de d $ su x2222222 # Ejecutamos un intérprete con un usuario conocido Password: #su nos pide su password (y lo introducimos con éxito) $ cat d/f # Podemos leer d/f siendo x2222222 murcielAgo $ cambia d/f i I # Pero no modificar su contenido cambia: no puedo abrir d/f $ rm d/f # Intentamos borrar d/f siendo x2222222 rm: remove write-protected file `d/f' ? y # Confirmamos el borrado rm: cannot unlink `d/f': Permiso denegado # Pero al final se nos deniega el borrado $ exit # Volvemos a ser el usuario x1111111 $ chmod 666 d/f # Establecemos los permisos rw-rw-rw- en d/f $ su x2222222 # Volvemos a ejecutar un intérprete con un usuario conocido Password: $ cambia d/f i I $ cat d/f murcIelAgo $ exit # Volvemos a ser el usuario x1111111 $ chmod 777 d # Establecemos los permisos rwxrwxrwx en d $ su x2222222 # Volvemos a ejecutar un intérprete con el usuario x2222222 Password: $ rm d/f # Borramos d/f aun siendo x2222222 $ exit #Volvemos a ser el usaurio x1111111 $ umask # Comprobamos el valor de umask 22 $ mkdir d2 # Creamos un directorio d2 $ ls -ld d2 # Consultamos sus permisos drwxr-xr-x x1111111 alumno 1024 Oct 4 10:50 d2 $ echo basura >f # Creamos el fichero f $ ls -l f # Observamos con qué permisos se creó f -rw-r--r-- 1 x1111111 alumno 7 Oct 4 10:52 f
```

$ umask 000 # Establecemos una máscara que no disminuye permisos

$ mkdir d3 # Creamos un directorio d3

$ ls -ld d3 # Consultamos sus permisos

drwxrwxrwx 2 x1111111 alumno 1024 Oct 4 10:54 d3

- ... como se observa, mkdir intenta crear directorios con permisos rwxrwxrwx

$ echo basura >f2

# Creamos el fichero f2

$ ls -l f2 # Observamos con qué permisos se creó f2

-rw-rw-rw- 1 x1111111 alumno 7 Oct 4 10:56 f2

- ... cuando redireccionamos la salida estándar de un programa a un fichero que no existe utilizando el metacarácter ">" el shell intenta crear el fichero de salida con permisos rw-rw-rw-

$ umask 022 # Restablecemos la máscara

## 7. Ejercicios propuestos

- 1) Cree en su directorio base un directorio de nombre d , y dentro de este directorio un fichero de nombre f cuyo contenido sea la palabra hola y un fichero f2 cuyo contenido sea la palabra adiós . Establezca permisos para d y f de forma que:
2. Usted pueda consultar el contenido de d , pero no pueda utilizar (no tenga acceso a) los ficheros que cuelgan de d .
3. Usted pueda consultar el contenido de d y pueda utilizar (tenga acceso a) los fichero que cuelgan de d . Sin embargo, podrá leer el contenido de f , pero no el de f2 .
4. Usted tenga acceso a los ficheros que cuelgan de d , pero no pueda ver su contenido. (Sólo podrá acceder a ellos si sabe sus nombres)
5. Usted pueda eliminar los ficheros que cuelgan de d , pero no puede leerlos ni modificar su contenido.
6. Usted no pueda eliminar los ficheros que cuelgan de d , aunque sí pueda leerlos o modificar su contenido.
- 2) Normalmente un fichero tiene asignados los permisos de forma que se da más o igual privilegio de acceso al propietario que a los miembros del grupo, y más o igual privilegio a los miembros del grupo que al resto de los usuarios. Sin embargo, un fichero podría tener permisos de, por ejemplo, -wxrwxrwx. ¿Podrá el propietario del fichero leerlo? Como propietario no debería, pero, ¿y cómo miembro de grupo?, ¿y cómo miembro del resto?. Experimente con ello y deduzca qué hace UNIX en estos casos.
- 3) Indique justificadamente qué máscara debería suministrarle a la orden umask para que sus ficheros ordinarios se crearan a lo sumo con los permisos rwxr-x---.
- 4) Descargue desde PLATEA el programa fuente consultar.c   a su directorio base. El objetivo de este programa es consultar un fichero de texto compuesto de líneas con el siguiente formato:

## login:nota:

Cada línea almacena dos campos (se utiliza el carácter : para separarlos): el primero representa el login de un usuario, y el segundo una nota (un valor entre 0 y 10). Un ejemplo de contenido de un fichero de este tipo es:

## x1111111:7:

## x2222222:8:

El programa busca la línea que contiene el login del usuario que ejecuta el programa, y muestra su nota. Si el usuario no se encuentra en el fichero se muestra un mensaje alusivo en la salida estándar.

En este ejercicio debe crear en su directorio base un fichero de notas, llámelo, por ejemplo notas . Debe editar su fichero consultar.c y cambiar la línea

#define ruta "/home/fmartin/src/notas"

por una que refleje su fichero de notas, por ejemplo

#define ruta "/home/x1111111/notas"

Compile el programa, y póngale de nombre consultar . Establezca permisos de forma que los demás usuarios puedan saber su nota ejecutando consultar , pero no directamente visualizando el contenido de notas con un programa como cat , esto último les permitiría ver las notas de los demás usuarios. Los demás usuarios tampoco deberían poder modificar su nota.

Como resultado del ejercicio debe comentar qué permisos asignó, y por qué.

- 5) Ejecute una orden para saber cuántos dispositivos de carácter y cuantos dispositivos de bloque tenemos en nuestro sistema de ficheros. Utilice una sola orden utilizando una interconexión o pipe. Use las órdenes ls, grep, wc.
1. Muestra el contenido del directorio actual con información extendida o larga de permisos.
2. Muestra los permisos del directorio actual, no de su contenido.
3. Crea los directorios público, privado y compartido en tu directorio personal.
4. Muestra los permisos de los tres directorios creados en tu directorio personal, público, privado y compartido, no de su contenido. Solo esos tres directorios.
5. Configura los permisos del directorio público para que el propietario tenga permisos de acceso, lectura y escritura, el grupo solo pueda acceder para leer y los otros usuarios no puedan realizar ninguna acción.
6. Configura los permisos del directorio privado para que el propietario tenga permisos de acceso, lectura y escritura, el grupo y el resto no puedan realizar ninguna acción.
7. Configura los permisos del directorio compartido para que el propietario y el grupo tengan permisos de acceso, lectura y escritura y los otros usuarios solo puedan acceder para leer.
8. Muestra información extendida de estos directorios.