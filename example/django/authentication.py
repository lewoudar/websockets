#!/usr/bin/env python

import asyncio

import django
import websockets

django.setup()

from sesame.utils import get_user


async def handler(websocket, path):
    sesame = await websocket.recv()
    user = await asyncio.to_thread(get_user, sesame)
    if user is None:
        await websocket.close(1011, "authentication failed")
        return

    await websocket.send(f"Hello {user}!")


async def main():
    async with websockets.serve(handler, "localhost", 8888):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
