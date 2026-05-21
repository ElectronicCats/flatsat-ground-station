# Guía Autodidacta: Laboratorio FlatSat CTF

Este documento es una guía paso a paso diseñada para que los estudiantes y profesionales de ciberseguridad espacial puedan resolver los desafíos (CTF) del FlatSat de manera autónoma, comprendiendo los conceptos detrás de cada vulnerabilidad sin revelar las respuestas directamente.

---

## Estructura del Laboratorio
El entorno consta de tres niveles de dificultad, controlados por la variable de entorno `FLATSAT_LEVEL` al iniciar la Ground Station. Cada nivel introduce controles de seguridad adicionales en la web y en el firmware del satélite.

```bash
# Cambiar de nivel (1, 2 o 3)
export FLATSAT_LEVEL=1
python -m webapp.app
```

---

## Nivel 1: Fácil (Web y Texto Claro)
**Objetivo:** Comprometer los controles de acceso de la estación terrena y comunicarse directamente con el transceptor de radio del satélite.

### Reto 1.1: Enumeración de API (GS-12)
* **Concepto:** Falta de control de acceso en la documentación o listado de rutas internas de desarrollo.
* **Pista:** Las aplicaciones web a menudo exponen rutas administrativas o de depuración por descuido. ¿Hay alguna ruta que liste todos los endpoints del servidor?
* **Cómo verificar:** Busca un endpoint en la raíz de la API que devuelva un listado de todos los métodos y rutas disponibles en el sistema.

### Reto 1.2: SQL Injection (GS-01)
* **Concepto:** Las consultas a bases de datos que concatenan texto directamente del usuario son vulnerables a inyecciones de código SQL.
* **Pista:** Observa la barra de búsqueda de telemetría. Intenta ingresar un carácter especial como `'` (comilla simple) y observa la respuesta del servidor. 
* **Estrategia:** Diseña una inyección de tipo `UNION SELECT` para consultar las tablas del sistema (como `users`). Recuerda alinear el número de columnas devueltas por la consulta original.
* **Resultado:** Debes obtener el hash de la contraseña de la cuenta del administrador.

### Reto 1.3: Falsificación de Sesión (GS-05)
* **Concepto:** Mecanismo débil de gestión de sesiones (tokens en texto claro o formatos simples sin firma).
* **Pista:** Decodifica tu propio token de sesión (usualmente en la cookie `session_token`) usando herramientas como Base64. ¿Qué estructura tiene?
* **Estrategia:** Modifica la estructura de tu token para cambiar tu identidad a `admin` y vuelve a codificarlo en Base64. Modifica tu cookie en las herramientas de desarrollo del navegador (`F12`) y navega al panel de administración.

### Reto 1.4: Comandos en Texto Claro (GS-08)
* **Concepto:** Falta de autenticación en la capa física de radio enlace.
* **Pista:** La placa de satélite en Nivel 1 acepta comandos directos por radio sin validar estructura ni firma.
* **Estrategia:** Envía la cadena de texto de prueba estándar (`TEST`) a través del formulario de comandos de radio.
* **Verificación Visual:** El LED Neopixel de la placa cambiará a color **Verde**.

---

## Nivel 2: Medio (Sistemas y CCSDS)
**Objetivo:** Explotar el sistema operativo subyacente de la estación terrena y elevar privilegios utilizando un rol de operador básico.

### Reto 2.1: Local File Inclusion (GS-04)
* **Concepto:** Entrada del usuario utilizada directamente para abrir rutas de archivos locales en el servidor (Directory Traversal).
* **Pista:** Examina el endpoint que lee los logs del sistema. ¿Permite rutas relativas usando `../` para salir del directorio de logs?
* **Estrategia:** Intenta leer archivos comunes de configuración del sistema (como `/etc/passwd` o el archivo de código fuente de la app).

