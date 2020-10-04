#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import traceback
import sys
import time
import datetime
import psycopg2
import psycopg2.extras
import os
import logging
import json
from logging import handlers
import re
import config as conf
import urllib
import requests
import cgi
import io

global_error_descr=""
conn=None
cur=None
log=None

def get_api_key_id(api_key):
  global log
  global conn
  global cur
  global global_error_descr
  try:
    sql="select api_key_id from tbl_api_keys where api_key='%s'"%api_key
    log.debug("sql='%s'" % sql)
    cur.execute(sql)
    data = cur.fetchone()
  except psycopg2.Error as e:
    global_error_descr="can not select from db: %s" % e.pgerror
    log.error(global_error_descr)
    return None
  try:
    if data == None:
      return 0
    else:
      return data[0]
  except:
    global_error_descr="internal error (convert data to int)"
    log.error(global_error_descr)
    return None

def get_message_type_id(message_type_name):
  global log
  global conn
  global cur
  global global_error_descr
  try:
    sql="select message_type_id from tbl_message_type where message_type_name='%s'"%message_type_name.strip()
    log.debug("sql='%s'" % sql)
    cur.execute(sql)
    data = cur.fetchone()
  except psycopg2.Error as e:
    global_error_descr="can not select from db: %s" % e.pgerror
    log.error(global_error_descr)
    return None
  return data[0]

def add_message_to_queue(data):
  global log
  global conn
  global cur
  global global_error_descr

  result={}
  try:
    columns=""
    values=""
    # проверка на присутствие обязятельных полей:
    if "address_im" not in data and "address_email" not in data or \
     "message" not in data or \
     "api_key" not in data:
      global_error_descr="need 'address_im' or 'address_im' and 'message' and 'api_key' in POST json-data!"
      log.warning(global_error_descr)
      return None

    # проверяем правильность API-ключа:
    api_key_id=get_api_key_id(data["api_key"])
    if api_key_id == None:
      log.error("is_api_key_valid()")
      return None
    elif api_key_id > 0:
      columns = "api_key_id"
      values = "%d"%api_key_id
    else:
      global_error_descr="access denide: api_key is not valid"
      log.warning(global_error_descr)
      return None

    # добавляем поля в запрос:
    if "address_im" in data:
      columns=columns + ",address_im"
      values=values + ",'%s'"%data["address_im"]
    
    if "address_email" in data:
      columns=columns + ",address_email"
      values=values + ",'%s'"%data["address_email"]

    if "message" in data:
      columns=columns + ",message"
      #values=values + ",'%s'"%data["message"].replace("'","''").replace('\\','\\\\')
      values=values + ",'%s'"%data["message"].replace("'","''") # https://postgrespro.ru/docs/postgrespro/9.5/plpgsql-development-tips

    if "type" in data:
      message_type_id = get_message_type_id(data["type"])
      if message_type_id==None:
        global_error_descr="error type of message from api call"
        log.warning(global_error_descr)
        return None
      else:
        columns=columns + ",message_type_id"
        values=values + ",%d"%message_type_id

    if "callback_url" in data:
      columns=columns + ",callback_url"
      values=values + ",'%s'"%data["callback_url"]
      # статус callback:
      columns=columns + ",callback_status_id"
      # берём идентификатор статуса 'new':
      values=values + ",(select callback_status_id from tbl_callback_status where callback_status_name='new')"

    if "sender_uniq_id" in data:
      columns=columns + ",sender_uniq_id"
      values=values + ",'%s'"%data["sender_uniq_id"]

    if "edit_previouse" in data and data["edit_previouse"] == True:
      columns=columns + ",edit_previouse"
      values=values + ",TRUE"

    columns=columns + ",sending_status_id"
    # берём идентификатор статуса 'new':
    values=values + ",(select sending_status_id from tbl_sending_status where sending_status_name='new')"



    # формируем sql-запрос:
    sql="insert INTO tbl_sending_queue (%s) VALUES (%s)"%(columns,values)
    log.debug("sql='%s'"%sql)
    try:
      cur.execute(sql)
      conn.commit()
      cur.execute('SELECT LASTVAL()')
      id_of_new_row = cur.fetchone()[0]
    except psycopg2.Error as e:
      global_error_descr="I am unable insert data to tbl_sending_queue: %s" % e.pgerror
      log.error(global_error_descr)
      log.info("try rollback insertion for this connection")
      try:
        conn.rollback()
      except psycopg2.Error as e:
        log.error("sql error: %s" % e.pgerror)
      return None

    if id_of_new_row == None:
      global_error_descr="unable get id_of_new_row"
      log.error(global_error_descr)
      return None
    else:
      result["message_id"]=int(id_of_new_row)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    global_error_descr="internal script error - see logs"
    log.error(global_error_descr)
    return None
  return result
  

