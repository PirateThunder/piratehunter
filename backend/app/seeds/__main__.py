"""Точка входа `python -m app.seeds` (ресед к эталону, §10)."""

import asyncio

from .runner import main

asyncio.run(main())
