#!/usr/bin/env python3

# Amazon ElastiCache for Redis as DbCache for Amazon RDS for MySQL

import json
import math
import os
import pickle
import pymysql, datetime, hashlib
import psycopg2
import random
import redis
import certifi
import requests
import socket
import sys
import threading
import time
import uuid
from psycopg2 import OperationalError
from flask import Flask, Markup, request, render_template, jsonify, make_response
from json import JSONEncoder


#app start
app = Flask(__name__, static_url_path='/static')


@app.route('/')
@app.route('/index')
@app.route('/index.html')
def index():
    return render_template('index.html')


#app end


#backend
m = None                # MySQL connection
r = None                # Redis connection
p = None                # PostgreSQL connection
start_time_value = None # Used to track start time of remote call
end_time_value = None   # Used to track start time of remote call
TTL = 5000              # In milliseconds, so 5 seconds
redis_counter = 0       # Track the number of Redis GETs
db_counter = 0          # Track the number of MySQL SELECTs
db_time = 0             # Total milliseconds accrued by MySQL
redis_time = 0          # Total milliseconds accrued by Redis
hits_counter = 0
key_prefix = "ex4:"
variability  = ""
db = 'PostgreSQL'            # MySQL | PostgreSQL
mySQL_con = None
PgSQL_con = None


@app.route('/start_db_run')
def start_db_run():
  TTL = request.args.get('ttl') or 5000
  complexity = request.args.get('complexity') or 'Low'
  variability = request.args.get('possibilites') or 500
  runs = int(request.args.get('runs')) or 5000
  db = request.args.get('db') or 'MySQL'  # MySQL | PostgreSQL
  # print(f"Start running test for {db}")
  connect_redis()
  connect_databases(db)
  threading.Thread(target=loadDbData, args=(TTL, complexity, variability, runs,)).start()
  return make_response((str(TTL) + str(complexity) + str(variability), 200))


@app.route('/get/db_run_sums')
def get_db_run_sums():
  global db
  connect_redis()
  summary = redis_reader_con.get('DBSUMMARY')
  if not summary:
    return make_response('still running', 200)
  return make_response(summary, 200)


@app.route('/get/db_cache')
def get_db_cache():
  connect_redis()
  hits = int(redis_reader_con.get('db_cache_hit_counter'))
  miss = int(redis_reader_con.get('db_cache_miss_counter'))
  res = make_response('{}|{}'.format(hits,miss),200)
  return res


@app.route('/get/log/<LogId>')
def get_logs(LogId):
  connect_redis()
  log = get_redis_client().lrange('WORKER_{}'.format(LogId), 0, 25)
  if not log:
    return(make_response('',200))
  res = make_response(make_json_from_redis(log), 200)
  return res


@app.route('/get/latest_time')
def get_times():
  global redis_counter, db_counter, redis_time, db_time, delta, cac
  connect_redis()
  tRedis = float(redis_reader_con.get('db_cache_redis_time')) / (float(redis_counter) - float(db_counter) + 0.0001)
  tDB = float(redis_reader_con.get('db_cache_db_time')) / float(db_counter + 0.0001)
  res = make_response('{}|{}|{}'.format(tRedis, tDB, db_counter), 200)
  return res


def make_json_from_redis(objs):
  lst = [] 
  for obj in objs:
    lst.append(obj)
  return json.dumps(lst)


def print_summary():
    global redis_counter, db_counter, redis_time, db_time, delta, cac
    db_avg_ms = db_time / (db_counter + .0001)
    redis_avg_ms = redis_time / (redis_counter + .00001)
    delta = db_avg_ms / (redis_avg_ms + .00001)
    header = '       {: ^6s}  {: ^6s}'
    entry  = '{:5s}  {:>6,d}  {:6.2f}'
    sm = summary(db_counter, redis_counter, int(db_avg_ms), int(redis_avg_ms))
    redis_writer_con.set('DBSUMMARY', json.dumps(sm.__dict__))
    redis_writer_con.set('Performance_Message', '\nRedis was about {:5,d} times faster\n'.format(int(delta)) )


def start_timer():
    global start_time_value
    start_time_value = datetime.datetime.now()


def end_timer():
    global end_time_value
    end = datetime.datetime.now()
    delta_time = datetime.datetime.now() - start_time_value
    end_time_value = delta_time.microseconds
    return (delta_time.microseconds)


def connect_redis():
    global redis_reader_con, redis_writer_con
    redis_reader_con = get_redis_reader_client()
    redis_writer_con =  get_redis_client()
    # print(f"Connected to ElastiCache")


def connect_databases(db):
    global mySQL_con, PgSQL_con
    if db == "MySQL":
      try:
        mySQL_con = pymysql.connect(
          host=os.getenv('DATABASE_HOST'),
          port=os.getenv('DATABASE_PORT'),
          user=os.getenv('DATABASE_USER'),
          password=os.getenv('DATABASE_PASS'),
          database=os.getenv('DB'),
        )
      except ValueError:
        print(ValueError)
    if db == "PostgreSQL":
      try:
        PgSQL_con = psycopg2.connect(
              sslmode='require',
#              database=os.getenv('DATABASE_NAME'),
              database='reviews',
              user=os.getenv('DATABASEPG_USER'),
              password=os.getenv('DATABASEPG_PASS'),
              host=os.getenv('DATABASEPG_HOST'),
              port=os.getenv('DATABASEPG_PORT'),
          )
      except OperationalError as e:
        print(f"The error '{e}' occurred")


