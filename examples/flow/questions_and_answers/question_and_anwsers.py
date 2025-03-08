#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "loguru",
#     "litellm",
#     "pydantic>=2.0",
#     "anyio",
#     "quantalogic>=0.35",
#     "jinja2",
#     "typer>=0.9.0"
# ]
# ///

import asyncio
import os
import random
import json
from typing import Annotated, List

import typer
from pydantic import BaseModel, Field
from loguru import logger

from quantalogic.flow.flow import Nodes, Workflow

# Initialize Typer app
app = typer.Typer(help="Extract facts from a markdown file and generate an educational questionnaire")

# Pydantic Models
class Fact(BaseModel):
    title: str
    claims: str
    sources: List[str]

class FactsList(BaseModel):
    facts: List[Fact]

class QuestionnaireItem(BaseModel):
    fact_title: str
    question: str
    options: List[str] = Field(..., min_items=3, max_items=6)  # 3 to 6 options
    correct_answers: List[int] = Field(..., min_items=1)       # At least one correct answer, 1-based index
    explanation: str
    is_multiple_choice_possible: bool                          # Flag indicating if multiple answers are possible

class Questionnaire(BaseModel):
    items: List[QuestionnaireItem]

class EvaluationItem(BaseModel):
    question_number: int
    relevance: int = Field(..., ge=1, le=5)
    plausibility: int = Field(..., ge=1, le=5)
    correctness: int = Field(..., ge=1, le=5)
    clarity: int = Field(..., ge=1, le=5)
    explanation_quality: int = Field(..., ge=1, le=5)
    comments: str

class Evaluation(BaseModel):
    items: List[EvaluationItem]
    overall_assessment: str

# Nodes
@Nodes.define(output="markdown_content")
async def read_markdown_file(file_path: str) -> str:
    """Read content from a markdown file."""
    try:
        with open(file_path, encoding="utf-8") as f:
            content = f.read()
        print(f"Read markdown content from {file_path}, length: {len(content)} characters")
        return content
    except Exception as e:
        print(f"Error reading markdown file {file_path}: {e}")
        raise

@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant tasked with extracting factual information from educational markdown texts.",
    output="facts_list",
    response_model=FactsList,
    prompt_template="Extract key facts from the markdown text below. Each fact must have a title, a detailed claims description with sufficient context for question generation, and the source (heading or section title).\n\n{{markdown_content}}"
)
async def extract_facts(markdown_content: str) -> FactsList:
    pass

@Nodes.define(output="selected_facts")
async def select_facts(facts_list: FactsList, num_questions: int, token_limit: int = 2000) -> List[FactsList]:
    """Select facts and split into batches if exceeding token limit."""
    if token_limit is None:
        token_limit = 2000  # Fallback to ensure no NoneType
        logger.warning("token_limit was None; defaulting to 2000")
    
    logger.debug(f"Selecting facts with num_questions={num_questions}, token_limit={token_limit}")
    selected = facts_list.facts[:num_questions]
    batches = []
    current_batch = []
    current_token_count = 0
    
    for fact in selected:
        # Rough token estimate: 1 token ~ 4 characters
        fact_text = f"{fact.title} {fact.claims} {''.join(fact.sources)}"
        fact_tokens = len(fact_text) // 4 + 1
        logger.debug(f"Fact '{fact.title}' estimated at {fact_tokens} tokens")
        if current_token_count + fact_tokens > token_limit and current_batch:
            batches.append(FactsList(facts=current_batch))
            current_batch = [fact]
            current_token_count = fact_tokens
        else:
            current_batch.append(fact)
            current_token_count += fact_tokens
    
    if current_batch:
        batches.append(FactsList(facts=current_batch))
    
    logger.info(f"Split {len(selected)} facts into {len(batches)} batches")
    return batches

@Nodes.define(output="estimated_tokens")
async def estimate_tokens(selected_facts: List[FactsList]) -> List[int]:
    """Estimate token count for each batch of facts."""
    token_counts = []
    for batch in selected_facts:
        batch_text = " ".join([f"{fact.title} {fact.claims} {''.join(fact.sources)}" for fact in batch.facts])
        # Rough estimate: 1 token ~ 4 characters
        token_count = len(batch_text) // 4 + 1
        token_counts.append(token_count)
    logger.debug(f"Estimated tokens per batch: {token_counts}")
    return token_counts

