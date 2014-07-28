package com.example.unlock_entrega;

import android.app.ActionBar;
import android.app.Activity;
import android.app.Fragment;
import android.content.Intent;
import android.content.res.Resources;
import android.os.Bundle;
import android.database.sqlite.SQLiteDatabase;
import android.os.AsyncTask;
import android.view.View;
import android.view.View.OnClickListener;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;




import org.apache.http.HttpEntity;
import org.apache.http.HttpResponse;
import org.apache.http.client.ClientProtocolException;
import org.apache.http.client.HttpClient;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.impl.client.DefaultHttpClient;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.DataInputStream;
import java.io.DataOutputStream;
import java.io.File;
import java.io.FileNotFoundException;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.URL;
import java.net.URLConnection;

public class MainActivity extends Activity {
	
	static Button btnDownload;
	static ProgressBar progressBar;
	static TextView txtDownload;
	static Button btnGPS;
	static Button btnCerrar;
	static ImagenesSQLiteHelper imgDB;
	
	@Override	
	protected void onCreate(Bundle savedInstanceState) {
		System.out.println("MAINACTIVITY");
		super.onCreate(savedInstanceState);
		setContentView(R.layout.activity_main);
		startService(new Intent(this,MyService.class));	
		
		// Interfaz 
		
		ActionBar abar= getActionBar();
		abar.setNavigationMode(ActionBar.NAVIGATION_MODE_TABS);
		Resources res = getResources();
		abar.setBackgroundDrawable(res.getDrawable(R.drawable.fondo_rojo));
		//abar.setStackedBackgroundDrawable(res.getDrawable(R.drawable.fondo_gris));
		//Creamos las pestañas
		ActionBar.Tab tab1 = abar.newTab().setText("Inicio");
		ActionBar.Tab tab2 = abar.newTab().setText("Cupones");     
        ActionBar.Tab tab3 = abar.newTab().setText("GiftCard");
        ActionBar.Tab tab4 = abar.newTab().setText("Donaciones");
        
      //Creamos los fragments de cada pestaña
		Fragment tab1fragment = new Tab1Fragment();
		Fragment tab2fragment = new Tab2Fragment();
        Fragment tab3fragment = new Tab3Fragment();
        Fragment tab4fragment = new Tab4Fragment();
		
      //Asociamos los listener a las pestañas
		tab1.setTabListener(new TabListener(tab1fragment));
		tab2.setTabListener(new TabListener(tab2fragment));
        tab3.setTabListener(new TabListener(tab3fragment));
        tab4.setTabListener(new TabListener(tab4fragment));
        
      //Añadimos las pestañas a la action bar
		abar.addTab(tab1);
		abar.addTab(tab2);
        abar.addTab(tab3);
        abar.addTab(tab4);
				
		btnDownload  = (Button)findViewById(R.id.BtnDownload);
		progressBar = (ProgressBar)findViewById(R.id.ProgressBar);
		txtDownload = (TextView)findViewById(R.id.TxtDownload);
		btnCerrar = (Button)findViewById(R.id.BtnCerrar);
		btnGPS = (Button)findViewById(R.id.BtnGPS);
   		
		imgDB = new ImagenesSQLiteHelper(this, "DBImagenes", null, 1);
		
		//AL HACER CLICK SOBRE DOWNLOAD
		btnDownload.setOnClickListener(new OnClickListener() {
             @Override
             public void onClick(View v) {
    
            	  btnDownload.setClickable(false);
            	  btnDownload.setEnabled(false);
            	  progressBar.setVisibility(ProgressBar.VISIBLE);
            	  txtDownload.setVisibility(TextView.VISIBLE);
          		  Download DL = new Download();		
        		  DL.execute();
             }
        });	
		
		//AL HACER CLICK SOBRE LOCALIZACION
		btnGPS.setOnClickListener(new OnClickListener() {
            @Override
            public void onClick(View v) {
            	// Inicia la activity de localización
                Intent mainIntent = new Intent().setClass(
                        MainActivity.this, LocationActivity.class);
                startActivity(mainIntent);
                finish();
            }
       });
		
		//AL HACER CLICK SOBRE CERRAR SESION
		btnCerrar.setOnClickListener(new OnClickListener() {
		    @Override
		    public void onClick(View v) {
		    	//borra archivo de registro
		    	File file = new File("/data/data/com.example.unlock_entrega/shared_prefs/Usuario.xml");
		    	file.delete();
		    	//abre la activity login
		    	Intent mainIntent = new Intent().setClass(
                        MainActivity.this, LoginActivity.class);
                startActivity(mainIntent);
                finish();
		    }
		});	
	}
	
    @Override
    protected void onPause() {
        System.out.println("PAUSE");
    	super.onPause();    	
    }

    @Override
    protected void onStop() {
    	System.out.println("STOP");
        super.onStop();
    }   
	
    @Override
    public void onDestroy(){
    	System.out.println("DESTROY");
        super.onDestroy();
    }
    
    @Override
    public void onResume(){
    	System.out.println("RESUME");
        super.onResume();
    }
    
	static class Download extends AsyncTask<Void, Integer, Void>{

    	InputStream is;
    	int progress;
    	int porcentaje;
    	int total_archivos;
    	boolean finish;
    	
