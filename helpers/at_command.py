import serial, re, traceback
import time
from typing import Iterable, Optional


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
    
def get_iccid(serial_port):
    try:
        response, time_taken = send_at_command_fast("AT+CCID", serial_port)
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
    

def get_balance(serial_port, iccid):
    try:
        print(f"Getting balance for iccid: {iccid}, port: {serial_port}")
        response, time_taken = send_at_command_fast('AT+CUSD=1,"#101#",15', serial_port)
        print(f"Response: {response}")
        print(f"Time taken: {time_taken}, port: {serial_port}, iccid: {iccid}")
        
    except Exception as e:
        print(f"Error getting balance: {e}")
        print(traceback.format_exc())
        return None