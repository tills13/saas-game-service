from saas import app, settings, socketio
from gevent import monkey

monkey.patch_all()

if __name__ == "__main__":
    socketio.run(app, debug=True, host='0.0.0.0', port=settings.PORT)