def get_rds_cursor(db):
  global mySQL_con, PgSQL_con
  if db == "MySQL":
    return mySQL_con.cursor()
  if db == "PostgreSQL":
    return PgSQL_con.cursor()


def fetch(sql, TTL, variability, db):
    global db_time, redis_time, redis_counter, db_counter, hits_counter, end_time_value
    # Format the SQL string
    SQLCmd = sql.format(random.randrange(1, int(variability)))
    # print(SQLCmd)
    # Create unique hash key from query string
    hash = hashlib.sha224(SQLCmd.encode('utf-8')).hexdigest()
    key = key_prefix + hash
    # Gather timing stats while fetching from Redis
    start_timer()
    value = redis_reader_con.get(key)
    redis_counter = redis_counter + 1
    if value is not None:
        # Result was in cache
        redis_time =  redis_time + end_timer()
        ql = query_line(SQLCmd,redis_time,redis_counter,'hit')
        log_data(redis_writer_con, 'DBCACHE',ql)
        hits_counter = hits_counter + 1
        redis_writer_con.set('db_cache_redis_time',redis_time)
        redis_writer_con.incr('db_cache_hit_counter')
        return value
    else:
        # Get data from SQL
        cursor = get_rds_cursor(db)
        cursor.execute(SQLCmd)
        value = cursor.fetchall()
        db_time = db_time + end_timer()
        db_counter = db_counter + 1
        ql = query_line(SQLCmd, db_time, db_counter, 'miss')
        redis_writer_con.incr('db_cache_miss_counter')
        redis_writer_con.set('db_cache_db_time', db_time)
        redis_writer_con.psetex(key, TTL, str(value))
        log_data(redis_writer_con, 'DBCACHE', ql)
        return value    


class query_line: 
  def __init__ (self,sql_txt,time,cnt,hm):
    self.sql_txt = sql_txt
    self.time = int(time) 
    self.cnt = int(cnt) 
    self.hm = hm


class summary: 
  def __init__ (self,sql_calls,redis_calls,sql_avg,redis_avg):
    self.sql_calls = sql_calls
    self.redis_calls = redis_calls 
    self.sql_avg = sql_avg
    self.redis_avg = redis_avg


def log_data(client, worker_id, data):
    log_line = json.dumps(data.__dict__)
    client.rpush('WORKER_{}'.format(worker_id), log_line)
    client.ltrim('WORKER_{}'.format(worker_id), -10, -1)


def clear_all_logs(client, worker_id):
    global db_time, redis_time, redis_counter, db_counter, hits_counter, end_time_value
    db_time=0
    redis_time=0
    redis_counter=0
    db_counter=0
    hits_counter=0
    end_time_value=0
    client.delete('WORKER_{}'.format(worker_id))
    client.delete('DBSUMMARY')
    client.set('db_cache_miss_counter',0)
    client.set('db_cache_hit_counter',0)
    client.set('db_cache_db_time',0)
    client.set('db_cache_redis_time',0)


def get_db_sql(db, complexity):
    if complexity == 'Medium':
      sql = 'SELECT SUBSTRING(review_id, 1, 5) AS code, {}, COUNT(review_id) FROM reviews GROUP BY code LIMIT 1'
    elif complexity  ==  'High':
      # this line works for mysql
      #sql = 'SELECT SUBSTRING(e.review_id, 1, 5) AS code, {}, r.review_id AS r_id, e.review_id AS e_id FROM reviews AS r INNER JOIN reviews AS e where r.review_id = e.review_id  GROUP BY code, r_id, e_id LIMIT 20'
      # this line works for postgresql
      sql = 'SELECT SUBSTRING(e.review_id, 1, 5) AS code, {}, r.review_id AS r_id, e.review_id AS e_id FROM reviews r INNER JOIN reviews e on r.review_id = e.review_id  GROUP BY code, r_id, e_id LIMIT 20'
    else:
      sql = 'SELECT review_id, {}  FROM reviews LIMIT 1'
    return sql
  

def get_redis_client():
    return redis.Redis(
      host=os.getenv('REDIS_PRIMARY_HOST'), 
      port=os.getenv('REDIS_PRIMARY_PORT'), 
      db=0, 
      decode_responses=True,
      ssl=True,
      ssl_ca_certs=certifi.where(),
      username=os.getenv('REDIS_USERNAME'),
      password=os.getenv('REDIS_PASSWORD'),
    )


def get_redis_reader_client():
    return redis.Redis(
      host=os.getenv('REDIS_READER_HOST'), 
      port=os.getenv('REDIS_READER_PORT'), 
      db=0, 
      decode_responses=True,
      ssl=True,
      ssl_ca_certs=certifi.where(),
      username=os.getenv('REDIS_USERNAME'),
      password=os.getenv('REDIS_PASSWORD'),
    )


def loadDbData(TTL, complexity, variability, runs):
    global db_time, redis_time, redis_counter, db_counter, hits_counter, end_time_value, db
    clear_all_logs(redis_writer_con,'DBCACHE')
    sql = get_db_sql(db, complexity)
    # print(sql)
    for _ in range(runs):
        fetch(sql, TTL, variability, db)
    print_summary()
    return


if __name__ == "__main__":
    print(__name__)
#    app.run(host='0.0.0.0', port=80)
    app.run(host='0.0.0.0')

