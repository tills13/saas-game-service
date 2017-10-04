import logging
import postgresql
import redis

from saas import settings
from flask import Flask
from flask_socketio import SocketIO

app = Flask(__name__)
socketio = SocketIO(app)

postgres = postgresql.open(user=settings.DB_USER, host=settings.DB_HOST, password=settings.DB_PASSWORD, database=settings.DB_NAME)
redis = redis.StrictRedis(host=settings.REDIS_HOST, password=settings.REDIS_PASSWORD, db=settings.REDIS_DATABASE)

from saas import manager

manager = manager.Manager()

from saas import routes
