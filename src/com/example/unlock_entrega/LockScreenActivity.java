package com.example.unlock_entrega;

import java.io.File;
import java.lang.reflect.Method;
import java.util.Calendar;

import android.app.Activity;
import android.widget.TextView;
import android.widget.ImageView;
import android.content.Context;
import android.content.Intent;
import android.database.Cursor;
import android.database.sqlite.SQLiteDatabase;
import android.graphics.drawable.Drawable;
import android.net.Uri;
import android.os.AsyncTask;
import android.os.Bundle;
import android.os.SystemClock;
import android.telephony.PhoneStateListener;
import android.telephony.TelephonyManager;
import android.view.Display;
import android.view.KeyEvent;
import android.view.MotionEvent;
import android.view.View;
import android.view.View.OnTouchListener;
import android.view.WindowManager;
import android.widget.RelativeLayout;
import android.widget.RelativeLayout.LayoutParams;

//Activity de la pantalla de bloqueo
public class LockScreenActivity extends Activity implements OnTouchListener{
	
    //vatiables de clase
	private int windowwidth, windowheight;
	private int[] block_bar_inicio, block_bar_actual;
	float dpi, posicion_x, posicion_y;
	private ImageView imgBoton;
	private TextView txtHora;
	private TextView txtFecha;
	private static ImageView imgBackground;
	private static String pag;
	private static String dir_img;
	private static CargarFondo cargarFondo;
	private static CargarFechaHora cargarFehaHora;
	private static boolean activa; 
	//private int phone_x,phone_y;
	//private int home_x,home_y;
	private RelativeLayout.LayoutParams layout_widget;
	private LayoutParams layoutParams;
 	
	//evita que la barra de estados se expanda sobre la pantalla de bloqueo
	public void onWindowFocusChanged(boolean hasFocus)
	{
		try	
		{
	       if(!hasFocus)
	       {
	            Object service  = getSystemService("statusbar");
	            Class<?> statusbarManager = Class.forName("android.app.StatusBarManager");
	            Method collapse = statusbarManager.getMethod("collapse");
	            collapse .setAccessible(true);
	            collapse .invoke(service);
	       }
	    }
	    catch(Exception ex)
	    {
	    }
	}
	@Override
	public void onAttachedToWindow() {
		// TODO Auto-generated method stub
		this.getWindow().setType(WindowManager.LayoutParams.TYPE_KEYGUARD_DIALOG|WindowManager.LayoutParams.FLAG_FULLSCREEN);
		super.onAttachedToWindow(); 
	 }
	
    public void onCreate(Bundle savedInstanceState) {
    
 	   super.onCreate(savedInstanceState);
 	   //getWindow().setFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN, WindowManager.LayoutParams.FLAG_FULLSCREEN);
 	   //getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON|WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED|WindowManager.LayoutParams.FLAG_FULLSCREEN);
 	   getWindow().addFlags(WindowManager.LayoutParams.FLAG_SHOW_WHEN_LOCKED|WindowManager.LayoutParams.FLAG_FULLSCREEN);
 	   startService(new Intent(this,MyService.class));
 	   setContentView(R.layout.activity_lock_screen); 
 	   
 	   activa = true;
 	   //pag = establecerBackgroundPag();
 	   pag_dir();
 	   //establecerHoraFecha();
 	   
 	   imgBoton = (ImageView)findViewById(R.id.ImgBoton);
 	   imgBackground = (ImageView)findViewById(R.id.ImgBackground);
 	   
 	   //new CargarFondo().execute();
 	  cargarFondo = new CargarFondo();
 	  cargarFondo.execute();
 	  //new CargarFechaHora().execute(); 
 	  cargarFehaHora = new CargarFechaHora();
 	  cargarFehaHora.execute();

 	   if(getIntent()!=null&&getIntent().hasExtra("kill")&&getIntent().getExtras().getInt("kill")==1){
	        	finish();
	   }
 	   
 	   try{

    	 StateListener phoneStateListener = new StateListener();
    	 TelephonyManager telephonyManager =(TelephonyManager)getSystemService(TELEPHONY_SERVICE);
    	 telephonyManager.listen(phoneStateListener,PhoneStateListener.LISTEN_CALL_STATE);
    	 
    	 //obtenemos datos de la pantalla
    	 Display display = ((WindowManager) getSystemService(Context.WINDOW_SERVICE)).getDefaultDisplay();
    	 windowwidth=display.getWidth();
    	 windowheight=display.getHeight();        
         dpi = getApplicationContext().getResources().getDisplayMetrics().densityDpi; 
         
         //pisiciones del imgBoton con respecto a los bordes 
         posicion_x = (float)((windowwidth/2.0)-((17.5*dpi)/160.0));
         posicion_y = (float)(windowheight-((52.5*dpi)/160.0));
         
    	 layout_widget = new RelativeLayout.LayoutParams((int)((35.0*dpi)/160.0), (int)((35.0*dpi)/160.0));
    	 layout_widget.setMargins((int)posicion_x, (int)posicion_y, 0, 0);
    	 imgBoton.setLayoutParams(layout_widget);
    	 
    	//deslizar block_bar;
    	imgBoton.setOnTouchListener(this);    	
     	}catch (Exception e) {
			// TODO: handle exception
     	} 	 
    }
    
