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
import traceback
from logging import handlers
import time
import json
import os
import psycopg2
import psycopg2.extras
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from matrix_client.api import MatrixHttpLibError
from requests.exceptions import MissingSchema
import config as conf

client = None
log = None
conn = None
cur = None

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
    log.info("try rollback updating for this connection")
    try:
      conn.rollback()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
    return False

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def send_html(log,client, room_id, html):
  room=None
  try:
    room = client.join_room(room_id)
  except MatrixRequestError as e:
    log.error(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't find room.")
      return False
  try:
    room.send_html(html)
  except MatrixRequestError as e:
    log.error("error at send message '%s' to room '%s'"%(message,room_id))
    log.error(e)
    return False
  except:
    log.error("Unknown error at send message '%s' to room '%s'"%(html,room_id))
    return False
  return True

def send_message(log, client, room_id,message):
  room=None
  try:
    room = client.join_room(room_id)
  except MatrixRequestError as e:
    log.error(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't find room.")
      return False
  try:
    room.send_text(message)
  except MatrixRequestError as e:
    log.error("error at send message '%s' to room '%s'"%(message,room_id))
    log.error(e)
    return False
  except:
    log.error("Unknown error at send message '%s' to room '%s'"%(message,room_id))
    return False
  return True

def send_notice(log, client, room_id,message):
  room=None
  try:
    room = client.join_room(room_id)
  except MatrixRequestError as e:
    log.error(e)
    if e.code == 400:
      log.error("Room ID/Alias in the wrong format")
      return False
    else:
      log.error("Couldn't find room.")
      return False
  try:
    room.send_notice(message)
  except:
    log.error("Unknown error at send notice message '%s' to room '%s'"%(message,room_id))
    return False
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

def set_sending_status(message_id, message_status, error_description_im="", error_description_email="", change_status_time=None ):
  global conn
  global cur
  global log
  time_execute=time.time()
  if change_status_time==None:
    change_status_time=time.strftime("%Y-%m-%d %T",time.localtime())
  log.debug("set_sending_status(): change_status_time=%s"%change_status_time)

  try:
    time_row=""
    if message_status=="new":
      time_row="time_create"
    elif message_status=="in progress":
      time_row="time_start_process"
    elif message_status=="sending_by_im" or message_status=="sending_by_email":
      time_row="time_send"
    elif message_status=="sent_by_im" or message_status=="sent_by_email":
      time_row="time_send"
    elif message_status=="readed":
      time_row="time_read"

    sql="update tbl_sending_queue set \
      sending_status_id=(select sending_status_id from tbl_sending_status where sending_status_name='%(message_status)s')"\
      % {"message_status":message_status}
    if time_row!="":
      sql=sql+", %(time_row)s='%(change_status_time)s'" % {"time_row":time_row, "change_status_time":change_status_time}
    if error_description_im!="":
      sql=sql+u", error_description_im='%s'" % error_description_im
    if error_description_email!="":
      sql=sql+u", error_description_email='%s'" % error_description_email
    sql=sql+" where id=%d" % message_id
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

  log.debug("set_sending_status(): sql=%s" % sql)
  try:
    cur.execute(sql)
    conn.commit()
    log.debug("set_sending_status(): Row(s) were updated : %s"%str(cur.rowcount))
  except psycopg2.Error as e:
    log.error("can not update row: %s" % e.pgerror)
    log.info("try rollback update for this connection")
    try:
      conn.rollback()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
    return False

  # раз статус обновился - помечаем запись как необходимую для отсылки по callback-у:
  if set_callback_status(message_id, "need send") == False:
    log.error("set_callback_status()")
    return False

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def create_room(address_im, user_power_level=50):
  global log
  global client
  global conn
  global cur

  try:
    # проверяем, может быть для этого пользователя уже создана комната (если сразу добавлено несколько сообщений для одного пользователя, 
    # то комната могла создасться во время обработки предыдущего сообщения)
    try:
      log.debug("check room exist for %s"%address_im)
      # обкусываем символы табуляции и пробелов:
      sql="select matrix_uid,user_room from tbl_matrix_rooms \
        where matrix_uid='%s'"%address_im
      log.debug("sql: %s" % sql )
      cur.execute(sql)
      data = cur.fetchone()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
      return False
    if data!=None:
      # все есть:
      log.warning("for user '%s' room exist: '%s' - skip creating new (second) room for this user"%(data[0],data[1]))
      return True
    else:
      log.debug("no room for user '%s' - try create new room"%address_im)

    # сначала спрашиваем у сервера, есть ли такой пользователь (чтобы не создавать просто так комнату):
    try:
      response = client.api.get_display_name(address_im)
    except MatrixRequestError as e:
      log.error("Couldn't get user display name - may be no such user on server? username = '%s'"%address_im)
      log.error("skip create room for user '%s' - need admin!"%address_im)
      return False
    log.debug("Success get display name '%s' for user '%s' - user exist. Try create room for this is user"%(response,address_im))

    try:
      room=client.create_room(is_public=False, invitees=None)
    except MatrixRequestError as e:
      log.debug(e)
      if e.code == 400:
        log.error("Room ID/Alias in the wrong format")
        return False
      else:
        log.error("Couldn't create room.")
        return False
    log.debug("New room created. room_id='%s'"%room.room_id)

    # приглашаем пользователя в комнату:
    try:
      response = client.api.invite_user(room.room_id,address_im)
    except MatrixRequestError as e:
      log.debug(e)
      log.error("Can not invite user '%s' to room '%s'"%(address_im,room.room_id))
      try:
        # Нужно выйти из комнаты:
        log.info("Leave from room: '%s'"%(room.room_id))
        response = client.api.leave_room(room.room_id)
      except:
        log.error("error leave room: '%s'"%(room.room_id))
        return False
      try:
        # И забыть её:
        log.info("Forgot room: '%s'"%(room.room_id))
        response = client.api.forget_room(room.room_id)
      except:
        log.error("error leave room: '%s'"%(room.room_id))
        return False
      return False
    log.debug("success invite user '%s' to room '%s'"%(address_im,room.room_id))

    # устанавливаем права в комнате для пользователя:
    try:
      response = room.modify_user_power_levels(users={address_im:user_power_level})
    except MatrixRequestError as e:
      log.debug(e)
      log.warning("Can not set user '%s' power level=%d to room '%s'"%(address_im,user_power_level,room.room_id))

    # обновляем базу:
    try:
      sql="insert into tbl_matrix_rooms (matrix_uid,user_room) VALUES ('%(address_im)s','%(user_room)s')"\
        %{\
        "address_im":address_im,\
        "user_room":room.room_id\
        }
      log.debug("sql='%s'"%sql)
      cur.execute(sql)
      conn.commit()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
      log.info("try rollback insertion for this connection")
      try:
        conn.rollback()
      except psycopg2.Error as e:
        log.error("sql error: %s" % e.pgerror)
      # т.к. комнаты уже создали - нужно выйти из них:
      try:
        # Нужно выйти из комнаты:
        log.info("Leave from new created room: '%s'"%(room.room_id))
        response = client.api.leave_room(room.room_id)
      except:
        log.error("error leave room: '%s'"%(room.room_id))
        return False
      try:
        # И забыть её:
        log.info("Forgot room: '%s'"%(room.room_id))
        response = client.api.forget_room(room.room_id)
      except:
        log.error("error leave room: '%s'"%(room.room_id))
        return False
      return False
    log.debug("create room '%s' and invite user '%s' to this room"%(room.room_id,address_im))

    # шлём help в комнаату:
    if send_message(log,client,room.room_id,conf.hello_message)==False:
      log.error("send_message()")
      return False

  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False

  return True

def connect_to_db():
  global log
  global conn
  global cur
  try:
    log.debug("connect to: dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='" + conf.send_db_passwd + "'")
    conn = psycopg2.connect("dbname='" + conf.send_db_name + "' user='" +conf.send_db_user + "' host='" + conf.send_db_host + "' password='" + conf.send_db_passwd + "'")
    cur = conn.cursor()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    log.error("I am unable to connect to the database")
    return False
  return True

def update_users_without_rooms():
  global log
  global conn
  global cur
  global client
  # проверяем, есть ли сообщения в очереди, для которых нужно создать комнату:
  items=None

  # Берём matrix ID-ы у которых нет комнат
  try:
    # обкусываем символы табуляции и пробелов:
    sql="select id,address_im from tbl_sending_queue \
      where sending_status_id=(select sending_status_id from tbl_sending_status where sending_status_name='no_room')\
      and address_im is not NULL"
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    items = cur.fetchall()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    return False
  if items==None:
    # все есть:
    return True
  try:
    for item in items:
      message_id=item[0]
      address_im=item[1].strip().lower()

      # подключаемся к матрице только если действительно есть запросы на создание комнат:
      if client == None:
        log.debug("try connect to matrix server...")
        client = matrix_connect()
        if client==None:
          log.error("matrix_connect()")
          return False
        else:
          log.debug("success connect to matrix server")

      log.info("proccess message_id=%d, try create room for address_im='%s'"%(message_id,address_im))
      if create_room(address_im, conf.user_power_level)==True:
        log.info("success create room for address_im='%s', set status for message_id=%d as 'new'"%(address_im,message_id))
        if set_sending_status(message_id, 'new') == False:
          log.error("set_sending_status()")
          return False
      else:
        log.error("error create room for user: '%s'" % address_im)
        # чтобы по нескольку раз не создавать комнаты в случае ошибки - помечаем как сбойное:
        if set_sending_status(message_id,"fault",error_description_im="ошибка заведения комнаты в IM для посылки сообщения - обратитесь к администратору") == False:
          log.error("set_sending_status()")
          return False
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
  return True


def matrix_connect():
    global log
    global client

    client = MatrixClient(conf.matrix_server)
    try:
        #token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id_create_rooms)
        token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id_create_rooms,sync=False)
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

def main():
    global client
    global log
    global conn
    global cur

    client = None

    if connect_to_db() == False:
      log.error("connect_to_db()")
      return False

    if update_users_without_rooms() == False:
      log.error("update_users_without_rooms()")
      return False

    conn.close()
    return True


if __name__ == '__main__':
  log=logging.getLogger("proccess_create_rooms")
  log_lib=logging.getLogger("matrix_client.client")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  #fh = logging.FileHandler(conf.log_path)
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_proccess_create_rooms, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
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
