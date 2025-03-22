rm -f poetry.lock && poetry env remove --all && poetry install --no-root
poetry update && poetry install --with dev,file-tools,git-tools,search-tools,document-tools,database-tools,llm-tools,web-tools,code-parsing,docs,composio-tools,utilities
poetry update && poetry install --with dev,file-tools,git-tools,search-tools,document-tools,database-tools,llm-tools,web-tools,code-parsing,docs,composio-tools,utilities
