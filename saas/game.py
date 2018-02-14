import time
import requests
import json
import base64

from flask_socketio import join_room, leave_room
from queue import Empty, PriorityQueue
from requests.exceptions import HTTPError, ConnectionError as RequestsConnectionError
from saas import app, postgres, redis, socketio
from saas.queries import clone_game, get_child_games, get_game_prepared, get_game_snakes_prepared, set_game_status, set_snake_place
from saas.board import Board
from threading import Event, Thread
from .patch import get_move_request, get_start_request

class Game(Thread):
    MODE_AUTO = "MODE_AUTO"
    MODE_MANUAL = "MODE_MANUAL"

    STATUS_CREATED = "CREATED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_RESTARTED = "RESTARTED"
    STATUS_STARTED = "STARTED"
    STATUS_STOPPED = "STOPPED"

    SPAWN_STRATEGY_RANDOM = "RANDOM"
    SPAWN_STRATEGY_RANDOM = "RANDOM"
    SPAWN_STRATEGY_RANDOM = "RANDOM"

    WALL_SPAWN_RATE = 10 # in seconds

    def __init__(self, game_id, board=None, start_on_turn_number=0):
        Thread.__init__(self)

        self.action_queue = PriorityQueue()
        self.stop_game_event = Event()

        self.board = board
        self.game_daemon = None
        self.game = None
        self.game_id = game_id
        self.mode = Game.MODE_MANUAL
        self.turn_number = start_on_turn_number

        self._initialized_called = False

        self.sync_game()

        self.action_queue.put((1, self.initialize_game, {
            "override_board": board is None
        }))

    def apply_daemon_update(self, update):
        app.logger.info("daemon updated %s %s", self.game_id, json.dumps(update))

        if update is None: return

        if "$spawn" in update:
            for element in ["walls"]:
                self.board.walls.extend(update["$spawn"][element])

        if "$destroy" in update:
            pass

        if "message" in update:
            self.game_daemon["message"] = update["message"]

        return

    def check_bounty_conditions(self, snake):
        try:
            response = requests.post(
                "{}/bounty/check".format(snake["url"]),
                headers={ "Content-Type": "application/json" },
                timeout=self.game["responseTime"],
                json=self.board.to_json(api_version=snake["api_version"])
            )

            response.raise_for_status()
        except (RequestsConnectionError, HTTPError) as error:
            app.logger.info(
                "[%s] bouty error (%s): %s",
                self.game_id,
                snake["id"],
                error
            )

        return

    def disconnect(self):
        leave_room(self.game_id)

        current = int(redis.get("game:viewer_count:{}".format(self.game_id)))

        if current <= 1: redis.set("game:viewer_count:{}".format(self.game_id), 0)
        else: redis.decr("game:viewer_count:{}".format(self.game_id))

        socketio.emit("viewer_count", int(redis.get("game:viewer_count:{}".format(self.game_id))), room=self.game_id)

    def finish_game(self):
        snakes = self.board.get_snakes()

        with postgres.xact():
            set_game_status(Game.STATUS_COMPLETED, self.game_id)
            self.sync_game()

            sorted_snakes = sorted(
                [snake for snake_id, snake in snakes.items()],
                key=lambda snake: snake["score"]
            )

            for place, snake in enumerate(sorted_snakes):
                set_snake_place(place + 1, snake["id"], self.game_id)

        self.redirect_to_child()

    def get_and_apply_daemon_update(self):
        update = self.get_daemon_update()
        self.apply_daemon_update(update)

    def get_daemon_update(self):
        try:
            app.logger.info("[%s] daemon posting %s", self.game_id, self.game["daemon_url"])
            response = requests.post(
                self.game["daemon_url"],
                timeout=self.game["responseTime"],
                headers={ "Content-Type": "application/json" },
                json=self.board.to_json()
            )

            if response.status_code == 200:
                response_json = response.json()

                time_elapsed = response.elapsed.total_seconds()

                pipe = redis.pipeline()
                pipe.zincrby("daemon:response_time:{}".format(self.game["daemon_id"]), "count")
                pipe.zincrby("daemon:response_time:{}".format(self.game["daemon_id"]), "sum", time_elapsed)
                pipe.zincrby("daemon:response_time:{}".format(self.game["daemon_id"]), "sumsq", time_elapsed * time_elapsed)
                pipe.execute()

                return response_json
        except (ValueError, RequestsConnectionError, HTTPError) as error:
            app.logger.info(
                "[%s] daemon error (%s): %s",
                self.game_id,
                self.game["daemon_name"],
                error
            )

        return None

    def get_game_snakes(self):
        snakes_rows = get_game_snakes_prepared.rows(self.game_id)
        return { str(row["id"]): dict(row) for row in snakes_rows }

    def get_snake_next_move(self, snake):
        app.logger.info("[%s] get_snake_next_move (%s)", self.game_id, snake["name"])

        try:
            snake_url = snake["devUrl"] if self.game["devMode"] and snake["devUrl"] else snake["url"]
            # app.logger.info(get_move_request(self.board, self, snake))
            response = requests.post(
                "{}/move".format(snake_url),
                timeout=self.game["responseTime"],
                headers={ "Content-Type": "application/json" },
                json=get_move_request(self.board, self, snake)
            )

            if response.status_code == 200:
                response_json = response.json()

                if snake["api_version"] == "2017":
                    snake["taunt"] = response_json["taunt"]

                snake["next_move"] = response_json.get("move", snake.get("nextMove", "up"))
        except (ValueError, RequestsConnectionError, HTTPError) as error:
            app.logger.info("[%s] init error (%s): %s", self.game_id, snake["name"], error)

        return snake

    def initialize_game(self, override_board=True):
        self.sync_game()

        if self.game["status"] == Game.STATUS_COMPLETED:
            return

        if override_board:
            board_configuration = None
            if self.game["board_configuration"] is not None:
                try: board_configuration = json.loads(self.game["board_configuration"])
                except (TypeError, ValueError) as error:
                    app.logger.error(
                        "[%s] invalid board configuration: %s",
                        self.game_id,
                        self.game["board_configuration"]
                    )

                    board_configuration = None

            snakes = self.get_game_snakes()

            if not board_configuration:
                self.board = Board(
                    snakes,
                    width=self.game["boardColumns"],
                    height=self.game["boardRows"]
                )

                self.board.clear()
                self.board.spawn_random_food(self.game["boardFoodCount"])

                if self.game["boardHasGold"]:
                    self.board.spawn_random_gold(self.game["boardGoldCount"])

                if self.game["boardHasTeleporters"]:
                    self.board.spawn_random_teleporters(self.game["boardTeleporterCount"])
            else:
                self.board = Board(snakes, configuration=board_configuration)
                self.board.spawn_random_food(self.game["boardFoodCount"] - self.board.get_food_count())

                if self.game["boardHasGold"]:
                    self.board.spawn_random_gold(self.game["boardGoldCount"] - self.board.get_gold_count())

                if self.game["boardHasTeleporters"]:
                    self.board.spawn_random_teleporters(self.game["boardTeleporterCount"] - self.board.get_teleporter_count())

        snakes = self.board.get_snakes()

        app.logger.info(
            "[%s] %d snakes [%s]",
            self.game_id,
            self.board.get_snake_count(),
            ",".join([snake["name"] for snake_id, snake in snakes.items()])
        )

        for snake_id, snake in snakes.items():
            snake = self.initialize_snake(snake)

        self.board.update(self, snakes, tick_snakes=False)
        self.update_clients()

        self._initialized_called = True

    def initialize_snake(self, snake):
        try:
            snake_url = snake["devUrl"] if self.game["devMode"] and snake["devUrl"] else snake["url"]
            response = requests.post(
                "{}/start".format(snake_url),
                headers={ "Content-Type": "application/json" },
                timeout=(self.game["responseTime"] * 2),
                json=get_start_request(self, snake["api_version"])
            )

            if response.status_code == 200:
                response_json = response.json()
                snake["taunt"] = response_json["taunt"]
                # snake["color"] = response_json["color"]
                # snake["secondary_color"] = response_json["color"]

                if snake["api_version"] == "2018":
                    snake["name"] = response_json["name"]
        except (ValueError, RequestsConnectionError, HTTPError) as error:
            app.logger.info("[%s] init error (%s): %s", self.game_id, snake["name"], error)

        return snake

    def pause_game(self):
        set_game_status(Game.STATUS_STOPPED, self.game_id)
        self.sync_game()

    def play_game(self):
        if self.game["status"] == Game.STATUS_IN_PROGRESS:
            self.mode = Game.MODE_AUTO
            return

        set_game_status(Game.STATUS_IN_PROGRESS, self.game_id)
        self.sync_game()
        self.step_game()

    def redirect_to_child(self):
        app.logger.info("%s complete, redirecting to child game", self.game_id)
        child_game = get_child_games.first(self.game_id)

        if child_game:
            m_child_game = dict(child_game)
            m_child_game["realId"] = m_child_game["id"]
            m_child_game["id"] = base64.b64encode(bytes("Game:{}".format(m_child_game["realId"]), "utf-8")).decode("utf-8")
            socketio.emit("redirect", m_child_game, room=self.game_id, broadcast=False)
        else:
            new_game = dict(clone_game(self.game_id))
            new_game["realId"] = new_game["id"]
            new_game["id"] = base64.b64encode(bytes("Game:{}".format(new_game["realId"]), "utf-8")).decode("utf-8")
            socketio.emit("redirect", new_game, room=self.game_id, broadcast=False)

        return

    def restart_game(self):
        app.logger.info("restarting game %s", self.game_id)
        set_game_status(Game.STATUS_RESTARTED, self.game_id)
        self.sync_game()
        self.initialize_game()

    def run(self):
        app.logger.info("thread starting")
        self.stop_game_event.clear()

        # try: tick_rate = int(self.game["tickRate"])
        # except ValueError: tick_rate = None

        # if tick_rate is None: tick_rate = 1000

        last_command = time.time()
        while not self.stop_game_event.isSet():
            try:
                priority, action, args = self.action_queue.get(True, 0.05)
                app.logger.info("processing %s (priority: %d)", action.__name__, priority)

                action(**args)

                last_command = time.time()
            except Empty:
                pass

            time_since_last_command = time.time() - last_command

            if time_since_last_command > 5:
                self.stop_game_event.set()

        app.logger.info("thread exiting")

    def start_game(self, mode=MODE_MANUAL):
        app.logger.info("starting game with mode: %s", mode)
        self.step_game()

    def step_game(self, allow_stepping = False):
        snakes = self.board.get_snakes()

        if self.game["status"] != Game.STATUS_IN_PROGRESS:
            set_game_status(Game.STATUS_IN_PROGRESS, self.game_id)
            self.sync_game()

        bounty_snakes = {
            snake_id: snake for snake_id, snake in snakes.items()
            if snake["isBountySnake"]
        }

        if self.game["daemon_id"] is not None:
            self.get_and_apply_daemon_update()

        for snake_id, bounty_snake in bounty_snakes.items():
            bounty = self.check_bounty_conditions(bounty_snake)

        for snake_id, snake in snakes.items():
            snake = self.get_snake_next_move(snake)

        self.board.update(self, snakes, tick_snakes=True)

        # top up the food
        if self.board.get_food_count() < self.game["boardFoodCount"]:
            spawn_count = self.game["boardFoodCount"] - self.board.get_food_count()
            if self.game["boardFoodStrategy"] == Game.SPAWN_STRATEGY_RANDOM: self.board.spawn_random_food(count=spawn_count)
            else: pass

        if self.game["boardHasGold"] and self.board.get_gold_count() < self.game["boardGoldCount"]:
            if self.board.last_gold_spawn and time.time() - self.board.last_gold_spawn >= (self.game["boardGoldRespawnInterval"]):
                if self.game["boardGoldStrategy"] == Game.SPAWN_STRATEGY_RANDOM: self.board.spawn_random_gold(count=1)
                else: pass

        if self.game["boardHasWalls"] and self.board.get_wall_count() / (self.board.width * self.board.height) < 0.10:
            if self.board.last_wall_spawn and time.time() - self.board.last_wall_spawn >= Game.WALL_SPAWN_RATE * 1000:
                self.board.spawn_random_walls(count=1)

        self.turn_number = self.turn_number + 1
        self.update_clients()

        # allow the game to continue until there are no snakes alive for testing purposes
        if self.win_conditions_met():
            self.finish_game()
        elif allow_stepping and self.mode == Game.MODE_AUTO and self.game["status"] == Game.STATUS_IN_PROGRESS:
            time.sleep(self.game["tickRate"] / 1000)
            self.action_queue.put((1, self.step_game, { "allow_stepping": allow_stepping }))

    def sync_game(self, and_daemon=True):
        app.logger.info("fetching game %s from db", self.game_id)
        self.game = get_game_prepared.first(self.game_id)

        if not self.game:
            raise Exception("game {} not found".format(self.game_id))

        if and_daemon and self.game:
            self.game_daemon = {
                "id": self.game["daemon_id"],
                "name": self.game["daemon_name"],
                "url": self.game["daemon_url"]
            } if self.game["daemon_id"] else None

    def update_clients(self, errors=None, broadcast=True):
        if self.board is not None:
            data = {
                "board": self.board.to_json(api_version="client"),
                "daemon": self.game_daemon,
                "errors": errors,
                "turn": self.turn_number,
                "turnLimit": self.game["turnLimit"]
            }

            socketio.emit("update", data, room=self.game_id, broadcast=broadcast)

    def watch(self):
        join_room(self.game_id)

        if self.game and self.game["status"] == Game.STATUS_COMPLETED:
            self.redirect_to_child()
            return

        redis.incr("game:viewer_count:{}".format(self.game_id))

        socketio.emit("viewer_count", int(redis.get("game:viewer_count:{}".format(self.game_id))), room=self.game_id)
        self.update_clients(broadcast=False)

    def win_conditions_met(self):
        snakes = self.board.get_snakes()

        if self.game["turnLimit"] != 0 and self.turn_number >= self.game["turnLimit"]:
            return True

        if not [snake for snake_id, snake in snakes.items() if snake["health"] > 0]:
            return True

        if [snake for snake_id, snake in snakes.items() if snake["gold_count"] >= self.game["boardGoldWinningThreshold"]]:
            return True

        return False
