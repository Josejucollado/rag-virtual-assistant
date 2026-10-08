# S01 Administración_Configuración de Linux - Conceptos Básicos de Linux _ PLATEA

## Administración/Configuración de Linux - Conceptos Básicos de Linux

Sitio:

PLATEA (Plataforma de Enseñanza y Aprendizaje de la Universidad de Jaén)

Curso:

24/25 Sistemas operativos (13312037-2425,74018016- 2425)

Libro:

Administración/Configuración de Linux - Conceptos Básicos de Linux

Imprimido por:

Díaz Galiano, Manuel Carlos

Día:

viernes, 10 de enero de 2025, 00:07

## Descripción

Decisiones al instalar linux, distribuciones, jerarquía de sistema ficheros

## Tabla de contenidos

## 1. Principales decisiones que debemos tomar

1.1. ¿Qué distribución voy a utilizar?

1.2. ¿Qué fuente de instalación voy a utilizar?

1.3. Dónde Instalar. Particiones de disco

2. Ejecutando Linux por primera vez

2.1. La jerarquía de directorios

2.2. Instalando paquetes

3. GRUB
4. Certificación Linux

## 1. Principales decisiones que debemos tomar

Autor: Lina García Cabrera & Fernando Martínez La instalación de Linux se ha simplificado extraordinariamente en los últimos años, con asistentes gráficos muy intuitivos que facilitan la tarea. Aún así, es necesario antes de acometer la instalación tener claras tres cuestiones:

<!-- image -->

- qué Linux quiero instalar ,
- desde dónde y
- dónde voy a instalarlo .

## 1.1. ¿Qué distribución voy a utilizar?

Existen multitud de distribuciones de Linux . Decantarse por una u otra suele ser en muchos casos una cuestión de preferencias personales. Las distribuciones matrices que han dado lugar a la gran variedad de distribuciones existentes actualmente. Las distribuciones que se consideran como matrices son: Debian , Slackware y RedHat .

Una distribución Linux (coloquialmente llamada distro ) es una distribución de software basada en el núcleo Linux que incluye determinados paquetes de software para satisfacer las necesidades de un grupo específico de usuarios , dando así origen a ediciones domésticas, empresariales y para servidores. Por lo general están compuestas, total o mayoritariamente, de software libre, aunque a menudo incorporan aplicaciones o controladores propietarios.

Además del núcleo Linux , las distribuciones incluyen habitualmente las bibliotecas y herramientas del proyecto GNU y el sistema de ventanas X Window System . Dependiendo del tipo de usuarios a los que la distribución esté dirigida se incluye también otro tipo de software como procesadores de texto, hoja de cálculo, reproductores multimedia, herramientas administrativas, etcétera. En el caso de incluir herramientas del proyecto GNU, también se utiliza el término distribución GNU/Linux .

Existen distribuciones que están soportadas comercialmente, como Fedora (Red Hat), openSUSE (Novell), Ubuntu (Canonical Ltd.), Mandriva, y distribuciones mantenidas por la comunidad como Debian y Gentoo. Aunque hay otras distribuciones que no están relacionadas con alguna empresa o comunidad, como es el caso de Slackware.

Ubuntu lanza una nueva versión cada 6 meses , y cada lanzamiento tiene un nombre en código y un número de versión . Es posible actualizar de una versión a otra sin necesidad de reinstalar.

El número de versión está basado en la fecha de lanzamiento, siendo el primer número el año y los dos últimos el mes, usando el formato año.mes . Así, la versión 12.04 fue lanzada en abril (04) del año 2012 (12).

El nombre en código o  clave es un nombre no oficial que se le asigna a cada versión, y está determinado por dos palabras (un adjetivo y un sustantivo).

Por ejemplo, Ubuntu 14.04 LTS (nombre clave Trusty Tahr - Tauro Fiel ) fue lanzado el 17 de abril de 2014.

Por ejemplo, Ubuntu 16.04 LTS (nombre clave Xenial Xerus - Ardillas Sociables [1]) Mark Shuttleworth es quién nombra las versiones de Ubuntu. Xenial: significa 'relaciones amistosas entre anfitriones y huéspedes. Xerus: Son las ardillas africanas de tierra, las ardillas más sociables) fue lanzado el 21 de abril de 2016.

