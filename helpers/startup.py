import os, dotenv

import uuid, platform
dotenv.load_dotenv()
node = uuid.getnode()
mac = ':'.join(['{:02x}'.format((node >> i) & 0xff) for i in range(0, 8*6, 8)][::-1])
unique_id = f"{platform.system()}-{mac}"
os.environ["UNIQUE_ID"] = unique_id.upper()