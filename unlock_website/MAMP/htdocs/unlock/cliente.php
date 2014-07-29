<?php 
	ob_start();
	error_reporting(E_ALL); 
	ini_set('display_errors', 'Off');

	session_start(); 
	require_once 'mysqlConnection.php'; //Requiere el archivo 'SqlConnection.php 

	$sqlSyntax= 'SELECT nombre,direccion,telefono,mail,id_agencia,imagen FROM agencia WHERE id_agencia = "'.$_SESSION['user'].'"'; //Se crea la sintaxis para la base de datos 
    $result= @mysql_query($sqlSyntax); //Se ejecuta el query de $sqlSyntax 
    $sqlSyntax2= 'SELECT nombre FROM agencia WHERE id_agencia = "'.$_SESSION['user'].'"'; //Se crea la sintaxis para la base de datos 
    $result2= @mysql_query($sqlSyntax2); //Se ejecuta el query de $sqlSyntax 
    $sqlSyntax3= 'SELECT id_agencia FROM agencia WHERE id_agencia = "'.$_SESSION['user'].'"'; //Se crea la sintaxis para la base de datos 
    $result3= @mysql_query($sqlSyntax3); //Se ejecuta el query de $sqlSyntax 


    if ($result == FALSE && $result2 == FALSE && $result3 == FALSE) {
    	die(@mysql_error());
    }

    $row = mysql_fetch_array($result);
    $contactname = mysql_fetch_array($result2);
    $agency_id = mysql_fetch_array($result3);

 ?>

<!DOCTYPE html>
<meta http-equiv="Content-Type" content="text/html; charset=UTF-8">

<html lang="es">
<head>
	<title>Unlock! take the opportunity</title>
	<!-- Latest compiled and minified CSS -->
	<link rel="stylesheet" href="css/style.css">
	<link rel="stylesheet" href="css/bootstrap.min.css">
	<link rel="stylesheet" href="css/prueba.css">
	<link rel="stylesheet" href="css/required_field.css">
	<link rel="stylesheet" href="css/propover-file.css">


	<!-- Latest compiled and minified JavaScript -->
	<script type="text/javascript" src="js/jquery-1.11.1.min.js"></script>
	<script src="js/bootstrap.min.js"></script>
	<script src="js/prueba.js"></script>
	<script src="js/require-field.js"></script>
	<script src="js/propover-file.js"></script>



</head>
<body>

<div class="container">
<ul style="background-color:black;" class="nav nav-pills navbar-fixed-top">
  <a class="navbar-brand" href="cliente.php">Unlock! AdvertPanel</a>
  <!--<li class="active"><a href="#">Home</a></li>
  <li><a href="#">Nueva Campana</a></li>
  <li><a href="campanas.html">Ver Campanas</a></li>-->
</ul>
</div>

<div class="row" style="padding: 120px 50px; margin-bottom: -40px;">
	<div class="col-md-2" style="padding: 0 100px;">
	</div>

	<div class="col-md-4" style="padding: 0 100px;">
		<img data-toggle="modal" data-target="#crearCampana" class="img-rounded" style="width:200px; height:200px;" src="img/<?php echo $row["image"]; ?>" alt="">
	</div>
	<div class="col-md-4" style="margin-left: -100px;">
		
		<h4>Agencia : <?php echo $row["nombre"]; ?> <h4>
		<h4>Direccion :<?php echo $row["direccion"]; ?> <h4>
		<h4>Telefono : <?php echo $row["telefono"]; ?></h4>
		<h4>Mail : <?php echo $row["mail"]; ?></h4>
		<h4>Contacto : <?php echo $contactname["user"]; ?></h4>
		<div class="col-sm-4" style="padding: 10px 0px;">
			<p><a href="#" class="btn btn-success" role="button" data-toggle="modal" data-target="#crear-campana">Crear Campaña</a></p>	
		</div>

		<div class="col-sm-2" style="padding: 10px 0px;">
			<p><a href="#" style="visibility:hidden;" class="btn btn-danger" role="button">Editar</a></p>	
		</div>
		<div class="col-sm-4" style="padding: 10px 0px;">
			<p><a href="index.php?end=1" class="btn btn-info" role="button">Cerrar Sesion</a></p>	
		</div>
	</div>
	<!--<div class="col-md-4">
		<a href="#"><img src="img/plus.png" alt="" class="img-rounded" style="width:200px; height:200px; margin: 0 40px;"></a>
		<p  style="width: 150px; margin: 0 auto;">CREAR CAMAPAÑA</p>
	</div>-->
