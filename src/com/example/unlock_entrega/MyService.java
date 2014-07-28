package com.example.unlock_entrega;

import com.example.unlock_entrega.LockScreenReeiver;

import android.app.KeyguardManager;
import android.app.Service;
import android.content.BroadcastReceiver;
import android.content.Intent;
import android.content.IntentFilter;
import android.os.IBinder;

public class MyService extends Service{
	
	BroadcastReceiver mReceiver;
	
	@Override
	public IBinder onBind(Intent intent) {
		// TODO Auto-generated method stub
		return null;
	}
	
	@Override
	public void onCreate() {
		 
		System.out.println("Se crea servicio");
		KeyguardManager.KeyguardLock k1;
		KeyguardManager km =(KeyguardManager)getSystemService(KEYGUARD_SERVICE);
	    k1= km.newKeyguardLock("IN");
	    k1.disableKeyguard();

	    IntentFilter filter = new IntentFilter(Intent.ACTION_SCREEN_ON);
	    filter.addAction(Intent.ACTION_SCREEN_OFF);

	    mReceiver = new LockScreenReeiver();
	    registerReceiver(mReceiver, filter);
	    super.onCreate();
	}
	
	@Override
	public void onStart(Intent intent, int startId) {
		// TODO Auto-generated method stub
		super.onStart(intent, startId);
	}
	
	public void onDestroy() {
		//unregisterReceiver(mReceiver);
		//super.onDestroy();
	}
}
