#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import traceback
import time
import datetime
import psycopg2
import psycopg2.extras
import os
import logging
from logging import handlers
import re
import config as conf
import sendemail as mail
import urllib
import requests
from matrix_client.client import MatrixClient
from matrix_client.api import MatrixRequestError
from matrix_client.api import MatrixHttpLibError
from requests.exceptions import MissingSchema

bot=None
matrix_client=None
global_error_descr=""
conn=None
cur=None
log=None

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

def matrix_connect():
    client = MatrixClient(conf.matrix_server)
    try:
        token = client.login(username=conf.matrix_username, password=conf.matrix_password,device_id=conf.matrix_device_id_proccess_sending,sync=False)
    except MatrixRequestError as e:
        print(e)
        if e.code == 403:
            log.error("matrix.login() Bad username or password.")
            return None
        else:
            log.error("matrix.login() Check your sever details are correct.")
            return None
    except MatrixHttpLibError as e:
        log.error(": %s"%e)
        return None
    except MissingSchema as e:
        log.error("matrix.login() Bad URL format.")
        print(e)
        return None
    except:
        log.error("unknown error at client.login()")
        return None
    return client

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

def set_im_event_id(message_id, im_event_id):
  global conn
  global cur
  global log
  time_execute=time.time()
  try:
    sql="update tbl_sending_queue set \
      im_event_id='%(im_event_id)s'"\
      % {"im_event_id":im_event_id}
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

def get_im_event_id_by_sender_uniq_id(log, address_im, sender_uniq_id):
  global conn
  global cur
  time_execute=time.time()
  try:
    sql="""select im_event_id from tbl_sending_queue where 
        address_im='%(address_im)s' and 
        im_event_id is not null and 
        sender_uniq_id = '%(sender_uniq_id)s'
        order by id limit 1"""%{\
          "address_im":address_im,\
          "sender_uniq_id":sender_uniq_id\
          }
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    return None
  if item==None:
    log.debug("no previouse success sended message for address_im='%(address_im)s' and sender_uniq_id='%(sender_uniq_id)s'"%{"address_im":address_im, "sender_uniq_id":sender_uniq_id})
    return None
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return item[0]