</div>

<div class="container">
    <h2>Campañas</h2>
    <!-- CAMPAÑAS -->
  		<?php 

		$sqlSyntax = 'SELECT id_campana,nombre,descripcion,imagen_frontal from campana where id_agencia="'.$agency_id["id_agencia"].'"'; //Se crea la sintaxis para la base de datos 
    	$advertresult = @mysql_query($sqlSyntax); //Se ejecuta el query de $sqlSyntax 

    	while ($row = mysql_fetch_array($advertresult)) {
			echo '<div class="row form-group product-chooser">';
			
			echo '<form method="POST" action="delete.php" enctype="multipart/form-data">';
			
			echo '<div class="col-xs-12 col-sm-12 col-md-4 col-lg-4">';
				
				echo '<div style="height: 400px;" class="product-chooser-item selected">';
					
					echo '<img src="img/imagen_frontal/'.$row["imagen_frontal"].'" class="img-rounded col-xs-4 col-sm-4 col-md-12 col-lg-12" alt="'.$row["nombre"].'">';
		           
		            echo '<div class="col-xs-8 col-sm-8 col-md-12 col-lg-12">';
						echo '<span class="title">'.$row["nombre"].'</span>';
						echo '<span class="description">'.$row["descripcion"].'</span>';
					echo '</div>';
					echo '<div class="clear"></div>';


			    echo '<input type="input" style="visibility:hidden;" name="id" id="id" value="'.$row["id_campana"].'">';
				echo '<p><a href="#" class="btn btn-success" role="button">Estadísticas</a> <a href="#" class="btn btn-danger"  role="button">Editar</a> <a href="delete.php?id='.$row["id_campana"].'" class="btn btn-success" role="button">Eliminar</a> </p>';
				
		echo '</div>';
    	echo '</form>';

    	echo '</div>';
		}
    	?>
   
    
</div>

<!-- MODAL CREAR CAMPAÑA V2 -->