def get_exception_traceback_descr(e):
  if hasattr(e, '__traceback__'):
    tb_str = traceback.format_exception(etype=type(e), value=e, tb=e.__traceback__)
    result=""
    for msg in tb_str:
      result+=msg
    return result
  else:
    return e

def connect_to_db():
  global conn
  global cur
  try:
    #log.debug("connect to: dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='" + conf.send_db_passwd + "'")
    log.debug("connect to: dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='XXXXXX'")
    conn = psycopg2.connect("dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='" + conf.send_db_passwd + "'")
    cur = conn.cursor()
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error("I am unable to connect to the database")
    return False
  return True

#=============== main() ===============
def main():
  global log
  result={}
  print("Content-Type: application/json")
  print('')
  sys.stdout.flush()
  # получаем данные из cgi запроса:
  try:
    #content_len = int(os.environ["CONTENT_LENGTH"])
    #req_body = sys.stdin.read(content_len)
    #req_body = sys.stdin.read()

    # информация о запросе:
    log_string="get request: REQUEST_METHOD='%s', REMOTE_ADDR='%s', HTTP_USER_AGENT='%s'"%(\
      os.environ.get("REQUEST_METHOD", "unknown"),\
      os.environ.get("REMOTE_ADDR", "unknown"),\
      os.environ.get("HTTP_USER_AGENT", "unknown")\
      )
    log.info(log_string)
    
    # устанавливаем кодировку для stdin:
    # https://stackoverflow.com/questions/16549332/python-3-how-to-specify-stdin-encoding
    input_stream = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8',errors='replace')
    output_stream = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8',errors='replace')
    req_body = input_stream.read()
    log.debug("get data: %s"%req_body)
    json_data = json.loads(req_body)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error("get json data from cgi")
    result["status"]="error"
    result["description"]="error parse json from POST data. Please correct POST data. For example: {'address_im':'@user:matrix-server.com','message':'test', 'api_key':'XXXXXXX'}"
    output_stream.write(json.dumps(result, indent=4, sort_keys=True,ensure_ascii=False))
    output_stream.flush()
    sys.stdout.flush()
    return False

  if connect_to_db()==False:
    log.error("connect_to_db()")
    result["status"]="error"
    result["description"]="internal server error: can not connect to database - please connect to system administrator!"
    output_stream.write(json.dumps(result, indent=4, sort_keys=True,ensure_ascii=False))
    output_stream.flush()
    sys.stdout.flush()
    return False

  ret = add_message_to_queue(json_data)
  if ret == None:
    log.error("add_message_to_queue()")
    result["status"]="error"
    result["description"]="error add message to queue for processing: %s"%global_error_descr
    output_stream.write(json.dumps(result, indent=4, sort_keys=True,ensure_ascii=False))
    output_stream.flush()
    sys.stdout.flush()
    return False
  else:
    ret["status"]="success"
    ret["description"]="add message to sending queue"
    output_stream.write(json.dumps(ret, indent=4, sort_keys=True,ensure_ascii=False))
    output_stream.flush()
    sys.stdout.flush()
    return True

if __name__ == '__main__':
  log=logging.getLogger("api_add_message")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_api_add_message, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  #if conf.debug:
  #  # логирование в консоль:
  #  stdout = logging.StreamHandler(sys.stdout)
  #  stdout.setFormatter(formatter)
  #  log.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")

  log.info("python version=%s"%sys.version)

  if main()==False:
    log.error("error main()")
    sys.exit(1)
  log.info("Program exit!")