    public void pag_dir(){
    	
    	String consulta = "SELECT dir, pag FROM Imagenes WHERE cont=";
    	
    	if(LockScreenReeiver.total_img == 0){
    		System.out.println("No hay Imagenes");
            pag = "http://www.getunlock.biz/"; //pagina de unlock
            dir_img = "unlock";
            LockScreenReeiver.cont--;
    	}
    	else{
    		//si ya mostró todas las publicidades, se reinicia
    		if(LockScreenReeiver.cont>LockScreenReeiver.total_img){
    			LockScreenReeiver.cont=1;
    		}
    		consulta = consulta+LockScreenReeiver.cont;
    		System.out.println(consulta);
	    	ImagenesSQLiteHelper imgDB =
	                new ImagenesSQLiteHelper(this, "DBImagenes", null, 1);
	            SQLiteDatabase db = imgDB.getReadableDatabase();
	            
	        Cursor cursor = db.rawQuery(consulta, null);
	        
	        if(cursor.moveToFirst()){
            	//obtenemos los datos del registro
	        	dir_img = cursor.getString(0);
	        	pag = cursor.getString(1);
                
            }
	        cursor.close();
	        db.close();
    	}
    }
    
    public void establecerHoraFecha(){
    	    	
    	int num;
    	
    	txtHora = (TextView)findViewById(R.id.TxtHora);
  	   	txtFecha = (TextView)findViewById(R.id.TxtFecha);
  	    Calendar c = Calendar.getInstance();  
  	    
  	    //establecemoos la hora
  	    num = c.getTime().getHours();
  	    if(num<10)
  	    	txtHora.setText("0"+num+":");
  	    else
  	    	txtHora.setText(num+":");
  	    
  	    num = c.getTime().getMinutes();
  	    if(num<10)
  	    	txtHora.setText(txtHora.getText().toString()+"0"+num);
  	    else
  	    	txtHora.setText(txtHora.getText().toString()+num);
  	    
  	    //establecemos la fecha
  	    num = c.getTime().getDay();
  	    switch(num){
  	    	case 1:
  	    		txtFecha.setText("lun. ");
  	    		break;
  	    	case 2:
  	    		txtFecha.setText("mar. ");
  	    		break;
  	    	case 3:
  	    		txtFecha.setText("mié. ");
  	    		break;
  	    	case 4:
  	    		txtFecha.setText("jue. ");
  	    		break;
  	    	case 5:
  	    		txtFecha.setText("vie. ");
  	    		break;
  	    	case 6:
  	    		txtFecha.setText("sab. ");
  	    		break;
  	    	default:
  	    		txtFecha.setText("dom. ");
  	    		break;
  	    }
  	    
  	    num = c.getTime().getDate();
  	    txtFecha.setText(txtFecha.getText().toString()+num+" ");
  	    
  	    num = c.getTime().getMonth(); 
  	    switch(num){
	    	case 0:
	    		txtFecha.setText(txtFecha.getText().toString()+"enero");
	    		break;
	    	case 1:
	    		txtFecha.setText(txtFecha.getText().toString()+"febrero");
	    		break;
	    	case 2:
	    		txtFecha.setText(txtFecha.getText().toString()+"marzo");
	    		break;
	    	case 3:
	    		txtFecha.setText(txtFecha.getText().toString()+"abril");
	    		break;
	    	case 4:
	    		txtFecha.setText(txtFecha.getText().toString()+"mayo");
	    		break;
	    	case 5:
	    		txtFecha.setText(txtFecha.getText().toString()+"junio");
	    		break;
	    	case 6:
	    		txtFecha.setText(txtFecha.getText().toString()+"julio");
	    		break;
	    	case 7:
	    		txtFecha.setText(txtFecha.getText().toString()+"agosto");
	    		break;
	    	case 8:
	    		txtFecha.setText(txtFecha.getText().toString()+"septiembre");
	    		break;
	    	case 9:
	    		txtFecha.setText(txtFecha.getText().toString()+"octubre");
	    		break;
	    	case 10:
	    		txtFecha.setText(txtFecha.getText().toString()+"noviembre");
	    		break;
	    	default:
	    		txtFecha.setText(txtFecha.getText().toString()+"diciembre");
	    		break;
	    }     	   
    }

    
	@Override
	public boolean onTouch(View v, MotionEvent event) {
		// TODO Auto-generated method stub
		layoutParams = (LayoutParams) v.getLayoutParams();

		switch(event.getAction())
		{
			case MotionEvent.ACTION_DOWN:
				block_bar_inicio = new int[2];
				block_bar_actual = new int[2];
				block_bar_inicio[0] = (int)posicion_x;
				block_bar_inicio[1] = (int)posicion_y;
				block_bar_actual[0] = block_bar_inicio[0];
				block_bar_actual[1] = block_bar_inicio[1];
				break;
					
			case MotionEvent.ACTION_MOVE:
				int x_cord = (int)event.getRawX();
				
				//if(x_cord > windowwidth-(windowwidth/24)){
					//x_cord=windowwidth-(windowwidth/24)*2;
				//}
				//se establecen los limites del desplazamiento horizontal del imgBoton
				if(x_cord-((17.5*dpi)/160.0) >= (windowwidth/100)*27 && x_cord+((17.5*dpi)/160.0) <= ((float)windowwidth/100.0)*78.0){
					layoutParams.leftMargin = x_cord - imgBoton.getWidth()/2;
					imgBoton.getLocationOnScreen(block_bar_actual);
					v.setLayoutParams(layoutParams);
				}
				break;
				
			case MotionEvent.ACTION_UP:
				int x_cord1 = (int)event.getRawX();

				if(x_cord1-((17.5*dpi)/160.0)<=((windowwidth/100)*27+((10*dpi)/160.0)))
				{
					v.setVisibility(View.GONE);
					//crea una activity para abrir una Uri
					Intent intent = new Intent(Intent.ACTION_VIEW);
					intent.setData(Uri.parse(pag));
					startActivity(intent);
					//cierra el thread antes de cerrar la pantalla de bloqueo
				 	activa = false;
					finish();
				}
				else{ 
					if(x_cord1+((17.5*dpi)/160.0)>=(((float)windowwidth/100.0)*78.0-((10*dpi)/160.0)))
					{
						v.setVisibility(View.GONE);
						//cierra el thread antes de cerrar la pantalla de bloqueo
						activa = false;
						finish();
					}
					else
					{
						layoutParams.leftMargin = block_bar_inicio[0];
						v.setLayoutParams(layoutParams);
					}
				}
        	}
		return true;
	}
    
