import re
import traceback

def balance_to_dict(string, iccid):
    try:
        res = {}
        phone_pattern = re.compile(r'(\+84\d{9,10})')
        phone = phone_pattern.search(string)
        phone = phone.group(1) if phone else None
        res["phone"] = phone
        balance_pattern = re.compile(r'TKC\s+(\d+)\s*(?:VND|d)', re.IGNORECASE)
        balance = balance_pattern.search(string)
        balance = balance.group(1) if balance else None
        res["balance"] = balance
        return res
    except Exception as e:
        print(f"Error parsing balance: {e}")
        print(traceback.format_exc())
        return {
            "phone": None,
            "balance": None,
            "error": str(e),
            "data": string
        }