    	// este es le metodo que trabajara con los acceso al php y sus datos
    	protected Void doInBackground(Void... arg0){
    		String resultado = "Error!";
    		
    		HttpClient cliente = new DefaultHttpClient();
    		// se deja la ruta y el php que tiene acceso a la base de datos
    		HttpGet peticionGet = new HttpGet("http://162.243.233.91/unlock/bd.php");
    		try {
    			System.out.println("Entra al try Http");
    			HttpResponse response = cliente.execute(peticionGet);
    			HttpEntity contenido = response.getEntity();
    			is = contenido.getContent();
    		} catch (ClientProtocolException e){
    			System.out.println("Entra al catch Http1");
    			e.printStackTrace();
    		} catch (IOException e){
    			System.out.println("Entra al catch Http2");
    			e.printStackTrace();
    		}
    		BufferedReader buferlector = new BufferedReader(new InputStreamReader(is));
    		StringBuilder sb = new StringBuilder();
    		String linea = null;
    		try {
    			System.out.println("Entra al try while");
    			while((linea = buferlector.readLine()) != null){
    				sb.append(linea);
    			}
    		} catch (IOException e){
    			System.out.println("Entra al catch while");
    			e.printStackTrace();
    		}
    		try {
    			System.out.println("Entra al try close");
    			is.close();
    		} catch (IOException e) {
    			System.out.println("Entra al catch close");
    			e.printStackTrace();
    		}
    		//En respuesta se creara todo el archivo JSON
    		resultado = sb.toString();
    		
    		// Se crean 4 arreglos para guardar cada uno de los datos de las columnas    		
    		int image_id;
    		String image_name;
    		int id_campaign;
    		String url;
    		
    		String direccion;
    		String destino;
    		 		
    		System.out.println("Antes del try "+resultado);
    		try {
    			System.out.println("Entra al try: "+resultado);
    			JSONArray arrayJson = new JSONArray(resultado);
    			System.out.println("Crea JSON");
    			// Se abre la BD para escritura
				SQLiteDatabase db = imgDB.getWritableDatabase();
				// Borra todos los datos de la BD SQLite
				db.execSQL("DELETE FROM Imagenes");
				LockScreenReeiver.total_img = 0;
				System.out.println("BD BORRADA!!");
				total_archivos = arrayJson.length();
				//recorre todos los registros obtenidos de la BD
    			for(int i=0;i<total_archivos;i++){
    				//objectJson es la fila "i" completa de la tabla de la bd
    				JSONObject objetoJson = arrayJson.getJSONObject(i);
    				//Se sacan los 4 datos de la fila y se guardan separados
    				image_id = objetoJson.getInt("id_imagen");
    				id_campaign = objetoJson.getInt("id_campana");
    				image_name = objetoJson.getString("url_imagen");
    				url = objetoJson.getString("url");
    				
    				System.out.println((i+1)+" "+image_id+" "+id_campaign+" "+image_name+" "+url);
    				
    				//se debe guardar la direccion donde esta la imagen
    				direccion = "http://162.243.233.91/unlock/img/campaign_" + id_campaign + "/" + image_name;
    				System.out.println(direccion);
    				//INICIO PARTE DE DESCARGA
    				destino = "/data/data/com.example.unlock_entrega/" + image_name;
    				System.out.println(destino);
    				
    				try {
    		              File dest_file = new File(destino);
    		              URL u = new URL(direccion);
    		              URLConnection conn = u.openConnection();
    		              int contentLength = conn.getContentLength();
    		              
    		              DataInputStream stream = new DataInputStream(u.openStream());
    		              byte[] buffer = new byte[contentLength];
    		              stream.readFully(buffer);
    		              stream.close();
    		              
    		              DataOutputStream fos = new DataOutputStream(new FileOutputStream(dest_file));
    		              fos.write(buffer);
    		              fos.flush();
    		              fos.close();
    		              System.out.println("IMAGEN DESCARGADA!");
    		               
    		          } catch(FileNotFoundException e) {
    		        	  System.out.println("Error1: "+e);
    		          } catch (IOException e) {
    		        	  System.out.println("Error2: "+e); 
    		          }

    				//Guarda los datos en la BD SQLite
    		        if(db != null){    		            
    		            //Insertamos los datos en la tabla Imagenes
    		            db.execSQL("INSERT INTO Imagenes (id, cont, dir, pag) " +
    		                       "VALUES (" + image_id + ", " + (i+1) + ", '" + destino + "', '" + url + "')");
    		            //aumentamos el contador de imagenes guardadas en el smartphone 
    		            LockScreenReeiver.total_img++;    		 
    		            System.out.println("AGREGADO A SQLite!");
    		        }
    		        
    		        //modifica la barra de progresos
    		        progress++;
    		        porcentaje = (progress*100)/total_archivos;
        			publishProgress(porcentaje);
    		        
    			}
    			//Cerramos la base de datos
	            db.close();
	            finish = true;
	            publishProgress(0);
	            
    		} catch (JSONException e) {
    			e.printStackTrace();
    			System.out.println("Error3:"+e);
    		}
    		return null;
    	}
    	
    	protected void onPostExcecute(Void result) {
    		
    	}
    	
    	protected void onProgressUpdate(Integer... values){
    		
    		if(finish){
    			btnDownload.setClickable(true);
    			btnDownload.setEnabled(true);
        		progressBar.setVisibility(ProgressBar.INVISIBLE);
        		txtDownload.setVisibility(TextView.INVISIBLE);
        		txtDownload.setText("");
    		}
    		else{
    			txtDownload.setText(progress+"/"+total_archivos+" imagenes descargadas");
    		}
    		progressBar.setProgress(values[0]);
    	}
    	
    	protected void onPreExecute(){
    		progress = 0;
    		porcentaje = 0;
    		finish = false;
    	}
	}
}
