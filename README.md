# SAAS - Snake as a Service

![https://i.imgur.com/6EZQ2Qc.png](https://i.imgur.com/6EZQ2Qc.png)
![https://i.imgur.com/o3LQAN2.png](https://i.imgur.com/o3LQAN2.png)

Not sure how I feel about the name but that's what I landed on ... good enough for now.

- [Client](https://www.github.com/tills13/saas-web)
- [Server](https://www.github.com/tills13/saas-api)
- [Manager](https://www.github.com/tills13/saas-game-service)


## What is it?

If you know about BattleSnake, you're most of the way there. I've taken a lot of ideas and concepts
from there and applied them here. If you haven't, however, SaaS/BattleSnake is a coding competition
where teams or individuals build "AI controlled" snakes (classic Snake) which duke it out on a board.

## Service

The game service actually runs the games being played. Clients connect to the service via Websockets. I'm honestly not sure about this part... but it works.

This is largely feature _incomplete_. Basic functionality is there but there's still a lot to do/implement (custom food/gold spawning strats. for example).

## How to Run

I suggest running it inside a `venv`

1. install `venv` - `pip install virtualenv` (I hear they come pre-packaged with Python3 - although I haven't even tried running this with Python 3)
2. create the virtualenv - `virtualenv . --python=python2.7`
3. start the virtualenv `source bin/activate`
4. install dependencies `pip install -r requirements.txt`
5. create `.env` (see `.env.example` for required params)
6. start service `python app.py`

It's kind of pointless to run this against a different RDS/Redis from [the api](https://www.github.com/tills13/saas-api), so you can grab/share most of the `.env` params from/with that. This pretty much only supports PostgreSQL because of the hand-written queries in `queries.py` (although I'm pretty sure most of what I wrote is ANSI compat.)

#### Tech

- Python 🤔
- PostgreSQL
- Websockets (Socket.IO)

PRs welcome but ¯\\\_(ツ)\_/¯ it's just a hobby project.