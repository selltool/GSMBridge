from config import mongo_lite
from typing import Optional
from microservices import com_manager
import re
import traceback


def parse_sms_data(data):
    # Regex này sẽ bắt: Index, Status, Sender, Timestamp và Nội dung (bao gồm cả xuống dòng)
    pattern = r'\+CMGL: (\d+),"(.*?)","(.*?)",,"(.*?)"\r?\n(.*?)(?=\r?\n\+CMGL:|\r?\n\r?\nOK)'
    
    matches = re.findall(pattern, data, re.DOTALL)
    results = []
    
    for m in matches:
        results.append({
            "index": m[0],
            "status": m[1],
            "sender": m[2],
            "time": m[3],
            "content": m[4].strip()
        })
    return results


class SMSManager:
    def __init__(self):
        self.sms_collection = mongo_lite.sms_collection
        self.sim_collection = mongo_lite.sim_collection
        
    def get_sms_all(self, iccid: str):
        try:
            print(f"Getting SMS for iccid: {iccid}")
            sim = self.sim_collection.find_one({"iccid": iccid})
            if not sim:
                print(f"Sim not found for iccid: {iccid}")
                return None
            print(f"Sim: {sim}")
            com_port = sim["com_port"]
            comport = com_manager.ComPort(com_port)
            _ = comport.connect()
            if _ is None:
                print(f"Error connecting to com port: {com_port}")
                return None
            print(f"Connected to com port: {com_port}")
            result, time_taken = comport.write("AT+CMGF=1")
            print(f"Set SMS mode to text: {result}")
            result, time_taken = comport.write('AT+CPMS="SM"')
            print(f"Set SMS mode to SIM memory: {result}")
            result, time_taken = comport.write('AT+CMGL="ALL"')
            print(f"Get all SMS: {result}")
            comport.disconnect()
            sms = parse_sms_data(result)
            result_sms = {
                'phone': sim['phone'],
                'sms': sms
            }
            print(f"Found {len(sms)} messages.")
            return result_sms
        except Exception as e:
            print(f"Error getting SMS: {e}, traceback: {traceback.format_exc()}")
            return None