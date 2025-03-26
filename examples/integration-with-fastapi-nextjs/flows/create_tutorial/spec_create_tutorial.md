
# Create a workflow with quantalogic flow.py, takes example on story_generator.py

## Objective

- Create an engaging tutorial from the markdown file 

## Prerequisites


- use typer of for cli 
- use quantalogic.flow for workflow
- use uv shebang to start the script 

## input 

    - path to markdown file support tilde expansion, local and full path
    - model to use for llm
    - option the number of chapters default 5
    - option the number of words by chapter default 2000
    - option to copy the final result to clipboard

## Workflow

    - Read the markdown file 
    - Propose a structure for the tutorial, organized in chapters, each chapter must organized in 
      Why, What, How

      Structure Object:

        Chapter:
            - Title
            - summary of content
            - ideas to structure in Why, What, How
            - ideas of examples to explain the content
            - ideas of mermaid diagram to represent the content
        
    - Generate the tutorial chapter by chapter, using as input the chapter structure and full content of the markdown file

        - Generate a draft chapter
        - Critics the draft chapter
        - Improve based on critics 

    - As book editor, revise the formatting to make it more engaging and reader-friendly chapter by chapter

    - Regroup each chapter in a final markdown file

    - Copy the final result to clipboard if option is selected

    - Save the final markdown file along with the markdown file

## Output

    - final markdown file
    - clipboard content

## Recommandations

    - The tutorial must be engaging and reader-friendly
    - You can include emojis to make it more engaging 
    - Use emotions and story to make it engaging
    - Use markdown formatting to make it more reader-friendly
    - Use mermaid diagram to represent the content
    - Use private insights to make it more engaging






