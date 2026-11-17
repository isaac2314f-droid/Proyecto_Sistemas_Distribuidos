import csv
import json
import sys
from time import perf_counter, sleep
from urllib.error import HTTPError
from urllib.request import Request, urlopen

SENDER = "http://chat:8000"
RECEIVER = "http://chat-b:8000"
USERNAME = "experimento"
REPETITIONS = 3
MESSAGES_PER_REPETITION = 10
POLL_SECONDS = 0.05
TIMEOUT_SECONDS = 15


def request_json(url, payload=None):
    if payload is None:
        request = Request(url)
    else:
        request = Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    with urlopen(request, timeout=3) as response:
        return json.load(response)


def register_sender():
    try:
        request_json(f"{SENDER}/users", {"username": USERNAME})
    except HTTPError as error:
        if error.code != 409:
            raise
        error.close()


def measure_message(body):
    started = perf_counter()
    sent = request_json(
        f"{SENDER}/messages",
        {"username": USERNAME, "body": body},
    )
    message_id = sent["id"]

    while perf_counter() - started < TIMEOUT_SECONDS:
        messages = request_json(f"{RECEIVER}/messages")
        if any(message["id"] == message_id for message in messages):
            elapsed_ms = (perf_counter() - started) * 1000
            return message_id, elapsed_ms
        sleep(POLL_SECONDS)

    raise TimeoutError(f"g3b no mostro el mensaje {message_id} en {TIMEOUT_SECONDS} s")


def main():
    register_sender()
    measure_message("calentamiento de latencia")

    rows = []
    for repetition in range(1, REPETITIONS + 1):
        for number in range(1, MESSAGES_PER_REPETITION + 1):
            message_id, elapsed_ms = measure_message(f"latencia {repetition}-{number}")
            rows.append((repetition, number, message_id, f"{elapsed_ms:.2f}"))

    writer = csv.writer(sys.stdout)
    writer.writerow(("repeticion", "mensaje", "id", "latencia_ms"))
    writer.writerows(rows)


if __name__ == "__main__":
    main()