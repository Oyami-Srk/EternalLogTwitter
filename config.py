from datetime import datetime, timezone, timedelta

# Database connection string
DATABASE_URL = ""

# Timezone
TIMEZONE = timezone(timedelta(hours=8))

# Access token
ACCESS_TOKEN = "test"

# Downloader configuration
GALLERY_DL = {}

# Retry Interval (in seconds)
RETRY_INTERVAL = 10

# Max retries
MAX_RETRIES = 6

# Force start worker
FORCE_START_WORKER = False

# --------------------------------------------------

# Load from yaml file
__loaded = False


def __load_from(file: str):
    global __loaded
    if __loaded:
        return

    print(f"Trying to load config file: {file}.")
    import os
    if not os.path.isfile(file):
        print("Unable to do so, file is not file.")
        return

    import yaml
    import re
    import pytz

    with open(file, encoding="UTF-8") as f:
        data = yaml.safe_load(f)

    global DATABASE_URL, TIMEZONE, ACCESS_TOKEN, GALLERY_DL, RETRY_INTERVAL, FORCE_START_WORKER
    DATABASE_URL = data.get("database", DATABASE_URL)
    TIMEZONE = data.get("timezone", TIMEZONE)
    if isinstance(TIMEZONE, str):
        if TIMEZONE == "UTC":
            TIMEZONE = timezone.utc
        elif re.match(r"UTC[+-]\d{1,2}", TIMEZONE):
            TIMEZONE = timezone(timedelta(hours=int(TIMEZONE[3:])))
        else:
            TIMEZONE = pytz.timezone(TIMEZONE)
    ACCESS_TOKEN = data.get("access-token", ACCESS_TOKEN)
    GALLERY_DL = data.get("gallery-dl", GALLERY_DL)
    RETRY_INTERVAL = data.get("retry-interval", RETRY_INTERVAL)
    FORCE_START_WORKER = data.get("force-start-worker", FORCE_START_WORKER)

    __loaded = True

import os
__load_from(os.environ.get("ELT_CONFIG", "config.yaml"))