Ubuntu 18.04 LTS (nombre clave Bionic Beaver - Castor Biónico [2]) Mark Shuttleworth: Celebramos a las personas que construyen nuestras aplicaciones y paquetes previos, a las personas que construyen Ubuntu en general. En honor a ese trabajo incansable, nuestra mascota de este ciclo es un mamífero conocido por su actitud enérgica, naturaleza industriosa y destreza de ingeniería.fue lanzada el 26 de abril de 2018, con soporte de cinco años.

Ubuntu 20.04 LTS (nombre clave Focal Fossa - Fosa Focal [3]) fosa es un animal muy parecido a un gato, el carnívoro más grande de Madagascar. El adjetivo guarda relación a un foco, por lo que podríamos decir que Focal Fossa es una fosa que se centra, la fosa central o la fosa que atrae todas las miradas.  es la versión LTS que se lanzó el 23 de abril de 2020, con soporte de 5 años. Dispone de GNOME 3.36, Linux Kernel 5.4 y soporte mejorado para ZFS entre otras características.

Ubuntu 22.04 LTS (nombre clave Jammy jellyfish - Mermelada de Medusa) En el Reino Unido también se utiliza la palabra 'jammy' para referirse a algo afortunado . Por tanto, y teniendo en cuenta que nunca nos hemos comido ninguna mascota de Ubuntu, tal vez se pueda traducir por Medusa Afortunada.

LTS son las siglas de L ong T erm S upport , que viene a significar Soporte a Largo Plazo . Si una versión de Ubuntu es LTS, es una versión de Ubuntu estable que tendrá soporte de 5 años y será actualizada durante más tiempo que una versión normal.

## Distribuición GNU Linux

Una distribución GNU/Linux es una colección de software que forma un sistema operativo basado en el kernel Linux. Hay tres elementos software principales que componen un sistema GNU/Linux:

- El kernel Linux : como vimos, el kernel es tan solo la pieza central del sistema. Pero sin las aplicaciones de utilidad, shells, compiladores, editores, etc. no podríamos tener un sistema entero.
- Las aplicaciones GNU : el desarrollo de Linux se vio complementado con el software existente de la FSF dentro de su proyecto GNU, que le aportó un intérprete de comandos (bash), un editor (emacs), un compilador (gcc) y utilidades diversas.
- El software de terceros : el cual permite añadir una serie de aplicaciones de amplio uso (de código abierto en su mayor parte), ya sea el propio sistema gráfico de X-Windows, servidores como el de Apache para la web, navegadores, etc. Asimismo, puede ser habitual incluir algún software propietario, dependiendo del carácter libre que en mayor o menor grado quieran disponer los creadores de la distribución

## Versión del núcleo Linux

La versión del núcleo Linux viene indicada por unos números X.Y.Z , donde normalmente

- X es la versión principal, que representa los cambios importantes del núcleo;
- Y es la versión secundaria, y normalmente implica mejoras en las prestaciones del núcleo: Y es par en los núcleos estables e impar en los núcleos en desarrollo (en pruebas).
- Por último, la Z es la versión de construcción, que indica el número de la revisión de X.Y, en cuanto a parches o correcciones hechas. Los distribuidores no suelen incluir la última versión del núcleo, sino la que ellos hayan probado más y además puedan verificar que es estable para el software y los componentes que ellos incluyen.

La orden uname imprime información del sistema y podemos utilizarlo para conocer el núcleo de nuestro sistema GNU/Linux.

<!-- image -->

Podemos ver el nombre del kernel (núcleo). Como vemos nuestro kernel es Linux pero podía haber sido otro, como por ejemplo Hurd.

## $ uname -s

## Linux

Podemos ver la versión de nuestro núcleo . Vemos que el núcleo es de 64 bits (amd64) cuya versión es la 3.2.0.

- $ uname -r

3.2.0-4-amd64

Si quisiéramos ver la plataforma hardware sobre la que se está ejecutando el núcleo: Es una arquitectura x86 de 64 bits.

$ uname -m

x86_64

[1] Mark Shuttleworth es quién nombra las versiones de Ubuntu. Xenial: significa 'relaciones amistosas entre anfitriones y huéspedes. Xerus: Son las ardillas africanas de tierra, las ardillas más sociables