@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant tasked with generating educational questionnaires from facts.",
    output="questionnaire",
    response_model=Questionnaire,
    prompt_template="""
Generate a questionnaire from these facts. Each question must have 3-6 options, one or more correct answers (1-based index), and a flag indicating if multiple answers are possible.

Facts:
{% for fact in facts_list.facts %}
- Title: {{ fact.title }}
  Claims: {{ fact.claims }}
  Source: {{ fact.sources | join(', ') }}
{% endfor %}

For each fact, provide:
- Fact title
- Question
- Options (3-6 strings)
- Correct answers (list of integers, e.g., [1, 3])
- Is multiple choice possible (true if multiple answers, false if one)
- Explanation (why the answers are correct)

Ensure questions are clear, options plausible, and explanations informative.
""",
    max_tokens=4000  # Increased to handle longer outputs
)
async def generate_questionnaire(facts_list: FactsList, model: str) -> Questionnaire:
    """Generate questionnaire with retry logic for truncation."""
    max_attempts = 2
    attempt = 1
    max_tokens = 4000
    
    while attempt <= max_attempts:
        try:
            result = await generate_questionnaire._original_func(facts_list=facts_list, model=model, max_tokens=max_tokens)
            # Check for truncation (e.g., missing items or abrupt end)
            if len(result.items) < len(facts_list.facts) or not all(item.explanation for item in result.items):
                raise ValueError("Output appears truncated")
            return result
        except Exception as e:
            logger.warning(f"Attempt {attempt} failed: {e}")
            attempt += 1
            max_tokens += 2000  # Increase tokens for retry
            if attempt > max_attempts:
                raise ValueError("Failed to generate complete questionnaire after retries")

@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant evaluating questionnaire quality.",
    output="evaluation",
    response_model=Evaluation,
    prompt_template="""
Evaluate this questionnaire against the facts. Rate each question (1-5) on:
1. Relevance: Related to the fact?
2. Plausibility: Options realistic?
3. Correctness: Answers accurate?
4. Clarity: Question clear?
5. Explanation Quality: Explanation informative?

Provide comments and an overall assessment.

Facts:
{% for fact in selected_facts.facts %}
- Title: {{ fact.title }}
  Claims: {{ fact.claims }}
  Source: {{ fact.sources | join(', ') }}
{% endfor %}

Questionnaire:
{% for item in questionnaire.items %}
Question {{ loop.index + 1 }}:
Fact Title: {{ item.fact_title }}
Fact Claims: {{ selected_facts.facts | selectattr('title', 'equalto', item.fact_title) | map(attribute='claims') | first | default('N/A', true) }}
Question: {{ item.question }}
Options:
{% for option in item.options %}
- {{ loop.index + 1 }}. {{ option }}
{% endfor %}
Correct Answers: {{ item.correct_answers | join(', ') }}
Is Multiple Choice Possible: {{ item.is_multiple_choice_possible }}
Explanation: {{ item.explanation }}
{% endfor %}
""",
    max_tokens=4000  # Increased to handle longer evaluations
)
async def verify_questionnaire(selected_facts: FactsList, questionnaire: Questionnaire, model: str) -> Evaluation:
    """Evaluate questionnaire with logging for debugging."""
    logger.debug(f"Verifying questionnaire with {len(questionnaire.items)} items against {len(selected_facts.facts)} facts using model {model}")
    logger.debug(f"Fact titles: {[fact.title for fact in selected_facts.facts]}")
    logger.debug(f"Questionnaire fact titles: {[item.fact_title for item in questionnaire.items]}")
    return await verify_questionnaire._original_func(selected_facts=selected_facts, questionnaire=questionnaire, model=model)

@Nodes.define(output="questionnaire")
async def shuffle_options(questionnaire: Questionnaire) -> Questionnaire:
    """Shuffle the options for each question and update the correct answers' indices."""
    for item in questionnaire.items:
        # Store the content of the correct options
        correct_contents = [item.options[i - 1] for i in item.correct_answers]  # 1-based to 0-based
        # Shuffle the options
        random.shuffle(item.options)
        # Update the correct_answers with new indices
        item.correct_answers = [item.options.index(content) + 1 for content in correct_contents]  # Back to 1-based
    return questionnaire

# Workflow
def create_fact_extraction_workflow() -> Workflow:
    """Create a workflow to extract facts from a markdown file and generate a questionnaire."""
    wf = Workflow("read_markdown_file")
    wf.sequence(
        "read_markdown_file",
        "extract_facts",
        "select_facts",
        "estimate_tokens",
        "generate_questionnaire",
        "verify_questionnaire",
        "shuffle_options"
    )
    wf.node_input_mappings["generate_questionnaire"] = {"facts_list": lambda ctx: ctx["selected_facts"][0]}  # Process first batch
    return wf

