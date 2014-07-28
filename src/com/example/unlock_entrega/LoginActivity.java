package com.example.unlock_entrega;

import com.example.unlock_entrega.MainActivity.Download;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.View.OnClickListener;
import android.widget.ImageView;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

public class LoginActivity extends Activity {
	
	static ImageView btnFacebook;
	static ImageView btnTwitter;
	static ImageView btnEmail;
	static ImageView btnCreateAccount;
	
	@Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState); 
        // Esconde la barra de titulo
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        setContentView(R.layout.activity_login);
        
        btnFacebook = (ImageView)findViewById(R.id.BtnFacebook);
        btnTwitter = (ImageView)findViewById(R.id.BtnTwitter);
        btnEmail = (ImageView)findViewById(R.id.BtnEmail);
        btnCreateAccount = (ImageView)findViewById(R.id.BtnCreateAccount);
        
        //AL HACER CLICK SOBRE FACEBOOK
      	btnFacebook.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   Toast.makeText(getBaseContext(),"FACEBOOK", Toast.LENGTH_SHORT).show();
                   }
        });
      	
      	//AL HACER CLICK SOBRE TWITTER
      	btnTwitter.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   Toast.makeText(getBaseContext(),"TWITTER", Toast.LENGTH_SHORT).show();
                   }
        });
      	
      	//AL HACER CLICK SOBRE EMAIL
      	btnEmail.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   Toast.makeText(getBaseContext(),"EMAIL", Toast.LENGTH_SHORT).show();
                   }
        });
      	
      	//AL HACER CLICK SOBRE CREATE ACCOUNT
      	btnCreateAccount.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   //abrimos activity login
                	   Intent mainIntent = new Intent().setClass(
               				LoginActivity.this, CreateAccountActivity.class);
               			startActivity(mainIntent);
               			finish();
                   }
        });
        
    }
}
