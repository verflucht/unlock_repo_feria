<?php
	ob_start();
	error_reporting(E_ALL); 
	ini_set('display_errors', 'On');

 	session_start(); 

    require_once 'mysqlConnection.php'; //Requiere el archivo 'SqlConnection.php 
    class login //Crea la clase 'login' 
    { 
        public function __construct($usr,$inUsr,$inPss) //Crea la función '__construct' con el las tres variables. 
        { 
            $this->Username=$usr; 
            $this->PostUser=$inUsr; 
            $this->PostPass=$inPss; 
        } 
        public function checkSession() //Crea la función 'checkSession()' 
        { 
            if(isset($this->Username)) //Si existe la variable 'Username': 
            { 
                header("Location: index.php"); //Redirige una carpeta atrás. O sea al index.php 
            } 
        } 
        public function checkForm() //Crea la función 'checkForm()' 
        { 
            if(!isset($this->PostUser)) //Si NO existe la variable 'PostUser': 
            { 
                header("Location: index.php"); 
            } 
            if(!isset($this->PostPass)) 
            { 
                header("Location: index.php"); 
            }    
        } 
    } 
    $check= new login($_SESSION['user'],$_POST['inUser'],$_POST['inPass']); //Se crea una nueva clase 'login' con los valores 'Username'=$_SESSION['user'] ; 'PostUser'=$_SESSION['inUser'] ; 'PostPass'=$_SESSION['inPass'] 
    $check-> checkSession(); //Se ejecuta la función 'checkSession()' 
    $check-> checkForm(); //Se ejecuta la función 'checkForm() 

    $sqlSyntax= 'SELECT user,pass FROM agencia WHERE id_agencia = "'.$_POST['inUser'].'" AND pass = "'.$_POST['inPass'].'"'; //Se crea la sintaxis para la base de datos 
    $sqlQuery= mysql_query($sqlSyntax); //Se ejecuta el query de $sqlSyntax 
    $sqlSyntax2= 'SELECT id_agencia FROM agencia WHERE id_agencia = "'.$_POST['inUser'].'"';  //Se crea la siguiente sintaxis 
    $sqlQuery2= mysql_query($sqlSyntax2); //Se ejecuta el segundo query 
    $sqlRow= mysql_num_rows($sqlQuery); //Se verifica el total de filas devueltas de $sqlQuery 
    if($sqlRow==1) //Si el valor devuelto por $sqlRow es igual a 1: 
    { 
        while($resQry2= mysql_fetch_array($sqlQuery2)) //Mientras se lee el array y lo guarda en $resQry2 ejecutando el segundo query: 
        { 
            $_SESSION['user']= $resQry2[0]; //Le asigna el valor contenido en la posición 0 del arrray a la variable de sesión 'user' 
        } 
        header('Location: index.php'); 
        $_SESSION['error']= 'Bienvenid@ '.$_SESSION['user'].''; //Le asigna a la variable de sesión un mensaje de bienvenida con el nombre del usuario 
        $_SESSION['time']= time(); //Asigna el valor time() a la variable de sesión 'time' 
         
    } 
    else //Si el valor de filas devuelto es distinto de 1: 
    { 
		$_SESSION['error']= 'Usuario o contraseña incorrectos'; //Se le asigna un mensaje de error a la variable de sesión 'error' 
    	header('Location: index.php');
	}
?>