# Contributing Guide

Thank you for your interest in contributing to this project! We welcome contributions from everyone. Below are guidelines to help you get started.

---

## Getting Started

1. **Fork the Repository**: Start by forking the repository to your GitHub account.
2. **Clone the Repository**: Clone your forked repository to your local machine:
   ```bash
   git clone https://github.com/quantalogic/quantalogic.git
   cd project-name
   ```
3. **Set Up the Environment**:
   - Create a virtual environment:
     ```bash
     python -m venv venv
     source venv/bin/activate  # On Windows: venv\Scripts\activate
     ```
   - Install dependencies:
     ```bash
     pip install -r requirements.txt
     ```

4. **Install Development Tools**:
   - Install `ruff` for linting and `pytest` for testing:
     ```bash
     pip install ruff pytest
     ```

---

## Code Style

We use `ruff` to enforce consistent code style and formatting. Follow these guidelines:

1. **Linting**: Run `ruff` to check for style issues:
   ```bash
   ruff check .
   ```
2. **Formatting**: Use `ruff` to format your code:
   ```bash
   ruff format .
   ```
3. **General Guidelines**:
   - Follow [PEP 8](https://peps.python.org/pep-0008/) for Python code style.
   - Use type hints where applicable.
   - Keep functions and classes concise and focused.

---

## Testing

We use `pytest` for testing. Follow these steps:

1. **Write Tests**: Add tests for new features or bug fixes in the `tests/` directory.
2. **Run Tests**: Execute all tests using:
   ```bash
   pytest
   ```
3. **Test Coverage**: Ensure your changes maintain or improve test coverage. Check coverage with:
   ```bash
   pytest --cov=.
   ```

---

## Pull Request Guidelines

1. **Branch Naming**: Create a new branch for your changes:
   ```bash
   git checkout -b feature/your-feature-name
   ```
2. **Commit Messages**: Write clear and concise commit messages. Use the present tense (e.g., "Add feature X").
3. **Pull Request**:
   - Push your branch to your forked repository:
     ```bash
     git push origin feature/your-feature-name
     ```
   - Open a Pull Request (PR) against the `main` branch of the original repository.
   - Provide a detailed description of your changes, including the problem solved and the solution.
4. **Code Review**: Address any feedback from reviewers promptly. Ensure all tests pass and the code is linted before marking the PR as ready for review.

---

## Code of Conduct

We are committed to fostering a welcoming and inclusive community. By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md). Please report any unacceptable behavior to the maintainers.

---

Thank you for contributing! Your efforts help make this project better for everyone. 🚀