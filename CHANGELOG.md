# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.94.0] - 2025-06-30

### Added
- **Component Architecture**: Introduced modular component-based architecture
- **Enhanced Documentation**: Added comprehensive architecture documentation with Mermaid diagrams
- **Component READMEs**: Professional documentation for each component with visual diagrams
- **Architecture Guide**: Detailed `docs/ARCHITECTURE.md` with system overview and integration patterns
- **Component Decision Matrix**: Added guidance for choosing the right component for specific use cases

### Changed
- **Project Structure**: Reorganized to component-based architecture without breaking changes
  - Core implementation moved to `quantalogic_react/` component
  - Added component specializations: `quantalogic_codeact/`, `quantalogic_flow/`, `quantalogic_toolbox/`
  - Root `quantalogic/` package now acts as user-facing wrapper with backward compatibility
- **Documentation Enhancement**: Updated all documentation to reflect new architecture
  - Enhanced main README.md with component architecture section and decision guide
  - Updated CONTRIBUTING.md with component-aware development workflows
  - Added visual architecture diagrams throughout documentation
- **Improved Tool Imports**: Made Composio tool imports conditional to prevent dependency errors

### Fixed
- **Test Compatibility**: Fixed test imports to work with new component structure
- **Conditional Imports**: Resolved import errors for optional dependencies like Composio
- **CLI Compatibility**: Ensured CLI commands continue to work unchanged

### Technical Details
- **Backward Compatibility**: 100% - All existing user code continues to work without modification
- **Performance**: No regressions detected (import ~1s, agent creation ~0.002s, memory ~205MB)
- **Testing**: All tests pass with new structure
- **Migration**: Automated migration scripts created and executed successfully

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

### Major Dependency Updates - Main Project
- **Rich**: 13.9.4 → 14.0.0 (improved terminal rendering)
- **Faker**: 36.1.1 → 37.4.0 (enhanced fake data generation)
- **Markdownify**: 0.14.1 → 1.1.0 (major version update with new features)
- **HTML2Text**: 2024.2.26 → 2025.4.15 (latest HTML to text conversion)
- **MarkItDown**: 0.0.1a3 → 0.1.2 (stable release with document conversion improvements)
- **DuckDuckGo Search**: 7.2.1 → 8.0.4 (enhanced search capabilities)
- **Tree-sitter**: 0.23.2 → 0.24.0 (improved code parsing)
- **Tree-sitter C**: 0.23.4 → 0.24.1 (enhanced C language support)
- **Tree-sitter Rust**: 0.23.2 → 0.24.0 (improved Rust parsing)
- **Tree-sitter Scala**: 0.23.4 → 0.24.0 (enhanced Scala support)
- **Pandas**: 2.2.3 → 2.3.0 (latest data analysis features)
- **Python-Levenshtein**: 0.26.1 → 0.27.1 (improved string similarity)
- **Pytest-asyncio**: 0.25.3 → 1.0.0 (stable async testing)
- **Ruff**: 0.8.4 → 0.12.1 (latest linting and formatting)
- **Ollama**: 0.4.4 → 0.5.1 (enhanced local LLM support)

### Technical Details
- **Date**: June 30, 2025
- **Scope**: Major dependency update across entire ecosystem
- **Impact**: Latest features, bug fixes, and performance improvements across all libraries
- **Projects Updated**: 4 total (main + 3 subprojects)
- **Breaking Changes**: None expected (compatible version updates)
- **Compatibility**: Maintained llama-index-embeddings-bedrock compatibility constraints

---

*This changelog was initiated on June 30, 2025. Previous changes may not be documented here.*
