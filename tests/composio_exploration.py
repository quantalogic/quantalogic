#!/usr/bin/env python3
"""
Script to explore Composio functionality and manage connected accounts.
"""

import os
from pprint import pprint
from typing import List
from composio import ComposioToolSet, Action
from composio.client.collections import ConnectedAccountModel

# Initialize Composio client with your API key
api_key = os.getenv("COMPOSIO_API_KEY", "95vfbyvfe1r6chz93o2bgq")
toolset = ComposioToolSet(api_key=api_key)

def list_connected_accounts():
    """List all connected accounts."""
    print("\n=== Connected Accounts ===")
    accounts = toolset.client.connected_accounts.get()
    for account in accounts:
        print(f"App: {account.appUniqueId}")
        print(f"ID: {account.id}")
        print(f"Created: {account.createdAt}")
        print("---")
    return accounts

def list_all_tools():
    """List all available tools in Composio."""
    print("\n=== Available Tools ===")
    try:
        # Get all apps
        apps = toolset.client.apps.get()
        print(f"\nFound {len(apps)} apps:")
        
        # Sort apps by name for better readability
        sorted_apps = sorted(apps, key=lambda x: x.name.lower() if hasattr(x, 'name') else '')
        
        for app in sorted_apps:
            try:
                print(f"\nApp: {app.name}")
                if hasattr(app, 'display_name'):
                    print(f"Display Name: {app.display_name}")
                if hasattr(app, 'description'):
                    print(f"Description: {app.description}")
                if hasattr(app, 'logo'):
                    print(f"Logo: {app.logo}")
                
                # Get actions for this app
                try:
                    actions = toolset.client.actions.get()
                    app_actions = [a for a in actions if hasattr(a, 'appName') and a.appName.lower() == app.name.lower()]
                    if app_actions:
                        print("Actions:")
                        for action in app_actions:
                            print(f"  - {action.name}")
                            if hasattr(action, 'description'):
                                print(f"    Description: {action.description}")
                except Exception as e:
                    print(f"  Error getting actions: {str(e)}")
            except Exception as e:
                print(f"Error processing app {app.name if hasattr(app, 'name') else 'unknown'}: {str(e)}")
            print("---")
        return apps
    except Exception as e:
        print(f"Error listing tools: {str(e)}")
        return []

def remove_all_connected_accounts():
    """Remove all connected accounts."""
    print("\n=== Removing All Connected Accounts ===")
    accounts = toolset.client.connected_accounts.get()
    for account in accounts:
        try:
            print(f"Removing {account.appUniqueId} (ID: {account.id})...")
            toolset.client.connected_accounts.delete(account.id)
            print(f"✓ Successfully removed {account.appUniqueId}")
        except Exception as e:
            print(f"✗ Error removing {account.appUniqueId}: {str(e)}")

def remove_app_connections(app_name: str):
    """Remove all connections for a specific app."""
    print(f"\n=== Removing All {app_name} Connections ===")
    accounts = toolset.client.connected_accounts.get()
    removed = 0
    
    for account in accounts:
        if account.appUniqueId.lower() == app_name.lower():
            try:
                print(f"Removing connection (ID: {account.id})...")
                toolset.client.connected_accounts.delete(account.id)
                removed += 1
                print("✓ Successfully removed")
            except Exception as e:
                print(f"✗ Error: {str(e)}")
    
    print(f"\nRemoved {removed} connection(s) for {app_name}")

def get_action_details(action_name: str):
    """Get detailed information about a specific action."""
    print(f"\n=== Action Details for {action_name} ===")
    try:
        action = Action(action_name)
        schemas = toolset.get_action_schemas(actions=[action])
        for schema in schemas:
            print("\nSchema:")
            pprint(schema.model_dump())
    except Exception as e:
        print(f"Error getting action details: {str(e)}")

def get_available_actions():
    """Get all available actions from Composio."""
    print("\n=== Available Actions ===")
    try:
        # Get all actions using the client API
        actions = toolset.client.actions.get()
        for action in actions:
            print(f"\nAction: {action.name}")
            print(f"App: {action.app}")
            print(f"Description: {action.description if hasattr(action, 'description') else 'No description'}")
            print("Parameters:", action.parameters if hasattr(action, 'parameters') else 'No parameters')
            print("---")
        return actions
    except Exception as e:
        print(f"Error getting actions: {str(e)}")
        return []

def get_action_details(action_name: str):
    """Get detailed information about a specific action."""
    print(f"\n=== Action Details for {action_name} ===")
    try:
        action = Action(action_name)
        schemas = toolset.get_action_schemas(actions=[action])
        for schema in schemas:
            print("\nSchema:")
            pprint(schema.model_dump())
    except Exception as e:
        print(f"Error getting action details: {str(e)}")

def remove_connected_account(account_id: str):
    """Remove a specific connected account."""
    try:
        toolset.client.connected_accounts.delete(account_id)
        print(f"Successfully removed account: {account_id}")
    except Exception as e:
        print(f"Error removing account: {str(e)}")

if __name__ == "__main__":
    print("=== Composio Explorer ===")
    
    # List connected accounts
    accounts = list_connected_accounts()
    
    # Get available actions
    # actions = get_available_actions()
    
    # Example: Get details for specific actions
    get_action_details("gmail_send_email")
    get_action_details("WEATHERMAP_WEATHER")
    get_action_details("SQLTOOL_SQL_QUERY")
    get_action_details("googlecalendar_create_event")
    
    # Example: Remove a specific account
    # Uncomment and replace with actual account ID to remove
    # remove_connected_account("account-id-here")
    
    print("\nDone!")
