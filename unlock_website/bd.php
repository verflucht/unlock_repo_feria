<?php
error_reporting(E_ALL ^ E_DEPRECATED);
mysql_connect('162.243.233.91', 'admin', 'malicedix') or die('No se encontro nada');
mysql_select_db('unlockbetatest');
$sql = "SELECT * FROM  imagen_lockscreen";
$resultado = mysql_query($sql);
while ($row = mysql_fetch_assoc($resultado)){
	$arr[] = $row;
}
$json = json_encode($arr);
echo $json;
?>