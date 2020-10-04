#!/usr/bin/env python
# -*- coding: utf-8 -*-
import config as conf
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from requests.exceptions import MissingSchema
import sys
import time
import json



# New user
#token = client.register_with_password(username=conf.username, password=conf.password)

token=None
session=None
# Existing user

def edit_matrix_message(client, room_id, edited_event_id, text, msgtype="m.text"):
  try:

    """Perform PUT /rooms/$room_id/state/m.room.avatar
    """
        #"info": {
        #  "mimetype": "image/jpeg"
        #},
    body = {
        "m.new_content": {
          "body": text,
          "msgtype": msgtype
        },
        "m.relates_to": {
          "rel_type": "m.replace",
          "event_id": edited_event_id
        },
        "body": " * %s"%text,
        "msgtype": msgtype
      }

    return client.api.send_state_event(room_id, "m.room.message", body, timestamp=None)
  except Exception as e:
#log.error(get_exception_traceback_descr(e))
#   log.error("exception at execute set_matrix_room_avatar()")
    print(e)
    return None

def edit_message():
  client = MatrixClient(conf.matrix_server)
  token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id)
  room_id="!XXXXX:corp.ru"
  print("send message")
  ret = client.api.send_message(room_id, "test")
  print("success send message")
  print("event_id=",ret["event_id"])
  print("edit message")
  ret = edit_matrix_message(client, room_id, ret["event_id"], "test2", msgtype="m.text")
  if ret is not None:
    print("success edit message")
  else:
    print("error edit message")
  return ret

def delete_all_devices():
  client = MatrixClient(conf.matrix_server)
  token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id)
  response=client.api.get_devices()

  #print(response)
  devices=response["devices"]

  print("len(devices)=%d"%len(response["devices"]))
#  sys.exit()

  device_list=[]
  index=0
  for device in response["devices"]:
    if device["device_id"]!=conf.matrix_device_id:
      device_list.append(device["device_id"])
      index+=1
    #if index > 1000:
    #  break

  # stage1 - берём сессию:
  try:
    #response=client.api.delete_device(auth_body={"auth":{}},device_id=device["device_id"])
    response=client.api.delete_devices({"auth":{}},[device["device_id"]])
  except MatrixRequestError as e:
    if e.code == 401:
      print("response=",e.content)
      response_data = json.loads(e.content)
      session=response_data["session"]
  # stage2 передаём пароль:
  print("session=",session)

  auth_body={}
  auth_body["type"]="m.login.password"
  auth_body["session"]=session
  auth_body["user"]=conf.matrix_username
  auth_body["password"]=conf.matrix_password
  response=client.api.delete_devices(auth_body,device_list)
  return True


def delete_device():
  client = MatrixClient(conf.server)
  token = client.login(username=conf.username, password=conf.password,device_id=conf.device_id)
  response=client.api.get_devices()

  #print(response)
  devices=response["devices"]

  print("len(devices)=%d"%len(response["devices"]))
  print("len(device_list)=%d"%len(device_list))
  print("device_list=",device_list)

  for device in response["devices"]:
    if device["device_id"]!=conf.device_id:
      #print(device)
      print("delete device: %s"%device["device_id"])

      # stage1 - берём сессию:
      try:
        #response=client.api.delete_device(auth_body={"auth":{}},device_id=device["device_id"])
        response=client.api.delete_devices({"auth":{}},[device["device_id"]])
      except MatrixRequestError as e:
        if e.code == 401:
          print("response=",e.content)
          response_data = json.loads(e.content)
          session=response_data["session"]
      # stage2 передаём пароль:
      print("session=",session)

      auth_body={}
      auth_body["type"]="m.login.password"
      auth_body["session"]=session
      auth_body["user"]=conf.matrix_username
      auth_body["password"]=conf.matrix_password
      response=client.api.delete_device(auth_body=auth_body,device_id=device["device_id"])
    # FIXME 
    break
  return True

edit_message()
