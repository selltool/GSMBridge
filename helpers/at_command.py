import serial, re, traceback
import time
from typing import Iterable, Optional
from helpers import re_string
from config import mongo_lite
import logging
from database import sim_db
from datetime import datetime, timezone


logger = logging.getLogger(__name__)

def send_at_command_fast(
    command: str,
    port: str,
    baudrate: int = 115200,
    timeout: float = 2.0,
    expected: Optional[Iterable[str]] = ("OK", "ERROR"),
) -> str:
    expected = tuple(expected) if expected else ()
    time_start = time.time()
    result = None
    with serial.Serial(
        port,
        baudrate,
        timeout=0.05,     # timeout nhỏ
        write_timeout=0.2
    ) as ser:

        ser.reset_input_buffer()
        ser.write((command + "\r").encode())

        buffer = ""
        deadline = time.time() + timeout

        while time.time() < deadline:
            try:
                line = ser.readline().decode(errors="ignore")
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
# ================================================
def send_at_command_fast_with_serial(ser: serial.Serial, command: str, timeout: float = 2, expected: Optional[Iterable[str]] = ("OK", "ERROR")):
    ser.reset_input_buffer()
    ser.write((command + "\r").encode())

    buffer = ""
    deadline = time.time() + timeout
    result = None
    while time.time() < deadline:
        try:
            line = ser.readline().decode(errors="ignore")
        except serial.SerialException:
            break

        if not line:
            continue

        buffer += line

        if expected and any(token in buffer for token in expected):
            result = buffer
            break
    return result


def ping_serial(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT", serial_port)
        if "OK" not in response:
            return False
        return True
    except Exception as e:
        print(f"Error pinging serial: {e}")
        return False
    
    
def get_cops(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+COPS?", serial_port)
        str_tmp = response.replace("+COPS: ", "")
        str_tmp = str_tmp.replace('OK', '').strip()
        str_tmp = str_tmp.replace('"', '')
        if "OK" not in response:
            return str_tmp
        cops = str_tmp.split(",")
        return {
            "mode": cops[0],
            "format": cops[1],
            "operator": cops[2],
            "other": cops[3:],
        }
    except Exception as e:
        print(f"Error parsing COPS: {e}")
        print(traceback.format_exc())
        return None
    
    
def get_csq(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+CSQ", serial_port)
        match = re.search(r'\d+', response)
        if match:
            result = int(match.group())
            return result
        else:
            return None
    except Exception as e:
        print(f"Error parsing CSQ: {e}")
        print(traceback.format_exc())
        return None
    
def get_creg(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+CREG?", serial_port)
        if "0,5" in response:
            return "roaming"
        elif "0,1" in response:
            return "home"
        else:
            return "unknown"    
    except Exception as e:
        print(f"Error parsing CREG: {e}")
        print(traceback.format_exc())
        return None
    
def get_cpin(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+CPIN?", serial_port)
        if response is None or "READY" not in response:
            return "unknown"
        return "ready"
    except Exception as e:
        if "Access is denied" in str(e):
            return "access_denied"
        elif "The system cannot find the file specified" in str(e):
            return "file_not_found"
        print(f"Error parsing CPIN: {e}")
        print(traceback.format_exc())
        return None
    
def get_iccid(serial):
    try:
        response = send_at_command_fast_with_serial(serial, "AT+CCID")
        if "OK" not in response:
            return "unknown"
        iccid = response.replace("+CCID: ", "").replace('OK', '').strip()
        if iccid == "":
            return "unknown"
        return iccid
    except Exception as e:
        print(f"Error parsing ICCID: {e}")
        print(traceback.format_exc())
        return None
    
def get_cnum(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+CNUM", serial_port)
        cnum = response.replace("+CNUM: ", "").replace('OK', '').strip()
        if cnum == "":
            return "unknown"
        return cnum
    except Exception as e:
        print(f"Error parsing CNUM: {e}")
        print(traceback.format_exc())
        return None
    

def get_balance(iccid):
    try:
        from microservices.com_manager import ComPort
        # name_func = "[at_command][get_balance]"
        sim = mongo_lite.sim_collection.find_one({"iccid": iccid})
        if not sim:
            logger.error(f"Sim not found for iccid: {iccid}")
            return "sim_not_found"
        if not sim['com_port']:
            return "comport_not_found"
        if "0,1" not in sim['creg'] and "0,5" not in sim['creg']:
            # print(f"Sim is not in home network, com port: {sim['com_port']}")
            return "no_network"
        logger.info(f"================================================")
        logger.info(f"Getting balance for sim: {sim['iccid']}, com port: {sim['com_port']}")
        comport = ComPort(sim["com_port"])
        
        _ = comport.connect()
        if not _:
            logger.error(f"Error connect com port: {sim['com_port']}, delete com port from database")
            sim_db.delete_com_port(iccid)
            return "comport_connect_error"
        check_iccid = comport.check_iccid(iccid)
        if not check_iccid:
            logger.info(f"Comport is not the same as iccid: {iccid}")
            return "comport_check_iccid_error"
        result, time_taken = comport.write('AT+CUSD=1,"*101#",15', timeout=20, expected=("+CUSD:", "ERROR", "+CME ERROR"))
        if result is None:
            logger.error(f"Error getting balance, com port: {sim['com_port']}")
            return "comport_write_error"
        if "+CUSD:" not in result:
            logger.error(f"Error getting balance, com port: {sim['com_port']}, result: {result}")
            return "comport_write_result_error"
        result = "".join(result.splitlines()).replace("+CUSD:", "").strip()
        balance_dict = re_string.balance_to_dict(result, sim['iccid'])
        logger.info(f"Balance: {balance_dict}, com port: {sim['com_port']}")
        comport.disconnect()
        mongo_lite.sim_collection.update_one(
            {"iccid": sim['iccid']},
            {
                "$set": {
                    "balance": balance_dict['balance'],
                    "balance_update_time": datetime.now(tz=timezone.utc),
                    "phone": balance_dict['phone'],
                    "balance_raw": result
                }
            }, upsert=True)
    except Exception as e:
        logger.error(f"Error getting balance: {e}")
        print(traceback.format_exc())
        return None