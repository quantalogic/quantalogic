"""Tool for performing Git operations like creating branches and making commits."""

import os
from git import Repo
from git.exc import GitCommandError
from loguru import logger
from pydantic import Field

from quantalogic.tools.tool import Tool, ToolArgument


class GitOperationsTool(Tool):
    """Tool for Git operations including branch creation and commits.
    
    This tool provides a simple interface for common Git operations like creating branches,
    making commits, pushing changes, and more.

    Examples:
        Create a new branch and switch to it:
        ```python
        tool = GitOperationsTool()
        tool.execute(
            repo_path="/path/to/repo",
            operation="create_branch",
            branch_name="feature/new-feature"
        )
        ```

        Make a commit with specific files:
        ```python
        tool.execute(
            repo_path="/path/to/repo",
            operation="commit",
            commit_message="Add new feature implementation",
            files_to_commit="file1.py,file2.py"
        )
        ```

        Push changes to remote:
        ```python
        tool.execute(
            repo_path="/path/to/repo",
            operation="push"
        )
        ```

        Pull latest changes:
        ```python
        tool.execute(
            repo_path="/path/to/repo",
            operation="pull"
        )
        ```

        Switch to existing branch:
        ```python
        tool.execute(
            repo_path="/path/to/repo",
            operation="checkout",
            branch_name="main"
        )
        ```
    """

    name: str = "git_operations_tool"
    description: str = (
        "Performs Git operations on a repository including creating branches, "
        "making commits, pushing changes, pulling updates, and checking out branches. "
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
            name="repo_path",
            arg_type="string",
            description=(
                "The local path to the Git repository. This should be an absolute path to "
                "an existing Git repository on your system.\n"
                "Examples:\n"
                "- '/home/user/projects/my-repo'\n"
                "- '/path/to/project'\n"
                "- './current/directory/repo'"
            ),
            required=True,
            example="/path/to/repo",
        ),
        ToolArgument(
            name="operation",
            arg_type="string",
            description=(
                "Git operation to perform. Available operations:\n"
                "- 'create_branch': Create and checkout a new branch\n"
                "- 'commit': Create a new commit with specified files\n"
                "- 'push': Push local changes to remote repository\n"
                "- 'pull': Pull latest changes from remote repository\n"
                "- 'checkout': Switch to an existing branch\n\n"
                "Usage examples:\n"
                "- operation='create_branch' + branch_name='feature/new-feature'\n"
                "- operation='commit' + commit_message='Add new feature' + files_to_commit='file1.py,file2.py'\n"
                "- operation='push' (pushes current branch)\n"
                "- operation='checkout' + branch_name='main'"
            ),
            required=True,
            example="create_branch",
        ),
        ToolArgument(
            name="branch_name",
            arg_type="string",
            description=(
                "Name of the branch to create or switch to. Required for 'create_branch' and 'checkout' operations.\n"
                "Branch naming conventions:\n"
                "- feature/[feature-name] for new features\n"
                "- bugfix/[bug-name] for bug fixes\n"
                "- hotfix/[fix-name] for urgent fixes\n"
                "- release/[version] for release branches\n\n"
                "Examples:\n"
                "- 'feature/user-authentication'\n"
                "- 'bugfix/login-error'\n"
                "- 'main' or 'master' for main branch\n"
                "- 'develop' for development branch"
            ),
            required=False,
            example="feature/new-feature",
        ),
        ToolArgument(
            name="commit_message",
            arg_type="string",
            description=(
                "Commit message when operation is 'commit'. If not provided, a default message will be generated.\n"
                "Commit message guidelines:\n"
                "- Start with a verb (Add, Fix, Update, Refactor, etc.)\n"
                "- Keep it concise but descriptive\n"
                "- Include ticket/issue number if applicable\n\n"
                "Examples:\n"
                "- 'Add user authentication feature'\n"
                "- 'Fix login validation bug #123'\n"
                "- 'Update README with API documentation'\n"
                "- 'Refactor database connection logic'"
            ),
            required=False,
            example="Add new feature implementation",
        ),
        ToolArgument(
            name="files_to_commit",
            arg_type="string",
            description=(
                "Comma-separated list of files to commit, or '.' for all changes. Used with 'commit' operation.\n"
                "File specification:\n"
                "- Use '.' to commit all changes\n"
                "- Use relative paths from repo root\n"
                "- Separate multiple files with commas\n"
                "- Supports wildcards (*.py, *.js)\n\n"
                "Examples:\n"
                "- '.' (all changes)\n"
                "- 'src/main.py,tests/test_main.py'\n"
                "- 'docs/*.md'\n"
                "- 'feature/auth/*.py,feature/auth/*.js'"
            ),
            required=False,
            example="file1.py,file2.py",
            default=".",
        ),
    ]

    def _setup_auth_for_remote(self, repo: Repo) -> tuple[str, str]:
        """Setup authentication for remote operations if needed.
        
        Args:
            repo: Git repository instance
        
        Returns:
            tuple: Original remote URL and whether URL was modified
        """
        original_url = repo.remote().url
        if self.auth_token and original_url.startswith("https://"):
            new_url = original_url.replace("https://", f"https://{self.auth_token}@")
            repo.remote().set_url(new_url)
            return original_url, True
        return original_url, False

    def execute(
        self,
        repo_path: str,
        operation: str,
        branch_name: str = None,
        commit_message: str = None,
        files_to_commit: str = ".",
    ) -> str:
        """Executes the specified Git operation.

        Args:
            repo_path: Path to the local Git repository
            operation: Git operation to perform
            branch_name: Name of the branch (for create_branch/checkout)
            commit_message: Commit message (for commit)
            files_to_commit: Files to commit (for commit)

        Returns:
            str: Result message

        Raises:
            GitCommandError: If there's an error during Git operations
            ValueError: If the parameters are invalid
        """
        try:
            if not os.path.exists(repo_path):
                raise ValueError(f"Repository path does not exist: {repo_path}")

            repo = Repo(repo_path)
            
            if operation == "create_branch":
                if not branch_name:
                    raise ValueError("branch_name is required for create_branch operation")
                
                # Create and checkout new branch
                current = repo.create_head(branch_name)
                current.checkout()
                logger.info(f"Created and checked out branch: {branch_name}")
                return f"Successfully created and checked out branch: {branch_name}"

            elif operation == "commit":
                # Handle default commit behavior
                if files_to_commit == ".":
                    # Stage all changes
                    repo.git.add(A=True)
                else:
                    # Stage specific files
                    for file in files_to_commit.split(","):
                        file = file.strip()
                        if os.path.exists(os.path.join(repo_path, file)):
                            repo.git.add(file)
                        else:
                            logger.warning(f"File not found: {file}")

                # Get list of staged files
                staged_files = repo.index.diff("HEAD")
                if not staged_files:
                    return "No changes to commit"

                # Generate default commit message if none provided
                if not commit_message:
                    # Get status of staged files
                    status = repo.git.status('--porcelain')
                    added = []
                    modified = []
                    deleted = []
                    
                    for line in status.split('\n'):
                        if line:
                            status_code = line[:2]
                            file_path = line[3:]
                            if status_code.startswith('A'):
                                added.append(file_path)
                            elif status_code.startswith('M'):
                                modified.append(file_path)
                            elif status_code.startswith('D'):
                                deleted.append(file_path)
                    
                    # Build commit message
                    message_parts = []
                    if added:
                        message_parts.append(f"Add {len(added)} file(s)")
                    if modified:
                        message_parts.append(f"Update {len(modified)} file(s)")
                    if deleted:
                        message_parts.append(f"Remove {len(deleted)} file(s)")
                    
                    commit_message = " & ".join(message_parts)
                    
                    # Add file details
                    details = []
                    if added:
                        details.append("\nAdded files:\n- " + "\n- ".join(added))
                    if modified:
                        details.append("\nModified files:\n- " + "\n- ".join(modified))
                    if deleted:
                        details.append("\nDeleted files:\n- " + "\n- ".join(deleted))
                    
                    commit_message += "".join(details)

                # Create commit
                commit = repo.index.commit(commit_message)
                logger.info(f"Created commit: {commit_message}")
                return f"Successfully created commit: {commit.hexsha[:8]}\n{commit_message}"

            elif operation in ["push", "pull"]:
                # Setup authentication if needed
                original_url, url_modified = self._setup_auth_for_remote(repo)
                
                try:
                    if operation == "push":
                        try:
                            repo.remote().push()
                        except GitCommandError as e:
                            if "no upstream branch" in str(e).lower():
                                # Get current branch name
                                current_branch = repo.active_branch.name
                                # Set upstream and push
                                repo.git.push('--set-upstream', 'origin', current_branch)
                            else:
                                raise
                        logger.info("Pushed changes to remote repository")
                        result = "Successfully pushed changes to remote repository"
                    else:  # pull
                        repo.remote().pull()
                        logger.info("Pulled latest changes from remote repository")
                        result = "Successfully pulled latest changes from remote repository"
                finally:
                    # Reset URL if it was modified
                    if url_modified:
                        repo.remote().set_url(original_url)
                
                return result

            elif operation == "checkout":
                if not branch_name:
                    raise ValueError("branch_name is required for checkout operation")
                
                # Check if branch exists
                if branch_name in repo.heads:
                    # Checkout existing branch
                    repo.heads[branch_name].checkout()
                    logger.info(f"Checked out existing branch: {branch_name}")
                    return f"Successfully checked out branch: {branch_name}"
                else:
                    raise ValueError(f"Branch '{branch_name}' does not exist. Use create_branch operation to create a new branch.")

            else:
                raise ValueError(f"Unsupported operation: {operation}")

        except GitCommandError as e:
            error_msg = str(e)
            # Remove sensitive information from error message
            if self.auth_token:
                error_msg = error_msg.replace(self.auth_token, "***")
            logger.error(f"Git operation failed: {error_msg}")
            raise GitCommandError(f"Git operation failed: {error_msg}", e.status)
        
        except Exception as e:
            logger.error(f"An error occurred during Git operation: {str(e)}")
            raise ValueError(f"An error occurred during Git operation: {str(e)}")


