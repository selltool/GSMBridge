from typing import Iterable, Optional
import serial
import serial.tools.list_ports
from config import mongo_lite
from helpers import at_command, re_string
import time
import threading
import traceback

print_log = False
def replace_data(str):
    str_tmp = str.replace("+CPIN: ", "").replace('OK', '').strip()
    return str_tmp

class ComPort:
    def __init__(self, port):
        self.port = port
        self.ser = None
        
    def connect(self, max_wait=10.0, retry_delay=0.5):
        start_time = time.time()
        deadline = start_time + max_wait
        while time.time() < deadline:
            try:
                self.ser = serial.Serial(self.port, 115200, timeout=1)
                return True
            except serial.SerialException as e:
                if "PermissionError" in str(e):
                    print(f"PermissionError, sleep {retry_delay} seconds")
                    time.sleep(retry_delay)
                    continue
                elif "The system cannot find the file specified" in str(e):
                    print(f"The system cannot find the file specified, return False")
                    return False
                print(f"Error connecting to com port 123124523: {self.port}: {e}")
            except Exception as e:
                print(f"Error connecting to com port {self.port}: {e}")
                print(traceback.format_exc())
                time.sleep(retry_delay)
        print(f"Failed to connect to com port {self.port}")
        return False
    
    def write(self, command, timeout: float = 2.0, expected: Optional[Iterable[str]] = ("OK", "ERROR"),):
        if self.ser is None:
            print(f"Com port {self.port} is not connected")
            return None, None
        expected = tuple(expected) if expected else ()
        time_start = time.time()
        result = None
        try:
            self.ser.reset_input_buffer()
            self.ser.write((command + "\r").encode())
            buffer = ""
            deadline = time.time() + timeout

            while time.time() < deadline:
                try:
                    line = self.ser.readline().decode(errors="ignore")
                except serial.SerialException:
                    break

                if not line:
                    continue

                buffer += line

                if expected and any(token in buffer for token in expected):
                    result = buffer
                    break
            time_taken = time.time() - time_start
            return result, time_taken
        except Exception as e:
            print(f"Error writing to com port {self.port}: {e}")
            return None, None
    
    def disconnect(self):
        if self.ser is not None:
            self.ser.close()
            self.ser = None
        return True
    


class ComManager:
    def __init__(self) -> None:
        self.com_ports = {}
    
    def get_com_have_sim(self):
        while True:
            try:
                ports = serial.tools.list_ports.comports()
                for com in list(self.com_ports):
                    if com not in [port.device for port in ports]:
                        del self.com_ports[com]
                for port in ports:
                    if "USB" not in port.description:
                        continue
                    if port.device in list(self.com_ports):
                        continue
                    cpin = at_command.get_cpin(port.device)
                    if cpin != "ready":
                        continue
                    else:
                        if port.device not in list(self.com_ports):
                            print(f"Add com port: {port.device}, cpin: {cpin}")
                            self.com_ports[port.device] = ComPort(port.device)
                time.sleep(1)
            except Exception as e:
                print(f"Error getting com ports: {e}")
                print(traceback.format_exc())
                time.sleep(5)
                
                
    def get_info_sim(self):
        while True:
            try:
                print(f"Getting info sim, with {len(list(self.com_ports))} com ports")
                for com in list(self.com_ports):
                    comport = ComPort(com)
                    _ = comport.connect()
                    if _ is None:
                        continue
                    time_save = {}
                    result, time_taken = comport.write("AT+CPIN?")
                    if result is None or "READY" not in result:
                        if result: result = "".join(result.splitlines()).strip()
                        print(f"{com} is not ready [7395], it is: {result}, remove from com ports")
                        self.com_ports.pop(com, None)
                        continue
                    cpin = replace_data(result)
                    time_save["cpin"] = time_taken
                    result, time_taken = comport.write("AT+CREG?")
                    creg = replace_data(result)
                    time_save["creg"] = time_taken
                    result, time_taken = comport.write("AT+COPS?")
                    cops = replace_data(result)
                    time_save["cops"] = time_taken
                    result, time_taken = comport.write("AT+CCID")
                    iccid = result.replace("+CCID: ", "").replace('OK', '').strip()
                    time_save["iccid"] = time_taken
                    result, time_taken = comport.write("AT+CSQ")
                    csq = replace_data(result)
                    time_save["csq"] = time_taken
                    result, time_taken = comport.write("AT+QNWINFO")
                    cpsi = replace_data(result)
                    time_save["cpsi"] = time_taken
                    result, time_taken = comport.write("AT+CIMI")
                    cimi = result.replace("+CIMI: ", "").replace('OK', '').strip()
                    time_save["cimi"] = time_taken
                    comport.disconnect()
                    data_save = {
                        "cpin": cpin,
                        "creg": creg,
                        "cops": cops,
                        "iccid": iccid,
                        "cimi": cimi,
                        "csq": csq,
                        "cpsi": cpsi,
                        "com_port": com,
                        "time_update_info_sim": time.time(),
                        "time_save": time_save
                    }
                    mongo_lite.sim_collection.update_one({"iccid": iccid}, {"$set": data_save}, upsert=True)
                    time.sleep(1)
                time.sleep(5)
            except Exception as e:
                print(f"Error getting info sim: {e}")
                print(traceback.format_exc())
                time.sleep(5)
            
    def get_balance(self):
        while True:
            try:
                query = {
                    "$or": [
                        {"balance": None},
                        {"balance_update_time": {"$lt": time.time() - (3600 * 24)}}
                    ]
                }
                sims_cursor = mongo_lite.sim_collection.find(query).limit(10)
                list_sims = list(sims_cursor)
                for sim in list_sims:
                    if "0,1" not in sim['creg'] and "0,5" not in sim['creg']:
                        # print(f"Sim is not in home network, com port: {sim['com_port']}")
                        continue
                    print(f"Getting balance for sim: {sim['iccid']}, com port: {sim['com_port']}")
                    comport = ComPort(sim["com_port"])
                    comport.connect()
                    result, time_taken = comport.write('AT+CUSD=1,"*101#",15', timeout=20, expected=("+CUSD:", "ERROR", "+CME ERROR"))
                    if result is None:
                        print(f"Error getting balance, com port: {sim['com_port']}")
                        continue
                    if "+CUSD:" not in result:
                        print(f"Error getting balance, com port: {sim['com_port']}, result: {result}")
                        continue
                    result = "".join(result.splitlines()).replace("+CUSD:", "").strip()
                    balance_dict = re_string.balance_to_dict(result, sim['iccid'])
                    print(f"Balance: {balance_dict}, com port: {sim['com_port']}")
                    comport.disconnect()
                    mongo_lite.sim_collection.update_one(
                        {"iccid": sim['iccid']},
                        {
                            "$set": {
                                "balance": balance_dict['balance'],
                                "balance_update_time": time.time(),
                                "phone": balance_dict['phone'],
                                "balance_raw": result
                            }
                        }, upsert=True)
                    time.sleep(1)
            except Exception as e:
                print(f"Error getting balance: {e}")
                time.sleep(5)
            
            
            # time.sleep(5)
                
com_manager = ComManager()
threading.Thread(target=com_manager.get_com_have_sim, daemon=True).start()
time.sleep(3)
threading.Thread(target=com_manager.get_info_sim, daemon=True).start()

threading.Thread(target=com_manager.get_balance, daemon=True).start()