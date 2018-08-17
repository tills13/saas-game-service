from typing import Dict
from collections import deque

from saas.board import Board
import saas.patch

class Snake(object):
  def __init__(self, data, starting_health=100):
    self._id = data["id"]

    self._api_version = data["api_version"]
    self._color = data["defaultColor"]
    self._body = []
    self._death = None
    self._dev_url = data["devUrl"]
    self._error = None
    self._kills = 0
    self._gold_count = 0
    self._health = starting_health
    self._is_bounty_snake = data["isBountySnake"]
    self._name = data["name"]
    self._next_move = Board.MOVE_UP
    self._score = 0
    self._taunt = ""
    self._url = data["url"]

  @property
  def api_version(self):
    return self._api_version

  @property
  def body(self):
    return self._body

  @body.setter
  def body(self, body):
    if not isinstance(body, deque):
      body = deque(body)

    self._body = body

  @property
  def color(self):
    return self._color

  @color.setter
  def color(self, color):
    self._color = color

  @property
  def death(self):
    return self._death

  @death.setter
  def death(self, death):
    self._death = death

  @property
  def error(self):
    return self._error

  @error.setter
  def error(self, error):
    self._error = error

  @property
  def gold(self):
    return self._gold_count

  @gold.setter
  def gold(self, gold_count):
    self._gold_count = gold_count

  def handle_move_response(self, move_response):
    self.error = None # clear error

    if self.api_version == "2017":
      self.taunt = move_response["taunt"]

    self.next_move = move_response["move"]

  def handle_start_response(self, start_response: Dict):
    self.taunt = start_response.get("taunt", "")

    if self.api_version == "2018":
      self.name = start_response["name"]
      self.color = start_response["color"]
      self.secondary_color = start_response.get("secondary_color", "")

  @property
  def head(self):
    return self.body[0]

  @property
  def health(self):
    return self._health

  @health.setter
  def health(self, health):
    self._health = health

  @property
  def id(self):
    return self._id

  def incr_gold(self):
    self.gold = self.gold + 1

  def incr_kills(self):
    self.kills = self.kills + 1

  @property
  def is_bounty_snake(self):
    return self._is_bounty_snake

  def is_alive(self):
    return self.health >= 0

  def kill(self, turn_number, reason, killer=None):
    self.health = 0
    self.death = { "turn": turn_number, "reason": reason, "killer": killer }

  @property
  def kills(self):
    return self._kills

  @kills.setter
  def kills(self, kills):
    self._kills = kills

  @property
  def length(self):
    return len(self._body)

  @property
  def name(self):
    return self._name

  @name.setter
  def name(self, new_name):
    self._name = new_name

  @property
  def next_move(self):
    return self._next_move

  @next_move.setter
  def next_move(self, next_move):
    self._next_move = next_move

  def reset(self, starting_health=100):
    self.body = []
    self.death = None
    self.error = None
    self.kills = 0
    self.gold = 0
    self.health = starting_health
    self.next_move = Board.MOVE_UP
    self.score = 0
    self.taunt = ""

  @property
  def secondary_color(self):
    return self._secondary_color

  @secondary_color.setter
  def secondary_color(self, secondary_color):
    self._secondary_color = secondary_color

  @property
  def taunt(self):
    return self._taunt

  @taunt.setter
  def taunt(self, taunt):
    self._taunt = taunt

  def tick(self):
    pass

  def get_url(self, dev_mode=False):
    return self._dev_url if dev_mode and self._dev_url else self._url

  url = property(get_url)

  def to_json(self, api_version):
    return patch.get_snake(self, self.api_version)
