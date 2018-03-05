# from saas import app, settings, socketio
from gevent import monkey
monkey.patch_all()

import saas

if __name__ == "__main__":
    saas.socketio.run(saas.app, debug=True, host='0.0.0.0', port=saas.settings.PORT)
