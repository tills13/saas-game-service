def wrap_list(items, api_version):
    if api_version == "2018":
        return { "data": items, "object": "list" }

    return items

def get_coordinate(coord, api_version):
    if api_version == "2017":
        return [coord["x"], coord["y"]]

    return coord

def get_move_request(board, game, snake):
    api_version = snake["api_version"]
    turn_number = game.turn_number

    request = board.to_json(api_version=api_version)
    request["turn"] = turn_number

    if api_version == "2017":
        request["game_id"] = game.game_id
        request["you"] = snake["id"]

        return request
    elif api_version == "2018":
        request["id"] = snake["id"]
        request["you"] = get_snake(snake, api_version)

    request["gameId"] = game.game_id
    request["apiVersion"] = api_version

    turn_limit = game.game["turnLimit"]
    if turn_limit is not None and turn_limit != 0:
        request["turnsRemaining"] = turn_limit - turn_number

    return request

def get_snake(snake, api_version):
    if api_version == "2017":
        return {
            "id": snake["id"],
            "color": snake["defaultColor"],
            "name": snake["name"],
            "taunt": snake["taunt"],
            "health_points": snake["health"],
            "coords": [ get_coordinate(coord, api_version) for coord in snake["body"] ]
        }
    elif api_version == "2018":
        return {
            "id": snake["id"],
            "body": wrap_list([ get_coordinate(coord, api_version) for coord in snake["body"] ], api_version),
            "health": snake["health"],
            "length": len(snake["body"]),
            "name": snake["name"],
            "object": "snake",
            "taunt": snake["taunt"]
        }

    return {
        "id": snake["id"],
        "color": snake["defaultColor"],
        "coords": [ get_coordinate(coord, api_version) for coord in snake["body"] ],
        "death": snake.get("death", { }),
        "name": snake["name"],
        "goldCount": snake["gold_count"],
        "health": snake["health"],
        "headImageUrl": snake["headImageUrl"]
                if snake["headImageUrl"] is not None \
                else "/images/{}".format(snake["headImage"]),
        "kills": snake["kills"],
        "score": snake["score"],
        "taunt": snake["taunt"]
    }

def get_start_request(game, api_version):
    if api_version == "2017":
        return {
            "game_id": game.game_id,
            "width": game.game["boardColumns"],
            "height": game.game["boardRows"]
        }
    elif api_version == "2018":
        return { "game_id": game.game_id }

    return { "gameId": game.game_id }

