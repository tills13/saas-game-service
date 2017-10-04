from os import environ
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), "..", ".env")
load_dotenv(dotenv_path)

PORT = int(environ.get("PORT", 3001))

DB_HOST = environ.get("DB_HOST")
DB_USER = environ.get("DB_USER")
DB_PASSWORD = environ.get("DB_PASSWORD")
DB_NAME = environ.get("DB_NAME")

REDIS_HOST = environ.get("REDIS_HOST")
REDIS_PASSWORD = environ.get("REDIS_PASSWORD")
REDIS_DATABASE = environ.get("REDIS_DATABASE")