# Run Workflow
async def run_workflow(file_path: str, model: str, num_questions: int, token_limit: int = 2000) -> dict:
    """Execute the workflow with the given file path, model, and number of questions."""
    initial_context = {
        "file_path": file_path,
        "model": model,
        "num_questions": num_questions,
        "token_limit": token_limit  # Explicitly pass token_limit
    }
    workflow = create_fact_extraction_workflow()
    engine = workflow.build()
    result = await engine.run(initial_context)
    
    # Combine batches if multiple were processed
    selected_facts_batches = result.get("selected_facts", [])
    if len(selected_facts_batches) > 1:
        combined_questionnaire = Questionnaire(items=[])
        combined_facts = FactsList(facts=[])
        for i, batch in enumerate(selected_facts_batches):
            logger.debug(f"Generating questionnaire for batch {i+1} with {len(batch.facts)} facts")
            batch_result = await generate_questionnaire(facts_list=batch, model=model)
            combined_questionnaire.items.extend(batch_result.items)
            combined_facts.facts.extend(batch.facts)
        result["questionnaire"] = combined_questionnaire
        logger.debug(f"Verifying combined questionnaire with model {model}")
        result["evaluation"] = await verify_questionnaire(selected_facts=combined_facts, questionnaire=combined_questionnaire, model=model)
    else:
        logger.debug(f"Verifying single batch questionnaire with model {model}")
        result["evaluation"] = await verify_questionnaire(selected_facts=selected_facts_batches[0], questionnaire=result["questionnaire"], model=model)
    
    # Ensure facts_list is included in the result
    if len(selected_facts_batches) > 1:
        result["facts_list"] = combined_facts
    else:
        result["facts_list"] = selected_facts_batches[0]
    
    return result

# Typer CLI Command
@app.command()
def generate(
    file_path: Annotated[str, typer.Argument(help="Path to the markdown file")],
    model: Annotated[str, typer.Option(help="LLM model to use")] = "gemini/gemini-2.0-flash",
    num_questions: Annotated[int, typer.Option(help="Number of questions to generate")] = 5,
    token_limit: Annotated[int, typer.Option(help="Token limit per batch")] = 2000,
    save: Annotated[bool, typer.Option(help="Save results to JSON file")] = True
):
    """Extract facts from a markdown file and generate an educational questionnaire."""
    try:
        # Validate the file path
        if not os.path.isfile(file_path):
            typer.echo(f"Error: The file '{file_path}' does not exist.")
            raise typer.Exit(code=1)

        # Run the workflow
        result = asyncio.run(run_workflow(file_path, model, num_questions, token_limit))
        
        # Extract the questionnaire from the result
        questionnaire = result.get("questionnaire")
        if not questionnaire:
            typer.echo("Error: No questionnaire generated.")
            raise typer.Exit(code=1)
        
        # Display the questionnaire
        typer.echo("\nGenerated Educational Questionnaire:")
        typer.echo("=====================================")
        for item in questionnaire.items:
            typer.echo(f"Fact: {item.fact_title}")
            typer.echo(f"Question: {item.question}")
            typer.echo(f"Multiple Choice Possible: {item.is_multiple_choice_possible}")
            for i, option in enumerate(item.options, 1):
                typer.echo(f"{i}. {option}")
            typer.echo(f"Correct Answers: {', '.join(map(str, item.correct_answers))}")
            typer.echo(f"Explanation: {item.explanation}")
            typer.echo("-------------------------------------")
        
        # Display the evaluation
        evaluation = result.get("evaluation")
        if evaluation:
            typer.echo("\nQuestionnaire Evaluation:")
            typer.echo("=========================")
            for eval_item in evaluation.items:
                typer.echo(f"Question {eval_item.question_number}:")
                typer.echo(f"  Relevance: {eval_item.relevance}/5")
                typer.echo(f"  Plausibility: {eval_item.plausibility}/5")
                typer.echo(f"  Correctness: {eval_item.correctness}/5")
                typer.echo(f"  Clarity: {eval_item.clarity}/5")
                typer.echo(f"  Explanation Quality: {eval_item.explanation_quality}/5")
                typer.echo(f"  Comments: {eval_item.comments}")
            typer.echo(f"\nOverall Assessment: {evaluation.overall_assessment}")
        
        # Save results to JSON if requested
        if save:
            # Extract facts_list
            facts_list = result.get("facts_list")
            if not facts_list:
                typer.echo("Warning: No facts_list found in result; saving without it.")
            
            # Prepare data for JSON using model_dump
            output_data = {
                "facts_list": facts_list.model_dump() if facts_list else None,
                "questionnaire": questionnaire.model_dump(),
                "evaluation": evaluation.model_dump() if evaluation else None
            }
            
            # Generate output filename
            base_name = os.path.splitext(file_path)[0]  # Remove extension
            output_file = f"{base_name}_results.json"
            
            # Save to JSON
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, indent=2, ensure_ascii=False)
            typer.echo(f"\nResults saved to {output_file}")
        
    except Exception as e:
        typer.echo(f"Error: {str(e)}")
        raise typer.Exit(code=1)

if __name__ == "__main__":
    app()