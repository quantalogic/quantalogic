from composio import ComposioToolSet, Action
import json

composio_toolset = ComposioToolSet()

# Get the action schema
action_schema = composio_toolset.get_action_schemas(actions=["GMAIL_SEND_EMAIL"]) 

# Print the parameters in a readable format
print(action_schema)
action_schema = composio_toolset.get_action_schemas(actions=["WEATHERMAP_WEATHER"])
print(action_schema)
action_schema = composio_toolset.get_action_schemas(actions=["GOOGLECALENDAR_CREATE_EVENT"])
print(action_schema)