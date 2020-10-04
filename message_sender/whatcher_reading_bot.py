#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# A simple chat client for matrix.
# This sample will allow you to connect to a room, and send/recieve messages.
# Args: host:port username password room
# Error Codes:
# 1 - Unknown problem has occured
# 2 - Could not find the server.
# 3 - Bad URL Format.
# 4 - Bad username/password.
# 11 - Wrong room format.
# 12 - Couldn't find room.

import sys
import logging
from logging import handlers
import traceback
import time
import json
import os
import re
import psycopg2
import psycopg2.extras
import requests
import systemd_watchdog

from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from matrix_client.api import MatrixHttpLibError
from requests.exceptions import MissingSchema
import config as conf

client = None
log = None
lock = None
wd = None
wd_timeout = 0
exit_flag = False

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
  global log
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
  
def update_readed_status_messages(room_id,matrix_uid,time_stamp):
  global log
  global cur
  global conn
  time_execute=time.time()

  time_string=time.strftime("%Y-%m-%d %T",time.localtime(time_stamp))
  log.debug("time_read=%s"%time_string)
  # проверяем, что у нас есть такое соответствие:
  data=None
  try:
    sql="select matrix_uid from tbl_matrix_rooms where matrix_uid='%(matrix_uid)s' and user_room='%(room_id)s'"\
      %{\
      "matrix_uid":matrix_uid,\
      "room_id":room_id\
      }
    log.debug("sql='%s'"%sql)
    cur.execute(sql)
    data=cur.fetchall()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    return False
  if data==None:
    log.warning("У нас нет информации о таком пользователе (%s) в такой комнате: %s" % (matrix_uid,room_id) )
    return False
  # Известная связка комната-пользователь.
  # Выставляем статусы о прочтении:
  # Одним запросом не получилось, т.к. нельзя обновлять таблицу и тут же делать из неё выборку,
  # поэтому делаем в цикле по массиву идентификаторов:
  try:
    sql="""update tbl_sending_queue set 
      sending_status_id = (select sending_status_id from tbl_sending_status where sending_status_name='readed'),
      time_read = '%(time_string)s'
      where 
      sending_status_id in (select sending_status_id from tbl_sending_status where sending_status_name='sent_by_im')
      and time_send <='%(time_string)s'
      and address_im='%(address_im)s'
      """%{\
      "address_im":matrix_uid,\
      "time_string":time_string\
      }
    #sql="select id from tbl_sending_queue where address_im='%(address_im)s' and sending_status_id in ()='sent_by_matrix' and time_send<='%(time_string)s'"\
     # %{\
     # "matrix_uid":matrix_uid,\
     # "time_string":time_string\
     # }
    log.debug("sql='%s'"%sql)
    cur.execute(sql)
    conn.commit()
    log.debug("set_sending_status(): Row(s) were updated : %s"%str(cur.rowcount))
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    return False
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def on_event(event):
    global log
    global conn
    global cur
    global wd
    global wd_timeout

    # watchdog notify:
    if conf.use_watchdog:
      wd.notify()

    log.debug("event:")
    log.debug(event)
    log.debug(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False))
    for i in range(1,10):
      if connect_to_db() == False:
        log.error("on_event(): connect_to_db()")
        log.info("on_event(): wait 120 seconds for reconnect...")
        conn=None
        cur=None
        time.sleep(120)
        continue
      else:
        break
    if conn==None or cur == None:
      log.error("on_event(): failed connect_to_db()")
      log.error("process on_event - failed: can not connect to postgres in connect_to_db()")
      return False

    if event['type'] == "m.receipt":
      for room_id in event['content']:
        if "m.read" in event['content'][room_id]:
          for matrix_uid in event['content'][room_id]["m.read"]:
            time_stamp=int(int(event['content'][room_id]["m.read"][matrix_uid]["ts"])/1000)
            time_string=time.strftime("%Y-%m-%d %T",time.localtime(time_stamp))
            log.info(u"Пришло уведомление о прочтении польльзователем '%s' сообщений ранее: %s"%(matrix_uid,time_string))
            if update_readed_status_messages(room_id,matrix_uid,time_stamp) == False:
              log.warning(u"ошибка обновления статуса о прочтении -  update_status_messages(room_id=%s, matrix_uid=%s, time_stamp=%d) == False"%(room_id,matrix_uid,time_stamp))
              continue
    else:
      log.debug(event['type'])
    conn.close()
    conn=None
    cur=None
    return True


