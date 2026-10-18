"""Debounce new messages without losing the latest one during cooldown."""
import asyncio
import time


async def next_reply_message(pending, engine, delay):
    message = await pending.get()
    quiet_until = time.monotonic() + delay
    while True:
        deadline = max(quiet_until, engine.last_sent + engine.config['cooldown_seconds'])
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return message, engine.revision
        try:
            message = await asyncio.wait_for(pending.get(), remaining)
            quiet_until = time.monotonic() + delay
        except TimeoutError:
            return message, engine.revision
