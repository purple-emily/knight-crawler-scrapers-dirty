from datetime import timedelta


def readable_timedelta(duration: timedelta):
    data = {}
    data["days"], remaining = divmod(duration.total_seconds(), 86_400)
    data["hours"], remaining = divmod(remaining, 3_600)
    data["minutes"], data["seconds"] = divmod(remaining, 60)

    time_parts = [f"{round(value)} {name}" for name, value in data.items() if value > 0]
    if time_parts:
        return " ".join(time_parts)
    else:
        return "below 1 second"
