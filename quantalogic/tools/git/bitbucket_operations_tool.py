"""Tool for performing Bitbucket operations including cloning, branch management, and commits.

This tool provides a comprehensive interface for Bitbucket operations, supporting both
public and private repositories through Repository Access Token authentication.
"""

import os
import re
import shutil
from pathlib import Path
from typing import ClassVar, Dict, List, Optional
from urllib.parse import urlparse

from git import Repo
from git.exc import GitCommandError
from loguru import logger
from pydantic import Field, validator

from quantalogic.tools.tool import Tool, ToolArgument

# Base directory for all Bitbucket repositories
BITBUCKET_REPOS_BASE_DIR = "/tmp/bitbucket_repos"

class BitbucketOperationsTool(Tool):
    """Tool for comprehensive Bitbucket operations.
    
    Provides functionality for:
    - Cloning repositories
    - Creating and managing branches
    - Making commits
    - Pushing and pulling changes
    - Managing repository access
    
    All operations use Bitbucket's Repository Access Token for authentication.
    """

    name: str = "bitbucket_operations_tool"
    description: str = (
        "Comprehensive tool for Bitbucket operations including cloning, branch management, "
        "commits, and repository access. Uses Repository Access Token authentication."
    )
    need_validation: bool = False
    access_token: Optional[str] = Field(
        default=None,
        description="Bitbucket Repository Access Token with 'Repository Read' and 'Repository Write' permissions"
    )

    def __init__(self, access_token: Optional[str] = None, **data):
        """Initialize the tool with a Bitbucket Repository Access Token.
        
        Args:
            access_token: Bitbucket Repository Access Token
            **data: Additional tool configuration data
        """
        super().__init__(**data)
        self.access_token = access_token if access_token and access_token.strip() else None
        logger.info(f"BitbucketOperationsTool initialized with token: {'provided' if self.access_token else 'not provided'}")

    arguments: list = [
        ToolArgument(
            name="operation",
            arg_type="string",
            description=(
                "The Git operation to perform. One of: clone, create_branch, checkout, "
                "commit, push, pull, status"
            ),
            required=True,
            example="clone",
        ),
        ToolArgument(
            name="repo_url",
            arg_type="string",
            description="The Bitbucket repository URL (HTTPS format)",
            required=False,
            example="https://bitbucket.org/workspace/repository.git",
        ),
        ToolArgument(
            name="repo_path",
            arg_type="string",
            description="Local repository path (must be within /tmp/bitbucket_repos)",
            required=True,
            example="/tmp/bitbucket_repos/repo_name",
        ),
        ToolArgument(
            name="branch_name",
            arg_type="string",
            description="Branch name for operations that require it",
            required=False,
            example="feature/new-feature",
        ),
        ToolArgument(
            name="commit_message",
            arg_type="string",
            description="Commit message for commit operations",
            required=False,
            example="Add new feature implementation",
        ),
        ToolArgument(
            name="files_to_commit",
            arg_type="string",
            description="Comma-separated list of files to commit",
            required=False,
            example="file1.py,file2.py",
        ),
    ]

    def _prepare_directory(self, path: str) -> None:
        """Prepare the target directory for repository operations."""
        path = os.path.abspath(path)
        if not path.startswith(BITBUCKET_REPOS_BASE_DIR):
            raise ValueError(f"Target path must be within {BITBUCKET_REPOS_BASE_DIR}")
        
        os.makedirs(BITBUCKET_REPOS_BASE_DIR, exist_ok=True)
        if os.path.exists(path):
            shutil.rmtree(path)
        os.makedirs(path)
        logger.debug(f"Prepared directory: {path}")

    def _get_clone_url(self, repo_url: str) -> str:
        """Get the proper clone URL with Repository Access Token authentication."""
        if not self.access_token:
            return repo_url

        # Remove /src/branch/ if present (from web URLs)
        if '/src/' in repo_url:
            repo_url = repo_url.split('/src/')[0]

        # Remove .git if present
        repo_url = repo_url.rstrip('.git')
        
        # Construct authenticated URL
        return f"https://x-token-auth:{self.access_token}@bitbucket.org/{repo_url.split('bitbucket.org/')[-1]}.git"

    def _clone_repository(self, repo_url: str, target_path: str, branch: str = "main") -> Repo:
        """Clone a Bitbucket repository.
        
        Args:
            repo_url: Repository URL
            target_path: Local path for cloning
            branch: Branch to clone (default: main)
            
        Returns:
            git.Repo: Cloned repository object
        """
        try:
            self._prepare_directory(target_path)
            clone_url = self._get_clone_url(repo_url)
            
            logger.info(f"Cloning repository to {target_path}")
            repo = Repo.clone_from(
                clone_url,
                target_path,
                branch=branch,
            )
            logger.info("Repository cloned successfully")
            return repo
            
        except GitCommandError as e:
            logger.error(f"Failed to clone repository: {str(e)}")
            raise

    def _create_branch(self, repo: Repo, branch_name: str) -> None:
        """Create and checkout a new branch.
        
        Args:
            repo: Repository object
            branch_name: Name of the branch to create
        """
        try:
            current = repo.active_branch
            new_branch = repo.create_head(branch_name)
            new_branch.checkout()
            logger.info(f"Created and checked out branch: {branch_name}")
            
        except GitCommandError as e:
            logger.error(f"Failed to create branch: {str(e)}")
            raise

    def _commit_changes(self, repo: Repo, message: str, files: Optional[List[str]] = None) -> None:
        """Commit changes to the repository.
        
        Args:
            repo: Repository object
            message: Commit message
            files: Optional list of specific files to commit
        """
        try:
            if files:
                repo.index.add(files)
            else:
                repo.git.add(A=True)
                
            repo.index.commit(message)
            logger.info(f"Changes committed with message: {message}")
            
        except GitCommandError as e:
            logger.error(f"Failed to commit changes: {str(e)}")
            raise

    def _push_changes(self, repo: Repo, branch_name: Optional[str] = None) -> None:
        """Push changes to remote repository.
        
        Args:
            repo: Repository object
            branch_name: Optional branch name to push
        """
        try:
            if branch_name:
                repo.git.push('origin', branch_name)
            else:
                repo.git.push()
            logger.info("Changes pushed to remote")
            
        except GitCommandError as e:
            logger.error(f"Failed to push changes: {str(e)}")
            raise

    def _pull_changes(self, repo: Repo) -> None:
        """Pull latest changes from remote repository.
        
        Args:
            repo: Repository object
        """
        try:
            repo.git.pull()
            logger.info("Latest changes pulled from remote")
            
        except GitCommandError as e:
            logger.error(f"Failed to pull changes: {str(e)}")
            raise

    def execute(self, **kwargs) -> Dict:
        """Execute the requested Bitbucket operation.
        
        Args:
            **kwargs: Operation-specific arguments
            
        Returns:
            Dict: Operation result status and details
        """
        operation = kwargs.get('operation')
        repo_path = kwargs.get('repo_path')
        
        try:
            if operation == 'clone':
                repo_url = kwargs.get('repo_url')
                if not repo_url:
                    raise ValueError("repo_url is required for clone operation")
                    
                repo = self._clone_repository(
                    repo_url,
                    repo_path,
                    kwargs.get('branch_name', 'main')
                )
                return {"status": "success", "message": f"Repository cloned to {repo_path}"}

            # For other operations, we need an existing repository
            if not os.path.exists(repo_path):
                raise ValueError(f"Repository not found at {repo_path}")
                
            repo = Repo(repo_path)
            
            if operation == 'create_branch':
                branch_name = kwargs.get('branch_name')
                if not branch_name:
                    raise ValueError("branch_name is required for create_branch operation")
                    
                self._create_branch(repo, branch_name)
                return {"status": "success", "message": f"Created branch: {branch_name}"}
                
            elif operation == 'commit':
                message = kwargs.get('commit_message')
                if not message:
                    raise ValueError("commit_message is required for commit operation")
                    
                files = kwargs.get('files_to_commit', '').split(',') if kwargs.get('files_to_commit') else None
                self._commit_changes(repo, message, files)
                return {"status": "success", "message": f"Changes committed: {message}"}
                
            elif operation == 'push':
                self._push_changes(repo, kwargs.get('branch_name'))
                return {"status": "success", "message": "Changes pushed to remote"}
                
            elif operation == 'pull':
                self._pull_changes(repo)
                return {"status": "success", "message": "Latest changes pulled from remote"}
                
            elif operation == 'checkout':
                branch_name = kwargs.get('branch_name')
                if not branch_name:
                    raise ValueError("branch_name is required for checkout operation")
                    
                repo.git.checkout(branch_name)
                return {"status": "success", "message": f"Checked out branch: {branch_name}"}
                
            elif operation == 'status':
                status = repo.git.status()
                return {"status": "success", "message": status}
                
            else:
                raise ValueError(f"Unsupported operation: {operation}")
                
        except Exception as e:
            logger.error(f"Operation failed: {str(e)}")
            return {"status": "error", "message": str(e)}


if __name__ == "__main__":
    # Example usage
    tool = BitbucketOperationsTool(access_token="your_access_token_here")
    
    # Clone a repository
    result = tool.execute(
        operation="clone",
        repo_url="https://bitbucket.org/workspace/repository.git",
        repo_path="/tmp/bitbucket_repos/repository"
    )
    print(result)
    
    # Create a new branch
    result = tool.execute(
        operation="create_branch",
        repo_path="/tmp/bitbucket_repos/repository",
        branch_name="feature/new-feature"
    )
    print(result)
