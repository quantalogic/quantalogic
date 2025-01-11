
# Example of using LLMLingua with Litellm for prompt compression
# https://github.com/microsoft/LLMLingua

import litellm
from litellm import completion
from llmlingua import PromptCompressor

from quantalogic.prompts import system_prompt

llm_lingua = PromptCompressor()

litellm.set_verbose = False 

system_prompt = system_prompt("","","")
print(system_prompt)

contexts_list = []
instruction = system_prompt

question = "What is the meaning of life?"

compressed_prompt = llm_lingua.compress_prompt(
    contexts_list,
    instruction=instruction,
    question=question,
    target_token=2000,
    condition_compare=True,
    condition_in_question="after",
    rank_method="longllmlingua",
    use_sentence_level_filter=False,
    context_budget="+100",
    dynamic_context_compression_ratio=0.4,  # enable dynamic_context_compression_ratio
    reorder_context="sort",
)   

# Count number of words in system prompt
num_words = len(system_prompt.split())
print(f"System prompt has {num_words} words")

# Count number of words in compressed prompt
num_words = len(compressed_prompt.split())
print(f"Compressed prompt has {num_words} words")

# Count number of tokens in compressed prompt
num_tokens = litellm.token_counter(model="deepseek/deepseek-chat", messages=[{"role": "user", "content": compressed_prompt}])
print(f"Compressed prompt has {num_tokens} tokens")

messages = [
    {"role": "user", "content": compressed_prompt},
]

response = completion(
    model="deepseek/deepseek-chat",
    messages=messages,
)

print(response.choices[0].message.content)
print(response.usage)