[2] Mark Shuttleworth: Celebramos a las personas que construyen nuestras aplicaciones y paquetes previos, a las personas que construyen Ubuntu en general. En honor a ese trabajo incansable, nuestra mascota de este ciclo es un mamífero conocido por su actitud enérgica, naturaleza industriosa y destreza de ingeniería.

[3] fosa es un animal muy parecido a un gato, el carnívoro más grande de Madagascar. El adjetivo guarda relación a un foco, por lo que podríamos decir que Focal Fossa es una fosa que se centra, la fosa central o la fosa que atrae todas las miradas.

## 1.2. ¿Qué fuente de instalación voy a utilizar?

La mayor parte de distribuciones de Linux permiten instalar nuestro sistema operativo a partir de diversas fuentes. En cualquier caso, en este momento debemos saber sobre qué plataforma se va a instalar el SO (Intel o AMD) o si necesitamos la versión de 32 o 64 bits . Para la mayoría de los usuarios es preferible la versión de 32 bits, pero si se necesitan más de 4 Gb o se van a manejar grandes archivos en memoria (edición de imágenes, por ejemplo) entonces deberemos decantarnos por la versión de 64 bits. Las fuentes que disponemos para instalar una distribución de Linux son las siguientes:

- Descargar imagen [1]:  Una imagen ISO es un tipo especial de archivo. Se llama imagen porque es un "reflejo" exacto de todo lo que contenga el CD, DVD o BD (Blue-ray Disc) a partir del que se haya creado. El nombre ISO viene de las siglas en inglés de la Asociación Internacional de Estandarización, que fue quien definió sus características. Los archivos de este tipo tienen la extensión de archivo .iso .: el modo más usual es descargar una imagen desde la página de esa distribución, para posteriormente grabarlo en algún dispositivo de almacenamiento secundario, típicamente un CD, DVD, o un memoria USB. También es posible adquirir el CD/DVD con todo lo necesario para la instalación.
- A través de la red : Descargar un pequeño programa de instalación para posteriormente descargar el SSOO a través de la red. Este método requiere conexión a internet cada vez que tengamos que instalar el software.
- Live CD o Live USB : Ejecutar el sistema operativo desde un CD o desde una memoria usb sin necesidad de instalarlo. Este método realmente no instala nada ni modifica el disco (si necesitamos almacenar archivos, se simula un pequeño disco duro en la memoria principal). Realmente, este modo no es válido para instalaciones estables, pero resulta muy útil para evaluar el SO sin instalarlo, o como SO de emergencia en caso que el SO ya instalado esté dañado y no permite acceder al sistema.
- A través de un instalador de Windows : este método es muy similar al basado en red (2), pero tiene la originalidad de que el programa de instalación se ejecuta desde windows, sin necesidad de grabar nada. Esa es su mayor ventaja. Como desventaja, obviamente, necesita tener preinstalado Windows en la máquina, SO con el que convivirá. A este tipo de configuraciones se le suele llamar instalaciones duales . Lo veremos con detalle en el apartado dedicado a GRUB .

[1] Una imagen ISO es un tipo especial de archivo. Se llama imagen porque es un "reflejo" exacto de todo lo que contenga el CD, DVD o BD (Blue-ray Disc) a partir del que se haya creado. El nombre ISO viene de las siglas en inglés de la Asociación Internacional de Estandarización, que fue quien definió sus características. Los archivos de este tipo tienen la extensión de archivo .iso.

## 1.3. Dónde Instalar. Particiones de disco

Es evidente que generalmente la instalación del SO será en un disco duro, pero hay que tener en cuenta que quizás contemos con varios discos o, lo que es más frecuente, deseemos compartir un único disco con otro sistema operativo. Una situación muy frecuente es tener Windows y Linux instalados en la misma máquina. Cada uno de ellos requieren, como mínimo, lo que se denomina una partición del disco .

Una partición de disco es el nombre genérico que recibe cada división presente en una sola unidad física de almacenamiento de datos. Toda partición tiene su propio sistema de archivos (formato); generalmente, casi cualquier sistema operativo interpreta, utiliza y manipula cada partición como un disco físico independiente, a pesar de que dichas particiones estén en un solo disco físico.

El formato o sistema de archivos de las particiones (p. ej. NTFS) no debe ser confundido con el tipo de partición (p. ej. partición primaria), ya que en realidad no tienen directamente mucho que ver.

Independientemente del sistema de archivos de una partición (FAT, ext3, NTFS, etc.), existen 3 tipos diferentes de particiones:

- Partición primaria : Son las divisiones crudas o primarias del disco, solo puede haber 4 de éstas o 3 primarias y una extendida. Depende de una tabla de particiones. Un disco físico completamente formateado consiste, en realidad, de una partición primaria que ocupa todo el espacio del disco y posee un sistema de archivos. A este tipo de particiones, prácticamente cualquier sistema operativo puede detectarlas y asignarles una unidad, siempre y cuando el sistema operativo reconozca su formato (sistema de archivos).
- Partición extendida : También conocida como partición secundaria es otro tipo de partición que actúa como una partición primaria; sirve para contener infinidad de unidades lógicas en su interior. Fue ideada para romper la limitación de 4 particiones primarias en un solo disco físico. Solo puede existir una partición de este tipo por disco, y solo sirve para

contener particiones lógicas. Por lo tanto, es el único tipo de partición que no soporta un sistema de archivos directamente.

- Partición lógica : Ocupa una porción de la partición extendida o la totalidad de la misma, la cual se ha formateado con un tipo específico de sistema de archivos (FAT32, NTFS, ext2,...) y se le ha asignado una unidad, así el sistema operativo reconoce las particiones lógicas o su sistema de archivos. Puede haber un máximo de 23 particiones lógicas en una partición extendida. Linux impone un máximo de 15, incluyendo las 4 primarias, en discos SCSI y en discos IDE 8963.

Cuando arrancamos un PC cuyo disco de arranque cuenta con diversas particiones es necesario indicar cuál de ellas se va a utilizar para cargar el SO. Todos los sistemas modernos ( Linux , cualquier Windows basado en NT e incluso OS/2) son capaces de arrancar desde una unidad lógica. Sin embargo, el denominado MBR ( Master Boot Record ), que es el sector de arranque por defecto utilizado por Windows y DOS, sólo es capaz de continuar el proceso de arranque con una partición primaria. Cuando se utiliza este MBR, es necesario que exista por lo menos una partición primaria que contenga un cargador de arranque (comúnmente el NTLDR de Windows). Otros cargadores de arranque que reemplazan el MBR, como por ejemplo GRUB, no sufren esta limitación.

El MBR es la causa por la que tradicionalmente en sistemas duales Windows/Linux se ha preferido instalar Linux tras Windows, ya que en otro caso Windows instala su propio sector de arranque, que podría no reconocer la partición donde tenemos instalado Linux .

Una partición estándar de Linux requiere típicamente de, al menos, dos particiones:

- Partición de swap . Esta partición la usará linux cuando no le quepan las cosas en la memoria. Usará esta partición como almacén temporal de datos. Se aconseja que esta partición tenga al menos el doble de bytes que la memoria RAM que tengamos. Si tenemos una memoria RAM de 8 Gb, la partición de swap debería tener al menos 16 Gb.
- Otra partición para el resto de los datos.

Es frecuente dividir los datos según sean del usuario o del SO, con lo que nos quedaría:

- La de swap.
- Otra para el sistema operativo
- Otra para nuestros datos.

## 2. Ejecutando Linux por primera vez

Cuando accedamos por primera vez es necesario estar familiarizado con la estructura de directorios que encontraremos, así como los mecanismos de que nos provee el sistema para mantenerlo actualizado e instalar paquetes adicionales como por ejemplo un compilador o un procesador de textos. Lamentablemente no hay un estándar para estas cuestiones, quedando en manos de cada fabricante. Por lo tanto, aunque es posible encontrar distribuciones que no se ajustan exactamente a lo que aquí se describe, si hay consenso entre las distribuciones más populares.

## 2.1. La jerarquía de directorios

La estructura del sistema de archivos nos indica dónde podemos encontrar en el disco nuestros ficheros o los propios del sistema. En UNIX hay algunos estándares de colocación de los archivos, como por ejemplo el FHS ( Filesystem Hierarchy Standard ); así, si tenemos una idea del estándar, sabremos dónde encontrar la mayor parte de los archivos, aunque luego depende de que la distribución lo siga más o menos y de que nos avisen de los cambios que hayan hecho. GNU/Linux sigue el estándar FHS .

Una instalación típica contará con una jerarquía de directorios como la descrita en la figura 1. Lo que podemos encontrar en cada directorio se detalla a continuación:

