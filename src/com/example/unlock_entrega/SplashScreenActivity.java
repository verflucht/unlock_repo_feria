package com.example.unlock_entrega;

import java.io.File;
import java.util.Timer;
import java.util.TimerTask;

import android.app.Activity;
import android.content.Intent;
import android.content.pm.ActivityInfo;
import android.os.AsyncTask;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Window;
import android.widget.ImageView;

public class SplashScreenActivity extends Activity{

	// establece la duracion del splashscreen
    private static final long SPLASH_SCREEN_DELAY = 2700;    
    private static ImageView imgTTO;
 
    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_PORTRAIT);
        // Esconde la barra de titulo
        requestWindowFeature(Window.FEATURE_NO_TITLE);
 
        setContentView(R.layout.activity_splash_screen);
        imgTTO = (ImageView)findViewById(R.id.ImgTTO);
 
        TimerTask task = new TimerTask() {
            @Override
            public void run() {
            	
            	/////SI NO EXISTE ARCHIVO DE REGISTRO/////
                //inicia sign_in_activity
            	if(!logeado()){
            		Intent mainIntent = new Intent().setClass(
            				SplashScreenActivity.this, LoginActivity.class);
            		startActivity(mainIntent);
            		finish();
            	}
            	/////SI EXISTE EL ARCHIVO DE REGISTRO/////
            	//inicia el main_activity
            	else{
            		Intent mainIntent = new Intent().setClass(
            				SplashScreenActivity.this, MainActivity.class);
            		startActivity(mainIntent);
            		finish();
            	}
            }
        };
 
        new ModAlpha().execute();
        // Simula estar cargando la aplicacion
        Timer timer = new Timer();
        timer.schedule(task, SPLASH_SCREEN_DELAY);
    }
    
    //verifica si existe el archivo registro del login
    public boolean logeado(){
    	
    	File folder = new File("/data/data/com.example.unlock_entrega/shared_prefs/");
    	//si la carpeta no existe retorna false
    	if(!folder.exists()){
    		System.out.println("No Existe la carpeta");
    		return false;
    	}
    	else{
    		System.out.println("La carpeta existe");
    		File file = new File("/data/data/com.example.unlock_entrega/shared_prefs/Usuario.xml");
    		//si no existe el archivo "login.txt"
    		if(!file.exists()){
        		System.out.println("No Existe el archivo Usuario.xml");
        		return false;
        	}
    		else{
    			System.out.println("El archivo login.txt existe");
    			return true;
    		}
    	}
    }
    
    //cambia los valores de alpha de la imagen "take the opportunity"
    public class ModAlpha extends AsyncTask<Void, Integer, Void>{
    	int progress;
    	
    	@Override
    	protected void onPostExecute(Void result){
    		
    	}
    	
    	@Override
    	protected void onPreExecute(){
    		progress = 0;
    	}
    	
    	@Override
    	protected void onProgressUpdate(Integer... values){
    		imgTTO.setAlpha((float)values[0]/(float)100);
    	}
    	
    	@Override
    	protected Void doInBackground(Void... arg0){
    		SystemClock.sleep(800);
    		while(progress<=90){
    			publishProgress(progress);
    			progress++;
    			SystemClock.sleep(17);    			
    		}
    		return null;
    	}
    }
}
