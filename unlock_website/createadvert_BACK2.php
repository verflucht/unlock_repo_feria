<?php 
	ob_start();
	error_reporting(E_ALL); 
	ini_set('display_errors', 'On');

	session_start(); 
	require_once 'mysqlConnection.php'; //Requiere el archivo 'SqlConnection.php 

	$name = $_POST["name"];
	$description = $_POST["description"];
	$agency_id = $_SESSION["user"];
	$i = 0;

	echo count($_FILES["images"])."<br>";
	foreach ($_FILES["images"] as $images) {
	 	echo $_FILES["images"]["name"][$i]."<br>";
	 	if($i == count($_FILES["images"])-3){
	 		echo "sale";
	 		break;
	 	}
	 	echo $i++."<br>";
	}

	echo $name."<br>";
	echo $description."<br>";
	echo $agency_id."<br>";

	if (isset($_FILES['image'])) {
		if ($_FILES["image"]["error"] > 0){
			echo "ERROR CTM!!!";
		} else {
			//Vamos a comprobar si el tipo de archivo es permitido y el tamaña no exceda los 100kb
			$permitidos = array("image/jpg", "image/jpeg", "image/gif", "image/png");
			$limite_kb = 10000;

			if (in_array($_FILES["image"]["type"], $permitidos) && $_FILES["image"]["size"] <= $limite_kb * 1024){
				//ahora se asigna la ruta donde se creara el archivo, debe estar en la misma ruta de upload.php
				$ruta = "img/" . $_FILES["image"]["name"];
				//comprobamos si existe el archivo para no volver a copiarlo.
				//o darle otro nombre para que sobrescriba al actual
				if (!file_exists($ruta)) {
					//movemos el archivo desde la ruta temporal a nuestra ruta
					//usamos $resultado para almcenar el booleano del proceso
					$resultado = @move_uploaded_file($_FILES["image"]["tmp_name"], $ruta);
					if ($resultado){
						$nombre = $_FILES["image"]["name"];
						@mysql_query("INSERT INTO adversting (frontimage,name,description,agency_id) VALUES ('$nombre','$name','$description','$agency_id')");
						echo "el archivo se subio correctamente";
						header("Location: cliente.php");
					}
					else {
						echo "error al subir el archivo";
						header("Location: cliente.php");
					}
				}
				//else {
				//	echo $_FILES["image"]["name"] . ", este archivo no existe";
					//header("Location: cliente.php");
				//}
			} else {
				echo "archivo no permitido, es de tipo prohibido o excede el tamaño maximo";
			}
		}
	}
?>