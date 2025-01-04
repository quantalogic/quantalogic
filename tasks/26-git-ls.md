Create a function that list the files in the current directory, taking into account the .gitignore file rules.

All the patterns in the .gitignore file / directory are ignored.

- You should be better to use an existing library to do this
- Expand the tilde to the user's home directory
- Convert relative paths to absolute paths using current working directory

- Format the output in a human-readable way, in a tree-like structure, include file sizes, and file types
- Return the output as a string

The function should take the following arguments:
- directory_path (str): The path to the directory to list.
- recursive (str): Whether to list directories recursively (true/false).
- max_depth (str): Maximum depth for recursive directory listing. default: 1
- start_line (str): Starting line for paginated results. default: 1
- end_line (str): Ending line for paginated results. default: 200

Write the function in ./quantalogic/tools/utils/git_ls.py

Write a test suite in ./tests/test_utils/test_git_ls.py


Code Rules:

1. Write Simple, Clear Code
- Readable > clever
- Minimal viable solution first
- Delete unused code
- No premature optimization

2. Function Rules
- Single responsibility
- ≤30 lines
- ≤6 parameters
- Descriptive names
- Type hints

3. Project Structure
- Group by feature
- Flat > nested
- Keep related code together
/project
  /feature1
    models.py
    services.py
    tests/
  /feature2
    ...
  main.py

4. Development Practice
- Use standard libs/tools
- Choose well-maintained libs
- Handle errors explicitly 
- Regular refactoring
- Document WHY not WHAT
- Executable scripts
- Write tests first
- Test Must be written to be insensitive to changes of formatting and not based on strict rules of display

5. Code Reviews
- Question complexity
- Check for dupes
- Verify error handling
- Ensure consistency

DEBUG PROCESS
1. Reproduce issue
2. Understand system
3. Form hypothesis
4. Test & verify
5. Document fix

REMEMBER
• Simple = Maintainable
• Code for humans
• Complexity kills
• Requirements drive changes

