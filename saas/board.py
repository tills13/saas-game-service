import random
import math
import time
from collections import deque

class Board(object):
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

    def __init__(self, snakes, width=20, height=20, configuration=None):
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

    def get_at_position(self, x, y, exclude=None):
        for snake_id, snake in self.snakes.items():
            if exclude and snake in exclude: continue
            for body_segment in [] if "body" not in snake else snake["body"]:
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

    def get_random_empty_position(self, positions=None):
        if positions is not None:
            for position in positions:
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

    def get_food_count(self):
        return len(self.food)

    def get_gold(self):
        return self.gold

    def get_gold_count(self):
        return len(self.gold)

    def get_snakes(self):
        return self.snakes

    def get_snake_count(self):
        return len(self.snakes.keys())

    def get_teleporters(self):
        return self.teleporters

    def get_teleporter_count(self):
        return len(self.teleporters)

    def get_walls(self):
        return self.walls

    def get_wall_count(self):
        return len(self.walls)

    def initialize_snakes(self):
        for index, (snake_id, snake) in enumerate(self.snakes.items()):
            if self.configuration:
                m_snake = None
                if snake_id in [snake["id"] for snake in self.configuration["snakes"]]:
                    m_snake = [snake for snake in self.configuration["snakes"] if snake_id == snake["id"]][0]
                elif index in [snake["number"] for snake in self.configuration["snakes"]]:
                    m_snake = [snake for snake in self.configuration["snakes"] if index == snake["number"]][0]

                if m_snake and "coords" in m_snake:
                    snake["body"] = deque([coord for coord in m_snake["coords"]])
                    continue

            # default to random placement
            x, y = self.get_random_empty_position()

            snake["body"] = deque([
                { "x": x, "y": y, "color": snake["defaultColor"] },
                { "x": x, "y": y - 1, "color": snake["defaultColor"] }
            ])

        for snake_id, snake in self.snakes.items():
            snake["gold_count"] = 0
            snake["health"] = 100
            snake["nextMove"] = Board.MOVE_UP
            snake["score"] = 0
            snake["taunt"] = ""

    def spawn_random_food(self, count = 1):
        for index in range(0, count):
            x, y = self.get_random_empty_position(
                positions=self.configuration["food"] if self.configuration else None
            )

            self.spawn_food(x, y)

    def spawn_food(self, x, y):
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

    def spawn_wall(self, x, y):
        self.walls.append({ "x": x, "y": y })
        self.last_wall_spawn = time.time()

    def update(self, snakes, tick_snakes = True):
        self.snakes = snakes

        if tick_snakes:
            # update all positions and health
            for snake_id, snake in self.snakes.items():
                snake["health"] = snake["health"] - 1

                current_head_position = snake["body"][0]
                next_position_vector = {
                    Board.MOVE_UP: [0, -1],
                    Board.MOVE_DOWN: [0, 1],
                    Board.MOVE_LEFT: [-1, 0],
                    Board.MOVE_RIGHT: [1, 0]
                }[snake["nextMove"]]

                snake["body"].appendleft({
                    "x": current_head_position["x"] + next_position_vector[0],
                    "y": current_head_position["y"] + next_position_vector[1],
                    "color": current_head_position.get("color", snake["defaultColor"])
                })

            for snake_id, snake in self.snakes.items():
                # reset head
                current_head_position = snake["body"][0]
                head_x = current_head_position["x"]
                head_y = current_head_position["y"]

                if head_x < 0 or head_x >= self.width or head_y < 0 or head_y >= self.height:
                    snake["health"] = 0
                    continue

                value, thing = self.get_at_position(head_x, head_y, [snake])

                if value == Board.BOARD_TYPE_FOOD:
                    snake["health"] = 100
                    self.food.remove(thing)
                elif value == Board.BOARD_TYPE_GOLD:
                    snake["score"] = snake["score"] + 5 # todo custom gold values?
                    snake["gold_count"] = snake["gold_count"] + 1
                    self.gold.remove(thing)
                elif value == Board.BOARD_TYPE_WALL:
                    snake["health"] = 0
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
                        snake["body"].popleft() # remove current head
                        snake["body"].appendleft({
                            "x": teleporter["x"],
                            "y": teleporter["y"],
                            "color": current_head_position["color"]
                        })
                elif value == Board.BOARD_TYPE_SNAKE:
                    snake_head = thing["body"][0]

                    if snake_head["x"] == head_x and snake_head["y"] == head_y:
                        # head to head collision
                        if len(snake["body"]) > len(thing["body"]): snake["score"] = snake["score"] + 1
                        else: snake["health"] = 0
                    else:
                        snake["health"] = 0
                else:
                    snake["score"] = snake["score"] + 0.1
                    snake["body"].pop()

    def to_json(self, compatibility = False):
        snakes = [ snake for snake_id, snake in self.snakes.items() if snake["health"] > 0 ]
        dead_snakes = [ snake for snake_id, snake in self.snakes.items() if snake["health"] == 0 ]

        m_coordinate = lambda coord: coord if not compatibility else [coord["x"], coord["y"]]

        m_snake = lambda snake: {
            "id": snake["id"],
            "color": snake["defaultColor"],
            "headImageUrl": snake["headImageUrl"]
                if snake["headImageUrl"] is not None \
                else "/images/{}".format(snake["headImage"]),
            "name": snake["name"],
            "score": snake["score"],
            "goldCount": snake["gold_count"],
            "gold_count": snake["gold_count"],
            "taunt": snake["taunt"],
            "health": snake["health"],
            "health_points": snake["health"],
            "coords": [ m_coordinate(coord) for coord in snake["body"] ]
        }

        return {
            "dead_snakes": [ m_snake(snake) for snake in dead_snakes ],
            "deadSnakes": [ m_snake(snake) for snake in dead_snakes ],
            "food": [ m_coordinate(coord) for coord in self.food ],
            "gold": [ m_coordinate(coord) for coord in self.gold ],
            "height": self.height,
            "snakes": [ m_snake(snake) for snake in snakes ],
            "teleporters": self.teleporters,
            "walls": [ m_coordinate(coord) for coord in self.walls ],
            "width": self.width
        }
