
from config import mongo_lite


def delete_com_port(iccid):
    print(f"Delete com port for iccid: {iccid}")
    sim = mongo_lite.sim_collection.find_one({"iccid": iccid})
    if not sim:
        return False
    old_com_port = sim["old_com_port"] if "old_com_port" in sim else []
    old_com_port.append(sim["com_port"])
    mongo_lite.sim_collection.update_one({"iccid": iccid}, {"$set": {
        "old_com_port": old_com_port,
        "com_port": None
    }}, upsert=True)
    return True