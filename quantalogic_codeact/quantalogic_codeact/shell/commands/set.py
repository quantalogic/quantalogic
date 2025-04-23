from dataclasses import fields, is_dataclass
from typing import List, Union, get_args, get_origin

from yaml import safe_load

from ...codeact.agent import Agent
from ..agent_state import AgentState


async def set_command(shell, args: List[str]) -> str:
    """Set a configuration field and switch to a new agent: /set <field> <value>
    
    Args:
        shell: The Shell instance.
        args: List containing field name and value (e.g., ['model', 'deepseek/deepseek-chat']).
    
    Returns:
        str: Result message.
    """
    if len(args) < 2:
        return "Usage: /set <field> <value>"

    field_name = args[0]
    value_str = " ".join(args[1:])
    current_config = shell.current_agent.config

    # Get valid fields from AgentConfig
    field_dict = {f.name: f for f in fields(current_config)}
    if field_name not in field_dict:
        return f"Invalid field: {field_name}. Use /config show to see available fields."

    field = field_dict[field_name]
    field_type = field.type

    # Generic support for complex types via YAML or literal mapping/list
    try:
        # Handle quoted YAML literals (e.g. "/set personality '{traits: a,b}'")
        val_to_parse = value_str
        if len(val_to_parse) > 1 and ((val_to_parse[0] == val_to_parse[-1] == '"') or (val_to_parse[0] == val_to_parse[-1] == "'")):
            val_to_parse = val_to_parse[1:-1]
        parsed = safe_load(val_to_parse) if val_to_parse else None
    except Exception:
        parsed = None
    if isinstance(parsed, (dict, list)) or (is_dataclass(field_type) and isinstance(parsed, dict)):
        # Instantiate dataclass or assign list/dict directly
        if is_dataclass(field_type):
            # Special-case personality comma-separated traits
            if field_name == 'personality' and isinstance(parsed, dict):
                traits = parsed.get('traits')
                if isinstance(traits, str):
                    parsed['traits'] = [t.strip() for t in traits.split(',') if t.strip()]
            try:
                value = field_type(**parsed)
            except Exception:
                return f"Invalid mapping for {field_name}; expected keys for {field_type.__name__}."
        else:
            value = parsed
        # Create new config and agent
        new_conf = {f.name: getattr(current_config, f.name) for f in field_dict.values()}
        new_conf[field_name] = value
        new_cfg = type(current_config)(**new_conf)
        new_agent = Agent(config=new_cfg)
        new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
        i = 1
        while f"agent_{i}" in shell.agents:
            i += 1
        name = f"agent_{i}"
        shell.agents[name] = AgentState(agent=new_agent)
        shell.current_agent_name = name
        return f"Created and switched to new agent: {name} with {field_name} set to {value}"

    try:
        # Convert value based on field type, supporting Optional
        origin = get_origin(field_type)
        if origin is Union and type(None) in get_args(field_type):
            inner_types = [t for t in get_args(field_type) if t is not type(None)]
            inner_type = inner_types[0] if inner_types else None
            # Handle None literal
            if value_str.lower() in ["none", "null"]:
                value = None
            else:
                t = inner_type
                if t is str:
                    value = value_str
                elif t is int:
                    value = int(value_str)
                elif t is float:
                    value = float(value_str)
                elif t is bool:
                    value = value_str.lower() in ["true", "1", "yes"]
                elif t is list:
                    value = value_str.split()
                else:
                    return f"Setting field '{field_name}' of type {field_type} is not supported via /set. Use /config save and edit the file."
        else:
            if field_type is str:
                value = value_str
            elif field_type is int:
                value = int(value_str)
            elif field_type is float:
                value = float(value_str)
            elif field_type is bool:
                value = value_str.lower() in ["true", "1", "yes"]
            elif field_type is list:
                value = value_str.split()
            else:
                return f"Setting field '{field_name}' of type {field_type} is not supported via /set. Use /config save and edit the file."

        # Create a new config with the updated field
        new_config_dict = {f.name: getattr(current_config, f.name) for f in field_dict.values()}
        new_config_dict[field_name] = value
        new_config = type(current_config)(**new_config_dict)

        # Create and register a new agent
        new_agent = Agent(config=new_config)
        new_agent.add_observer(shell._stream_token_observer, ["StreamToken"])
        
        # Generate a unique name
        base_name = "agent"
        index = 1
        while f"{base_name}_{index}" in shell.agents:
            index += 1
        name = f"{base_name}_{index}"
        
        shell.agents[name] = AgentState(agent=new_agent)
        shell.current_agent_name = name
        
        return f"Created and switched to new agent: {name} with {field_name} set to {value}"
    except ValueError as e:
        return f"Invalid value for {field_name}: {e}"
    except Exception as e:
        return f"Error setting {field_name}: {e}"