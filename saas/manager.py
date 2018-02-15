from saas.game import Game
from saas import redis

class Manager(object):
    def __init__(self, maximum_concurrent_games = 5):
        self.maximum_concurrent_games = maximum_concurrent_games
        self.games = {}

    def create_game(self, game_id, board=None, start_on_turn_number=0):
        if game_id in self.games:
            raise Exception("game {} already created".format(game_id))

        game = Game(game_id, board=board, start_on_turn_number=start_on_turn_number)
        self.games[game_id] = game

        self._reset_game_viewer_count(game_id)

        return game

    def find_game(self, game_id):
        return None if game_id not in self.games else self.games[game_id]

    def find_or_create_game(self, game_id):
        created = False
        game = self.find_game(game_id)

        if not game:
            game = self.create_game(game_id)
            created = True

        return game, created

    def get_games(self):
        return self.games

    def pause_game(self, game_id):
        game = self.find_game(game_id)

        if not game or game.stop_game_event.isSet():
            if game: del self.games[game_id]

            game = self.create_game(game_id)
            game.start()
        else:
            game.action_queue.put((1, game.pause_game, {}))

    def restart_game(self, game_id):
        game = self.find_game(game_id)

        if not game or game.stop_game_event.isSet():
            if game: del self.games[game_id]

            game = self.create_game(game_id)
            game.start()
        else:
            game.action_queue.put((1, game.restart_game, {}))

    def _reset_game_viewer_count(self, game_id):
        redis.set("game:viewer_count:{}".format(game_id), 0)

    def start_game(self, game_id):
        game = self.find_game(game_id)

        if not game or game.stop_game_event.isSet():
            if game: del self.games[game_id]

            game = self.create_game(game_id)
            game.start()
        else:
            game.action_queue.put((1, game.start_game, {}))

    def step_game(self, game_id):
        game = self.find_game(game_id)

        if not game or game.stop_game_event.isSet():
            previous_board = None

            if game:
                previous_board = game.board
                del self.games[game_id]

            game = self.create_game(game_id, board=previous_board, start_on_turn_number=game.turn_number)
            game.start()

        game.action_queue.put((1, game.step_game, {}))

    def toggle_game_mode(self, game_id):
        game = self.find_game(game_id)

        if not game or game.stop_game_event.isSet():
            if game: del self.games[game_id]

            game = self.create_game(game_id)
            game.start()

        if game.mode == Game.MODE_AUTO:
            game.mode = Game.MODE_MANUAL
            # game.action_queue
        else:
            game.mode = Game.MODE_AUTO
            game.action_queue.put((1, game.step_game, { "allow_stepping": game.mode != Game.MODE_MANUAL }))

    def watch_game(self, game):
        game.watch()

        current_viewer_count = redis.get("game:viewer_count:{}".format(game.game_id))
        max_viewer_count = redis.get("game:max_viewer_count:{}".format(game.game_id))

        current_viewer_count = int(current_viewer_count) if current_viewer_count else 0
        max_viewer_count = int(max_viewer_count) if max_viewer_count else 0

        redis.set(
            "game:max_viewer_count:{}".format(game.game_id),
            max(max_viewer_count, current_viewer_count)
        )
