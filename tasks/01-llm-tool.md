Implement a LLM tool called llm_tool that takes a question as input and returns the answer as output.

The LLM Tool with derive from Tool class

Example:

<llm_tool>
    <system_prompt>Answer the question as truthfully as possible using the provided context, and if the answer is not contained within the context, say "I don't know".</system_prompt
    >
    <prompt>What is the meaning of life?</prompt>
    <temperature>0.7</temperature>
</llm_tool>

The LLM will use the quantalogic/generative_model.py class to generate the response, the LLM Tool will take a model_name in the constructor.