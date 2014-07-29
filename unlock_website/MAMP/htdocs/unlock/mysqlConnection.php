<?php
    require("mysqlData.php"); //Requerimos los datos para la conexión a la base de datos. 
     
    class SQLConnection 
    { 
        public function __construct($user,$pass,$host) 
        { 
            $this->sqlUser=$user; 
            $this->sqlPass=$pass; 
            $this->sqlHost=$host; 
        } 
        public function selectDatabase($datab)
        { 
            $this->sqlData=$datab; 
        } 
        public function sqlConnect()
        {
            $sqlCon = @mysql_connect($this->sqlHost,$this->sqlUser,$this->sqlPass); //Se crea el famoso "link identifier', el cual es un valor verdadero en caso de la conexión sea realizada correctamente. Se almacena dentro de $sqlCon 
            if(!$sqlCon) //Si NO existe $sqlCon 
            { 
                die(mysql_error($sqlCon)); //Mata la conexión con la base de datos y muestra el error que tira el SQL 
            } 
        } 
        public function dbSelect() 
        { 
            $sqlSel = mysql_select_db($this->sqlData); //Guarda el valor verdadero si la selección de la base de datos se realizó correctamente y la guarda en $sqlSel 
            if(!$sqlSel) 
            { 
                die(mysql_error($sqlCon)); 
            } 
        } 
    } 
    $sql= new SQLConnection($sqlUser,$sqlPass,$sqlHost); 
    $sql->selectDatabase($sqlBase); 
    $sql->sqlConnect(); 
    $sql->dbSelect(); 
?>