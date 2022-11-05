#!/usr/bin/python3

import http.client
import json
import configparser
import time
import paho.mqtt.client as mqtt
import os

config = configparser.RawConfigParser()  
config.read('config.ini')

FS_API = dict(config.items('huaweiAPI'))
API_URL = FS_API['url']

activetoken = configparser.RawConfigParser()  
activetoken.read('token.ini')
token = activetoken['token']['active']

def get_token():

	username = FS_API['username']
	password = FS_API['password']

	print("Renewing Token!")

	conn = http.client.HTTPSConnection(API_URL, 27200)

	payload = json.dumps({
		"username": username,
		"password": password
		})

	headers = {
		'Content-Type': 'application/json'
	}

	conn.request("POST", "/rest/openapi/pvms/v1/login", payload, headers)
	res = conn.getresponse()
	data = res.read()
	token = res.getheader("XSRF-TOKEN")
	print("token:" , token)

	conn.close() 
	return(token)


def get_deviceList(token):

  conn = http.client.HTTPSConnection(API_URL, 27200)

  payload = json.dumps({
  "pageNo": 1,
  "pageSize": 10,
  "plantCodes": FS_API['stationid']
  })

  headers = {
  'Content-Type': 'application/json', 
  'XSRF-TOKEN': token
  }

  conn.request("POST","/rest/openapi/pvms/v1/devices", payload, headers)

  res = conn.getresponse()
  data = json.loads(res.read())

  return(data)


def renew_token():
	print("Renewing Token")

	newtoken = get_token()
	activetoken['token']['active'] = newtoken

	with open('token.ini', 'w') as configfile:
		activetoken.write(configfile)

	return(newtoken)


def get_currentdata(stationid):

	conn = http.client.HTTPSConnection(API_URL, 27200)
	payload = json.dumps({"plantCodes": stationid})
	newtoken = token

	headers = {
		'Content-Type': 'application/json', 
		'XSRF-TOKEN': token
	}

	print("Getting current data: ")
	print(headers)

	conn.request("POST","/rest/openapi/pvms/v1/vpp/plantRealtimeKpi", payload, headers)
	res = conn.getresponse()
	dataLength = res.getheader('content-length')

	# Handling Response Errors
	if dataLength=="0":
		print("Empty Response Body")
		newtoken = renew_token()
	
	else:
		data = json.loads(res.read())
		try:
			if data["failCode"] == 305:
				print("failcode 305")
				newtoken = renew_token()
		except:
			pass

	headers = {
		'Content-Type': 'application/json', 
		'XSRF-TOKEN': newtoken
	}

	conn.request("POST","/rest/openapi/pvms/v1/vpp/plantRealtimeKpi", payload, headers)
	res = conn.getresponse()
	data = json.loads(res.read())
	print(data)
	if "dataItemMap" in data["data"][0]:
		inverter_data = data["data"][0]["dataItemMap"]

		send_to_mqtt(inverter_data)

		return(inverter_data)
	else:
		print(data)
	return


def send_to_mqtt(inverter_data):
	print("Publishing Data To MQTT: ")
	print(json.dumps(inverter_data))


	client = mqtt.Client("PVdata", False)
	client.connect("192.168.1.100",1883,60)
	client.publish("PV", json.dumps(inverter_data), qos=1, retain=True)
	client.disconnect()
	return


#token = get_token()
#devices = get_deviceList(token)
#print(str(devices))

current_data = get_currentdata(FS_API['stationid'])
