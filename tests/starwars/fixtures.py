import asyncio
from collections import namedtuple

Human = namedtuple('Human', 'id name friends appearsIn homePlanet isAlive')

luke = Human(
    id='1000',
    name='Luke Skywalker',
    friends=['1002', '1003', '2000', '2001'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    homePlanet='Tatooine',
    isAlive=True,
)

vader = Human(
    id='1001',
    name='Darth Vader',
    friends=['1004'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    homePlanet='Tatooine',
    isAlive=False,
)

han = Human(
    id='1002',
    name='Han Solo',
    friends=['1000', '1003', '2001'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    homePlanet=None,
    isAlive=True,
)

leia = Human(
    id='1003',
    name='Leia Organa',
    friends=['1000', '1002', '2000', '2001'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    homePlanet='Alderaan',
    isAlive=True,
)

tarkin = Human(
    id='1004',
    name='Wilhuff Tarkin',
    friends=['1001'],
    appearsIn=['NEWHOPE'],
    homePlanet=None,
    isAlive=False,
)

humanData = {
    '1000': luke,
    '1001': vader,
    '1002': han,
    '1003': leia,
    '1004': tarkin,
}

Droid = namedtuple('Droid', 'id name friends appearsIn primaryFunction')

threepio = Droid(
    id='2000',
    name='C-3PO',
    friends=['1000', '1002', '1003', '2001'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    primaryFunction='Protocol',
)

artoo = Droid(
    id='2001',
    name='R2-D2',
    friends=['1000', '1002', '1003'],
    appearsIn=['NEWHOPE', 'EMPIRE', 'JEDI'],
    primaryFunction='Astromech',
)

droidData = {
    '2000': threepio,
    '2001': artoo,
}

reviews = {
    'NEWHOPE': [
        {
            'stars': 4,
            'commentary': 'Was good.',
            'episode': 'NEWHOPE'
        },
    ],
    'EMPIRE': [
        {
            'stars': 5,
            'commentary': 'This is a great movie!',
            'episode': 'EMPIRE'
        },
    ],
    'JEDI': [
        {
            'stars': 3,
            'commentary': 'Was expecting more stuff',
            'episode': 'JEDI'
        },
    ]
}


def getCharacter(id):
    return humanData.get(id) or droidData.get(id)


def getCharacters(ids):
    return map(getCharacter, ids)


def getFriends(character):
    return map(getCharacter, character.friends)


def getHero(episode):
    if episode == 'EMPIRE':
        return humanData.get('1000')
    return droidData.get('2001')


def getHuman(id):
    return humanData.get(id)


def getDroid(id):
    return droidData.get(id)


def createReview(episode, review):
    reviews[episode].append(review)
    review['episode'] = episode
    return review


async def reviewAdded(episode):
    count = 0
    while count < len(reviews[episode]):
        yield reviews[episode][count]
        await asyncio.sleep(1)
        count += 1

