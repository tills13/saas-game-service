import random
import math
import time

from typing import Any, Dict, List

from .patch import get_coordinate, get_snake, wrap_list
from .constants import SPAWN_STRATEGY_RANDOM, SPAWN_STRATEGY_STATIC, SPAWN_STRATEGY_DONT_RESPAWN
from .types import Position, PositionList

BoardPosition = Dict[str, int]
Food = BoardPosition
Gold = BoardPosition
Wall = BoardPosition
Teleporter = BoardPosition

class Board:
    DEFAULT_DIMENSIONS = 20
    BOARD_TYPE_EMPTY = -1
    BOARD_TYPE_FOOD = 0
    BOARD_TYPE_GOLD = 1
    BOARD_TYPE_SNAKE = 2
    BOARD_TYPE_TELEPORTER = 3
    BOARD_TYPE_WALL = 4

    MOVE_UP = "up"
    MOVE_DOWN = "down"
    MOVE_LEFT = "left"
    MOVE_RIGHT = "right"


    def __init__(self, snakes, width: int = 20, height: int = 20, configuration=None):
        self.snakes = snakes
        self.configuration = configuration

        if self.configuration:
            self.width = self.configuration["boardColumns"]
            self.height = self.configuration["boardRows"]

            self.food = self.configuration["food"]
            self.gold = self.configuration["gold"]
            self.teleporters = self.configuration["teleporters"]
            self.walls = self.configuration["walls"]
        else:
            self.width = width
            self.height = height

            self.food = []
            self.gold = []
            self.teleporters = []
            self.walls = []

        self.last_wall_spawn = None
        self.last_gold_spawn = None
        self.initialize_snakes()

    def clear(self):
        self.food = []
        self.gold = []
        self.teleporters = []
        self.walls = []

        self.initialize_snakes()

    def get_at_position(self, x: int, y: int, exclude: List[Any] = None):
        for snake_id, snake in self.snakes.items():
            if exclude and snake in exclude: continue
            for body_segment in snake.body:
                if body_segment["x"] == x and body_segment["y"] == y:
                    return Board.BOARD_TYPE_SNAKE, snake

        for food in self.food:
            if exclude and food in exclude: continue
            if food["x"] == x and food["y"] == y:
                return Board.BOARD_TYPE_FOOD, food

        for gold in self.gold:
            if exclude and gold in exclude: continue
            if gold["x"] == x and gold["y"] == y:
                return Board.BOARD_TYPE_GOLD, gold

        for wall in self.walls:
            if exclude and wall in exclude: continue
            if wall["x"] == x and wall["y"] == y:
                return Board.BOARD_TYPE_WALL, wall

        for teleporter in self.teleporters:
            if exclude and teleporter in exclude: continue
            if teleporter["x"] == x and teleporter["y"] == y:
                return Board.BOARD_TYPE_TELEPORTER, teleporter

        return Board.BOARD_TYPE_EMPTY, None

    def get_neighbors(self, position: BoardPosition):
        neighbors = [
            [position["x"] + dx, position["y"] + dy]
            for [ dx, dy ] in
            [ [0, 1], [1, 0], [-1, 0], [0, -1] ]
        ]

        # filter neighbors that are outside the board
        return [
            [x, y] for [x, y] in neighbors
            if x >= 0 and \
                y >= 0 and \
                x < self.width and \
                y < self.width
        ]

    def get_random_empty_position(self, positions: PositionList = None, exclude: PositionList = None) -> Position:
        if positions is not None:
            for position in random.shuffle(positions):
                value, thing = self.get_at_position(position["x"], position["y"])
                if value == Board.BOARD_TYPE_EMPTY: return position["x"], position["y"]

        x = random.randint(0, self.width - 1)
        y = random.randint(0, self.height - 1)

        while self.get_at_position(x, y)[0] != Board.BOARD_TYPE_EMPTY:
            x = random.randint(0, self.width - 1)
            y = random.randint(0, self.height - 1)

        return x, y

    def get_food(self):
        return self.food

    def get_food_count(self) -> int:
        return len(self.food)

    def get_gold(self):
        return self.gold

    def get_gold_count(self) -> int:
        return len(self.gold)

    def get_snakes(self):
        return self.snakes

    def get_snake_count(self) -> int:
        return len(self.snakes.keys())

    def get_teleporters(self):
        return self.teleporters

    def get_teleporter_count(self) -> int:
        return len(self.teleporters)

    def get_walls(self):
        return self.walls

    def get_wall_count(self) -> int:
        return len(self.walls)

    def initialize_snakes(self, snake_start_length=3):
        for index, (snake_id, snake) in enumerate(self.snakes.items()):
            snake.reset()

            if self.configuration:
                m_snake = None
                if snake_id in [snake["id"] for snake in self.configuration["snakes"]]:
                    m_snake = [snake for snake in self.configuration["snakes"] if snake_id == snake["id"]][0]
                elif index in [snake["number"] for snake in self.configuration["snakes"]]:
                    m_snake = [snake for snake in self.configuration["snakes"] if index == snake["number"]][0]

                if m_snake and "coords" in m_snake:
                    snake.body = [coord for coord in m_snake["coords"]]
                    continue

            # default to random placement
            for _ in range(0, snake_start_length):
                if not snake.body: x, y = self.get_random_empty_position()
                else:
                    neighbors = [
                        n for n in
                        self.get_neighbors(position=snake.body[-1])
                        if n not in [ [p["x"], p["y"]] for p in snake.body ]
                    ]

                    if not neighbors: break

                    x, y = random.choice(neighbors)

                snake.body.append({ "x": x, "y": y, "color": snake.color })

    def spawn_food_by_strat(self, strat: str):
        if strat == SPAWN_STRATEGY_RANDOM:
            return self.spawn_random_food()
        elif strat == SPAWN_STRATEGY_STATIC:
            hidden_food = [food for food in self.food if food["hidden"] == True]
            if hidden_food and len(hidden_food) > 0:
                food = random.choice(hidden_food)
                return self.spawn_food(food["x"], food["y"])

    def spawn_random_food(self, count = 1):
        for index in range(0, count):
            x, y = self.get_random_empty_position(
                positions=self.configuration["food"] if self.configuration else None
            )

            self.spawn_food(x, y)

    def spawn_food(self, x, y):
        m_type, thing = self.get_at_position(x, y)

        if thing and m_type == Board.BOARD_TYPE_FOOD:
            m_thing = thing.copy()
            m_thing["hidden"] = False

            self.food.insert(self.food.index(thing), m_thing)
            return
        elif thing:
            return

        self.food.append({ "x": x, "y": y })

    def spawn_random_gold(self, count = 1):
        for index in range(0, count):
            x, y = self.get_random_empty_position(
                positions=self.configuration["gold"] if self.configuration else None
            )

            self.spawn_gold(x, y)

    def spawn_gold(self, x, y):
        self.gold.append({ "x": x, "y": y })
        self.last_gold_spawn = time.time()

    def spawn_random_teleporters(self, count = 1):
        for index in range(0, (count * 2)):
            x, y = self.get_random_empty_position(
                positions=self.configuration["teleporters"] if self.configuration else None
            )

            self.spawn_teleporter(x, y, math.ceil(count / 2))

    def spawn_teleporter(self, x, y, channel):
        self.teleporters.append({ "x": x, "y": y, "channel": channel })

    def spawn_random_walls(self, count = 1):
        for index in range(0, (count * 2)):
            x, y = self.get_random_empty_position(
                positions=self.configuration["walls"] if self.configuration else None
            )

            self.spawn_wall(x, y)

    def spawn_wall(self, x: int, y: int):
        self.walls.append({ "x": x, "y": y })
        self.last_wall_spawn = time.time()

    def update(self, game, snakes, tick_snakes = True):
        self.snakes = snakes

        if tick_snakes:
            # update all positions and health
            for snake_id, snake in self.snakes.items():
                current_head_position = snake.head
                next_position_vector = {
                    Board.MOVE_UP: [0, -1],
                    Board.MOVE_DOWN: [0, 1],
                    Board.MOVE_LEFT: [-1, 0],
                    Board.MOVE_RIGHT: [1, 0]
                }[snake.next_move]

                snake.body.appendleft({
                    "x": snake.head["x"] + next_position_vector[0],
                    "y": snake.head["y"] + next_position_vector[1],
                    "color": snake.head.get("color", snake.color)
                })

            for snake_id, snake in self.snakes.items():
                # reset head
                current_head_position = snake.head
                head_x = current_head_position["x"]
                head_y = current_head_position["y"]

                if head_x < 0 or head_x >= self.width or head_y < 0 or head_y >= self.height:
                    snake.kill(game.turn_number, "oob")
                    continue

                value, thing = self.get_at_position(head_x, head_y, [snake])

                if value == Board.BOARD_TYPE_FOOD:
                    snake.health = 100
                    self.food.remove(thing)
                elif value == Board.BOARD_TYPE_GOLD:
                    snake.score = snake.score + 5 # todo custom gold values?
                    snake.incr_gold()

                    self.gold.remove(thing)
                elif value == Board.BOARD_TYPE_WALL:
                    snake.kill(game.turn_number, "wall")
                elif value == Board.BOARD_TYPE_TELEPORTER:
                    channel = thing["channel"]
                    channel_teleporters = [
                        teleporter for teleporter in self.teleporters
                        if teleporter["channel"] == channel and (
                            teleporter["x"] != thing["x"] or
                            teleporter["y"] != thing["y"]
                        )
                    ]

                    if channel_teleporters:
                        teleporter = random.choice(channel_teleporters)
                        snake.body.popleft() # remove current head
                        snake.body.appendleft({
                            "x": teleporter["x"],
                            "y": teleporter["y"],
                            "color": current_head_position["color"]
                        })
                elif value == Board.BOARD_TYPE_SNAKE:
                    snake_head = thing.head

                    if snake_head["x"] == head_x and snake_head["y"] == head_y:
                        # head to head collision
                        if snake.length > thing.length:
                            # handle the other snake's death in their loop iteration
                            snake.score = snake.score + 1
                        else:
                            snake.kill(game.turn_number, "killed", thing.id)
                            thing.incr_kills()
                    else:
                        snake.kill(game.turn_number, "collision", thing.id)
                else:
                    snake.score = snake.score + 0.1
                    if not game.game["pinTail"]: snake.body.pop()

    def to_json(self, api_version: str = None):
        if api_version == "2018": snakes = [ snake for snake_id, snake in self.snakes.items() ]
        else: snakes = [ snake for snake_id, snake in self.snakes.items() if snake.is_alive ]

        dead_snakes = [ snake for snake_id, snake in self.snakes.items() if not snake.is_alive ]
        food = [ get_coordinate(food, api_version) for food in self.food if not food.get("hidden", False) ]

        board_json = {
            "food": wrap_list(food, api_version),
            "height": self.height,
            "snakes": wrap_list([ get_snake(snake, api_version) for snake in snakes ], api_version),
            "width": self.width
        }

        if api_version == "2016":
            board_json["walls"] = [ get_coordinate(coord, api_version) for coord in self.walls ]

            return board_json
        if api_version == "2017":
            board_json["dead_snakes"] = wrap_list([ get_snake(snake, api_version) for snake in dead_snakes ], api_version)
            board_json["gold"] = wrap_list([ get_coordinate(coord, api_version) for coord in self.gold ], api_version)

            return board_json
        elif api_version == "2018":
            return board_json

        board_json["deadSnakes"] = [ get_snake(snake, api_version) for snake in dead_snakes ]
        board_json["teleporters"] = self.teleporters
        board_json["walls"] = [ get_coordinate(coord, api_version) for coord in self.walls ]

        return board_json

    def to_string(self):
        board_string = "|" + " - " * self.width + "|\n"

        for x in range(0, self.width):
            board_string = board_string + "|"

            for y in range(0, self.height):
                value, thing = self.get_at_position(x, y)
                if value == Board.BOARD_TYPE_EMPTY: char = " "
                elif value == Board.BOARD_TYPE_FOOD: char = "O"
                elif value == Board.BOARD_TYPE_GOLD: char = "X"
                elif value == Board.BOARD_TYPE_SNAKE:
                    print(thing.head)
                    if [x, y] == [thing.head["x"], thing.head["y"]]: char = "*"
                    else: char = "="
                elif value == Board.BOARD_TYPE_WALL: char = "¤"

                board_string = board_string + f" {char} "

            board_string = board_string + "|\n"

        board_string = board_string + "|" + " - " * self.width + "|"

        return board_string
