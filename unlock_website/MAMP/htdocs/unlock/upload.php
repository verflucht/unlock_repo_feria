<?php 

//echo $_FILES['image']['name']; //este es el nombre del archivo que acabas de subir
//echo $_FILES['image']['type']; //este es el tipo de archivo que acabas de subir
//echo $_FILES['image']['tmp_name'];//este es donde esta almacenado el archivo que acabas de subir.
//echo $_FILES['image']['size']; //este es el tamaño en bytes que tiene el archivo que acabas de subir.
//echo $_FILES['image']['error']; //este almacena el codigo de error que resultaría en la subida.
//imagen es el nombre del input tipo file del formulario.

//conexion a la base de datos
mysql_connect("162.243.233.91", "admin", "malicedix") or die(mysql_error()) ;
mysql_select_db("unlockbetatest") or die(mysql_error()) ;


if (isset($_FILES['image'])) {
	if ($_FILES["image"]["error"] > 0){
		echo "ERROR CTM!!!";
	} else {
		//Vamos a comprobar si el tipo de archivo es permitido y el tamaña no exceda los 100kb
		$permitidos = array("image/jpg", "image/jpeg", "image/gif", "iamge/png");
		$limite_kb = 100;

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
					@mysql_query("INSERT INTO agencia (imagen) VALUES ('$nombre')");
					echo "el archivo se subio correctamente";
					header("Location: ver.php");
				}
				else {
					echo "error al subir el archivo";
					header("Location: index.php");
				}
			}
			else {
				echo $_FILES["image"]["name"] . ", este archivo no existe";
				header("Location: index.php");
			}
		} else {
			echo "archivo no permitido, es de tipo prohibido o excede el tamaño maximo";
		}
	}
}

?>

<html>
<head>
	<title></title>
</head>
<body>
<html>
<head>
    <title>SUBIR IMAGENES</title>
</head>
<body>
    <form action="upload.php" method="POST" enctype="multipart/form-data">
        <label form ="image">Imagen:</label>
        <input type="file" name="image" id="image">
        <input type="submit" name="upload" value="Upload Image">
    </form>
</body>
</html>
</body>
</html>