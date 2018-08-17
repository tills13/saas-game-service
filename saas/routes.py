import json
from saas import socketio, app, manager
from flask_socketio import emit, rooms
from flask import render_template, request, jsonify

@app.route("/")
def index():
    return json.dumps([game.id for id, game in manager.get_games().items()])

@app.route("/start/<string:game_id>")
def start(game_id):
    manager.start_game(game_id)
    return json.dumps([id for id, game in manager.get_games().items()])

@app.route("/board/<string:game_id>")
def board(game_id):
    game, created = manager.find_or_create_game(game_id)
    return jsonify(game.to_json())

@app.route("/step/<string:game_id>")
def step(game_id):
    game, created = manager.find_or_create_game(game_id)
    game.step_game(allow_stepping=False)
    # print(game.board.to_json())

    return ""

@socketio.on("connect")
def on_connect():
    app.logger.info("client %s connected", request.sid)

@socketio.on("disconnect")
def on_disconnect():
    client_rooms = [ room for room in rooms() if room != request.sid ]
    app.logger.info("client %s disconnected, leaving %s", request.sid, ",".join(client_rooms))

    if client_rooms:
        game_id = client_rooms[0]
        game = manager.find_game(game_id)
        game.disconnect()

@socketio.on("watch")
def watch_game(game_id):
    app.logger.info("client %s joined %s",request.sid, game_id)
    game, created = manager.find_or_create_game(game_id)
    manager.watch_game(game)

    emit("message", "watching {}".format(game.game_id), broadcast=False)
    if created: game.start()

@socketio.on("keyboard_event")
def handle_keyboard_event(event):
    app.logger.info("keyboard event: %s", event)
    client_rooms = [ room for room in rooms() if room != request.sid ]

    if client_rooms:
        game_id = client_rooms[0]
        app.logger.info("keyboard event -> %s", game_id)
        key = event["key"]

        if key == "q": manager.restart_game(game_id)
        elif key == "d": manager.step_game(game_id)
        elif key == "w": manager.start_game(game_id)
        elif key == "s": manager.pause_game(game_id)
        elif key == "e": manager.toggle_game_mode(game_id)
        else:
            emit("error", "unknown keyboard_event: {}".format(event), broadcast=False)
            return

        app.logger.info("processed keyboard event %s -> %s", event, game_id)
        emit("message", "handled keyboard_event: {}".format(event), broadcast=False)

#@socketio.on_error()
def on_error(e):
    app.logger.error(e)