    class StateListener extends PhoneStateListener{
        @Override
        public void onCallStateChanged(int state, String incomingNumber) {

        	super.onCallStateChanged(state, incomingNumber);
            switch(state){
                case TelephonyManager.CALL_STATE_RINGING:
                    break;
                case TelephonyManager.CALL_STATE_OFFHOOK:
                    System.out.println("call Activity off hook");
                    //finish();
                    break;
                case TelephonyManager.CALL_STATE_IDLE:
                    break;
            }
        }
    };
    
    @Override
    public void onBackPressed() {
        // Don't allow back to dismiss.
    	System.out.println("Back");
    	return;
    }

    //only used in lockdown mode
    @Override
    protected void onPause() {
    	System.out.println("Pause");
    	super.onPause();    	
    }

    @Override
    protected void onStop() {
    	System.out.println("Stop");
    	//bloquea el thread de CargarFechaHora si la pantalla está encendida
    	/*if(LockScreenReeiver.wasScreenOn){
    		activa = false;
    	}*/
    	super.onStop();
        
        /*String linea = lee();
        if(linea.equals("home")){
        	System.out.println("HOME");
        	Intent intent = new Intent(getApplicationContext(),Home.class);
        	//startActivity(intent);
        	//Intent intent = new Intent(Intent.ACTION_VIEW);
			//intent.setData(Uri.parse(establecerPagina()));
			startActivity(intent);
        }
        else{
        	System.out.println("OUT");
        	escribe("home");
        }*/
    }   
    
