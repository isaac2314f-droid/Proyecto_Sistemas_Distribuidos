from urllib.request import urlopen

from pydantic import TypeAdapter

from inbox import FederatedMessage, receive_message

history_adapter = TypeAdapter(list[FederatedMessage])


def recover_history(central_url):
    with urlopen(f"{central_url}/history?since=0", timeout=3) as response:
        messages = history_adapter.validate_json(response.read())

    for message in messages:
        receive_message(message)

    return len(messages)