if __name__ == "__main__":
    # Example usage of the GitOperationsTool
    def run_example(repo_path: str):
        """Run example Git operations using the tool."""
        tool = GitOperationsTool(auth_token="your_token_here")
        
        try:
            # 1. Create and switch to a new feature branch
            logger.info("Creating new feature branch...")
            tool.execute(
                repo_path=repo_path,
                operation="create_branch",
                branch_name="feature/example-feature"
            )

            # 2. Make some changes and commit them
            logger.info("Creating a commit...")
            tool.execute(
                repo_path=repo_path,
                operation="commit",
                commit_message="Add new example feature",
                files_to_commit="."  # Commit all changes
            )

            # 3. Push changes to remote
            logger.info("Pushing changes to remote...")
            tool.execute(
                repo_path=repo_path,
                operation="push"
            )

            # 4. Switch back to main branch
            logger.info("Switching back to main branch...")
            tool.execute(
                repo_path=repo_path,
                operation="checkout",
                branch_name="main"
            )

            # 5. Pull latest changes
            logger.info("Pulling latest changes...")
            tool.execute(
                repo_path=repo_path,
                operation="pull"
            )

        except (GitCommandError, ValueError) as e:
            logger.error(f"Error during Git operations: {str(e)}")

    # To run the example, uncomment and modify the path:
    # run_example("/path/to/your/repo")
    
    # Print tool documentation
    tool = GitOperationsTool(auth_token="your_token_here")
    print(tool.to_markdown())
