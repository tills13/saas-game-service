import uuid

from saas import postgres

set_game_status = postgres.prepare("""
    UPDATE "public"."Games" AS "g" SET "status" = $1 WHERE "g"."id" = $2
""")

set_snake_place = postgres.prepare("""
    UPDATE "public"."SnakeGames" SET "place" = $1 WHERE "SnakeId" = $2 AND "GameId" = $3
""")

get_game_prepared = postgres.prepare("""
    SELECT
        "g"."id"::text, "g"."boardFoodCount", "g"."boardFoodStrategy", "g"."boardGoldCount", "g"."boardGoldStrategy",
        "g"."boardGoldWinningThreshold", "g"."boardGoldRespawnInterval", "g"."boardHasGold", "g"."boardHasWalls", "g"."boardHasTeleporters", "g"."boardRows",
        "g"."boardColumns", "g"."boardTeleporterCount", "g"."creatorId"::text, "g"."devMode", "g"."status", "g"."tickRate", "g"."turnLimit", "g"."responseTime",
        "d"."id"::text AS "daemon_id", "d"."name" AS "daemon_name", "d"."url" AS "daemon_url",
        "bc"."id"::text AS "board_configuration_id", "bc"."configuration" AS "board_configuration", "bc"."name" AS "board_configuration_name"
    FROM "public"."Games" AS "g"
    LEFT JOIN "public"."Daemons" AS "d" ON "g"."daemonId" = "d"."id"
    LEFT JOIN "public"."BoardConfigurations" AS "bc" ON "g"."boardConfigurationId" = "bc"."id"
    WHERE "g"."id" = $1
""")

get_game_snakes_prepared = postgres.prepare("""
    SELECT
        s."id"::text, s."defaultColor", s."headImage", s."headImageUrl",
        s."isBountySnake", s."isLegacy", s."name", s."url", s."devUrl"
    FROM "public"."Snakes" AS s
    LEFT JOIN "public"."SnakeGames" sg ON s."id" = "sg"."SnakeId"
    LEFT JOIN "public"."Games" AS g ON "sg"."GameId" = g."id"
    WHERE g."id" = $1
""")

get_child_games = postgres.prepare("""
    SELECT
        "id"::text, "parentGameId"::text, "creatorId"::text, "boardHasWalls", "boardColumns", "boardRows", "boardFoodCount",
        "boardFoodStrategy", "tickRate", "responseTime", "boardGoldCount", "boardGoldWinningThreshold",
        "boardGoldStrategy", "boardGoldRespawnInterval", "visibility", "boardHasTeleporters", "boardTeleporterCount",
        "boardHasGold", "turnLimit", "boardConfigurationId"::text, "daemonId"::text
    FROM "public"."Games" WHERE "parentGameId" = $1
""")

clone_game_prepared = postgres.prepare("""
    INSERT INTO "public"."Games" (
        "id", "parentGameId", "creatorId", "boardHasWalls", "boardColumns", "boardRows", "boardFoodCount",
        "boardFoodStrategy", "tickRate", "responseTime", "boardGoldCount", "boardGoldWinningThreshold",
        "boardGoldStrategy", "boardGoldRespawnInterval", "visibility", "boardHasTeleporters", "boardTeleporterCount",
        "boardHasGold", "turnLimit", "boardConfigurationId", "daemonId", "devMode", "createdAt", "updatedAt"
    ) SELECT
        $1, $2, "creatorId", "boardHasWalls", "boardColumns", "boardRows", "boardFoodCount",
        "boardFoodStrategy", "tickRate", "responseTime", "boardGoldCount", "boardGoldWinningThreshold",
        "boardGoldStrategy", "boardGoldRespawnInterval", "visibility", "boardHasTeleporters", "boardTeleporterCount",
        "boardHasGold", "turnLimit", "boardConfigurationId", "daemonId", "devMode", NOW(), NOW()
    FROM "public"."Games" WHERE "id" = $2
    RETURNING
        "id"::text, "creatorId"::text, "boardHasWalls", "boardColumns", "boardRows", "boardFoodCount",
        "boardFoodStrategy", "tickRate", "responseTime", "boardGoldCount", "boardGoldWinningThreshold",
        "boardGoldStrategy", "boardGoldRespawnInterval", "visibility", "boardHasTeleporters", "boardTeleporterCount",
        "boardHasGold", "turnLimit", "boardConfigurationId"::text, "daemonId"::text, "devMode"
""")

clone_snake_games_prepared = postgres.prepare("""
    INSERT INTO "public"."SnakeGames" ("GameId", "SnakeId", "createdAt", "updatedAt")
    SELECT $1, "SnakeId", NOW(), NOW() FROM "SnakeGames" WHERE "GameId" = $2
""")


def clone_game(game_id):
    new_uuid = uuid.uuid4()

    with postgres.xact():
        new_game = clone_game_prepared.first(new_uuid, game_id)
        clone_snake_games_prepared(new_game["id"], game_id)

    return new_game

