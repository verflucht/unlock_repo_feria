package com.example.unlock_entrega;

import android.app.Activity;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.view.View.OnClickListener;
import android.widget.EditText;
import android.widget.ImageView;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;

public class CreateAccountActivity extends Activity {
	
	static ImageView btnBack;
	static EditText txtNombre;
	static EditText txtEmail;
	static EditText txtUser;
	static EditText txtPass;
	static ImageView btnRegistrarse;
	
	@Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState); 
        // Esconde la barra de titulo
        requestWindowFeature(Window.FEATURE_NO_TITLE);
        setContentView(R.layout.activity_create_2);
        
        btnBack = (ImageView)findViewById(R.id.BtnCreateAccount_2);
        txtNombre = (EditText)findViewById(R.id.TxtNombre);
        txtEmail = (EditText)findViewById(R.id.TxtEmail);
        txtUser = (EditText)findViewById(R.id.TxtUser);
        txtPass = (EditText)findViewById(R.id.TxtPass);
        btnRegistrarse = (ImageView)findViewById(R.id.BtnRegistrarse);
        
        //AL HACER CLICK SOBRE LA FLECHA ATRAS
      	btnBack.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   Intent backIntent = new Intent().setClass(
                  				CreateAccountActivity.this, LoginActivity.class);
                  			startActivity(backIntent);
                  			finish();  
                   }
        });
      	
      	//AL HACER CLICK SOBRE REGISTRARSE
      	btnRegistrarse.setOnClickListener(new OnClickListener() {
                   @Override
                   public void onClick(View v) {
                	   //guarda las preferencias
                	   SharedPreferences prefs =
      					     getSharedPreferences("Usuario", Context.MODE_PRIVATE);
                	   SharedPreferences.Editor editor = prefs.edit();
                	   editor.putString("nombre", txtNombre.getText().toString());
                	   editor.putString("mail", txtEmail.getText().toString());
                	   editor.putString("user", txtUser.getText().toString());
                	   editor.putString("pass", txtPass.getText().toString());
                	   editor.commit();
                	   
                	   ////////////////////////////////////
                	   //GUARDAR DATOS EN LA BD DEL BAKA//
                	   //////////////////////////////////
                	   Intent mainIntent = new Intent().setClass(
               				CreateAccountActivity.this, MainActivity.class);
               			startActivity(mainIntent);
               			finish();               			
                   }
        });
        
    }
}
