<?php 
	ob_start();
	error_reporting(E_ALL); 
	ini_set('display_errors', 'On');
?>
<!DOCTYPE html>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

<html>
<head>
	<title>Unlock - Atrevete!</title>
	<link rel="stylesheet" type="text/css" href="css/login.css">
	<link rel="stylesheet" href="css/bootstrap.min.css">
	<link rel="stylesheet" href="css/vertical_slider.css">
	<script src="js/vertical_slider.js" type="text/javascript"></script>
	<script type="text/javascript"> 
        function CheckForm() 
        { 
            var User= document.getElementById('inUser').value; //Se crea la variable User conteniendo el valor del input con id 'inUser' 
            var Pass= document.getElementById('inPass').value; 
            var errormsg= 'Debe completar: n' //Se crea un mensaje de error en la variable errormsg 
            if(User == '') //Si la variable 'User' no tiene contenido: 
                { 
                var error= true; //crea la variable 'error' con valor verdadero (existe) 
                var errormsg= errormsg + 'Nombre de Usuarion'; 
                } 
            if(Pass == '') 
                { 
                var error= true; 
                var errormsg= errormsg + 'Contraseñan'; 
                } 
            if(error) //Si existe la variable 'error' (si el valor es verdadero, true): 
            { 
                alert(errormsg) //Muestra un mensaje de alerta con el contenido de la variable 'errormsg' 
            } 
            else //sino 
            { 
                document.getElementById('loginForm').submit(); //Hace un submit en el form con id 'loginForm' 
            } 
        } 
    </script> 
</head>
<body style="padding: 0px;">
<div class="container">
<?php
    session_start(); //Esto inicia la sesión 

    if (isset($_GET["end"])) {
        if ($_GET["end"] == 1) {
            unset($_SESSION['user']);
            unset($_SESSION['time']);
            session_destroy();
        }   
    }
    


    if(isset($_SESSION['user'])) //Si existe la variable de sesión 'user': 
    { 
        $_SESSION['time']= time(); //Se crea la variable de sesión 'time' con el valor de time() (ejemplo: 1339168896) 
        if(isset($_SESSION['time'])) //Si existe la variable de sesión 'time': 
        { 
            $timeNow= time(); //Se asigna el valor de time() (ejemplo: 1339168963) a la variable timeNow 
            $timeCount= $timeNow - $_SESSION['time']; //Se le asigna a la variable timeCount el valor de la variable timeNow menos la variable de sesión 'time' (1339168963 - 1339168896 = 67 segundos) 

            if($timeCount>1200) //Si el valor de la variable timeCount es superior a 1200 (segundos, 20 minutos):  
            { 
                unset($_SESSION['user']); //Se destruye el valor de la variable de sesión 'user' 
                $_SESSION['error'] = 'Su sesion ha expirado. Ingrese nuevamente.'; //Se le asigna un mensaje de error a la variable de sesión 'error' 
            } 
        } 
    } 
    if(isset($_SESSION['error'])) //Si existe la variable de sesión 'error': 
    { 
        echo '<div style="margin-bottom: -52px;" class="alert alert-danger" id="error"><p>'.$_SESSION['error'].'</p></div>'; //Muestra un div con el mensaje de error contenido en la variable de sesión 'error' 
        unset($_SESSION['error']); //Destruye la variable de sesión 'error' 
    } 
    if(isset($_SESSION['user'])) //Si existe la variable de sesión 'user' 
    {  
        $_SESSION['time']= time(); //Se establece el valor time() de la variable de sesión 'time'.  
        header('Location: cliente.php'); //Redirecciona a la carpeta 'home' 
    } 
    else //si no existe la variable de sesión 'user' muestra el html siguiente: 
    { 
?>
	<form class="form-signin" id="loginForm" method="POST" action="login.php">
		<h1 class="form-signin-heading text-muted"><img src="img/unlock.jpg" style="width: 250px; margin: 0 auto;" alt=""></h1>
		<input type="text" id="inUser" name="inUser" class="form-control" placeholder="ID usuario" required="" autofocus="">
		<input type="password" id="inPass" name="inPass" class="form-control" placeholder="Password" required="">
		<input type="button" class="btn btn-lg btn-danger btn-block" id="inForm" onclick="CheckForm()" value="Iniciar Sesión">
	</form>
</div>
</body>
</html>
<?php } ?>