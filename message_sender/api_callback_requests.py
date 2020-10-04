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
import config as conf
import urllib
import requests

global_error_descr=""
conn=None
cur=None
log=None

def send_callback_json(callback_url,json_data):
  global log
  log.debug("try send to '%s')"%callback_url)
  time_execute=time.time()
  num=0
  try:
    response = requests.post(callback_url, json=json_data)
    data = response.raw      # a `bytes` object
    if response.status_code != 200:
      log.error("response != 200 (OK)")
      return False
  except:
    log.error("post data to url: %s"%callback_url)
    return False
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True
   
def set_callback_retry_num(message_id, callback_retry_num):
  global conn
  global cur
  global log
  time_execute=time.time()
  try:
    sql="update tbl_sending_queue set \
      callback_retry_num=%(callback_retry_num)d"\
      % {"callback_retry_num":callback_retry_num}
    sql=sql+" where id=%d" % message_id
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

  log.debug("sql=%s" % sql)
  try:
    cur.execute(sql)
    conn.commit()
    log.debug("Row(s) were updated : %s"%str(cur.rowcount))
  except psycopg2.Error as e:
    log.error("can not update row: %s" % e.pgerror)
    log.info("try rollback update for this connection")
    try:
      conn.rollback()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
    return False

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def set_callback_status(message_id, callback_status):
  global conn
  global cur
  global log
  time_execute=time.time()
  try:
    sql="update tbl_sending_queue set \
      callback_status_id=(select callback_status_id from tbl_callback_status where callback_status_name='%(callback_status)s')"\
      % {"callback_status":callback_status}
    sql=sql+" where id=%d" % message_id
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

  log.debug("sql=%s" % sql)
  try:
    cur.execute(sql)
    conn.commit()
    log.debug("Row(s) were updated : %s"%str(cur.rowcount))
  except psycopg2.Error as e:
    log.error("can not update row: %s" % e.pgerror)
    log.info("try rollback update for this connection")
    try:
      conn.rollback()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
    return False

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def process_needed_callbacks():
  global log
  global conn
  global cur
  global global_error_descr

  time_execute=time.time()
  try:
    # формируем sql-запрос:
    sql="""
    select 
      a.id,
      a.address_im,
      a.address_email,
      a.time_create,
      a.time_start_process,
      a.time_send,
      a.time_read,
      b.sending_status_name,
      a.sending_retry_num,
      a.sender_uniq_id,
      a.error_description_im,
      a.error_description_email,
      c.callback_status_name,
      a.callback_retry_num,
      a.im_event_id,
      a.callback_url,
      a.edit_previouse
      from tbl_sending_queue as a
      LEFT JOIN tbl_sending_status as b ON a.sending_status_id = b.sending_status_id
      LEFT JOIN tbl_callback_status as c ON a.callback_status_id = c.callback_status_id
      where a.callback_url is not null and a.callback_status_id in (select c.callback_status_id from tbl_callback_status where c.callback_status_name='need send' or callback_status_name='error');
    """

    try:
      cur.execute(sql)
      items = cur.fetchall()
    except psycopg2.Error as e:
      log.error("I am unable select data from tbl_sending_queue: %s" % e.pgerror)
      return False
    log.debug("execute select() time=%f"%(time.time()-time_execute))
    # обработка:
    for item in items:
      time_proccess_one_callback=time.time()
      log.info("proccess callback for message id=%d"%item[0])
      data={}
      data["message_id"]=item[0]
      data["address_im"]=item[1]
      data["address_email"]=item[2]
      if item[3]!=None:
        data["time_create"]=str(item[3])
      else:
        data["time_create"]=None
      if item[4]!=None:
        data["time_start_process"]=str(item[4])
      else:
        data["time_start_process"]=None
      if item[5]!=None:
        data["time_send"]=str(item[5])
      else:
        data["time_send"]=None
      if item[6]!=None:
        data["time_read"]=str(item[6])
      else:
        data["time_read"]=None
      data["sending_status"]=item[7]
      data["sending_retry_num"]=item[8]
      data["sender_uniq_id"]=item[9]
      data["error_description_im"]=item[10]
      data["error_description_email"]=item[11]
      data["callback_status"]=item[12]
      data["callback_retry_num"]=item[13]
      data["im_event_id"]=item[14]
      callback_url=item[15]
      data["edit_previouse"]=item[16]

      if data["callback_status"] == "error" and data["callback_retry_num"] == conf.callback_max_retry:
        log.warning("callback_max_retry (%d) exeed for callback() of message_id=%d - set callback status as 'fault' for item"%(conf.callback_max_retry, data["message_id"]))
        if set_callback_status(data["message_id"],"fault") == False:
          log.error("set_callback_status()")
          return False
        continue

      # отправляем 
      log.debug(json.dumps(data, indent=4, sort_keys=True,ensure_ascii=False))
      if send_callback_json(callback_url,data) == False:
        # не получилось отправить callback. Помечаем статус отправки callback-а:
        log.warning("send_callback_json('%s')"%callback_url)
        if set_callback_status(data["message_id"],"error") == False:
          log.error("set_callback_status()")
          return False
        if set_callback_retry_num(data["message_id"],data["callback_retry_num"]+1) == False:
          log.error("set_callback_retry_num()")
          return False
      else:
        # успешно отправили callback, сбрасываем счётчик ошибок отправок, если нужно:
        if data["callback_retry_num"] > 0:
          if set_callback_retry_num(data["id"],0) == False:
            log.error("set_callback_retry_num()")
            return False
        # помечаем как отправленное:
        if set_callback_status(data["id"],"sended") == False:
          log.error("set_callback_status()")
          return False
      log.debug("time proccess one callback=%f"%(time.time()-time_proccess_one_callback))

  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True
  

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
    log.debug("connect to: dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='" + conf.send_db_passwd + "'")
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
  if connect_to_db()==False:
    log.error("connect_to_db()")
    return False
  if process_needed_callbacks() == False:
    log.error("process_needed_callbacks()")
    return False
  return True

if __name__ == '__main__':
  log=logging.getLogger("api_callback_requests")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_api_callback_requests, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  if conf.debug:
    # логирование в консоль:
    #stdout = logging.FileHandler("/dev/stdout")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)

  log.info("Program started")

  log.info("python version=%s"%sys.version)

  if main()==False:
    log.error("error main()")
    sys.exit(1)
  log.info("Program exit!")
