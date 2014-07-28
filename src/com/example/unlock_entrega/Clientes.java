package com.example.unlock_entrega;


public class Clientes{


	private int image_id;
	private String image_name;
	private int id_campaign;
	private String url;

	public Clientes(int image_id, String image_name, int id_campaign, String url) {
		super();
		this.image_id = image_id;
		this.image_name = image_name;
		this.id_campaign = id_campaign;
		this.url = url;
	}

	public Clientes(String image_name, String url){
		super();
		this.image_name = image_name;
		this.url = url;
	}

	public int getId(){
		return image_id;
	}

	public void setId(int image_id){
		this.image_id = image_id;
	}
	
	public String getName(){
		return image_name;
	}
	
	public void setName(String image_name){
		this.image_name = image_name;
	}
	
	public int getCamp(){
		return id_campaign;
	}

	public void setCamp(int id_campaign){
		this.id_campaign = id_campaign;
	}
	
	public String getUrl(){
		return url;
	}
	
	public void setUrl(String url){
		this.url = url;
	}
	
	public String toString(){
		return this.image_name;
	}

}