### Reto 2.2: Remote Code Execution (GS-03)
* **Concepto:** Ejecución de comandos del sistema operativo concatenados directamente con la entrada de diagnóstico.
* **Pista:** El comando de diagnóstico de red ejecuta utilidades del sistema en la terminal. ¿Qué pasa si inyectas un separador de comandos como `;` o `&&`?
* **Estrategia:** Ejecuta comandos del sistema operativo a través del diagnóstico para explorar el entorno interno del servidor.

### Reto 2.3: Insecure Direct Object Reference - IDOR (GS-06)
* **Concepto:** Falta de control de acceso horizontal donde un usuario de bajo privilegio puede solicitar recursos de otros usuarios cambiando un identificador.
* **Pista:** Si visitas la configuración de radio de tu propio usuario, observa el número identificador en la URL (ej. `.../config/radio/2`). ¿Qué ocurre si cambias ese identificador al del administrador?
* **Estrategia:** Consulta la información de configuración clasificada del administrador utilizando tu sesión de operador.

### Reto 2.4: Protocolo CCSDS (GS-08)
* **Concepto:** El satélite ahora filtra el texto plano y exige la estructura de trama estándar CCSDS.
* **Pista:** Un paquete CCSDS Space Packet tiene una cabecera de 6 bytes que indica el APID (identificador de aplicación), secuencia y longitud, seguida del comando.
* **Estrategia:** Encapsula el comando PING en formato hexadecimal con la cabecera correspondiente al APID de telemetría y control.
* **Verificación Visual:** Al recibir la trama CCSDS válida, el LED Neopixel cambiará a color **Azul**.

---

## Nivel 3: Difícil (Firmware y Criptografía)
**Objetivo:** Romper la criptografía de las sesiones y explotar una vulnerabilidad física de memoria en el firmware de la placa RP2040.

### Reto 3.1: Falsificación de Tokens Firmados (GS-05 / Lvl 3)
* **Concepto:** Firmas criptográficas débiles debido a secretos compartidos cableados en código fuente o archivos de configuración accesibles.
* **Pista:** Los tokens ahora están firmados con HMAC-SHA256. ¿Cómo obtiene el servidor la clave secreta?
* **Estrategia:** Si lograste leer los archivos de configuración usando vulnerabilidades del Nivel 2, busca la variable `SECRET_KEY` e implementa un script en Python para firmar tu propio token de administrador.

### Reto 3.2: Criptografía SDLS (GS-08 / Lvl 3)
* **Concepto:** Uso de la capa estándar Space Data Link Security (SDLS) para cifrar datos.
* **Pista:** El satélite exige tramas cifradas o autenticadas con AES. La clave maestra se encuentra en la base de datos o en la memoria del satélite.
* **Estrategia:** Extrae la llave maestra de la base de datos mediante volcados de telemetría y utilízala para cifrar las tramas CCSDS antes de transmitirlas por RF.

### Reto 3.3: Buffer Overflow en Firmware (Reto 3.3)
* **Concepto:** Falta de validación de límites en buffers de entrada del firmware en lenguaje C (Stack Buffer Overflow).
* **Pista:** El comando de diagnóstico de memoria `DIAG_MEM` procesa datos sin verificar el tamaño.
* **Estrategia:** Envía un comando `DIAG_MEM` acompañado de un payload de desbordamiento (relleno superior a 32 bytes) para sobrescribir la pila de ejecución del RP2040.
* **Verificación Visual:** El LED Neopixel cambiará a color **Púrpura**, lo que indica que se ha activado la simulación del buffer overflow exitosamente.

---

## Resumen de Indicadores Visuales (LED Neopixel)

| Acción / Reto | Color de LED en Hardware | Significado |
|---|---|---|
| Comando `TEST` (Nivel 1) | **Verde** | Recepción de comando en texto plano exitosa. |
| Comando PING CCSDS (Nivel 2) | **Azul** | Recepción de paquete espacial estructurado exitosa. |
| Comando `DIAG_MEM` Overflow (Nivel 3) | **Púrpura** | Simulación de explotación física de pila exitosa. |
