import time, os

import threading
from helpers import at_command
from config import mongo_lite
from serial.tools.list_ports_common import ListPortInfo

print_log = False
unique_id = os.environ["UNIQUE_ID"]

def check_port(port: ListPortInfo):
    if "USB" not in port.description:
        return
    data_save = {}
    data_save["unique_id"] = unique_id
    data_save["port"] = port.device
    if not at_command.ping_serial(port.device):
        return
    cpin = at_command.get_cpin(port.device)
    data_save["cpin"] = cpin
    if cpin == "unknown":
        return
    # csq = at_command.get_csq(port.device)
    # data_save["csq"] = csq
    # if csq < 9 or csq > 31:
    #     if print_log:
    #         print(f"CSQ is not in the range 9-31: {csq}")
    #     return
    # creg = at_command.get_creg(port.device)
    # data_save["creg"] = creg
    # if creg == "unknown":
    #     if print_log:
    #         print(f"CREG is unknown: {creg}")
    #     return
    # cops = at_command.get_cops(port.device)
    # data_save["cops"] = cops
    # iccid = at_command.get_iccid(port.device)
    # data_save["iccid"] = iccid
    # if iccid == "unknown":
    #     if print_log:
    #         print(f"ICCID is unknown: {iccid}")
    #     return
    # cnum = at_command.get_cnum(port.device)
    # data_save["cnum"] = cnum
    
    # Update or insert data into database with iccid as key
    data_save["time_update_com_port"] = time.time()
    mongo_lite.sim_collection.update_one({"iccid": iccid}, {"$set": data_save}, upsert=True)
    if print_log:
        print(f"Updated or inserted data for ICCID: {iccid}")


def scan_com():
    threading.Thread(target=scan_balance, daemon=True).start()
    while True:
        ports = serial.tools.list_ports.comports()
        for port in ports:
            thread = threading.Thread(target=check_port, args=(port,))
            thread.start()
        time.sleep(10)
        

def scan_balance():
    
    while True:
        print("Scanning balance...")
        # 1. Đưa query vào trong để lấy thời gian hiện tại chính xác
        now = time.time()
        one_day_ago = now - (3600 * 24)
        query = {
        "$or": [
            {"balance": None},
            {"balance_update_time": {"$lt": one_day_ago}}
        ]
    }
        sims_cursor = mongo_lite.sim_collection.find(query).limit(10)
        list_sims = list(sims_cursor)
        print(len(list_sims))
        # for sim in list_sims:
            # print(sim)
            # balance = at_command.get_balance(sim["port"], sim["iccid"])
            # print(f"Balance: {balance}")
        # for sim in sims_cursor:
        #     print(sim)
        
        # for sim in sims_cursor:
        #     balance = at_command.get_balance(sim["port"], sim["iccid"])
        #     print(f"Balance: {balance}")
        #     sim_collection.update_one({"_id": sim["_id"]}, {"$set": {"balance": balance}})
        # time.sleep(10)