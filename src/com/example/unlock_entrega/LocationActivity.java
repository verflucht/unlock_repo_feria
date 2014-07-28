package com.example.unlock_entrega;

import android.app.ActionBar;
import android.app.Activity;
import android.content.Context;
import android.content.Intent;
import android.content.res.Resources;
import android.location.Location;
import android.location.LocationListener;
import android.location.LocationManager;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.View.OnClickListener;
import android.widget.Button;
import android.widget.ProgressBar;
import android.widget.TextView;

public class LocationActivity extends Activity{
	
	static TextView txtLatitud;
	static TextView txtLongitud;
	static Button btnActualizar;
	static Button btnDesactivar;
	static Button btnVolver;
	
	private LocationManager locManager;
	private LocationListener locListener;
	
	@Override	
	protected void onCreate(Bundle savedInstanceState) {
		
		super.onCreate(savedInstanceState);
		setContentView(R.layout.activity_location);
		
		txtLatitud = (TextView)findViewById(R.id.TxtLatitud);
		txtLongitud = (TextView)findViewById(R.id.TxtLongitud);
		btnActualizar  = (Button)findViewById(R.id.BtnActualizar);
		btnDesactivar  = (Button)findViewById(R.id.BtnDesactivar);
		btnVolver = (Button)findViewById(R.id.btnBack);
		
		ActionBar abar= getActionBar();
		Resources res = getResources();
		abar.setBackgroundDrawable(res.getDrawable(R.drawable.fondo_rojo));
		
		//AL HACER CLICK SOBRE ACTIVAR
		btnActualizar.setOnClickListener(new OnClickListener() {
             @Override
             public void onClick(View v) {
            	 btnActualizar.setEnabled(false);
            	 btnDesactivar.setEnabled(true);
            	 comenzarLocalizacion();
            	 btnVolver.setVisibility(Button.VISIBLE);
             }
        });	
		
		//AL HACER CLICK SOBRE DESACTIVAR
		btnDesactivar.setOnClickListener(new OnClickListener() {
            @Override
            public void onClick(View v) {
            	btnActualizar.setEnabled(true);
           	 	btnDesactivar.setEnabled(false);
            	locManager.removeUpdates(locListener);
            	btnVolver.setVisibility(Button.VISIBLE);
            }
       });
		
		//AL HACER CLICK SOBRE VOLVER
				btnVolver.setOnClickListener(new OnClickListener() {
		             @Override
		             public void onClick(View v) {
		            	 btnActualizar.setEnabled(true);
		            	 btnDesactivar.setEnabled(false);
		            	 locManager.removeUpdates(locListener);
		            	 
		            	 Intent mainIntent = new Intent().setClass(
		                         LocationActivity.this, MainActivity.class);
		                 startActivity(mainIntent);
		            	 finish();
		             }
		        });	
	}
	
	@Override
    protected void onStop() {
		System.out.println("STOP");
    	super.onStop();
    }   
	
	private void comenzarLocalizacion()
    {
    	//Obtenemos una referencia al LocationManager
    	locManager = (LocationManager)getSystemService(Context.LOCATION_SERVICE);
    	
    	//Obtenemos la última posición conocida
    	Location loc = locManager.getLastKnownLocation(LocationManager.GPS_PROVIDER);
    	
    	//Mostramos la última posición conocida
    	mostrarPosicion(loc);
    	
    	//Nos registramos para recibir actualizaciones de la posición
    	locListener = new LocationListener() {
	    	public void onLocationChanged(Location location) {
	    		mostrarPosicion(location);
	    	}
	    	public void onProviderDisabled(String provider){
	    		Log.i("LocAndroid", "Provider Status: OFF");
	    	}
	    	public void onProviderEnabled(String provider){
	    		Log.i("LocAndroid", "Provider Status: ON");
	    	}
	    	public void onStatusChanged(String provider, int status, Bundle extras){
	    		Log.i("LocAndroid", "Provider Status: " + status);
	    	}
    	};
    	
    	locManager.requestLocationUpdates(
    			LocationManager.GPS_PROVIDER, 5000, 0, locListener);
    }
	
	@Override
    public void onBackPressed() {
        // Don't allow back to dismiss.
    	System.out.println("Back");
    	return;
    } 
	
    private void mostrarPosicion(Location loc) {
    	//Si está acitvado el GPS
    	if(loc != null)
    	{
    		txtLatitud.setText(String.valueOf(loc.getLatitude()));
    		txtLongitud.setText(String.valueOf(loc.getLongitude()));
    		Log.i("LocAndroid", String.valueOf(loc.getLatitude() + " - " + String.valueOf(loc.getLongitude())));    	}
    	//si no esta activado GPS
    	else
    	{
    		txtLatitud.setText("(sin_datos)");
    		txtLongitud.setText("(sin_datos)");
    	}
    }
}
