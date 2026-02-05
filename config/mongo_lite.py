from pymongo import MongoClient
import os
print("CONFIG MONGO LITE")
# Mọi cơ chế Retry và Timeout có thể gom vào đây
uri = os.getenv("MONGO_URI")
if not uri:
    raise ValueError("MONGO_URI is not set")
client = MongoClient(
    uri,
    retryWrites=True, 
    retryReads=True,
    serverSelectionTimeoutMS=5000,
    connectTimeoutMS=5000
)
db = client[os.getenv("MONGO_DB")]
sim_collection = db["sims"]
sms_collection = db["sms"]