import asyncio
from typing import Collection


class Character:
    id: str
    name: str
    friends: Collection[str]
    appearsIn: Collection[str]


# noinspection PyPep8Naming
class Human(Character):
    type = "Human"
    homePlanet: str

    # noinspection PyShadowingBuiltins
    def __init__(self, id, name, friends, appearsIn, homePlanet):
        self.id, self.name = id, name
        self.friends, self.appearsIn = friends, appearsIn
        self.homePlanet = homePlanet


# noinspection PyPep8Naming
class Droid(Character):
    type = "Droid"
    primaryFunction: str

    # noinspection PyShadowingBuiltins
    def __init__(self, id, name, friends, appearsIn, primaryFunction):
        self.id, self.name = id, name
        self.friends, self.appearsIn = friends, appearsIn
        self.primaryFunction = primaryFunction


luke = Human(
    id="1000",
    name="Luke Skywalker",
    friends=["1002", "1003", "2000", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet="Tatooine",
)

vader = Human(
    id="1001",
    name="Darth Vader",
    friends=["1004"],
    appearsIn=[4, 5, 6],
    homePlanet="Tatooine",
)

han = Human(
    id="1002",
    name="Han Solo",
    friends=["1000", "1003", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet=None,
)

leia = Human(
    id="1003",
    name="Leia Organa",
    friends=["1000", "1002", "2000", "2001"],
    appearsIn=[4, 5, 6],
    homePlanet="Alderaan",
)

tarkin = Human(
    id="1004",
    name="Wilhuff Tarkin",
    friends=["1001"],
    appearsIn=[4],
    homePlanet=None,
)

humanData = {
    "1000": luke,
    "1001": vader,
    "1002": han,
    "1003": leia,
    "1004": tarkin,
}

threepio = Droid(
    id="2000",
    name="C-3PO",
    friends=["1000", "1002", "1003", "2001"],
    appearsIn=[4, 5, 6],
    primaryFunction="Protocol",
)

artoo = Droid(
    id="2001",
    name="R2-D2",
    friends=["1000", "1002", "1003"],
    appearsIn=[4, 5, 6],
    primaryFunction="Astromech",
)

droidData = {
    "2000": threepio,
    "2001": artoo,
}

reviews = {
    4: [{"stars": 4, "commentary": "Was good.", "episode": 4}],
    5: [{"stars": 5, "commentary": "This is a great movie!", "episode": 5}],
    6: [{"stars": 3, "commentary": "Was expecting more stuff", "episode": 6}],
}


def get_character(id):
    return humanData.get(id) or droidData.get(id)


def get_characters(ids):
    return map(get_character, ids)


def get_friends(character):
    return map(get_character, character.friends)


def get_hero(episode):
    if episode == 5:
        return luke
    return artoo


async def get_hero_async(episode):
    await asyncio.sleep(0.001)
    return get_hero(episode)


def get_human(id):
    return humanData.get(id)


def get_droid(id):
    return droidData.get(id)


def create_review(episode, review):
    reviews[episode].append(review)
    review["episode"] = episode
    return review


async def make_starwars_backend(aiohttp_server):
    from aiohttp import web
    from .schema import StarWarsSchema
    from graphql import graphql_sync

    async def handler(request):
        data = await request.json()
        source = data["query"]

        try:
            variables = data["variables"]
        except KeyError:
            variables = None

        result = graphql_sync(StarWarsSchema, source, variable_values=variables)

        return web.json_response(
            {
                "data": result.data,
                "errors": [str(e) for e in result.errors] if result.errors else None,
            }
        )

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    return server


async def make_starwars_transport(aiohttp_server):
    from gql.transport.aiohttp import AIOHTTPTransport

    server = await make_starwars_backend(aiohttp_server)

    url = server.make_url("/")

    transport = AIOHTTPTransport(url=url, timeout=10)

    return transport
