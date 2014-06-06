package com.example.unlock_prot;

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

	 // fija la duracion de la pantalla splash_screen
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
 
                // Inicia la nueva acivity
                Intent mainIntent = new Intent().setClass(
                        SplashScreenActivity.this, MainActivity.class);
                startActivity(mainIntent);
                finish();
            }
        };
 
        new ModAlpha().execute();
        // Simula estar cargando la aplicacion
        Timer timer = new Timer();
        timer.schedule(task, SPLASH_SCREEN_DELAY);
    }
    
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
