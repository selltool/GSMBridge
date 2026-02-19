from config import mongo_lite
from typing import Optional
from microservices.com_manager import ComPort
import re
import traceback
import logging


logger = logging.getLogger(__name__)

def decode_ascii_concat(s):
    result = ""
    i = 0

    while i < len(s):
        # ASCII printable characters range from 32 to 126
        # Try 2-digit first, then 3-digit
        if i + 2 <= len(s) and 32 <= int(s[i:i+2]) <= 99:
            result += chr(int(s[i:i+2]))
            i += 2
        elif i + 3 <= len(s) and 100 <= int(s[i:i+3]) <= 126:
            result += chr(int(s[i:i+3]))
            i += 3
        else:
            raise ValueError(f"Invalid ASCII sequence at position {i}")

    return result


def replace_line_end(str):
    return "".join(str.splitlines()).strip()

def parse_sms_data(data):
    # Regex này sẽ bắt: Index, Status, Sender, Timestamp và Nội dung (bao gồm cả xuống dòng)
    pattern = r'\+CMGL: (\d+),"(.*?)","(.*?)",,"(.*?)"\r?\n(.*?)(?=\r?\n\+CMGL:|\r?\n\r?\nOK)'
    
    matches = re.findall(pattern, data, re.DOTALL)
    results = []
    
    for m in matches:
        results.append({
            "index": m[0],
            "status": m[1],
            "sender": decode_ascii_concat(m[2]),
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
            comport = ComPort(com_port)
            _ = comport.connect()
            if _ is None:
                print(f"Error connecting to com port: {com_port}")
                return None
            print(f"Connected to com port: {com_port}")
            result, time_taken = comport.write('AT+CSCS?')
            if "OK" not in result:
                logger.error(f"Error getting SMS mode: {replace_line_end(result)}, iccid: {iccid}")
                return None
            result, time_taken = comport.write('AT+CSCS="GSM"')
            if "OK" not in result:
                logger.error(f"Error setting SMS mode to GSM: {replace_line_end(result)}, iccid: {iccid}")
                return None
            result, time_taken = comport.write("AT+CMGF=1")
            if "OK" not in result:
                logger.error(f"Error setting SMS mode to text: {replace_line_end(result)}, iccid: {iccid}")
                return None
            result, time_taken = comport.write('AT+CPMS="SM"')
            if "OK" not in result:
                logger.error(f"Error setting SMS mode to SIM memory: {replace_line_end(result)}, iccid: {iccid}")
                return None
            result, time_taken = comport.write('AT+CMGL="ALL"')
            if "OK" not in result:
                logger.error(f"Error getting all SMS: {replace_line_end(result)}, iccid: {iccid}")
                return None
            comport.disconnect()
            sms = parse_sms_data(result)
            result_sms = {
                'phone': sim['phone'],
                'sms': sms,
                'cimi': sim['cimi'],
            }
            self.save_sms(result_sms)
            print(f"Found {len(sms)} messages.")
            return result_sms
        except Exception as e:
            print(f"Error getting SMS: {e}, traceback: {traceback.format_exc()}")
            return None
        
    
    def save_sms(self, sms_data):
        list_sms = list(sms_data['sms'])
        for sms in list_sms:
            print(f"Saving SMS: {sms}")
            self.sms_collection.update_one({
                "cimi": sms_data['cimi'],
                "time_received": sms['time'],
                "sender": sms['sender'],
            }, {
                "$set": {
                    "content": sms['content'],
                    "status": sms['status'],
                    "index": sms['index'],
                }
            }, upsert=True)
        print(f"Saved {len(list_sms)} SMS")