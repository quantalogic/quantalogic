"""Tool for cloning Git repositories with support for both public and private repositories."""

import os
import shutil
from pathlib import Path

import requests
from git import Repo
from git.exc import GitCommandError
from loguru import logger
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument

# Base directory for all cloned repositories
GITHUB_REPOS_BASE_DIR = "/tmp/github_repos"

class CloneRepoTool(Tool):
    """Tool for cloning Git repositories."""

    name: str = "clone_repo_tool"
    description: str = (
        "Clones a Git repository (public or private) to a specified location. "
        "Automatically handles authentication for private repositories using the provided token."
    )
    need_validation: bool = False
    auth_token: str = Field(default=None, description="GitHub authentication token for private repositories")

    def __init__(self, auth_token: str = None, **data):
        """Initialize the tool with an optional auth token.
        
        Args:
            auth_token: GitHub authentication token for private repositories
            **data: Additional tool configuration data
        """
        super().__init__(**data)
        self.auth_token = auth_token

    arguments: list = [
        ToolArgument(
            name="repo_url",
            arg_type="string",
            description="The URL of the Git repository to clone (HTTPS format)",
            required=True,
            example="https://github.com/username/repo.git",
        ),
        ToolArgument(
            name="target_path",
            arg_type="string",
            description="The local path where the repository should be cloned (must be within /tmp/github_repos)",
            required=True,
            example="/tmp/github_repos/repo_name",
        ),
        ToolArgument(
            name="branch",
            arg_type="string",
            description="Specific branch to clone (defaults to main/master)",
            required=False,
            default="main",
        ),
    ]

    def is_private_repo(self, repo_url: str) -> bool:
        """Check if a GitHub repository is private.
        
        Args:
            repo_url: Repository URL in format https://github.com/username/repo.git
        
        Returns:
            bool: True if repository is private, False otherwise
        """
        try:
            # Extract owner and repo name from URL
            parts = repo_url.rstrip(".git").split("/")
            owner, repo = parts[-2], parts[-1]
            
            # Try to access repo info without token first
            response = requests.get(f"https://api.github.com/repos/{owner}/{repo}")
            
            if response.status_code == 404 and self.auth_token:
                # Try again with token
                headers = {"Authorization": f"token {self.auth_token}"}
                response = requests.get(
                    f"https://api.github.com/repos/{owner}/{repo}",
                    headers=headers
                )
                return response.status_code == 200  # If accessible with token, it's private
            
            return False  # Repository is public
            
        except Exception as e:
            logger.warning(f"Error checking repository visibility: {str(e)}")
            return True  # Assume private if can't determine

    def _prepare_target_directory(self, target_path: str) -> None:
        """Prepare the target directory for cloning.
        
        Ensures the target directory is within GITHUB_REPOS_BASE_DIR and prepares it for cloning.
        
        Args:
            target_path: Path where the repository will be cloned
            
        Raises:
            ValueError: If the target path is not within GITHUB_REPOS_BASE_DIR
        """
        # Ensure base directory exists
        os.makedirs(GITHUB_REPOS_BASE_DIR, exist_ok=True)
        
        # Convert to absolute path and ensure it's within GITHUB_REPOS_BASE_DIR
        abs_target = os.path.abspath(target_path)
        if not abs_target.startswith(GITHUB_REPOS_BASE_DIR):
            raise ValueError(f"Target directory must be within {GITHUB_REPOS_BASE_DIR}")
        
        if os.path.exists(target_path):
            logger.info(f"Target directory exists, removing: {target_path}")
            try:
                # Remove directory and all its contents
                shutil.rmtree(target_path)
            except Exception as e:
                logger.error(f"Error removing existing directory: {str(e)}")
                raise ValueError(f"Failed to remove existing directory: {str(e)}")
        
        # Create new empty directory
        os.makedirs(target_path, exist_ok=True)
        logger.info(f"Created clean target directory: {target_path}")

    def execute(self, repo_url: str, target_path: str, branch: str = "main") -> str:
        """Clones a Git repository to the specified path within GITHUB_REPOS_BASE_DIR.

        Args:
            repo_url: URL of the Git repository
            target_path: Local path where to clone the repository (must be within GITHUB_REPOS_BASE_DIR)
            branch: Branch to clone (defaults to main)

        Returns:
            str: Path where the repository was cloned

        Raises:
            GitCommandError: If there's an error during cloning
            ValueError: If the parameters are invalid or target_path is outside GITHUB_REPOS_BASE_DIR
        """
        try:
            # Ensure target_path is within GITHUB_REPOS_BASE_DIR
            if not os.path.abspath(target_path).startswith(GITHUB_REPOS_BASE_DIR):
                target_path = os.path.join(GITHUB_REPOS_BASE_DIR, os.path.basename(target_path))
                logger.info(f"Adjusting target path to: {target_path}")

            # Prepare target directory (remove if exists and create new)
            self._prepare_target_directory(target_path)

            # Check if repo is private and token is needed
            is_private = self.is_private_repo(repo_url)
            
            if is_private and not self.auth_token:
                raise ValueError("Authentication token required for private repository")
            
            # Prepare the clone URL with auth token if needed
            clone_url = repo_url
            if is_private and self.auth_token:
                clone_url = repo_url.replace("https://", f"https://{self.auth_token}@")

            logger.info(f"Cloning repository to {target_path}")
            
            # Clone the repository
            repo = Repo.clone_from(
                url=clone_url,
                to_path=target_path,
                branch=branch,
            )

            logger.info(f"Successfully cloned repository to {target_path}")
            return f"Repository successfully cloned to: {target_path}"

        except GitCommandError as e:
            error_msg = str(e)
            # Remove sensitive information from error message if present
            if self.auth_token:
                error_msg = error_msg.replace(self.auth_token, "***")
            logger.error(f"Failed to clone repository: {error_msg}")
            raise GitCommandError(f"Failed to clone repository: {error_msg}", e.status)
        
        except Exception as e:
            logger.error(f"An error occurred while cloning the repository: {str(e)}")
            raise ValueError(f"An error occurred while cloning the repository: {str(e)}")


if __name__ == "__main__":
    tool = CloneRepoTool(auth_token="your_token_here")
    print(tool.to_markdown())