    @Override
    public boolean onKeyDown(int keyCode, android.view.KeyEvent event) {

    	if ((keyCode == KeyEvent.KEYCODE_VOLUME_DOWN)||(keyCode == KeyEvent.KEYCODE_POWER)||(keyCode == KeyEvent.KEYCODE_VOLUME_UP)||(keyCode == KeyEvent.KEYCODE_CAMERA)) {
    	    //this is where I can do my stuff
    		System.out.println("VOL-POWER-CAMARA");
    	    return true; //because I handled the event
    	}
    	if((keyCode == KeyEvent.KEYCODE_HOME)){
    		System.out.println("HOME");
    	   return true;
        }

	return false;

    }

    public boolean dispatchKeyEvent(KeyEvent event) {
    	if (event.getKeyCode() == KeyEvent.KEYCODE_POWER ||(event.getKeyCode() == KeyEvent.KEYCODE_VOLUME_DOWN)) {
    	    //Intent i = new Intent(this, NewActivity.class);
    	    //startActivity(i);
    		System.out.println("VOL-POWER");
    	    return false;
    	}
    	if((event.getKeyCode() == KeyEvent.KEYCODE_HOME)){
    		
    		return true;
        }
    	return false;
    }

    public void onDestroy(){
    	System.out.println("DESTROY");
    	LockScreenReeiver.active=false;
        super.onDestroy();
        //startService(new Intent(this,MyService.class)); 
    }
    
    public class CargarFondo extends AsyncTask<Void, Integer, Void>{
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
    		
    		if(dir_img.equals("unlock")){
    			imgBackground.setImageResource(R.drawable.unlock_fondo);
    		}
    		else{
        		//cargamos la imagen
            	File file = new File(dir_img);
                Drawable fondo = (Drawable) Drawable.createFromPath(file.toString());
                imgBackground.setImageDrawable(fondo);
    		}
    	}
    	
    	@Override
    	protected Void doInBackground(Void... arg0){
    		
    		publishProgress(progress);
    		return null;
    	}
    }
    
    public class CargarFechaHora extends AsyncTask<Void, Integer, Void>{
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
    		establecerHoraFecha();
    	}
    	
    	@Override
    	protected Void doInBackground(Void... arg0){
    		while(activa){
    			//incrementa cada 1 segundo
    			if(progress == 0){
    				publishProgress(progress);
    			}
    			progress++;
    			SystemClock.sleep(1000); 
    			System.out.println("Pasó un segundo "+progress);
    			if(progress == 60){
    				progress = 0;
    				System.out.println("Pasó un minuto");
    			}
    		}
    		System.out.println("Se cierra el thread");
    		activa = true;
    		return null;
    	}
    }
}
