import json
import random
import re
from xml.etree import ElementTree as ET


def trim_excess_newlines(content: str | list) -> str | list:
    if isinstance(content, list):
        result = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                item["text"] = _trim_text_newlines(item.get("text", ""))
            result.append(item)
        return result
    return _trim_text_newlines(content)


def _trim_text_newlines(text: str) -> str:
    if not isinstance(text, str):
        return text
    stripped = text.rstrip('\n')
    original_trailing = len(text) - len(stripped)
    if original_trailing <= 2:
        return text
    return stripped + '\n' * 2


def generate_tool_id(tool_name: str, index: int) -> str:
    return f"call_{index}_{tool_name}"


def replace_placeholder(value: str, context: dict) -> str:
    result = value
    for key, val in context.items():
        result = result.replace("{" + key + "}", str(val))
    return result


def extract_function_calls(text: str) -> list[dict]:
    tool_calls = []
    pattern = r'<function_calls>.*?</function_calls>'
    blocks = re.findall(pattern, text, re.DOTALL)

    for block in blocks:
        try:
            root = ET.fromstring(block)
            for invoke_elem in root.findall('.//invoke'):
                tool_call = {"type": "tool_call", "id": None}
                tool_name = invoke_elem.get('name')
                if tool_name:
                    tool_call["name"] = tool_name

                args_dict = {}
                for param_elem in invoke_elem.findall('.//parameter'):
                    param_name = param_elem.get('name')
                    param_value = param_elem.text
                    if not param_name:
                        continue
                    string_attr = param_elem.get('string')
                    if string_attr == 'true' and param_value:
                        args_dict[param_name] = param_value.strip()
                    else:
                        try:
                            if param_value:
                                args_dict[param_name] = json.loads(param_value)
                        except json.JSONDecodeError:
                            args_dict[param_name] = param_value
                tool_call["args"] = args_dict
                tool_calls.append(tool_call)
        except ET.ParseError:
            tool_call = _extract_with_regex(block)
            if tool_call:
                tool_calls.append(tool_call)

    return tool_calls


def extract_and_format_function_calls(text: str, generate_ids: bool = True) -> list[dict]:
    tool_calls = extract_function_calls(text)
    if generate_ids:
        for _i, tool_call in enumerate(tool_calls):
            random_id = ''.join(random.choices('0123456789abcdef', k=6))
            tool_call["id"] = f"call_{tool_call.get('name', 'unknown')}_{random_id}"
    return tool_calls


def _extract_with_regex(block: str) -> dict | None:
    name_match = re.search(r'<invoke\s+name="([^"]+)"', block)
    if not name_match:
        return None

    tool_call = {"name": name_match.group(1), "type": "tool_call", "id": None, "args": {}}
    param_pattern = r'<parameter\s+name="([^"]+)"(?:\s+string="([^"]+)")?>(.*?)</parameter>'
    for param_name, string_type, param_value in re.findall(param_pattern, block, re.DOTALL):
        if not param_value:
            continue
        cleaned = param_value.strip()
        if string_type == 'true':
            tool_call["args"][param_name] = cleaned
        else:
            try:
                tool_call["args"][param_name] = json.loads(cleaned)
            except json.JSONDecodeError:
                tool_call["args"][param_name] = cleaned
    return tool_call
