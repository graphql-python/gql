# First install fastapi and uvicorn:
#
# pip install fastapi uvicorn
#
# then run:
#
# uvicorn fastapi_async:app --reload

import logging

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

transport = AIOHTTPTransport(url="https://countries.trevorblades.com/graphql")

client = Client(transport=transport)

query = gql(
    """
query getContinentInfo($code: ID!) {
  continent(code:$code) {
    name
    code
    countries  {
      name
      capital
    }
  }
}
"""
)

app = FastAPI()


@app.on_event("startup")
async def startup_event():
    print("Connecting to GraphQL backend")

    await client.connect_async(reconnecting=True)
    print("End of startup")


@app.on_event("shutdown")
async def shutdown_event():
    print("Shutting down GraphQL permanent connection...")
    await client.close_async()
    print("Shutting down GraphQL permanent connection... done")


continent_codes = [
    "AF",
    "AN",
    "AS",
    "EU",
    "NA",
    "OC",
    "SA",
]


@app.get("/", response_class=HTMLResponse)
def get_root():

    continent_links = ", ".join(
        [f'<a href="continent/{code}">{code}</a>' for code in continent_codes]
    )

    return f"""
    <html>
        <head>
            <title>Continents</title>
        </head>
        <body>
            Continents: {continent_links}
        </body>
    </html>
"""


@app.get("/continent/{continent_code}")
async def get_continent(continent_code):

    if continent_code not in continent_codes:
        raise HTTPException(status_code=404, detail="Continent not found")

    try:
        result = await client.session.execute(
            query, variable_values={"code": continent_code}
        )
    except Exception as e:
        log.debug(f"get_continent Error: {e}")
        raise HTTPException(status_code=503, detail="GraphQL backend unavailable")

    return result
