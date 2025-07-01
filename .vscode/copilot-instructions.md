# VSCode Copilot Instructions

## Core Principles
- Prioritize readability over cleverness
- Implement minimal viable solutions first
- Remove unused code and avoid premature optimization
- Write code for humans, not just machines
- Simple equals maintainable

## Code Style Guidelines

### Function Design
- **Single Responsibility**: Each function should do one thing well
- **Size Limit**: Keep functions ≤20 lines
- **Parameter Limit**: Use ≤3 parameters per function
- **Naming**: Use descriptive, clear function names
- **Type Hints**: Always include type annotations
- **Arguments**: Prefer named arguments for clarity

### Project Organization
- Group code by feature, not by type
- Prefer flat structure over deep nesting
- Keep related functionality together
- Use standard directory structure:
```
/project
  /feature1
    models.py
    services.py
    tests/
  /feature2
    models.py
    services.py
    tests/
  main.py
```

### Development Standards
- Use standard libraries when possible
- Choose well-maintained third-party libraries
- Handle errors explicitly with proper exception handling
- Document WHY decisions were made, not WHAT the code does
- Make scripts executable and self-contained
- Use loguru for all logging needs
- Use pydantic for data validation and serialization

### Code Quality Checklist
When generating code, ensure:
- [ ] No unnecessary complexity
- [ ] No duplicate functionality
- [ ] Proper error handling
- [ ] Consistent style and patterns
- [ ] Clear variable and function names

### Debugging Approach
Follow this systematic process:
1. Reproduce the issue consistently
2. Understand the system context
3. Form testable hypothesis
4. Test and verify the solution
5. Document the fix and reasoning

## Language-Specific Guidelines

### Python
- Use type hints for all function signatures
- Prefer f-strings for string formatting
- **Avoid nested f-strings** - Use separate variable assignments for Python 3.10/3.11 compatibility
- Use list/dict comprehensions when they improve readability
- Import only what you need
- Follow PEP 8 naming conventions
- Use loguru instead of standard logging
- Use pydantic for data models, validation, and serialization

#### F-String Compatibility Rule
❌ **Don't use nested f-strings** (causes SyntaxError in Python 3.10/3.11):
```python
# Bad - nested f-strings
f'result: {", ".join(f"{item}" for item in items)}'
f'output: {some_func(f"{var}_suffix")}'
```

✅ **Use separate variable assignments instead**:
```python
# Good - separate assignments
quoted_items = [f"{item}" for item in items]
result = f'result: {", ".join(quoted_items)}'

# Good - separate assignments
suffix_var = f"{var}_suffix"
output = f'output: {some_func(suffix_var)}'
```

### Error Handling
- Be explicit about expected exceptions
- Use specific exception types, not bare `except:`
- Provide meaningful error messages
- Log errors with appropriate context using loguru

### Testing
- Write tests for core functionality
- Use descriptive test names that explain the scenario
- Keep tests simple and focused
- Group tests by feature

## Examples

### Good Function Example
```python
from typing import List
from loguru import logger

def calculate_average(numbers: List[float]) -> float:
    """Calculate arithmetic mean of numbers."""
    if not numbers:
        logger.warning("Empty list provided to calculate_average")
        return 0.0
    
    return sum(numbers) / len(numbers)
```

### Good Class Example
```python
from typing import Optional
from loguru import logger

class UserValidator:
    """Validates user input data."""
    
    def validate_email(self, email: str) -> bool:
        """Check if email format is valid."""
        if not email or "@" not in email:
            logger.info(f"Invalid email format: {email}")
            return False
        return True
    
    def validate_age(self, age: int) -> bool:
        """Check if age is within valid range."""
        if not 0 <= age <= 150:
            logger.warning(f"Age out of valid range: {age}")
            return False
        return True
```

### Good Pydantic Model Example
```python
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, validator
from loguru import logger

class User(BaseModel):
    """User data model with validation."""
    
    name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    age: int = Field(ge=0, le=150)
    active: bool = True
    
    @validator('name')
    def validate_name(cls, value: str) -> str:
        """Ensure name contains only valid characters."""
        if not value.strip():
            logger.warning("Empty name provided")
            raise ValueError("Name cannot be empty")
        return value.strip()
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        use_enum_values = True
```

## Reminders
- Complexity kills maintainability
- Requirements should drive all changes
- Refactor regularly to maintain code quality
- Always question if there's a simpler approach
