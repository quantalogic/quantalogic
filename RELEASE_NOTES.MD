## v0.2.27

### New Features

- Added a new Tool `grep_app_tool` to search on GitHub repositories using grep.app API.
- Added a new Tool `sql_query_tool` to execute SQL queries on a database.
- Added a new Tool `generate_database_report_tool` to generate a report on a database. (creation of a semantic layer)
- Added a new example how to create SQL Query agent `examples/09-sql-query.py`
- Added a new tutorial how to create SQL Query agent `docs/articles/how_to_create_a_db_analyst.md` 


## v0.2.26

### Fix

- Fixed a bug in LLM Tools
- Fixed a bug in when 2 consecutive task are used in the same session

## v0.2.25

### New Features
- Added support to https://huggingface.co/deepseek-ai/DeepSeek-R1 

Usage:

quantalogic --model-name deepseek/deepseek-reasoner 

Or via OpenRouter:

quantalogic --model-name openrouter/deepseek/deepseek-r1

- Add multi questions in a session
- Add /clear command in a session to clear the memory

## v0.2.23

### New Features
- Added a new tool `dalle_e` for image generation. (Yatchi)
- Updated documentation to include details about DALL-E image generation. (Raphaël MANSUY)

### Enhancements
- Improved the `read html` tool with updates and refinements. (Raphaël MANSUY)
- Reorganized imports for better code structure and maintainability. (Raphaël MANSUY)
- Updated `agent.py` to improve functionality and performance. (Ikko Eltociear Ashimine)

### Documentation
- Updated the README.md file with the latest information and improvements. (Raphael MANSUY)


## [0.2.21] (2025-01-13)
- Fix a git_ls bug that caused that block the tool execution on certain directories
- By default create a basic agent instead of a coding agent


## [0.2.20] (2025-01-13)
- Added tool property injection precedence at runtime using tool.get_injectable_properties_in_execution()
- Added Jinja2 template support with enhanced variable handling
- Implemented pagination support for search_definition_names tool
- Updated documentation including JinjaTool and parameter descriptions
- Various README improvements and tutorial additions

## [0.2.19] (2025-01-12)
- Refactor _handle_repeated_tool_call to return tuple instead of ObserveResponseResult (182c505)
- Add link (e455657)
- Add how to document (e5df4fe)
- Update README with video (2727b96)
- Update README.md (b737caf)
- Add video (48d9ea4)


## [0.2.18] - 2025-01-12
### Added
- Memory management features: configurable compaction frequency and working memory limits
- New CLI parameters: --max-tokens-working-memory and --compact-every-n-iteration
- Documentation updates including README improvements and release notes
- Added git commit guidelines and TODO.md for future features