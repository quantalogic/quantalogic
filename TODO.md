## Ideas of future features:

- [ ] Implement session token tracking
- [ ] Add document to memory storage
- [ ] Query stored document
- [ ] Add MCP Anthropic client/server support
- [ ] Add model list name 
- [ ] Add cost tracking
- [ ] Improve interactive session
    - [X] Thinking indicator
    - [X] Don't quit session after a task has completed 
        - [X] Ask for a new task / another question or quit 
    - [ ] Add commands 
        - [ ] /list of commands
        - [ ] /tools list of tools
        - [ ] /help
        - [ ] /exit
- [ ] Add Reflexion after N steps to see if the problem is solvable
- [X] Add event streaming
- [ ] Asynchronous execution

## Backlog:

- [ ] Different strategy of function calling: actually we use XML function calling that are good for coding agent, we can add 2 new paradigam: JSON Tool function calling or Python Function Calling (as Pydantic) to use specific fined tuned LLM such as driaforall Dria-Agent-a-3B
- Memory Handling 
- [ ] Add integration with Composio https://app.composio.dev/, and create a pull request in https://docs.composio.dev/framework/ 


## Demo:

- [ ] Create a knwoledge base using https://github.com/BuilderIO/gpt-crawler 
- [ ] Search from RAG
- [ ] Browse code 
- [ ] Analyze code and generate diagram
- [ ] Coding assistant with DeepSeek V3
- [ ] Query a SQL Database
- [ ] Query a DuckDb 
- [ ] Query a CSV file
- [ ] Classify photo in directory
- [ ] Reorganize files in directory
- [ ] Slide generator using https://sli.dev/guide/ 


## Features:

New command in interactive session:

/set_mode 
/set_model
/set_vision_model
/set_max_iterations

/list_mode

/list_models

/debug_mode

/log debug/info/warning/error


## Ideas for Tools

- [X] Analyze image processing tools
- [X] Add a efficient text reader for Html
- [X] Add BeautifulSoup tool
- [ ] Add a Browser Tool (chrome plugin)
- [ ] Add a RAG tool, search from a knowledge base
- [ ] Add https://pypi.org/project/unstructured/ to extract text from PDFs
- [X] Add a Jinja2 tool
- [ ] Add search images tool
- [ ] Add a whisper tool to transcribe audio
- [ ] Add a generate image tool
- [ ] Add an analize video tool
- [ ] Add a TTS tool
- [ ] Add Search Tool for action
- [-] Add Search WebTool like DuckDuckGo, Wikipedia, SerpAPI, Perplexity ...
- [X] Add a grep.app Tool to find code on the web
- [ ] Add a GronTool 
- [ ] Add A sequence operation to call multiple tools in one call
- [ ] Add integration to CodeGen https://x.com/mathemagic1an/status/1884660574241657048?s=12&t=TDcEu-9VmV2EvPkDUefXPg 




## Article

- [ ] How to create a agent to find code on the web use grep.app (example https://github.com/popovicn/grepgithub)
- [ ] An agent that find coins info on the Web https://danaepp.com/grepping-through-api-payloads-with-gron 



## Interesting research articles

- [Training Software Engineering Agents and Verifiers with SWE-Gym](https://arxiv.org/pdf/2412.21139)