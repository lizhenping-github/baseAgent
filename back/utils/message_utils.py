import json

import orjson
from langchain_core.messages import BaseMessage, message_to_dict, messages_from_dict


def message_to_str(message: BaseMessage) -> str:
    return orjson.dumps(message_to_dict(message)).decode('utf-8')


def messages_from_str(data: str) -> list[BaseMessage]:
    return messages_from_dict(json.loads(data))


def messages_to_str_list(messages: list[BaseMessage]) -> list[str]:
    return [message_to_str(m) for m in messages]


def str_list_to_messages(data_list: list[str]) -> list[BaseMessage]:
    message_dicts = []
    for data in data_list:
        try:
            message_dicts.append(json.loads(data))
        except json.JSONDecodeError:
            pass
    return messages_from_dict(message_dicts)
