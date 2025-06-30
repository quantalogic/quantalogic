# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Updated LiteLLM dependency to version 1.73.6 across all projects
  - Main project: 1.63.14 → 1.73.6
  - QuantaLogic CodeAct: 1.66.2 → 1.73.6
  - QuantaLogic Flow: 1.67.0 → 1.73.6
  - Planning Toolbox: 1.65.4.post1 → 1.73.6
- Updated related dependencies to maintain compatibility across all subprojects
  - Standardized Python version requirement to `<4.0,>=3.10` across all projects
  - Updated Pydantic to ^2.10.4 for consistency
  - Updated Jinja2 to ^3.1.5 across projects
  - Updated Instructor to ^1.7.2 for alignment
  - Updated Rich to ^13.9.4 in CodeAct to match main project
  - Added missing core dependencies (requests, click, prompt-toolkit, tenacity, pathspec, python-dotenv, typing-extensions) to CodeAct
- Regenerated Poetry lock files across all subprojects

### Technical Details
- **Date**: June 30, 2025
- **Scope**: Major dependency update
- **Impact**: Latest LiteLLM features, bug fixes, and performance improvements
- **Projects Updated**: 4 total (main + 3 subprojects)
- **Breaking Changes**: None expected (compatible version update)

---

*This changelog was initiated on June 30, 2025. Previous changes may not be documented here.*
