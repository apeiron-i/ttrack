# settings.py

from datetime import time

# Define your tracked clients and their working requirements
CLIENT_QUOTAS = {
    "sandisk": {
        "weekly_schedule": {
            0: 8.5,  # Monday
            1: 8.5,  # Tuesday
            2: 8.5,  # Wednesday
            3: 8.5,  # Thursday
            4: 8.0,  # Friday
            # 5/6 (Saturday/Sunday) excluded automatically
        },
        "enabled": True,
    },
    # You can add others here if needed:
    # "studio": {
    #     "weekly_schedule": {0: 8.0, 1: 8.0, 2: 8.0, 3: 8.0, 4: 8.0},
    #     "enabled": False,
    # }
}

HOLIDAY_FILE = "holidays.txt"