def on_invite(room, event):
    global client
    global log

    if conf.debug:
      log.debug("invite:")
      log.debug("room_data:")
      log.debug(room)
      log.debug("event_data:")
      log.debug(event)
      log.debug(json.dumps(event, indent=4, sort_keys=True,ensure_ascii=False,encoding='utf8'))

    # По приглашению не вступаем с точки зрения безопасности. Только мы можем приглашать в комнаты, а не нас:
    # Просматриваем сообщения:
#    for event_item in event['events']:
#      if event_item['type'] == "m.room.join_rules":
#        if event_item['content']['join_rule'] == "invite":
#          # Приглашение вступить в комнату:
#          log.debug("join to room: %s"%room)
#          room = client.join_room(room)
#          room.send_text("Спасибо за приглашение! Недеюсь быть Вам полезным. :-)")
#          room.send_text("Для справки по доступным командам - неберите: '!help' (или '!?', или '!h')")

def matrix_connect():
    global log
    global lock

    client = MatrixClient(conf.matrix_server)
    try:
        token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id_reading_updater)
        #token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id_reading_updater,sync=False)
    except MatrixRequestError as e:
        log.error(e)
        log.debug(e)
        if e.code == 403:
            log.error("Bad username or password.")
            return None
        else:
            log.error("Check your sever details are correct.")
            return None
    except MatrixHttpLibError as e:
        log.error(e)
        return None
    except MissingSchema as e:
        log.error("Bad URL format.")
        log.error(e)
        log.debug(e)
        return None
    except:
        log.error("unknown error at client.login()")
        return None
    return client

def exception_handler(e):
  global log
  global wd
  global wd_timeout
  global exit_flag
  log.error("exception_handler(): main listener thread except!")
  log.error(e)
  if conf.use_watchdog:
    log.info("send to watchdog error service status")
    wd.notify_error("An irrecoverable error occured! exception_handler()")
  time.sleep(5)
  log.info("exception_handler(): wait 5 second before programm exit...")
  log.info("set exit_flag=True")
  exit_flag = True
  time.sleep(5)
  log.info("sys.exit(1)")
  sys.exit(1)

def main():
    global client
    global data
    global log
    global conn
    global cur
    global wd
    global wd_timeout
    global exit_flag

    # watchdog:
    if conf.use_watchdog:
      log.info("init watchdog")
      wd = systemd_watchdog.watchdog()
      if not wd.is_enabled:
        # Then it's probably not running is systemd with watchdog enabled
        log.error("Watchdog not enabled in systemdunit, but enabled in bot config!")
        return False
      wd.status("Starting service...")
      wd_timeout=int(float(wd.timeout) / 1000000)
      log.info("watchdog timeout=%d"%wd_timeout)

    for i in range(1,10):
      log.debug("try connect to matrix server...")
      client = matrix_connect()
      if client==None:
        log.error("matrix_connect() - try reconnect")
        #time.sleep(120)
        time.sleep(1)
        continue
      else:
        log.debug("success connect to matrix server")
        break
    if client == None:
      log.error("matrix_connect() fault! - exit")
      sys.exit(1)

    client.add_ephemeral_listener(on_event)
    client.start_listener_thread(exception_handler=exception_handler)
    
    # программа инициализировалась - сообщаем об этом в watchdog:
    if conf.use_watchdog:
      wd.ready()
      wd.status("start main loop")
      log.debug("watchdog send notify")
      wd.notify()

    while True:
      # watchdog notify:
      if conf.use_watchdog:
        wd.notify()
      time.sleep(int(wd_timeout/2))
      if exit_flag == True:
        log.warning("got exit_flag == True - exit")
        # неуспешный выход:
        return False
    # успешный выход:
    return True

if __name__ == '__main__':
  log=logging.getLogger("whatcher_reading_bot")
  log_lib=logging.getLogger("matrix_client.client")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  #fh = logging.FileHandler(conf.log_path)
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_whatcher_reading_bot, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
  formatter = logging.Formatter('%(asctime)s - %(name)s - %(filename)s:%(lineno)d - %(funcName)s() %(levelname)s - %(message)s')
  fh.setFormatter(formatter)

  if conf.debug:
    # логирование в консоль:
    #stdout = logging.FileHandler("/dev/stdout")
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setFormatter(formatter)
    log.addHandler(stdout)
    log_lib.addHandler(stdout)

  # add handler to logger object
  log.addHandler(fh)
  log_lib.addHandler(fh)

  log.info("Program started")

  log.info("python version=%s"%sys.version)

  if main()==False:
    log.error("error main()")
    sys.exit(1)
  log.info("Program exit!")
