from logging_config import setup_logging
import logging
setup_logging()
logger = logging.getLogger(__name__)
logger.info("Starting GSM Bridge...")
from helpers import startup
import logging, threading, time
from contextlib import asynccontextmanager
import uvicorn
from fastapi import FastAPI
from config import mongo_lite
from microservices import com_manager
from routes import register_routes
from services import ably_listen

@asynccontextmanager
async def lifespan(_: FastAPI):
    # 2. Đưa logic khởi chạy của bạn vào đây
    print("Starting GSM Bridge...")
    com_manager.start_com_manager()
    # mongo_manager = mongo_lite.sim_collection
    # print("Mongo Manager started...")
    # threading.Thread(target=scan_com.scan_com, daemon=True).start()
    # threading.Thread(target=com_manager.com_manager.get_com_have_sim, daemon=True).start()
    yield

app = FastAPI(lifespan=lifespan)
register_routes(app)

if __name__ == "__main__":
    logger.info("Starting GSM Bridge...")
    uvicorn.run("main:app", host="0.0.0.0", port=6969, reload=True)
