package com.example.unlock_prot;

import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class LockScreenReeiver extends BroadcastReceiver{
	
	//varibles de clase
	public static boolean wasScreenOn = true;
	public static boolean active = false;
	public static int cont = 0;
	public static int total_img = 0;

	@Override
	public void onReceive(Context context, Intent intent) {
		
		//si la pantalla se apaga, carga una nueva pantalla de bloqueo
        if (intent.getAction().equals(Intent.ACTION_SCREEN_OFF) && active==false) {
        	
        	wasScreenOn=false;
        	active = true;
        	cont++;
        	
        	Intent intent11 = new Intent(context, LockScreenActivity.class);
    		intent11.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    		context.startActivity(intent11);
        } 
        //cuando la pantalla se enciende ya está cargada la pantalla de bloqueo
        else if (intent.getAction().equals(Intent.ACTION_SCREEN_ON)) {
        	
        	wasScreenOn=true;
       }
       //cuando se inicia android, inicia automaticamente la pantalla de bloqueo
       else if(intent.getAction().equals(Intent.ACTION_BOOT_COMPLETED) && active==false){
    	
    	   
    	   	wasScreenOn=true;
       		active = true;
       		cont++;
       		
    	   	Intent intent11 = new Intent(context, LockScreenActivity.class);
        	intent11.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        	context.startActivity(intent11);       	
        	
       }

    }
}
