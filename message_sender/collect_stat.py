#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import time
import datetime
import psycopg2
import psycopg2.extras
import os
import logging
from logging import handlers
import config as conf

def get_num_send_request_at_last_30_days():
  global con
  global cur
  global log

  time_execute=time.time()

  time_line=time.time()-30*24*3600
  time_string=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time_line)))
  log.debug("time_line=%s"%time_string)
  item=None
  try:
    sql="select count(*) from tbl_sending_queue where time_create > '%s'"%time_string
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("can not select data from db: %s" % e.pgerror)
    return None

  if item == None:
    log.error("sql error")
    return None

  value=int(item[0])
  log.debug("value=%d"%value)

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return value

def get_num_send_request_at_last_24_hour():
  global con
  global cur
  global log

  time_execute=time.time()

  time_line=time.time()-24*3600
  time_string=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time_line)))
  log.debug("time_line=%s"%time_string)
  item=None
  try:
    sql="select count(*) from tbl_sending_queue where time_create > '%s'"%time_string
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("can not select data from db: %s" % e.pgerror)
    return None

  if item == None:
    log.error("sql error")
    return None

  value=int(item[0])
  log.debug("value=%d"%value)

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return value

def get_num_fault_send_request_at_last_24_hour():
  global con
  global cur
  global log

  time_execute=time.time()

  time_line=time.time()-24*3600
  time_string=time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(time_line)))
  log.debug("time_line=%s"%time_string)
  item=None
  try:
    sql="""select count(*) from tbl_sending_queue where
    sending_status_id in (select sending_status_id from tbl_sending_status where sending_status_name='fault'))
    and time_create > '%s'"""%time_string
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("sql execute error: %s" % e.pgerror)
    return None

  if item == None:
    log.error("sql error")
    return None

  value=int(item[0])
  log.debug("value=%d"%value)

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return value

def get_num_send_request_in_new_state():
  global con
  global cur
  global log

  time_execute=time.time()
  item=None
  try:
    sql="""select count(*) from tbl_sending_queue where 
    sending_status_id in (select sending_status_id from tbl_sending_status where sending_status_name='new'))
    """
    log.debug("sql: %s" % sql )
    cur.execute(sql)
    item = cur.fetchone()
  except psycopg2.Error as e:
    log.error("sql execute error: %s" % e.pgerror)
    return None

  if item == None:
    log.error("sql error")
    return None

  value=int(item[0])
  log.debug("value=%d"%value)

  log.debug("execute function time=%f"%(time.time()-time_execute))
  return value

def write_stat_data(path,value):
  time_execute=time.time()
  f=None
  try:
    f=open(path,"w+")
    f.write(value)
    f.close()
  except:
    # файла нет, значит всё хорошо - интернет есть
    log.error("open o write data to file: %s"%path )
    return False
  log.debug("execute function time=%f"%(time.time()-time_execute))
  return True

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

  # Статистика по заявкам на рассылку за последние 24 часа:
  value=get_num_send_request_at_last_30_days()
  if value == None:
    log.error("Error get_num_send_request_at_last_30_days()")
    return False
  write_stat_data(conf.stat_path+"/disp_vl_send_request_at_last_30_days.num",str(value))

  # Статистика по заявкам на рассылку за последние 24 часа:
  value=get_num_send_request_at_last_24_hour()
  if value == None:
    log.error("Error get_num_send_request_at_last_24_hour()")
    return False
  write_stat_data(conf.stat_path+"/disp_vl_send_request_at_last_24_hour.num",str(value))
  all_send_request_at_last_24_hour=value

  # Статистика по сбойным заявкам на рассылку за последние 24 часа:
  value=get_num_fault_send_request_at_last_24_hour()
  if value == None:
    log.error("Error get_num_fault_send_request_at_last_24_hour()")
    return False
  write_stat_data(conf.stat_path+"/disp_vl_fault_send_request_at_last_24_hour.num",str(value))
  fault_send_request_at_last_24_hour=value

  # Статистика по % сбойных заявок на рассылку за последние 24 часа:
  fault_procent=(float(fault_send_request_at_last_24_hour)/float(all_send_request_at_last_24_hour))*100
  write_stat_data(conf.stat_path+"/disp_vl_fault_procent_send_request_at_last_24_hour.num","%f"%fault_procent)

  # Статистика по новым заявкам на рассылку:
  value=get_num_send_request_in_new_state()
  if value == None:
    log.error("Error get_num_send_request_in_new_state()")
    return False
  write_stat_data(conf.stat_path+"/disp_vl_send_request_in_new_state.num",str(value))

  log.debug("time get all statistic in secods=%f"%(time.time()-time_execute))
  return True

if __name__ == '__main__':
  log=logging.getLogger("disp_stat")
  if conf.debug:
    log.setLevel(logging.DEBUG)
  else:
    log.setLevel(logging.INFO)

  # create the logging file handler
  fh = logging.handlers.TimedRotatingFileHandler(conf.log_path_stat, when=conf.log_backup_when, backupCount=conf.log_backup_count, encoding='utf-8')
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
