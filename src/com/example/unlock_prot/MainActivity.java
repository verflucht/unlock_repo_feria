package com.example.unlock_prot;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;

public class MainActivity extends Activity {

	@Override	
	protected void onCreate(Bundle savedInstanceState) {
		
		super.onCreate(savedInstanceState);
		setContentView(R.layout.activity_main);
		startService(new Intent(this,MyService.class));		
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
}
