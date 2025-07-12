Code Rules:

1. Write Simple, Clear Code
- Readable > clever
- Minimal viable solution first
- Delete unused code
- No premature optimization

2. Function Rules
- Single responsibility
- ≤20 lines
- ≤3 parameters
- Descriptive names
- Type hints (Python 3.10+ compatible)

3. Python Version Compatibility
- Support Python 3.10+ syntax
- Use `Union[X, Y]` instead of `X | Y` for type hints
- Use `Optional[X]` instead of `X | None`
- Import `Union` and `Optional` from `typing`
- Avoid features requiring Python 3.11+

4. Project Structure
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

5. Development Practice
- Use standard libs/tools
- Choose well-maintained libs
- Handle errors explicitly 
- Regular refactoring
- Document WHY not WHAT
- Executable scripts

6. Code Reviews
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
