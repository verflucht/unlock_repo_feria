<?php 
	ob_start();
	ini_set('display_errors', 'On');

	session_start(); 
	require_once 'mysqlConnection.php'; //Requiere el archivo 'SqlConnection.php 


	if ($_POST['cancelar']) {
		header("Location: cliente.php");
	}

	if($_POST['crear']){
		$name = $_POST["name"];
		$description = $_POST["description"];
		$agency_id = $_SESSION["user"];
		$url = $_POST["url"];
		$i = 0;
		$ruta_agencia = "img/imagen_frontal/";

		if (isset($_FILES['image'])) {
			if ($_FILES["image"]["error"] > 0){
				echo "ERROR CTM!!!";
			} 
			else {
				if ( !is_dir($ruta_agencia)) {
			    	mkdir($ruta_agencia);
				}
				//Vamos a comprobar si el tipo de archivo es permitido y el tamaña no exceda los 100kb
				$permitidos = array("image/jpg", "image/jpeg", "image/gif", "image/png");
				$limite_kb = 10000;

				if (in_array($_FILES["image"]["type"], $permitidos) && $_FILES["image"]["size"] <= $limite_kb * 1024){
					//ahora se asigna la ruta donde se creara el archivo, debe estar en la misma ruta de upload.php
					$ruta = "img/imagen_frontal/img_" . $_FILES["image"]["name"];
					//comprobamos si existe el archivo para no volver a copiarlo.
					//o darle otro nombre para que sobrescriba al actual
					if (!file_exists($ruta)) {
						//movemos el archivo desde la ruta temporal a nuestra ruta
						//usamos $resultado para almcenar el booleano del proceso
						$resultado = @move_uploaded_file($_FILES["image"]["tmp_name"], $ruta);
						if ($resultado){
							$nombre = $_FILES["image"]["name"];
							@mysql_query("INSERT INTO campana (imagen_frontal,nombre,descripcion,id_agencia) VALUES ('$nombre','$name','$description','$agency_id')");
							
							$id_campaign = @mysql_fetch_array(@mysql_query("SELECT id_campana FROM campana WHERE id_agencia='$agency_id' ORDER BY id_campana DESC"));
							$id_2 = $id_campaign["id_campana"];
							$type_image = str_replace("image/", "", $_FILES["image"]["type"]);
							$path = "img/imagen_frontal/img_".$id_campaign["id_campana"].".".$type_image;
							rename($ruta, $path);
							$nombre = "img_".$id_campaign['id_campana'].".".$type_image;
							echo $id_2;
							@mysql_query("UPDATE campana SET imagen_frontal='$nombre' WHERE id_campana='$id_2'");

							echo "el archivo se subio correctamente";
							header("Location: cliente.php");
						}
						else {
							echo "error al subir el archivo";
							header("Location: cliente.php");
						}
					}
					else {						
						echo "el archivo se subio correctamente";
						header("Location: cliente.php");
					}
				} 
				else {
					echo "archivo no permitido, es de tipo prohibido o excede el tamaño maximo";
					header("Location: cliente.php");
				}
			}
		}

		$id_campaign = @mysql_fetch_array(@mysql_query("SELECT id_campana FROM campana WHERE id_agencia='$agency_id' ORDER BY id_campana DESC"));
		$path = "img/campaign_".$id_campaign['id_campana'];
		$iddes = @mysql_fetch_array(@mysql_query("SELECT id_imagen FROM imagen_lockscreen ORDER BY id_imagen DESC"));
		echo "<br> ID:: ".$iddes['id_imagen'];
		$iddes = $iddes['id_imagen'];
		echo "<br> id: ".$iddes;
		if($iddes == "")
			$iddes = -1;
		echo "<br> id: ".$iddes;
		echo " path: ".$path;
		if ( !is_dir($path)) {
		    mkdir($path);
		}
		echo "<br>".count($_FILES["images"]["name"]);
		foreach ($_FILES["images"]["name"] as $images) {
			echo $i;
			
			if (isset($_FILES["images"]["name"][$i])) {
				if ($_FILES["images"]["error"][$i]){
					echo "ERROR CTM!!!";
				} else {
					//Vamos a comprobar si el tipo de archivo es permitido y el tamaña no exceda los 100kb
					$permitidos = array("image/jpg", "image/jpeg", "image/gif", "image/png");
					$limite_kb = 10000;
					//Multiples imagenes
					if (in_array($_FILES["images"]["type"][$i], $permitidos) && $_FILES["images"]["size"][$i] <= $limite_kb * 1024){
						//ahora se asigna la ruta donde se creara el archivo, debe estar en la misma ruta de upload.php
						$ruta = $path."/".$_FILES["images"]["name"][$i];
						//comprobamos si existe el archivo para no volver a copiarlo.
						//o darle otro nombre para que sobrescriba al actual
						if (!file_exists($ruta)) {
							//movemos el archivo desde la ruta temporal a nuestra ruta
							//usamos $resultado para almcenar el booleano del proceso
							$resultado = @move_uploaded_file($_FILES["images"]["tmp_name"][$i], $ruta);
							if ($resultado){
								$nombre = $_FILES["images"]["name"][$i];
								$type_image = str_replace("image/", "", $_FILES["images"]["type"][$i]);
								$iddes++;
								$newruta = $path."/img_".$id_campaign["id_campana"]."_".$iddes.".".$type_image;
								rename($ruta, $newruta);
								$nombre = "img_".$id_campaign["id_campana"]."_".$iddes.".".$type_image;
								echo $newruta."__".$nombre;
								$type = $_FILES["images"]["type"][$i];
							 	$size = $_FILES["images"]["size"][$i];
							 	$id = $id_campaign['id_campana'];
							 	@mysql_query("INSERT INTO imagen_lockscreen (url_imagen,id_campana,url) VALUES ('$nombre','$id','$url')");
								echo "el archivo se subio correctamente";
								header("Location: cliente.php");
							}
							else {
								echo "error al subir el archivo";
								header("Location: cliente.php");
							}
						}
						else {							
							echo "el archivo se subio correctamente";
							header("Location: cliente.php");
						}
					}
				}
			}else{
				echo "ERROR";
				header("Location: cliente.php");
			}
			$i++;
		}
	}

?>