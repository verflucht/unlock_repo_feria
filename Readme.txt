Prototipo del Proyecto Unlock

Para esta entrega se realizó un prototipo de la aplicación móvil Unlock, que incluye el funcionamiento de la pantalla de bloqueo y un “Splash Screen”. Este prototipo está desarrollado para smartphone’s con sistema operativo Android 3.0 o superiores.

Pantalla de bloqueo:

1) Se logra crear la pantalla de bloqueo con las dos funcionalidades necesarias (desbloqueo y re-direccionar a url de campaña publicitaria).

2) Las imágenes publicitarias de fondo cambian luego de cada desbloqueo del smartphone, cambiando también la url de la campaña publicitaria.

3) La aplicación se ejecuta automáticamente al encender el smartphone.

4) Se muestra la fecha y hora en la pantalla de bloqueo.

5) Se bloquea la expansión de la barra de notificaciones mientras se encuentre en la pantalla de bloqueo.

6) El botón "Back" del smartphone se deshabilita cuando la pantalla de bloqueo está activa.

Splash Screen:

Se crea una pantalla de bienvenida a la aplicación que se ejecuta durante 2.7 segundos. Luego de finalizar ese tiempo, se redirige automáticamente a la pantalla principal de la aplicación.

Organización del código en el repositorio GIT

En el repositorio GIT se encuentra la carpeta del proyecto desarrollado en Eclipse y el archivo de instalación del prototipo llamado “Unlock_prot.apk”.

En la ruta “Unlock_prot/src/com/example/unlock_prot” se encuentra los siguientes archivos:

1) MainActivity.java: código de la página de inicio de Unlock (no desarrollada para esta entrega).

2) MyService.java: servicio que se ejecuta en segundo plano, y que crea un objeto de la clase LockScreenReceiver.

3) LockScreenReceiver.java: extensión de la clase BroadcastReciever encargada de captar el instante en que la pantalla se enciende y apaga. Cuando la pantalla se apaga es el momento en que se inicia la “activity” LockScreenActivity. También esta es iniciada al momento de encender el smartphone de manera automática.

4) LockScreenActivity.java: extensión de la clase Activity que se encarga de crear la pantalla de bloqueo y darle todas las funcionalidades necesarias.

5) SplashScreenActivity.java: extensión de la clase Activity que muestra una pantalla de bienvenida durante pocos segundos, para luego re-direccionar al MainActivity.

En la ruta “Unlock_prot/res” se encuentra todos los recursos necesarios para la aplicación,