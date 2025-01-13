# Release Notes

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