- / (raíz) : Es el nivel más alto dentro de la jerarquía de directorios. De aquí cuelgan el resto de carpetas, particiones y otros dispositivos. Es por esto que donde se instala el sistema, se selecciona la partición deseada y se le indica que el punto de montaje es justamente /.
- /bin (binarios) : Los binarios son los ejecutables de Linux. Aquí tendremos los ejecutables de los programas propios del sistema operativo, entre ellos órdenes como cp , mv , cat , chown , etc. No es el único directorio que contiene ejecutables como veremos más adelante.

Figura 1. Estructura de directorios Linux

<!-- image -->

- /boot (arranque) : Aquí nos encontramos los archivos necesarios para el inicio del sistema, desde los archivos de configuración de GRUB , LILO , hasta el propio kernel del sistema
- /dev (dispositivos) : Linux se basa en la simpleza y en el tratamiento homogéneo de la información. Linux trata los dispositivos como si fueran un fichero más para facilitar el flujo de la información. En esta carpeta tenéis los dispositivos del sistema, por ejemplo los usb, sda (o hda) con sus respectivos números que indican las particiones, etc.
- /etc (etcétera) : Aquí se guardan los ficheros de configuración de los programas instalados, así como ciertos scripts que se ejecutan en el inicio del sistema. Los valores de estos ficheros de configuración pueden ser complementados o sustituidos por los ficheros de configuración de usuario que cada uno tiene en su respectivo ' home ' (carpeta personal).
- /home (hogar o casa) : Este directorio casa no es más que un directorio que a su vez contiene otros, uno por cada usuario dado de alta en el sistema. Dentro de dichos directorios es donde el usuario tiene su carpeta personal, donde están los ficheros de configuración de usuario, así como los archivos personales del mismo que puede crear, modificar y eliminar bajo su propio criterio.
- /lib (bibliotecas) : Contiene las bibliotecas (también mal conocidas como librerías) del sistema, así como módulos y controladores ( drivers ).
- /lost+found (perdido y encontrado) : Es una carpeta que nos podemos encontrar en todas las particiones. Cuando por cualquier circunstancia se cierra mal el sistema (un apagón por ejemplo), al reiniciar el computador comprobaréis que se llamará al programa fsck para restaurar la integridad del sistema de ficheros. En esta carpeta encontraremos la información que se mal-guardó debido a la incidencia.
- /media (media/medios) : Es donde se montan las unidades que se pueden extraer como los dispositivos USB, disqueteras, unidades de CD/DVD y en algunas distros , como Ubuntu, las particiones adicionales.
- /mnt (montajes) : Es un directorio que se suele usar para montajes temporales de unidades.
- /opt (opcionales) : Destinado para guardar paquetes adicionales de aplicaciones.
- /proc : Información para la virtualización del sistema de ficheros de Linux. El directorio /proc es un sistema de archivos virtual que proporciona información sobre los procesos y el kernel del sistema. Se denomina sistema de archivos virtual porque se encuentra dentro de la RAM y no consume almacenamiento físico. Si se apaga o reinicia el sistema, se borra la RAM y se generan desde cero los archivos del directorio /proc.
- /root : Es el /home del administrador. Es el único /home que no está incluido -por defecto- en el directorio anteriormente mencionado.
- /sbin (binarios de sistema) : Son los ejecutables de administración, tales como mount , umount , shutdown …
- /srv (servicios) : Información del sistema sobre ciertos servicios que ofrece (FTP, HTTP…).
- /sys (sistema) : Información sobre los dispositivos tal y como los ve el kernel Linux .
- /tmp (temporales) : Es un directorio donde se almacenan ficheros temporales. Cada vez que se inicia el sistema este directorio se limpia.
- /usr : Es el directorio padre de otros subdirectorios de importancia:

