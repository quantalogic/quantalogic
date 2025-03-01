"""Tool for cloning Bitbucket repositories using Repository Access Tokens.

Following Bitbucket's official documentation for Repository Access Tokens:
https://support.atlassian.com/bitbucket-cloud/docs/using-repository-access-tokens/
"""

import os
import shutil
from pathlib import Path
from typing import Optional

from git import Repo
from git.exc import GitCommandError
from loguru import logger
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument

# Base directory for all cloned repositories
BITBUCKET_REPOS_BASE_DIR = "/tmp/bitbucket_repos"

class BitbucketCloneTool(Tool):
    """Tool for cloning Bitbucket repositories using Repository Access Tokens."""

    name: str = "bitbucket_clone_tool"
    description: str = (
        "Clones a Bitbucket repository using Repository Access Token authentication. "
        "Requires a token with 'Repository Read' and 'Repository Write' permissions."
    )
    need_validation: bool = False
    access_token: Optional[str] = Field(
        default=None,
        description="Bitbucket Repository Access Token. Must have 'Repository Read' and 'Repository Write' permissions."
    )

    def __init__(self, access_token: Optional[str] = None, **data):
        """Initialize the tool with a Bitbucket Repository Access Token."""
        super().__init__(**data)
        # Treat empty string as None
        self.access_token = access_token if access_token and access_token.strip() else None
        logger.info(f"BitbucketCloneTool initialized with access token: {'provided' if self.access_token else 'not provided'}")
        
        # Add token validation logging
        if self.access_token:
            logger.info(f"Access token provided, length: {len(self.access_token)}")
            logger.info(f"First 4 chars of token (masked): {self.access_token[:4]}***")
        else:
            logger.warning("No access token provided during initialization")

    arguments: list = [
        ToolArgument(
            name="repo_url",
            arg_type="string",
            description="The URL of the Bitbucket repository to clone (HTTPS format)",
            required=True,
            example="https://bitbucket.org/workspace/repository.git",
        ),
        ToolArgument(
            name="target_path",
            arg_type="string",
            description="The local path where the repository should be cloned",
            required=True,
            example="/tmp/bitbucket_repos/repo_name",
        ),
        ToolArgument(
            name="branch",
            arg_type="string",
            description="Specific branch to clone (defaults to main/master)",
            required=False,
            default="main",
        ),
    ]

    def _prepare_directory(self, path: str) -> None:
        """Prepare the target directory for cloning."""
        path = os.path.abspath(path)
        if not path.startswith(BITBUCKET_REPOS_BASE_DIR):
            raise ValueError(f"Target path must be within {BITBUCKET_REPOS_BASE_DIR}")
        
        os.makedirs(BITBUCKET_REPOS_BASE_DIR, exist_ok=True)
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
        logger.debug(f"Prepared directory: {path}")

    def _get_clone_url(self, repo_url: str) -> str:
        """Get the proper clone URL with Repository Access Token authentication.
        
        Following Bitbucket's official format:
        https://x-token-auth:{repository_access_token}@bitbucket.org/{workspace}/{repository}.git
        """
        # Log token state at URL construction
        logger.debug(f"Token state in _get_clone_url: {'present' if self.access_token else 'missing'}")
        if self.access_token:
            logger.debug(f"Token length: {len(self.access_token)}")
        
        logger.debug(f"Original URL: {repo_url}")
        
        # Remove /src/branch/ if present (from web URLs)
        if '/src/' in repo_url:
            repo_url = repo_url.split('/src/')[0]
            logger.debug(f"URL after removing /src/: {repo_url}")
        
        # Ensure URL ends with .git
        if not repo_url.endswith('.git'):
            repo_url = f"{repo_url}.git"
            logger.debug(f"URL after adding .git: {repo_url}")

        # Add authentication using the official Bitbucket format
        if self.access_token and self.access_token.strip():
            # First, extract the workspace and repository from the URL
            parts = repo_url.split('bitbucket.org/')
            if len(parts) != 2:
                raise ValueError("Invalid Bitbucket URL format")
            
            workspace_repo = parts[1].rstrip('.git')
            # Construct the URL exactly as per Bitbucket docs
            clone_url = f"https://x-token-auth:{self.access_token}@bitbucket.org/{workspace_repo}.git"
            logger.debug("Added Repository Access Token authentication to clone URL")
            logger.debug(f"Final URL format (token masked): {clone_url.replace(self.access_token, '***')}")
            return clone_url
        
        logger.debug("No token provided, using public URL")
        return repo_url

    def execute(self, **kwargs) -> str:
        """Execute the repository cloning operation using Repository Access Token."""
        # Log token state at execution start
        logger.debug("=== Token Tracing ===")
        logger.debug(f"Token present at execute start: {bool(self.access_token)}")
        if self.access_token:
            logger.debug(f"Token length at execute: {len(self.access_token)}")
            logger.debug(f"Token first 4 chars (masked): {self.access_token[:4]}***")
        else:
            logger.warning("No access token available during execution")
        logger.debug("==================")

        repo_url = kwargs.get("repo_url")
        target_path = kwargs.get("target_path")
        branch = kwargs.get("branch", "main")
        
        if not repo_url or not target_path:
            raise ValueError("Both repo_url and target_path are required")
        
        try:
            logger.info(f"Starting clone of {repo_url} to {target_path}")
            self._prepare_directory(target_path)
            
            clone_url = self._get_clone_url(repo_url)
            
            # Log environment before clone
            logger.debug("=== Clone Environment ===")
            logger.debug(f"Branch: {branch}")
            logger.debug(f"Target path: {target_path}")
            logger.debug("======================")
            
            # Clone with authentication disabled to prevent prompts
            repo = Repo.clone_from(
                clone_url,
                target_path,
                branch=branch,
                env={"GIT_TERMINAL_PROMPT": "0"}
            )
            
            logger.info(f"Successfully cloned repository to {target_path}")
            return f"Repository successfully cloned to {target_path}"
            
        except GitCommandError as e:
            error_msg = str(e)
            if self.access_token:
                error_msg = error_msg.replace(self.access_token, '***')
            logger.error(f"Git command error: {error_msg}")
            raise GitCommandError("git clone", error_msg)
        
        except Exception as e:
            logger.error(f"Error during repository cloning: {str(e)}")
            raise

if __name__ == "__main__":
    tool = BitbucketCloneTool(access_token="your_access_token_here")
    print(tool.to_markdown())
