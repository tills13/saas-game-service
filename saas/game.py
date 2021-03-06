import time
import requests
import json
import base64

from flask_socketio import join_room, leave_room
from queue import Empty, PriorityQueue
from requests.exceptions import HTTPError, ConnectionError as RequestsConnectionError
from threading import Event, Thread

from . import app, postgres, redis, socketio
from . import models
from .queries import clone_game, get_child_games, get_game_prepared, get_game_snakes_prepared, set_game_status, set_snake_place
from .board import Board
from .patch import get_move_request, get_start_request


class Game(Thread):
    api_version = "client"

    MODE_AUTO = "MODE_AUTO"
    MODE_MANUAL = "MODE_MANUAL"

    STATUS_CREATED = "CREATED"
    STATUS_COMPLETED = "COMPLETED"
    STATUS_IN_PROGRESS = "IN_PROGRESS"
    STATUS_RESTARTED = "RESTARTED"
    STATUS_STARTED = "STARTED"
    STATUS_STOPPED = "STOPPED"

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
        self.history = []

        self._initialized_called = False

        self.sync_game()

        self.action_queue.put((1, self.initialize_game, {
            "override_board": board is None
        }))

    def apply_daemon_update(self, update):
        app.logger.info("daemon updated %s %s", self.game_id, json.dumps(update))

        if update is None: return

        for wall in update["$spawn"]["walls"]:
            self.board.spawn_wall(wall["x"], wall["y"])

        if "$destroy" in update:
            pass

        if "message" in update:
            self.game_daemon["message"] = update["message"]

        return

    def check_bounty_conditions(self, snake):
        try:
            response = requests.post(
                "{}/bounty/check".format(snake.url),
                headers={ "Content-Type": "application/json" },
                timeout=self.game["responseTime"],
                json=self.board.to_json(api_version=snake.api_version)
            )

            response.raise_for_status()
        except (RequestsConnectionError, HTTPError) as error:
            app.logger.info(
                "[%s] bouty error (%s): %s",
                self.game_id,
                snake.id,
                error
            )

        return

    def disconnect(self):
        leave_room(self.game_id)

        current = int(redis.get("game:viewer_count:{}".format(self.game_id)))

        if current <= 1: redis.set("game:viewer_count:{}".format(self.game_id), 0)
        else: redis.decr("game:viewer_count:{}".format(self.game_id))

        self.update_clients()

    def finish_game(self):
        snakes = self.board.get_snakes()

        with postgres.xact():
            set_game_status(Game.STATUS_COMPLETED, self.game_id)
            self.sync_game()

            if self.game["gameType"] == "TYPE_SCORE":
                sorted_snakes = sorted(
                    [snake for snake_id, snake in snakes.items()],
                    key=lambda snake: snake.score
                )
            elif self.game["gameType"] == "TYPE_PLACEMENT":
                sorted_snakes = reversed(sorted(
                    [snake for snake_id, snake in snakes.items()],
                    # cmp=lambda a, b:
                    key=lambda snake: 0 if not snake.death else snake.death["turn"]
                ))

            for place, snake in enumerate(sorted_snakes):
                set_snake_place(place + 1, snake.id, self.game_id)

        for snake in snakes.items():
            try:
                response = requests.post(
                    f"{snake.get_url(dev_mode=self.game['devMode'])}/end",
                    headers={ "Content-Type": "application/json" },
                    timeout=self.game["responseTime"],
                    json={ "winner_id": sorted_snakes[0].id, "you": snake.id }
                )
            except (RequestsConnectionError, HTTPError) as error:
                app.logger.info(
                    "[%s] /end (%s): %s",
                    self.game_id,
                    snake.id,
                    error
                )

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
                json=self.to_json()
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
        snakes = get_game_snakes_prepared.rows(self.game_id)
        return { str(snake_data["id"]): models.Snake(snake_data) for snake_data in snakes }

    def get_snake_next_move(self, snake):
        app.logger.info("[%s] get_snake_next_move (%s)", self.game_id, snake.name)
        error = None

        try:
            snake_url = snake.get_url(self.game["devMode"])

            response = requests.post(
                "{}/move".format(snake_url),
                timeout=self.game["responseTime"],
                headers={ "Content-Type": "application/json" },
                json=get_move_request(self.board, self, snake)
            )

            if response.status_code == 200:
                response_json = response.json()
                snake.handle_move_response(response_json)
        except (ValueError, RequestsConnectionError, HTTPError) as m_error:
            app.logger.info("[%s] get_snake_next_move error (%s): %s", self.game_id, snake.name, m_error)
            snake.error = m_error
            error = m_error

        return snake, error

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

        self.history = []
        snakes = self.board.get_snakes()

        if not snakes:
            app.logger.error("[%s] no snakes in game", self.game_id)
            return

        app.logger.info(
            "[%s] %d snakes [%s]",
            self.game_id,
            self.board.get_snake_count(),
            ",".join([snake.name for snake_id, snake in snakes.items()])
        )

        for snake_id, snake in snakes.items():
            snake = self.initialize_snake(snake)

        self.board.update(self, snakes, tick_snakes=False)
        self.update_clients()

        self._initialized_called = True

    def initialize_snake(self, snake):
        try:
            snake_url = snake.get_url(self.game["devMode"])
            response = requests.post(
                "{}/start".format(snake_url),
                headers={ "Content-Type": "application/json" },
                timeout=(self.game["responseTime"] * 2),
                json=get_start_request(self, api_version=snake.api_version)
            )

            if response.status_code == 200:
                response_json = response.json()
                snake.handle_start_response(response_json)
        except (ValueError, RequestsConnectionError, HTTPError) as error:
            app.logger.info("[%s] init error (%s): %s", self.game_id, snake.name, error)

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
        self.turn_number = 0
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
        self.history.append(self.board.to_json(api_version=Game.api_version))
        self.step_game()

    def step_game(self, allow_stepping = False):
        snakes = self.board.get_snakes()
        errors = { }

        if self.game["status"] != Game.STATUS_IN_PROGRESS:
            set_game_status(Game.STATUS_IN_PROGRESS, self.game_id)
            self.sync_game()

        bounty_snakes = {
            snake_id: snake for snake_id, snake in snakes.items()
            if snake.is_bounty_snake
        }

        if self.game["daemon_id"] is not None:
            self.get_and_apply_daemon_update()

        for snake_id, bounty_snake in bounty_snakes.items():
            bounty = self.check_bounty_conditions(bounty_snake)

        for snake_id, snake in snakes.items():
            snake, error = self.get_snake_next_move(snake)

            if error: errors[snake.id] = error.message

        self.board.update(self, snakes, tick_snakes=True)

        # top up the food
        if self.board.get_food_count() < self.game["boardFoodCount"]:
            spawn_count = self.game["boardFoodCount"] - self.board.get_food_count()
            self.board.spawn_food_by_strat(self.game["boardFoodStrategy"])

        if self.game["boardHasGold"] and self.board.get_gold_count() < self.game["boardGoldCount"]:
            if self.board.last_gold_spawn and time.time() - self.board.last_gold_spawn >= (self.game["boardGoldRespawnInterval"]):
                pass
                # if self.game["boardGoldStrategy"] == Game.SPAWN_STRATEGY_RANDOM: self.board.spawn_random_gold(count=1)
                # else: pass

        if self.game["boardHasWalls"] and self.board.get_wall_count() / (self.board.width * self.board.height) < 0.10:
            if self.board.last_wall_spawn and time.time() - self.board.last_wall_spawn >= Game.WALL_SPAWN_RATE * 1000:
                self.board.spawn_random_walls(count=1)

        self.turn_number = self.turn_number + 1
        self.update_clients(errors=errors)

        self.history.append(self.board.to_json(api_version=Game.api_version))

        # allow the game to continue until there are no snakes alive for testing purposes
        if self.win_conditions_met():
            self.finish_game()
        elif allow_stepping and self.mode == Game.MODE_AUTO and self.game["status"] == Game.STATUS_IN_PROGRESS:
            time.sleep(self.game["tickRate"] / 1000)
            self.action_queue.put((1, self.step_game, { "allow_stepping": allow_stepping }))

    def sync_game(self, and_daemon=True):
        app.logger.info("fetching game %s from db", self.game_id)

        self.game = get_game_prepared.first(self.game_id)
        # self.history = self.game["history"]

        if not self.game:
            raise Exception("game {} not found".format(self.game_id))

        if and_daemon and self.game:
            self.game_daemon = {
                "id": self.game["daemon_id"],
                "name": self.game["daemon_name"],
                "url": self.game["daemon_url"]
            } if self.game["daemon_id"] else None

    def update_clients(self, errors=None, broadcast=True):
        data = self.to_json(errors)
        socketio.emit("update", data, room=self.game_id, broadcast=broadcast)

    def watch(self):
        join_room(self.game_id)

        if self.game and self.game["status"] == Game.STATUS_COMPLETED:
            self.redirect_to_child()
            return

        redis.incr("game:viewer_count:{}".format(self.game_id))

        self.update_clients(broadcast=False)

    def win_conditions_met(self):
        snakes = self.board.get_snakes()

        if self.game["turnLimit"] != 0 and self.turn_number >= self.game["turnLimit"]:
            return True

        if not [snake for snake_id, snake in snakes.items() if snake.is_alive]:
            return True

        if [snake for snake_id, snake in snakes.items() if snake.gold >= self.game["boardGoldWinningThreshold"]]:
            return True

        return False

    def to_json(self, errors=None):
        data = { }

        if self.board is not None:
            data = {
                "id": self.game["id"],
                "board": self.board.to_json(api_version=Game.api_version),
                "daemon": self.game_daemon,
                "errors": errors,
                "turnNumber": self.turn_number,
                "viewers": int(redis.get("game:viewer_count:{}".format(self.game_id)))
            }

        return data