- /usr/bin : Conjunto de ejecutables de la mayoría de aplicaciones de escritorio entre otras (por ejemplo fi refox ).
- /usr/include : Los ficheros cabeceras para C y C++.
- /usr/lib : Las bibliotecas para C y C++.
- /usr/local : Es otro nivel dentro que ofrece una jerarquía parecida al propio directorio /usr .
- /usr/sbin : Otra serie de comandos administrativos para el sistema.
- /usr/share : Archivos compartidos como ficheros de configuración, imágenes, iconos, etc.
- /usr/src : Tiene en su interior el código fuente para el kernel Linux .
- /var : Ficheros de sistema como el buffer de impresión, logs …
- /var/cache : Se almacenan datos cacheados para las aplicaciones.
- /var/lib : Información sobre el estado actual de las aplicaciones, modificable por las propias aplicaciones.
- /var/lock : Ficheros que se encargan de que un recurso sólo sea usado por una aplicación determinada que ha pedido su exclusividad, hasta que ésta lo libere.
- /var/log : Es uno de los subdirectorios más importantes ya que aquí se guardan todo tipo de logs del sistema.
- /var/mail : Los correos de los usuarios.
- /var/opt : Datos usados por los paquetes almacenados en /opt .
- /var/run : Información sobre el sistema desde que se inició.
- /var/spool : Datos esperando a que sean tratados por algún tipo de proceso.
- /var/tmp : Otro fichero temporal.

## 2.2. Instalando paquetes

Si bien Linux no define el modo en que debe distribuirse software, los distintos fabricantes han ido aportando diversas soluciones. En la actualidad se han reducido a dos los mecanismos de distribución de software los que podemos encontrar en casi cualquier distribución de Linux : los rpm y los deb . Tanto uno como otro permite que instalemos paquetes (software) de otros fabricantes o usuarios de un modo ordenado facilitando la administración de tales paquetes.

- RPM ( Red Hat Package Manager ): originariamente desarrollado por Red Hat , este gestor de paquetes es el elegido por Fedora , Mandriva o Suse , entre otros, además del mismo Red Hat , por supuesto.
- deb : este formato fue desarrollado por Debian , una de las distribuciones que más ha influido en el desarrollo de Linux en entornos empresariales, lo que explica que la gran cantidad de distribuciones (Ubuntu, Knoppix, Maemo…) que soportan los paquetes deb a través de herramientas como apt/aptitude o dpkg .

Si bien los gestores de paquetes han simplificado muchísimo la administración de sistemas Linux , aun persisten algunos problemas, como por ejemplo la gestión de las dependencias entre paquetes , o el hecho de que no es posible gestionar varias versiones de bibliotecas (librerías). A veces es necesario para que funcionen a la vez programas antiguos y modernos.

## 3. GRUB

GRUB es un potente gestor de arranque que es lanzado desde el MBR . Para modificar el tiempo de espera, el sistema operativo por defecto, el nombre de los sistemas operativos y toda la información del arranque de cada uno de ellos se puede hacer modificando el archivo /boot/grub/grub.cfg (versión GRUB 2.0).

## 4. Certificación Linux

Las siglas de LPI significan " Linux Professional Institute ". Y es una organización sin ánimo de lucro que se dedica a la certificación de profesionales de Linux.

## Historia

LPI Inc se constituye formalmente como una organización sin ánimo de lucro en Octubre de 1999, con su sede cerca de Toronto, Canadá. A LPI se le reconoce en todo el mundo como la primera organización en impulsar y apoyar el uso de Linux, Código Abierto y SW Libre. Nuevos colaboradores, patrocinadores e ideas son siempre bienvenidos.

## Nuestra misión

Promover y certificar capacidades esenciales en Linux y Código Abierto a través de la creación de exámenes altamente comprensibles, de gran calidad y además independientes de cualquier distribución.

LPI tiene dos tipos de certificaciones: Linux Essentials y LPIC (1,2,3)

- Linux Essentials está pensado para novatos y aquellos que quieran comenzar su andadura en el mundo del Software Libre. Al aprobar el exámen se obtiene el "LPI Linux Essentials Professional Development Certificate". Especialmente diseñado para colegios.
- LPIC Estas certificaciones LPI han sido diseñadas para certificar la capacitación de los profesionales de las Tecnologías de la Información usando el Sistema Operativo Linux y herramientas asociadas a este sistema .

Ha sido diseñado para ser independiente de la distribución y siguiendo la Linux Standard Base y otros estándares relacionados. Estas certificaciones LPI  están orientadas al puesto de trabajo a desempeñar utilizando para ello procesos de Psicometría para garantizar la relevancia y calidad de la certificación.

Actualmente existen tres niveles de certificación profesional:

- LPIC-1 Linux Server Professional
- LPIC-2 Linux Network Professional
- LPIC-3 Linux Enterprise Professional (especialidades 300, 303 y 304)