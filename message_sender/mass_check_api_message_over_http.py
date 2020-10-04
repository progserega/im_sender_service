#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import os
import json
import urllib
import requests

global_error_descr=""
conn=None
cur=None
log=None

def send_json(url,json_data):
  print("try send to '%s')"%url)
  time_execute=time.time()
  response = requests.post(url, json=json_data, verify=False)
  print("response.elapsed.total_seconds=",response.elapsed.total_seconds())
#  print("response=",response)
  data = response.text 
#  print("response.text=%s"%str(data))
#  print("response.json=",response.json())
  if response.status_code != 200:
    print("response != 200 (OK)")
    return False
  print("execute send_json() function time=%f"%(time.time()-time_execute))
  return True
   

#=============== main() ===============

json_data={"api_key":"XXXXXXXX", "message":"тестовый текст", "type":"text","address_im":"@user:corp.ru" }

time_execute=time.time()
for i in range(0,15):
  if send_json("https://api-sending-messages.corp.ru/api_add_message.cgi",json_data) == False:
    print("error send_json()")
print("full execute main() time=%f"%(time.time()-time_execute))
