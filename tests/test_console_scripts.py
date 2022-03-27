"""tests of console_scripts entry_point (formerly scripts/gql-cli)"""
import io
import json

import pytest

from gql import __version__


def test_cli_ep_version(script_runner):
    ret = script_runner.run("gql-cli", "--version")

    assert ret.success

    assert ret.stdout == f"v{__version__}\n"
    assert ret.stderr == ""


@pytest.mark.asyncio
@pytest.mark.script_launch_mode("subprocess")
async def test_cli_ep_aiohttp_using_cli(
    event_loop, aiohttp_server, monkeypatch, script_runner, run_sync_test
):
    from aiohttp import web

    from .test_aiohttp import (
        query1_server_answer,
        query1_server_answer_data,
        query1_str,
    )

    async def handler(request):
        return web.Response(text=query1_server_answer, content_type="application/json")

    app = web.Application()
    app.router.add_route("POST", "/", handler)
    server = await aiohttp_server(app)

    url = str(server.make_url("/"))

    def test_code():

        monkeypatch.setattr("sys.stdin", io.StringIO(query1_str))

        ret = script_runner.run(
            "gql-cli", url, "--verbose", stdin=io.StringIO(query1_str)
        )

        assert ret.success

        # Check that the result has been printed on stdout
        captured_out = str(ret.stdout).strip()

        expected_answer = json.loads(query1_server_answer_data)
        print(f"Captured: {captured_out}")
        received_answer = json.loads(captured_out)

        assert received_answer == expected_answer

    await run_sync_test(event_loop, server, test_code)
