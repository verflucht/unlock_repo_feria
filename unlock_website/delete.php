<?php 
	ob_start();
	ini_set('display_errors', 'On');
	require_once 'mysqlConnection.php'; //Requiere el archivo 'SqlConnection.php 

	session_start(); 

	$id = $_GET["id"];
	$imagelink = "img/campaign_".$id."/";
	$frontimagelink = "img/imagen_frontal/";


	echo $id."<br>";


	/* Ademas me falta leer todas las imagenes de la campaña, tanto frontimage como images para eliminarlas */

	//Se necesita recorrer la base de datos, y leer los nombres de los archivos para eliminar las imagenes del servidor.
	$SqlQuery1 = "SELECT url_imagen FROM imagen_lockscreen WHERE id_campana = '$id'";
	$searchResult = @mysql_query($SqlQuery1);
	
	//Eliminacion imagenes del servidor.

	while ($row = @mysql_fetch_array($searchResult)) {
		$link = $imagelink.$row["url_imagen"];
		echo $link."<br>";
		unlink($link);
	}

	//Se reccorre la tabla adversting para obtener el nombre de la front image
	$SqlQuery2 = "SELECT imagen_frontal FROM campana WHERE id_campana = '$id'";
	$searchResult = @mysql_query($SqlQuery2);
	while ($row = @mysql_fetch_array($searchResult)) {
		$link = $frontimagelink.$row["imagen_frontal"];
		unlink($link);
	}

	//Finalmente se remueve el directorio
	rmdir($imagelink);

	//Se borra todo lo que exista en la base de datos
	$SqlQuery3 = "DELETE FROM imagen_campana WHERE id_campana = '$id'";
	@mysql_query($SqlQuery3);

	//Se elimina la campaña luego de borrar todas las imagenes
	$SqlQuery4 = "DELETE FROM campana WHERE id_campana='$id'";
	@mysql_query($SqlQuery4);

	header("Location: cliente.php");

 ?>