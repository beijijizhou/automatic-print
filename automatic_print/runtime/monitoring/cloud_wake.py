"""Supabase Realtime fallback used only when a LAN dispatch is not acknowledged."""

import asyncio
import base64
import hashlib
import hmac
import json
import logging
from threading import Event, Thread
import time
from urllib.parse import quote
from urllib.request import Request, urlopen

from ...automation.api.gateway_credentials import shared_client_key
from ...automation.api.supabase_public import PUBLIC_ANON_JWT
from .protocol import decode_dispatch_message, encode_dispatch_message


PROJECT_REF = "bhhbztpmwlzuzbzfmsos"
REALTIME_URL = f"wss://{PROJECT_REF}.supabase.co/realtime/v1"
REALTIME_HTTP = f"https://{PROJECT_REF}.supabase.co/realtime/v1/api/broadcast"
EVENT_NAME = "machine-command"


def machine_topic(machine, *, key=None):
    secret = str(key or shared_client_key()).encode("utf-8")
    digest = hmac.new(secret, str(machine).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"automatic-print:dispatch:{digest[:32]}"


def notify_machine_via_cloud(target_machine_id, *, command_id="", key=None, timeout=5):
    """Publish an opaque signed wake-up after the UDP acknowledgement timed out."""
    message = encode_dispatch_message(target_machine_id, command_id=command_id, key=key)
    topic = quote(machine_topic(target_machine_id, key=key), safe="")
    event = quote(EVENT_NAME, safe="")
    request = Request(
        f"{REALTIME_HTTP}/{topic}/events/{event}",
        data=json.dumps({"message": base64.b64encode(message).decode("ascii")}).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "apikey": PUBLIC_ANON_JWT,
            "Authorization": f"Bearer {PUBLIC_ANON_JWT}",
        },
    )
    with urlopen(request, timeout=float(timeout)) as response:
        if int(getattr(response, "status", 200)) >= 300:
            raise OSError(f"Realtime broadcast returned {response.status}")
    return True


class CloudWakeListener:
    def __init__(self, *, target_machine_id, dispatch, key=None):
        self.target_machine_id = str(target_machine_id)
        self.dispatch = dispatch
        self.key = key
        self.stop_event = Event()
        self.thread = None

    def start(self):
        if self.thread is None or not self.thread.is_alive():
            self.thread = Thread(target=self._run, daemon=True, name="cloud-wake")
            self.thread.start()

    def stop(self):
        self.stop_event.set()

    def _run(self):
        while not self.stop_event.is_set():
            try:
                asyncio.run(self._listen())
            except Exception as error:
                logging.getLogger("automatic-print.printerexp-monitor").warning(
                    "Cloud wake listener reconnecting: %s", error,
                )
            if not self.stop_event.is_set():
                time.sleep(5)

    async def _listen(self):
        from realtime import AsyncRealtimeClient

        client = AsyncRealtimeClient(REALTIME_URL, PUBLIC_ANON_JWT, auto_reconnect=True)
        channel = client.channel(machine_topic(self.target_machine_id, key=self.key))
        channel.on_broadcast(EVENT_NAME, self._receive)
        try:
            await channel.subscribe()
            while not self.stop_event.is_set():
                await asyncio.sleep(0.25)
        finally:
            await channel.unsubscribe()
            await client.close()

    def _receive(self, event):
        try:
            encoded = event.get("payload", {}).get("message", "")
            payload = decode_dispatch_message(base64.b64decode(encoded), key=self.key)
        except (TypeError, ValueError):
            return
        if payload and payload.get("target_machine_id") == self.target_machine_id:
            self.dispatch(payload)


class HybridWakeListener:
    def __init__(self, *, target_machine_id, dispatch):
        from .control import AutomationWakeListener

        self.listeners = (
            AutomationWakeListener(
                target_machine_id=target_machine_id, dispatch=dispatch,
            ),
            CloudWakeListener(
                target_machine_id=target_machine_id, dispatch=dispatch,
            ),
        )

    def start(self):
        for listener in self.listeners:
            listener.start()

    def stop(self):
        for listener in self.listeners:
            listener.stop()
