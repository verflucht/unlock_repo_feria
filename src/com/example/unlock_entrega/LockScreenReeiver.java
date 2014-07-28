package com.example.unlock_entrega;

import java.io.File;
import android.content.BroadcastReceiver;
import android.content.Context;
import android.content.Intent;

public class LockScreenReeiver extends BroadcastReceiver{
	
	public static boolean wasScreenOn = true;
	public static boolean active = false;
	public static int cont = 0;
	public static int total_img = 0;
	public static int i = 0;

	@Override
	public void onReceive(Context context, Intent intent) {
				
        if (intent.getAction().equals(Intent.ACTION_SCREEN_OFF) && active==false) {
        	
        	wasScreenOn=false;
        	active = true;
        	cont++;
        	
        	if(total_img == 0){
           		//obtenemos el numero total de publicidades descargadas
        		String ruta = "/data/data/com.example.unlock";
        		File dir = new File(ruta);
           		String[] ficheros = dir.list();
           		
           		if(ficheros!=null){
           			int cont=0;
           			for (int i=0; i<ficheros.length; i++){
           				dir = new File(ruta+"/"+ficheros[i]);
           				if(dir.isFile()){
           					cont++;
           					System.out.println(cont+" "+ficheros[i]);
           				}
           			}
           			total_img = cont;
               		System.out.println(ficheros.length);
           		}
           		else
           			total_img = 0;
        	}
        	
        	Intent intent11 = new Intent(context, LockScreenActivity.class);
    		intent11.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
    		context.startActivity(intent11);
        } 
        else if (intent.getAction().equals(Intent.ACTION_SCREEN_ON)) {
        	
        	wasScreenOn=true;
        	
        	//Intent intent11 = new Intent(context, LockScreenActivity.class);
        	//intent11.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        	//intent11.setAction(Intent.ACTION_SCREEN_OFF);
        	//context.startActivity(intent11);
       }
       else if(intent.getAction().equals(Intent.ACTION_BOOT_COMPLETED) && active==false){
    	
    	   
    	   	wasScreenOn=true;
       		active = true;
       		cont++;
       		
       		//obtenemos el numero total de publicidades descargadas
    		String ruta = "/data/data/com.example.unlock";
    		File dir = new File(ruta);
       		String[] ficheros = dir.list();
       		
       		if(ficheros!=null){
       			int cont=0;
       			for (int i=0; i<ficheros.length; i++){
       				dir = new File(ruta+"/"+ficheros[i]);
       				if(dir.isFile()){
       					cont++;
       					System.out.println(cont+" "+ficheros[i]);
       				}
       			}
       			total_img = cont;
           		System.out.println(ficheros.length);
       		}
       		else
       			total_img = 0;
       		
    	   	Intent intent11 = new Intent(context, LockScreenActivity.class);
        	intent11.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        	context.startActivity(intent11);       	
        	
       }

    }
}
