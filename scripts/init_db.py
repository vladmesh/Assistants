#!/usr/bin/env python3
import sys
from typing import Dict, List, Optional, TypedDict

import requests
import yaml  # Use PyYAML

API_URL = "http://localhost:8000/api"
TEMPLATE_FILE = "scripts/assistants_template.yaml" # Updated file path


class AssistantTemplateData(TypedDict):
    name: str
    description: str
    instructions: str
    model: str
    is_secretary: bool
    assistant_type: str


def parse_assistant_templates(filename: str) -> List[AssistantTemplateData]:
    """Parses the YAML template file to extract assistant details."""
    print(f"Parsing YAML template file: {filename}")
    try:
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            # Basic validation
            if not isinstance(data, dict) or "assistants" not in data:
                print(f"Error: Invalid YAML format. Expected a dictionary with an 'assistants' key.", file=sys.stderr)
                sys.exit(1)
            assistants = data["assistants"]
            if not isinstance(assistants, list):
                 print(f"Error: Invalid YAML format. 'assistants' should be a list.", file=sys.stderr)
                 sys.exit(1)
            # Further validation could be added here (e.g., check required fields)
            print(f"Parsed {len(assistants)} assistant templates.")
            return assistants
    except FileNotFoundError:
        print(f"Error: Template file '{filename}' not found.", file=sys.stderr)
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{filename}': {e}", file=sys.stderr)
        sys.exit(1)


def make_request(
    method: str, endpoint: str, data: Optional[Dict] = None
) -> Dict | List:
    """Helper function to make requests to the API."""
    url = f"{API_URL}{endpoint}"
    try:
        response = requests.request(method, url, json=data, timeout=10)
        response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
        # Handle cases where response might be successful but empty (e.g., 204 No Content)
        if response.status_code == 204:
            return {}
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error making request to {method} {url}: {e}", file=sys.stderr)
        print(f"Response body: {e.response.text if e.response else 'No response'}", file=sys.stderr)
        sys.exit(1)


def get_existing_tool_id(name: str) -> Optional[str]:
    """Return existing tool ID if a tool with the given name exists."""
    tools = make_request("GET", "/tools/")
    if isinstance(tools, list):
        for tool in tools:
            if tool.get("name") == name and tool.get("id"):
                return str(tool["id"])
    return None


def get_existing_assistant_id(name: str) -> Optional[str]:
    """Return existing assistant ID if an assistant with the given name exists."""
    assistants = make_request("GET", "/assistants/")
    if isinstance(assistants, list):
        for assistant in assistants:
            if assistant.get("name") == name and assistant.get("id"):
                return str(assistant["id"])
    return None


def assistant_has_tool(assistant_id: str, tool_id: str) -> bool:
    """Check if an assistant already has the tool linked."""
    tools = make_request("GET", f"/assistants/{assistant_id}/tools")
    if isinstance(tools, list):
        for tool in tools:
            if str(tool.get("id")) == tool_id:
                return True
    return False


def create_tool(name: str, tool_type: str, description: str) -> str:
    """Creates a tool via API and returns its ID."""
    print(f"Create tool: {name} ({tool_type})")
    existing_id = get_existing_tool_id(name)
    if existing_id:
        print(f"  -> already exists ({existing_id})")
        return existing_id
    payload = {
        "name": name,
        "tool_type": tool_type,
        "description": description,
    }
    # Specific handling for sub_assistant if needed in the future
    # if tool_type == "sub_assistant":
    #     payload["assistant_id"] = assistant_id
    try:
        result = make_request("POST", "/tools/", data=payload)
        tool_id = result["id"]
        print(f"  -> {tool_id}")
        return tool_id
    except KeyError:
        print(f"Error: 'id' not found in response for creating tool {name}.", file=sys.stderr)
        print(f"Response: {result}", file=sys.stderr)
        sys.exit(1)


