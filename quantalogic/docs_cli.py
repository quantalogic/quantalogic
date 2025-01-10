import subprocess
import os
import sys

def get_config_path():
    """Get the absolute path to the mkdocs configuration file."""
    return os.path.join(os.path.dirname(os.path.dirname(__file__)), 'mkdocs', 'mkdocs.yml')

def serve_docs():
    """Serve MkDocs documentation locally."""
    config_path = get_config_path()
    try:
        subprocess.run(['mkdocs', 'serve', '--config-file', config_path], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error serving documentation: {e}")
        sys.exit(1)

def build_docs():
    """Build MkDocs documentation."""
    config_path = get_config_path()
    try:
        subprocess.run(['mkdocs', 'build', '--config-file', config_path], check=True)
        print("Documentation built successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error building documentation: {e}")
        sys.exit(1)

def deploy_docs():
    """Deploy MkDocs documentation to GitHub Pages."""
    config_path = get_config_path()
    try:
        subprocess.run(['mkdocs', 'gh-deploy', '--config-file', config_path], check=True)
        print("Documentation deployed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error deploying documentation: {e}")
        sys.exit(1)

# Ensure the script can be run directly for testing
if __name__ == '__main__':
    command = sys.argv[1] if len(sys.argv) > 1 else None
    
    if command == 'serve':
        serve_docs()
    elif command == 'build':
        build_docs()
    elif command == 'deploy':
        deploy_docs()
    else:
        print("Usage: python docs_cli.py [serve|build|deploy]")
        sys.exit(1)