<div class="modal fade" id="crear-campana" tabindex="-1" role="dialog" aria-labelledby="contactLabel" aria-hidden="true">
    <div class="modal-dialog">
        <div class="panel panel-primary">
            <div class="panel-heading">
                <button type="button" class="close" data-dismiss="modal" aria-hidden="true">X</button>
                <h4 class="panel-title" id="contactLabel"><span class="glyphicon glyphicon-record"></span>Crear Camapaña</h4>
            </div>
            <form action="createadvert.php" method="POST" enctype="multipart/form-data" accept-charset="utf-8">
            <div class="modal-body" style="padding: 5px;">
                  <div class="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
                            <input class="form-control" name="name" placeholder="Nombre Campaña" type="text" required autofocus />
                        </div>
                        <!--<div class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                            <input class="form-control" name="lastname" placeholder="Lastname" type="text" required />
                        </div>-->
                    </div>

                    <div class ="row">
                    	<div class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                            Categoría <?php echo '<br>'; ?>
                            <select id="selectbasic" name="selectbasic" class="form-control">
						      <option value="1">Categoria 1</option>
						      <option value="2">Categoria 2</option>
						      <option value="">Categoria 3</option>
						    </select>
                        </div>
                        <div class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                        	Sexo: <?php echo '<br>'; ?>
                        	<select id="selectbasic" name="selectbasic" class="form-control">
						      <option value="1">Masculino</option>
						      <option value="2">Femenino</option>
						      <option value="3">Mixto</option>
						    </select>
                        </div>
                    </div>
					<div class ="row">
                    	<div class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                            Público Objetivo: <?php echo '<br>'; ?>
                            <select id="selectbasic" name="selectbasic" class="form-control">
						      <option value="1">Público Objetivo 1</option>
						      <option value="2">Público Objetivo 2</option>
						    </select>
                        </div>
                        <div style="visibility:hidden;" class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                        </div>
                    </div>	
                    <div class ="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
                        	Rango Etario: <?php echo '<br>'; ?>
                        	<label class="checkbox-inline" for="checkboxes-0">
						      <input type="checkbox" name="checkboxes" id="checkboxes-0" value="1">
						      1-10
						    </label>
						    <label class="checkbox-inline" for="checkboxes-1">
						      <input type="checkbox" name="checkboxes" id="checkboxes-1" value="2">
						      11-20
						    </label>
						    <label class="checkbox-inline" for="checkboxes-2">
						      <input type="checkbox" name="checkboxes" id="checkboxes-2" value="3">
						      21-30
						    </label>
						    <label class="checkbox-inline" for="checkboxes-3">
						      <input type="checkbox" name="checkboxes" id="checkboxes-3" value="4">
						      31-40
						    </label>
						    <label class="checkbox-inline" for="checkboxes-4">
						      <input type="checkbox" name="checkboxes" id="checkboxes-4" value="">
						      41-50
						    </label>
						    <label class="checkbox-inline" for="checkboxes-5">
						      <input type="checkbox" name="checkboxes" id="checkboxes-5" value="">
						      51-60
						    </label>
						    <label class="checkbox-inline" for="checkboxes-6">
						      <input type="checkbox" name="checkboxes" id="checkboxes-6" value="">
						      61-70
						    </label>
						    <label class="checkbox-inline" for="checkboxes-7">
						      <input type="checkbox" name="checkboxes" id="checkboxes-7" value="">
						      71-80
						    </label>
                        </div>
                    </div>
                    <div class ="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
                    		Descripción: <?php echo '<br>'; ?>
							<textarea style="resize:vertical;" rows="6" class="form-control" id="description" name="description" required></textarea>
                        </div>
                    </div>
                    <div class ="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
                    		#Tags: <?php echo '<br>'; ?>
							<textarea style="resize:vertical;" rows="6" class="form-control" id="tags" name="description" placeholder="Ingrese palabras claves de su campaña y sepárelas por #"></textarea>
                        </div>
                    </div>
                    <div class ="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
	                		Imagen Corporativa: <?php echo '<br>'; ?>
                    		<div class="input-group image-preview">
				                <input type="text" class="form-control image-preview-filename" disabled="disabled"> <!-- don't give a name === doesn't send on POST/GET -->
				                <span class="input-group-btn">
				                    <!-- image-preview-clear button -->
				                    <button type="button" class="btn btn-default image-preview-clear" style="display:none;">
				                        <span class="glyphicon glyphicon-remove"></span> Borrar
				                    </button>
				                    <!-- image-preview-input -->
				                    <div class="btn btn-default image-preview-input">
				                        <span class="glyphicon glyphicon-folder-open"></span>
				                        <span class="image-preview-input-title">Buscar</span>
				                        <input type="file" accept="image/png, image/jpeg, image/gif, image/jpg" name="image"/> <!-- rename it -->
				                    </div>
				                </span>
				            </div><!-- /input-group image-preview [TO HERE]-->
                        </div>
                    </div>
					<div class="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
	                			Url Campaña: <?php echo '<br>'; ?>
                            <input class="form-control" name="url" placeholder="http://www.ejemplo.cl" type="text" required />
                        </div>
                        <!--<div class="col-lg-6 col-md-6 col-sm-6" style="padding-bottom: 10px;">
                            <input class="form-control" name="lastname" placeholder="Lastname" type="text" required />
                        </div>-->
                    </div>
                	<div class ="row">
                        <div class="col-lg-12 col-md-12 col-sm-12" style="padding-bottom: 10px;">
                        	Imagenes Campaña: <br>
	                        <input type="file" multiple="True" accept="image/png, image/jpeg, image/gif, image/jpg" name="images[]"/> <!-- rename it -->
                        </div>
                    </div>
                </div>  
                <div class="panel-footer" style="margin-bottom:-14px;">
                    <input type="submit" name="crear" class="btn btn-success" value="Crear Campaña"/>
                        <!--<span class="glyphicon glyphicon-ok"></span>-->
                    <input type="reset" class="btn btn-danger" value="Clear" />
                        <!--<span class="glyphicon glyphicon-remove"></span>-->
                    <button style="float: right;" type="button" class="btn btn-default btn-close" data-dismiss="modal">Cancelar</button>
                </div>
            </div>
        </div>
    </div>
</div>



</body>
</html>