def create_assistant(
    name: str,
    instructions: str,
    description: str,
    is_secretary: bool,
    model: str,
    assistant_type: str,
) -> str:
    """Creates an assistant via API and returns its ID."""
    print(f"Create assistant: {name} (Secretary: {is_secretary})")
    existing_id = get_existing_assistant_id(name)
    if existing_id:
        print(f"  -> already exists ({existing_id})")
        return existing_id
    payload = {
        "name": name,
        "is_secretary": is_secretary,
        "model": model,
        "instructions": instructions,
        "description": description,
        "assistant_type": assistant_type,
        "is_active": True,
    }
    try:
        result = make_request("POST", "/assistants/", data=payload)
        assistant_id = result["id"]
        print(f"  -> {assistant_id}")
        return assistant_id
    except KeyError:
        print(f"Error: 'id' not found in response for creating assistant {name}.", file=sys.stderr)
        print(f"Response: {result}", file=sys.stderr)
        sys.exit(1)


def link_tool_to_assistant(assistant_id: str, tool_id: str):
    """Links a tool to an assistant via API."""
    print(f"Link tool {tool_id} to assistant {assistant_id}")
    if assistant_has_tool(assistant_id, tool_id):
        print("  -> already linked, skipping")
        return
    make_request("POST", f"/assistants/{assistant_id}/tools/{tool_id}")


def main():
    try:
        pass
    except ImportError:
        print("Error: PyYAML library not found. Please install it: pip install pyyaml", file=sys.stderr)
        sys.exit(1)

    print("Parsing assistant templates from YAML...")
    assistant_templates = parse_assistant_templates(TEMPLATE_FILE)

    print("\n=== Creating base tools ===")
    tool_ids = []
    tool_ids.append(
        create_tool("calendar_create", "calendar", "Creates calendar events")
    )
    tool_ids.append(
        create_tool("calendar_list", "calendar", "Lists calendar events")
    )
    tool_ids.append(
        create_tool(
            "reminder_create",
            "reminder_create",
            "Используй чтобы создать напоминание",
        )
    )
    tool_ids.append(
        create_tool(
            "reminder_list",
            "reminder_list",
            "Получает список активных напоминаний пользователя",
        )
    )
    tool_ids.append(
        create_tool(
            "reminder_delete",
            "reminder_delete",
            "Удаляет существующее напоминание по идентификатору",
        )
    )
    tool_ids.append(create_tool("time", "time", "Возвращает текущее время"))
    tool_ids.append(
        create_tool(
            "memory_save",
            "memory_save",
            "Сохраняет факты о пользователе в память",
        )
    )
    tool_ids.append(
        create_tool(
            "memory_search",
            "memory_search",
            "Ищет сохраненные факты о пользователе",
        )
    )
    tool_ids.append(
        create_tool("web_search", "web_search", "Performs a web search")
    )

    # Create the assistants (now secretaries) from the template
    print(f"\n=== Creating SECRETARY assistants from template: {[t['name'] for t in assistant_templates]} ===")
    secretary_ids = []
    for template in assistant_templates:
        # Validate required fields from template
        required_keys = ["name", "instructions", "description", "is_secretary", "model", "assistant_type"]
        if not all(key in template for key in required_keys):
            print(f"Error: Template for '{template.get('name', 'UNKNOWN')}' is missing required fields.", file=sys.stderr)
            continue # Skip this template

        # Ensure is_secretary is explicitly True for these
        if not template["is_secretary"]:
             print(f"Warning: Template for '{template['name']}' has is_secretary=false. Setting to true.", file=sys.stderr)

        assistant_id = create_assistant(
            name=template["name"],
            instructions=template["instructions"],
            description=template["description"],
            is_secretary=True, # Explicitly set to True
            model=template["model"],
            assistant_type=template["assistant_type"],
        )
        secretary_ids.append(assistant_id)

    if not secretary_ids:
        print("Error: No secretary assistants were created from templates.", file=sys.stderr)
        sys.exit(1)

    print("\n=== Linking all BASE tools to each secretary ===")
    for sec_id in secretary_ids:
        for tool_id in tool_ids:
            link_tool_to_assistant(sec_id, tool_id)

    print("\n=== Done ===")


if __name__ == "__main__":
    main() 