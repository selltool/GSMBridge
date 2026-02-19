import asyncio, os
from ably import AblyRealtime
import logging
logger = logging.getLogger(__name__)

async def get_started():
    # Initialize the Ably Realtime client
    ably_realtime = AblyRealtime(os.getenv("ABLY_API_KEY"), client_id="client_sim_bridge")
    def on_state_change(state_change):
        if state_change.current.value == "connected":
            logger.info("Made my first connection!")
    ably_realtime.connection.on(on_state_change)
    await ably_realtime.connection.once_async("connected")
    channel = ably_realtime.channels.get("channel_sim_bridge")

    # Subscribe to messages on the channel
    def on_message(message):
        logger.info(f"Received message: {message.data}")
        logger.info(f"Event: {message.name}")

    await channel.subscribe(on_message)
    logger.info("Subscribed to messages on the channel")
    await asyncio.Event().wait()
    

    
def start_ably_listen():
    logger.info("Starting ably listen...")
    asyncio.create_task(get_started())