
## Task 

Write the best possible tutorial on a specific topic.

## Step 1: Get the needs of the user

- Ask the user about a specific topic (Default: "Python")
- Ask the user how many chapters they want in the tutorial (default: 3)
- Ask the user what type of tutorial they want (e.g., "Beginner" or "Advanced") (default: "Beginner")
- Ask the user how many words by chapter (default: 500)
- Ask the user the target directory (by default, "./examples/generated_tutorials")

## Step 2: Assess the user's needs and preferences

Please evaluate your understanding of the topic to determine if you can advance to step 3. 
If you feel unable to do so, kindly explain to the user the reasons for this.

Choose a subdirectory name that best represents the topic, e.g., "python"

## Step 3: Generate a tutorial based on the user's needs and preferences

- First generate a detailled outline of the tutorial
- Then generate the actual tutorial content based on the outline, one file by chapter. 

 Guide for writing a tutorial:

    - Use markdown to write the tutorial
    - Use Richard Feynman's style to explain difficult concepts, never mention Richard Feynman
    - Use code examples to illustrate concepts, use an example oriented approach
    - Include some mermaid diagrams to illustrate complex concepts if useful
    - You can use emojis to add fun to your tutorial
    - Be clear and concise, always start by WHY, then WHAT, then HOW