def get_matrix_room(matrix_address):
  global conn
  global cur
  time_execute=time.time()
  try:
    sql=u"select user_room from tbl_matrix_rooms where matrix_uid='%s'"%matrix_address
    log.debug("get_matrix_room(): sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    return None
  if item==None:
    log.warning("get_matrix_room(%s) == None. Return 'no_room'."%matrix_address)
    return "no_room"
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return item[0]

def incress_sending_retry_num(message_id):
  global conn
  global cur
  time_execute=time.time()
  try:
    sql="select sending_retry_num from tbl_sending_queue where id=%d"%message_id
    log.debug("incress_sending_retry_num(): sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    sys.exit(1)
  if item==None:
    log.error("get sending_retry_num == None - internal script error!")
    sys.exit(1)
  retry_num=int(item[0])+1
  try:
    sql="update tbl_sending_queue set sending_retry_num=%(retry_num)d where id=%(message_id)d" % {"retry_num":retry_num,"message_id":message_id}
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    conn.commit()
    log.debug("Row(s) were updated : %s"%str(cur.rowcount))
  except psycopg2.Error as e:
    log.error("sql error: %s" % e.pgerror)
    log.info("try rollback update for this connection")
    try:
      conn.rollback()
    except psycopg2.Error as e:
      log.error("sql error: %s" % e.pgerror)
    sys.exit(1)

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def send_by_email(message_id,address_email,message_text):
  time_execute=time.time()
  log.debug(" Email start send")

  log.debug("Try set_sending_status(sending_by_email)")
  if set_sending_status(message_id, "sending_by_email") == False:
    log.error("set_sending_status()")
    return False
  log.debug("success set_sending_status(sending_by_email)")

  log.debug("Try mail.sendmail()")
  if mail.sendmail(text=message_text, subj=u"Диспетчерская рассылка", send_to=address_email, server=conf.email_server, send_from=conf.email_from) == False:
    log.error("mail.sendmail( send_to=%(address_email)s, server=%(email_server)s, send_from=%(email_from)s)" %{"address_email":address_email,"email_server":conf.email_server,"email_from":conf.email_from})
    if set_sending_status(message_id, "error",error_description_email="Send mail time (20 minutes) is exceed. Try send by email, but system ERROR send over email!") == False:
      log.error("set_sending_status()")
    return False
  else:
    log.debug("success mail.sendmail()")
    log.info("success send to email '%(address_email)s', message_id=%(message_id)d" %{"address_email":address_email,"message_id":message_id})
    log.debug("Try set_sending_status(sent_by_email)")
    if set_sending_status(message_id, "sent_by_email") == False:
      log.error("set_sending_status()")
      return False
    log.debug("success set_sending_status(sent_by_email)")
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def process_new_messages():
  global conn
  global cur
  try:
    time_execute=time.time()
    while True:
      #time.sleep(1)
      item=None
      try:
        sql="""select
          tbl_sending_queue.id,
          tbl_sending_queue.address_im,
          tbl_sending_queue.address_email,
          tbl_sending_queue.message,
          tbl_sending_queue.time_create,
          tbl_sending_queue.sending_retry_num,
          tbl_message_type.message_type_name,
          tbl_sending_queue.sender_uniq_id,
          tbl_sending_queue.edit_previouse
          from tbl_sending_queue
          LEFT JOIN tbl_message_type ON tbl_sending_queue.message_type_id = tbl_message_type.message_type_id
          where sending_status_id in (select sending_status_id from tbl_sending_status where sending_status_name='new') order by id"""
        log.debug("process_new_messages(): sql: %s" % sql )
        cur.execute(sql)
        items = cur.fetchall()
      except psycopg2.Error as e:
        global_error_descr="sql execute error: %s" % e.pgerror
        log.error(global_error_descr)
        return None

      # проверяем, нашли ли запись:
      if items==None or len(items)==0:
        # Не нашли ни одной записи со 'status'='new':
        log.debug("not found in 'status'='new' - exit")
        # Завершаем обработку сообщений:
        break

      log.info("found %d new records for process"%len(items))

      for item in items:
        try:
          time_process_one_message=time.time()
          # Нашли одну запись со статусом 'new'
          # Сразу же помечаем её в статус 'in progress'
          # и разблокируем базу:
          message_id=int(item[0])
          if item[1]!=None:
            address_im=item[1].strip()
          else:
            address_im=None
          if item[2]!=None:
            address_email=item[2].strip()
          else:
            address_email=None
          message_text=item[3]
          time_create=item[4]
          retry_num=int(item[5])
          message_type=item[6]
          sender_uniq_id=item[7]
          edit_previouse=item[8]
          log.debug("message to proccess: message_id=%(message_id)d, address_im='%(address_im)s', address_email='%(address_email)s', message_type='%(message_type)s', sender_uniq_id='%(sender_uniq_id)s', edit_previouse=%(edit_previouse)r " % {"message_id":message_id, "address_im":address_im, "address_email":address_email, "message_type":message_type, "sender_uniq_id":sender_uniq_id, "edit_previouse":edit_previouse})

          # помечаем "в работе"
          if set_sending_status(message_id, "in progress") == False:
            log.error("set_sending_status()")
            return False

          # увеличиваем счётчик отправок:
          incress_sending_retry_num(message_id)

          send_over_im=False
          send_over_email=False
          if address_im!=None:
            if len(address_im)>0:
              send_over_im=True
              # если прописан - пробуем отправить через IM:
              # Проверяем по edit_previouse == True и sender_uniq_id - если не пустое и были сообщения с таким sender_uniq_id - то получаем im_event_id исходного сообщения из IM
              # т.е. сообщения, которое было первоначально отправлено с таким же sender_uniq_id - мы будем его исправлять, вместо отправки нового:
              im_event_id = None
              if edit_previouse == True and sender_uniq_id is not None and len(sender_uniq_id)>0:
                im_event_id = get_im_event_id_by_sender_uniq_id(log, address_im, sender_uniq_id)
                log.debug("found source message by sender_uniq_id='%s' with im_event_id='%s'"%(sender_uniq_id,im_event_id))
              if im_event_id is not None and edit_previouse == True:
                # правим старое:
                if edit_IM_message(message_id, im_event_id, address_im,message_text,message_type) == False:
                  log.warning("edit_IM_message() message_id=%(message_id)d, im_event_id='%(im_event_id)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im, "im_event_id":im_event_id})
                else:
                  log.info("SUCCESS edit_IM_message() message_id=%(message_id)d, im_event_id='%(im_event_id)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im, "im_event_id":im_event_id })
              else:
                # отправляем как новое сообщение:
                if send_IM_message(message_id,address_im,message_text,message_type) == False:
                  log.warning("send_IM_message() message_id=%(message_id)d, address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im})
                else:
                  log.info("SUCCESS send_IM_message() message_id=%(message_id)d, address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im })

          if send_over_im==False:
            if set_sending_status(message_id,"error",error_description_im="ERROR - не указано ни одного адреса сервиса мгновенных сообщений (чата)!") == False:
              log.error("set_sending_status()")
              return False

            # Отправляем через почту, если она включена:
            if address_email!=None:
              if len(address_email)>0:
                send_over_email=True
                if send_by_email(message_id,address_email,message_text) == False:
                  log.error("ERROR send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
                else:
                  log.info("SUCCESS send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
              else:
                log.info("SKIP email send becouse address_email is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
            else:
              log.info("SKIP email send becouse address_email is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})

          # Если не отправляли по почте, и IM-сервер не имеет доступа в интернет, то нужно дополнительно отправить сообщение по почте:
          if send_over_email == False and is_im_server_have_internet_access() == False:
            # при этом не важно - отправляли ли мы через IM (т.к. пользователи с мобильных не могут подключиться к нашему серверу)
            if set_sending_status(message_id,"error",u"ERROR - удалённые (мобильные) пользователи IM-сервера не имеют соединения с сервером (нет интернета)!") == False:
              log.error("set_sending_status()")
              return False
            log.error("process_new_messages(): ERROR IM server have no internet connectin - send message over email")
            # Отправляем через почту, если она включена:
            if address_email!=None:
              if len(address_email)>0:
                send_over_email=True
                if send_by_email(message_id,address_email,message_text) == False:
                  log.error("ERROR send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
                else:
                  log.info("SUCCESS send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
              else:
                log.info("SKIP email send becouse email_to is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
            else:
              log.info("SKIP email send becouse email_to is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})

          # если не отправили никак - выставляем статус:
          if send_over_email == False and send_over_im == False:
            if set_sending_status(message_id,"error",error_description_email=u"ERROR - не указано ни одно адреса (IM, email) для рассылки - пропускаю отправку!") == False:
              log.error("set_sending_status()")
              return False
          time_process_one_message=time.time()-time_process_one_message
          log.debug("time_process_one_message=%f"%time_process_one_message)
          if time_process_one_message>5:
            log.warning("send one message more 5 seconds! time_process_one_message=%f"%time_process_one_message)
        except Exception as e:
          log.error(get_exception_traceback_descr(e))
          if set_sending_status(message_id, "error",str(e)) == False:
            log.error("set_sending_status()")

    log.debug("execute function time=%f"%(time.time()-time_execute))
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    return False
  return True

def process_error_messages():
  global conn
  global cur

  time_execute=time.time()
  item=None
  items=None
  try:
    sql="""select
        tbl_sending_queue.id,
        tbl_sending_queue.address_im,
        tbl_sending_queue.address_email,
        tbl_sending_queue.message,
        tbl_sending_queue.time_create,
        tbl_sending_queue.sending_retry_num,
        tbl_message_type.message_type_name,
        tbl_sending_queue.sender_uniq_id,
        tbl_sending_queue.edit_previouse
        from tbl_sending_queue
        LEFT JOIN tbl_message_type ON tbl_sending_queue.message_type_id = tbl_message_type.message_type_id
        where sending_status_id in (select sending_status_id from tbl_sending_status where sending_status_name='error') order by id"""
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    items = cur.fetchall()
  except psycopg2.Error as e:
    log.error("sql execute error: %s" % e.pgerror)
    return False

  # проверяем, нашли ли запись:
  if items==None:
    # Не нашли ни одной записи со 'status'='error':
    log.debug("not found 'status'='error' - exit")
    # Завершаем обработку сообщений:
    return True

  log.info("found %d errors for process"%len(items))

  for item in items:
    try:
      # Обрабатываем запись со статусом 'error'
      message_id=int(item[0])
      if item[1]!=None:
        address_im=item[1].strip()
      else:
        address_im=None
      if item[2]!=None:
        address_email=item[2].strip()
      else:
        address_email=None
      message_text=item[3]
      time_create=item[4]
      retry_num=int(item[5])
      message_type=item[6]
      sender_uniq_id=item[7]
      edit_previouse=item[8]

      send_over_email=False
      log.debug("message to proccess: message_id=%(message_id)d, address_im=%(address_im)s, address_email='%(address_email)s', time_create=%(time_create)s, retry_num=%(retry_num)d, message_type='%(message_type)s', sender_uniq_id='%(sender_uniq_id)s', edit_previouse=%(edit_previouse)r" % \
            {"message_id":message_id, "address_im":address_im, "time_create":time_create,"address_email":address_email,"retry_num":retry_num,"message_type":message_type, "sender_uniq_id":sender_uniq_id, "edit_previouse":edit_previouse})

      # помечаем "в работе" - убрал, т.к. иначе время запуска в обработку будет перезатираться и будет отображать только время последней попытки отправить:
      #set_sending_status(message_id, "in progress")

      # увеличиваем счётчик отправок:
      incress_sending_retry_num(message_id)

      # Проверяем, прошло ли 20 минут с момента создания сообщения, если прошло, то нужно уже отправлять через почту:
      time_delta=datetime.datetime.now() - time_create
      log.debug("time_create: %s"%time_create)
      log.debug("time_now: %s"%datetime.datetime.now() )
      log.debug("time_delta: %s"%time_delta)
      log.debug("Возраст сообщения: %d секунд" % time_delta.total_seconds() )
      if time_delta.total_seconds() > 20*60:
        log.debug("Возраст сообщения более 20 минут - пробуем слать почтой" )
        # Нужно слать почтой:
        # Проверяем, если сообщение не старше, чем 3 часа - то пробуем ещё раз отправить по почте, иначе будет без конца заваливать логи ошибками:
        if time_delta.total_seconds() < 3*3600:
          log.debug("Возраст сообщения менее 3 часов - ещё можно попробовать отправить почтой" )

          if address_email!=None:
            if len(address_email)>0:
              log.debug("TRY send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % \
                    {"message_id":message_id, "address_email":address_email, "address_im":address_im})
              text_to_email=u"""Добрый день!
              В течении 20 минут после наступления события были предприняты %(retry_num)d неудачных попыток отправить Вам сообщение через matrix как пользователю '%(address_im)s'.
              Это не удалось, поэтому сообщение отправляется почтой.
              Сообщение было:

              %(message_text)s""" % {"retry_num":retry_num, "address_im":address_im, "message_text":message_text,"address_im":address_im}
              send_over_email=Truematrix_address
              if send_by_email(message_id,address_email,text_to_email) == False:
                log.error("ERROR send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % \
                    {"message_id":message_id, "address_email":address_email, "address_im":address_im})
              else:
                log.info("SUCCESS send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % \
                    {"message_id":message_id, "address_email":address_email, "address_im":address_im})
            else:
              if set_sending_status(message_id,"error",error_description_email=u"ERROR - ошибка отправки по почте - пустой адрес!") == False:
                log.error("set_sending_status()")
                return False
              log.info("SKIP send to email (to_addres is empty). message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % \
                  {"message_id":message_id, "address_email":address_email, "address_im":address_im})
          else:
            if set_sending_status(message_id,"error",error_description_email=u"ERROR - ошибка отправки по почте - пустой адрес!") == False:
              log.error("set_sending_status()")
              return False
            log.info("SKIP send to email (to_addres is empty). message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % \
                {"message_id":message_id, "address_email":address_email, "address_im":address_im})
        else:
          log.info("Возраст сообщения более 3 часов - прекращаем попытки обработки сообщения" )
          if set_sending_status(message_id,"fault") == False:
            log.error("set_sending_status()")
            return False

      else:
        # Ещё не прошло 20 минут - шлём через im:
        log.info("Возраст сообщения менее 20 минут - пробуем слать через im" )
        # сначала пробуем отправить через IM, потом через почту:
        if address_im != None and len(address_im)>0:
          log.info("address_im не пуст - пробуем отправить через IM" )
          # шлём через IM:

          # если прописан - пробуем отправить через IM:
          # Проверяем по edit_previouse == True и sender_uniq_id - если не пустое и были сообщения с таким sender_uniq_id - то получаем im_event_id исходного сообщения из IM
          # т.е. сообщения, которое было первоначально отправлено с таким же sender_uniq_id - мы будем его исправлять, вместо отправки нового:
          im_event_id = None
          if edit_previouse == True and sender_uniq_id is not None and len(sender_uniq_id)>0:
            im_event_id = get_im_event_id_by_sender_uniq_id(log, address_im, sender_uniq_id)
            log.debug("found source message by sender_uniq_id='%s' with im_event_id='%s'"%(sender_uniq_id,im_event_id))
          if im_event_id is not None and edit_previouse == True:
            # повторно правим старое (т.к. прошлый раз не получилось - ошибка была):
            if edit_IM_message(message_id, im_event_id, address_im,message_text,message_type) == False:
              log.warning("edit_IM_message() message_id=%(message_id)d, im_event_id='%(im_event_id)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im, "im_event_id":im_event_id})
            else:
              log.info("SUCCESS edit_IM_message() message_id=%(message_id)d, im_event_id='%(im_event_id)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im, "im_event_id":im_event_id })
          else:
            # отправляем как новое сообщение:
            if send_IM_message(message_id,address_im,message_text,message_type) == False:
              log.warning("send_IM_message() message_id=%(message_id)d, address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im})
            else:
              log.info("SUCCESS send_IM_message() message_id=%(message_id)d, address_im='%(address_im)s'" % {"message_id":message_id, "address_im":address_im })

        elif address_email !=None and len(address_email)>0:
          # Сразу пробуем отправить через почту:
          if len(address_email)>0:
            send_over_email=True
            if send_by_email(message_id,address_email,message_text) == False:
              log.error("ERROR send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
            else:
              log.info("SUCCESS send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
          else:
            log.info("SKIP email send becouse email_to is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})

        else:
          log.info("SKIP any send becouse all addresses is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})

      # Если не отправляли по почте, и IM-сервер не имеет доступа в интернет, то нужно дополнительно отправить сообщение по почте:
      if send_over_email == False and is_im_server_have_internet_access() == False:
        # при этом не важно - отправляли ли мы через IM (т.к. пользователи с мобильных не могут подключиться к нашему серверу)
        if set_sending_status(message_id,"error",u"ERROR - удалённые (мобильные) пользователи IM-сервера не имеют соединения с сервером (нет интернета)!") == False:
          log.error("set_sending_status()")
          return False
        log.error("ERROR IM server have no internet connectin - send message over email")
        # Отправляем через почту, если она включена:
        if address_email!=None:
          if len(address_email)>0:
            send_over_email=True
            if send_by_email(message_id,address_email,message_text) == False:
              log.error("ERROR send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
            else:
              log.info("SUCCESS send_by_email(message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
          else:
            log.info("SKIP email send becouse email_to is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
        else:
          log.info("SKIP email send becouse email_to is empty. message_id=%(message_id)d, address_email='%(address_email)s', address_im='%(address_im)s'" % {"message_id":message_id, "address_email":address_email, "address_im":address_im})
    except Exception as e:
      log.error(get_exception_traceback_descr(e))
      if set_sending_status(message_id, "error",str(e)) == False:
        log.error("set_sending_status()")

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def edit_IM_message(message_id, im_event_id, matrix_address, message_text, message_type="text"):
  global matrix_client
  time_execute=time.time()
  if set_sending_status(message_id, "sending_by_im") == False:
    log.error("set_sending_status()")
    return False
  tg_state = {}
  log.debug("MATRIX start send to '%s'"%matrix_address)

  if len(matrix_address)==0:
    # пустой ник:
    log.error("Error! Empty matrix_uid! Skip sending!")
    if set_sending_status(message_id, "error","Error! Empty matrix_uid! Skip sending!") == False:
      log.error("set_sending_status()")
      return False
    return False

  if matrix_client==None:
    time_execute_internal=time.time()
    # одно соединение за обработку:
    matrix_client = matrix_connect()
    if matrix_client == None:
      log.error("matrix_client api error - cannot connect to matrix for send message_id=%(message_id)d"%{"message_id":message_id})
      if set_sending_status(message_id, "error", "matrix connect error - cannot init matrix_client") == False:
        log.error("set_sending_status()")
      return False
    log.debug("execute function matrix_connect() time=%f"%(time.time()-time_execute_internal))

  log.debug("Try get_matrix_room(matrix_address='%s')"%matrix_address)
  time_execute_internal=time.time()
  room_id=get_matrix_room(matrix_address)
  if room_id == "no_room":
    log.warning("no exist room for user '%s'"%matrix_address)
    # нет комнаты для этого пользователя - помечаем для стороннего скрипта, что нужно создать комнату для пользователя:
    if set_sending_status(message_id, "no_room") == False:
      log.error("set_sending_status()")
      return False
    # это не ошибка скрипта, просто пока нет комнаты для пользователя:
    return True
  elif room_id == None:
    log.error("internal matrix-bot error when proccess message with id=%d - can not get room of user" % message_id )
    if set_sending_status(message_id, "error",u"внутренняя ошибка matrix-бота - не смог получить соответствие matrix_uid->room_id" ) == False:
      log.error("set_sending_status()")
    return False
  log.debug("execute function get_matrix_room() time=%f"%(time.time()-time_execute_internal))
  log.debug("room_id='%s'"%room_id)
  log.debug("username='%s'"%matrix_address)
  log.debug("success get_matrix_room(matrix_address='%s')"%matrix_address)

  log.debug("Try matrix_client.join_room()")
  room=None
  time_execute_internal=time.time()
  try:
    room = matrix_client.join_room(room_id)
  except MatrixRequestError as e:
    print(e)
    if e.code == 400:
      error_description="Room ID/Alias in the wrong format (over matrix)"
      log.error("matrix_bot.join_room() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
      if set_sending_status(message_id, "error", error_description) == False:
        log.error("set_sending_status()")
      return False
    else:
      error_description="Could do not find room %s at matrix server."%room_id
      log.error("matrix_bot.join_room() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
      if set_sending_status(message_id, "error", error_description) == False:
        log.error("set_sending_status()")
      return False
  log.debug("execute function matrix_client.join_room() time=%f"%(time.time()-time_execute_internal))
  log.debug("success matrix_client.join_room()")
  log.debug("Try edit_matrix_message()")
  time_execute_internal=time.time()
  try:
    if message_type=="markdown" or message_type=="html":
      log.debug("send message as 'formated' (html/markdown) - sending by edit_matrix_message()")
      ret = edit_matrix_message(room_id, im_event_id, message_text, msgtype="m.html")
    else:
      log.debug("send message as 'text' (without formating) - sending by edit_matrix_message()")
      ret = edit_matrix_message(room_id, im_event_id, message_text, msgtype="m.text")

    if ret == None or 'event_id' not in ret:
      log.error("edit_matrix_message() not return 'event_id' of message")
      if set_sending_status(message_id, "error", "edit_matrix_message() error or not return 'event_id' of message") == False:
        log.error("set_sending_status()")
      return False
    else:
      if set_im_event_id(message_id,ret["event_id"]) == False:
        log.error("set_im_event_id()")
        return False
  except:
    error_description="Unknown error at send message to room %s over matrix"%room_id
    log.error("matrix_bot.send_message() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
    if set_sending_status(message_id, "error", error_description) == False:
      log.error("set_sending_status()")
    return False
  log.debug("success edit_matrix_message()")
  log.debug("execute function edit_matrix_message() time=%f"%(time.time()-time_execute_internal))

  # успешно отправили:
  log.debug("Try set_sending_status(edited_previous_sended_by_im)")
  if set_sending_status(message_id, "edited_previous_sended_by_im","edit_im_event_id=%s"%im_event_id) == False:
    log.error("set_sending_status()")
    return False
  else:
    log.debug("success set_sending_status(edited_previous_sended_by_im)")
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def send_IM_message(message_id, matrix_address, message_text, message_type="text"):
  global matrix_client
  time_execute=time.time()
  if set_sending_status(message_id, "sending_by_im") == False:
    log.error("set_sending_status()")
    return False
  tg_state = {}
  log.debug("MATRIX start send to '%s'"%matrix_address)

  if len(matrix_address)==0:
    # пустой ник:
    log.error("Error! Empty matrix_uid! Skip sending!")
    if set_sending_status(message_id, "error","Error! Empty matrix_uid! Skip sending!") == False:
      log.error("set_sending_status()")
      return False
    return False

  if matrix_client==None:
    time_execute_internal=time.time()
    # одно соединение за обработку:
    matrix_client = matrix_connect()
    if matrix_client == None:
      log.error("matrix_client api error - cannot connect to matrix for send message_id=%(message_id)d"%{"message_id":message_id})
      if set_sending_status(message_id, "error", "matrix connect error - cannot init matrix_client") == False:
        log.error("set_sending_status()")
      return False
    log.debug("execute function matrix_connect() time=%f"%(time.time()-time_execute_internal))

  log.debug("Try get_matrix_room(matrix_address='%s')"%matrix_address)
  time_execute_internal=time.time()
  room_id=get_matrix_room(matrix_address)
  if room_id == "no_room":
    log.warning("no exist room for user '%s'"%matrix_address)
    # нет комнаты для этого пользователя - помечаем для стороннего скрипта, что нужно создать комнату для пользователя:
    if set_sending_status(message_id, "no_room") == False:
      log.error("set_sending_status()")
      return False
    # это не ошибка скрипта, просто пока нет комнаты для пользователя:
    return True
  elif room_id == None:
    log.error("internal matrix-bot error when proccess message with id=%d - can not get room of user" % message_id )
    if set_sending_status(message_id, "error",u"внутренняя ошибка matrix-бота - не смог получить соответствие matrix_uid->room_id" ) == False:
      log.error("set_sending_status()")
    return False
  log.debug("execute function get_matrix_room() time=%f"%(time.time()-time_execute_internal))
  log.debug("room_id='%s'"%room_id)
  log.debug("username='%s'"%matrix_address)
  log.debug("success get_matrix_room(matrix_address='%s')"%matrix_address)

  log.debug("Try matrix_client.join_room()")
  room=None
  time_execute_internal=time.time()
  try:
    room = matrix_client.join_room(room_id)
  except MatrixRequestError as e:
    print(e)
    if e.code == 400:
      error_description="Room ID/Alias in the wrong format (over matrix)"
      log.error("matrix_bot.join_room() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
      if set_sending_status(message_id, "error", error_description) == False:
        log.error("set_sending_status()")
      return False
    else:
      error_description="Could do not find room %s at matrix server."%room_id
      log.error("matrix_bot.join_room() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
      if set_sending_status(message_id, "error", error_description) == False:
        log.error("set_sending_status()")
      return False
  log.debug("execute function matrix_client.join_room() time=%f"%(time.time()-time_execute_internal))
  log.debug("success matrix_client.join_room()")
  log.debug("Try room.send_text()")
  time_execute_internal=time.time()
  try:
    if message_type=="markdown" or message_type=="html":
      log.debug("send message as 'formated' (html/markdown) - sending by room.send_html()")
      ret = room.send_html(message_text)
    else:
      log.debug("send message as 'text' (without formating) - sending by room.send_text()")
      ret = room.send_text(message_text)

    if ret == None or 'event_id' not in ret:
      error_description="room.send_text() or room.send_html() not return 'event_id' of message"
      log.error(error_description)
      if set_sending_status(message_id, "error", error_description) == False:
        log.error("set_sending_status()")
      return False
    else:
      if set_im_event_id(message_id,ret["event_id"]) == False:
        log.error("set_im_event_id()")
        return False
  except:
    error_description="Unknown error at send message to room %s over matrix"%room_id
    log.error("matrix_bot.send_message() error for send message_d=%(message_id)d, descr: %(error_description)s"%{"message_id":message_id, "error_description":error_description})
    if set_sending_status(message_id, "error", error_description) == False:
      log.error("set_sending_status()")
    return False
  log.debug("success room.send_text()")
  log.debug("execute function room.send_text() time=%f"%(time.time()-time_execute_internal))

  # успешно отправили:
  log.debug("Try set_sending_status(sent_by_im)")
  if set_sending_status(message_id, "sent_by_im") == False:
    log.error("set_sending_status()")
    return False
  else:
    log.debug("success set_sending_status(sent_by_im)")
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def is_im_server_have_internet_access():
  # файл создан zabbix-агентом. В случае, если на проксе, через которую IM-сервер ходит в интернет пропадает интернет - файл
  # содержит дату 'ERROR', если интернет есть - то содержит дату 'SUCCESS'
  time_execute=time.time()
  f=None
  try:
    f=open(conf.file_internet_status,"r")
    line=f.readline()
    result=re.search(r'ERROR', line)
    if result != None:
      # нашли
      log.debug("is_im_server_have_internet_access(): IM-server have NOT internet connection! (file exist and have error-word)" )
      return False
  except:
    # файла нет, значит всё хорошо - интернет есть
    log.debug("is_im_server_have_internet_access(): IM-server HAVE internet connection! (no file)" )
    return True
  log.debug("is_im_server_have_internet_access(): IM-server HAVE internet connection! (file exist, but have not error-word)" )
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

def edit_matrix_message(room_id, edited_event_id, text, msgtype="m.text"):
  global matrix_client
  global log
  try:
    if msgtype=="m.text":
      body = {
          "m.new_content": {
            "body": text,
            "msgtype": "m.text"
          },
          "m.relates_to": {
            "rel_type": "m.replace",
            "event_id": edited_event_id
          },
          "body": " * %s"%text,
          "msgtype": "m.text"
        }
    else:
      # html/markdown:
     not_html_text = re.sub('<[^<]+?>', '', text),
     body = {
          "m.new_content": {
            "body": not_html_text,
            "msgtype": "m.text",
            "format": "org.matrix.custom.html",
            "formatted_body": text
          },
          "m.relates_to": {
            "rel_type": "m.replace",
            "event_id": edited_event_id
          },
          "format": "org.matrix.custom.html",
          "body": " * %s"%not_html_text,
          "formatted_body": text,
          "msgtype": "m.text"
        }
    return matrix_client.api.send_state_event(room_id, "m.room.message", body, timestamp=None)
  except Exception as e:
    log.error(get_exception_traceback_descr(e))
    log.error("exception at execute edit_matrix_message()")
    return None

#=============== main() ===============
def main():
  global conn
  global cur
  global log

  time_execute=time.time()

  if connect_to_db()==False:
    log.error("connect_to_db()")
    return False
  log.debug("time connect to postgres in secods=%f"%(time.time()-time_execute))

  time_execute=time.time()
  # Обрабатываем новые сообщения:
  if process_new_messages() == False:
    log.error("main(): Error process_new_messages()")
    sys.exit(1)
  log.debug("time process_new_messages() in secods=%f"%(time.time()-time_execute))
  # Повторная отправка неотправленных другими ботами:
  time_execute=time.time()
  if process_error_messages() == False:
    log.error("main(): Error process_error_messages()")
    sys.exit(1)
  log.debug("time process_error_messages() in secods=%f"%(time.time()-time_execute))

  time_execute=time.time()
  if conn:    
    conn.close()
  log.debug("time close connect to postgres in secods=%f"%(time.time()-time_execute))
  return True

if __name__ == '__main__':
  log=logging.getLogger("proccess_sending_queue")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_proccess_sending_queue, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
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
  log.info("success main()")
  log.info("Program success exit")
