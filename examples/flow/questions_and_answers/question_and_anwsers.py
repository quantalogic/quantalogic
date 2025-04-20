#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "anyio",
#     "quantalogic-flow>=0.5.0",
#     "typer>=0.9.0"
# ]
# ///

import asyncio
import json
import os
import random
from typing import Annotated, List

import typer
from loguru import logger
from pydantic import BaseModel, Field

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
    system_prompt="You are an AI assistant tasked with extracting detailed factual information from educational markdown texts. For each fact, provide a comprehensive summary in the 'claims' field that captures sufficient context from the source, including background details, explanations, and implications, ensuring the summary is detailed and long enough to support generating educational questions. Avoid vague or brief descriptions; instead, aim for thoroughness and accuracy.",
    output="facts_list",
    response_model=FactsList,
    prompt_template="""
Extract key facts from the markdown text below. For each fact, include:
- A concise 'title' summarizing the fact.
- A detailed 'claims' description that provides a comprehensive summary with enough context (e.g., background, specifics, and implications) from the source to enable question generation. The summary should be at least 100-150 words or more if needed to fully explain the fact.
- A list of 'sources' identifying the specific headings, sections, or parts of the text (e.g., 'Introduction', 'Section 2.1') where the fact is derived.

Markdown content:
{{markdown_content}}

Ensure the extracted facts are accurate, representative of the text, and rich in detail to serve as a foundation for educational purposes.
""",
    max_tokens=4000  # Increased to prevent truncation
)
async def extract_facts(markdown_content: str) -> FactsList:
    pass

@Nodes.define(output="selected_facts")
async def select_facts(facts_list: FactsList, num_questions: int, token_limit: int = 2000) -> FactsList:
    """Select a subset of facts based on the number of questions."""
    logger.debug(f"Selecting {num_questions} facts from {len(facts_list.facts)} available")
    selected = FactsList(facts=facts_list.facts[:num_questions])
    logger.info(f"Selected {len(selected.facts)} facts")
    return selected

@Nodes.define(output=None)
async def initialize_question_processing(selected_facts: FactsList) -> dict:
    """Initialize state for processing questions one by one."""
    logger.debug(f"Initializing question processing for {len(selected_facts.facts)} facts")
    return {
        "fact_index": 0,
        "combined_questionnaire": Questionnaire(items=[]),
        "combined_evaluation": Evaluation(items=[], overall_assessment="")
    }

@Nodes.define(output="current_fact")
async def get_current_fact(selected_facts: FactsList, fact_index: int) -> Fact:
    """Retrieve the current fact based on the fact index."""
    if fact_index < len(selected_facts.facts):
        logger.debug(f"Retrieving fact {fact_index}: {selected_facts.facts[fact_index].title}")
        return selected_facts.facts[fact_index]
    logger.warning(f"Fact index {fact_index} exceeds available facts {len(selected_facts.facts)}")
    raise IndexError("Fact index out of range")

@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant tasked with generating educational questionnaires from a single fact.",
    output="questionnaire_item",
    response_model=QuestionnaireItem,
    prompt_template="""
Generate a single questionnaire item from the fact below. The question must have 3-6 options, one or more correct answers (1-based index), and a flag indicating if multiple answers are possible.

Fact:
- Title: {{ current_fact.title }}
- Claims: {{ current_fact.claims }}
- Source: {{ current_fact.sources | join(', ') }}

Provide:
- Fact title
- Question
- Options (3-6 strings)
- Correct answers (list of integers, e.g., [1, 3])
- Is multiple choice possible (true if multiple answers, false if one)
- Explanation (why the answers are correct)

Ensure the question is clear, options plausible, and explanation informative.
""",
    max_tokens=2000  # Sufficient for a single item
)
async def generate_questionnaire_item(current_fact: Fact, model: str) -> QuestionnaireItem:
    pass

@Nodes.define(output="combined_questionnaire")
async def append_questionnaire_item(questionnaire_item: QuestionnaireItem, combined_questionnaire: Questionnaire) -> Questionnaire:
    """Append the current questionnaire item to the combined questionnaire."""
    new_items = combined_questionnaire.items + [questionnaire_item]
    logger.debug(f"Appending item for fact '{questionnaire_item.fact_title}', total items now {len(new_items)}")
    return Questionnaire(items=new_items)

@Nodes.structured_llm_node(
    system_prompt="You are an AI assistant evaluating the quality of a single questionnaire item against its fact.",
    output="evaluation_item",
    response_model=EvaluationItem,
    prompt_template="""
Evaluate this questionnaire item against its corresponding fact. Rate the question (1-5) on:
1. Relevance: Related to the fact?
2. Plausibility: Options realistic?
3. Correctness: Answers accurate?
4. Clarity: Question clear?
5. Explanation Quality: Explanation informative?

Provide comments specific to this item.

Fact:
- Title: {{ current_fact.title }}
- Claims: {{ current_fact.claims }}
- Source: {{ current_fact.sources | join(', ') }}

Questionnaire Item:
- Fact Title: {{ questionnaire_item.fact_title }}
- Question: {{ questionnaire_item.question }}
- Options:
{% for option in questionnaire_item.options %}
- {{ loop.index + 1 }}. {{ option }}
{% endfor %}
- Correct Answers: {{ questionnaire_item.correct_answers | join(', ') }}
- Is Multiple Choice Possible: {{ questionnaire_item.is_multiple_choice_possible }}
- Explanation: {{ questionnaire_item.explanation }}

Assign a question_number based on the order (provided as {{ question_number }}).
""",
    max_tokens=2000  # Sufficient for a single evaluation
)
async def verify_questionnaire_item(current_fact: Fact, questionnaire_item: QuestionnaireItem, model: str, question_number: int) -> EvaluationItem:
    pass

@Nodes.define(output="combined_evaluation")
async def append_evaluation_item(evaluation_item: EvaluationItem, combined_evaluation: Evaluation) -> Evaluation:
    """Append the current evaluation item to the combined evaluation."""
    new_items = combined_evaluation.items + [evaluation_item]
    logger.debug(f"Appending evaluation for question {evaluation_item.question_number}, total items now {len(new_items)}")
    return Evaluation(items=new_items, overall_assessment=combined_evaluation.overall_assessment)

@Nodes.define(output="fact_index")
async def increment_fact_index(fact_index: int) -> int:
    """Increment the fact index."""
    logger.debug(f"Incrementing fact index from {fact_index} to {fact_index + 1}")
    return fact_index + 1

@Nodes.define(output="evaluation")
async def finalize_evaluation(combined_evaluation: Evaluation, selected_facts: FactsList) -> Evaluation:
    """Add an overall assessment to the evaluation."""
    overall_assessment = f"Evaluated {len(combined_evaluation.items)} questions based on {len(selected_facts.facts)} facts. The questionnaire appears consistent and well-structured overall."
    logger.info("Finalizing evaluation with overall assessment")
    return Evaluation(items=combined_evaluation.items, overall_assessment=overall_assessment)

@Nodes.define(output="questionnaire")
async def shuffle_options(combined_questionnaire: Questionnaire) -> Questionnaire:
    """Shuffle the options for each question and update the correct answers' indices."""
    for item in combined_questionnaire.items:
        # Store the content of the correct options
        correct_contents = [item.options[i - 1] for i in item.correct_answers]  # 1-based to 0-based
        # Shuffle the options
        random.shuffle(item.options)
        # Update the correct_answers with new indices
        item.correct_answers = [item.options.index(content) + 1 for content in correct_contents]  # Back to 1-based
    return combined_questionnaire

# Workflow
def create_fact_extraction_workflow() -> Workflow:
    """Create a workflow to extract facts and generate/verify a questionnaire one fact at a time."""
    wf = Workflow("read_markdown_file")
    
    # Initial sequence: read file, extract and select facts
    wf.node("read_markdown_file").then("extract_facts")
    wf.then("select_facts")
    wf.then("initialize_question_processing")
    
    # Fact-by-fact processing loop
    wf.then("get_current_fact")
    wf.then("generate_questionnaire_item")
    wf.then("append_questionnaire_item")
    wf.then("verify_questionnaire_item")
    wf.then("append_evaluation_item")
    wf.then("increment_fact_index")
    
    # Conditional transitions to simulate loop
    wf.transitions["increment_fact_index"] = [
        ("get_current_fact", lambda ctx: ctx.get("fact_index", 0) < len(ctx.get("selected_facts", FactsList(facts=[])).facts)),
        ("finalize_evaluation", lambda ctx: ctx.get("fact_index", 0) >= len(ctx.get("selected_facts", FactsList(facts=[])).facts))
    ]
    
    # Post-loop: finalize evaluation and shuffle options
    wf.node("finalize_evaluation").then("shuffle_options")
    
    # Input mappings
    wf.node_input_mappings["get_current_fact"] = {
        "selected_facts": "selected_facts",
        "fact_index": "fact_index"
    }
    wf.node_input_mappings["generate_questionnaire_item"] = {
        "current_fact": "current_fact",
        "model": "model"
    }
    wf.node_input_mappings["append_questionnaire_item"] = {
        "questionnaire_item": "questionnaire_item",
        "combined_questionnaire": "combined_questionnaire"
    }
    wf.node_input_mappings["verify_questionnaire_item"] = {
        "current_fact": "current_fact",
        "questionnaire_item": "questionnaire_item",
        "model": "model",
        "question_number": lambda ctx: ctx.get("fact_index", 0) + 1  # 1-based question number
    }
    wf.node_input_mappings["append_evaluation_item"] = {
        "evaluation_item": "evaluation_item",
        "combined_evaluation": "combined_evaluation"
    }
    wf.node_input_mappings["increment_fact_index"] = {
        "fact_index": "fact_index"
    }
    wf.node_input_mappings["finalize_evaluation"] = {
        "combined_evaluation": "combined_evaluation",
        "selected_facts": "selected_facts"
    }
    wf.node_input_mappings["shuffle_options"] = {
        "combined_questionnaire": "combined_questionnaire"
    }
    
    # Added input mapping for extract_facts to use the context-provided model
    wf.node_input_mappings["extract_facts"] = {
        "markdown_content": "markdown_content",
        "model": "model"
    }
    
    logger.info("Workflow created with fact-by-fact processing loop")
    return wf

# Run Workflow
async def run_workflow(file_path: str, model: str, num_questions: int, token_limit: int = 2000) -> dict:
    """Execute the workflow with the given file path, model, and number of questions."""
    initial_context = {
        "file_path": file_path,
        "model": model,
        "num_questions": num_questions,
        "token_limit": token_limit
    }
    workflow = create_fact_extraction_workflow()
    engine = workflow.build()
    result = await engine.run(initial_context)
    
    # Ensure facts_list is included in the result for compatibility
    result["facts_list"] = result.get("selected_facts", FactsList(facts=[]))
    
    logger.info("Workflow execution completed")
    return result

# Typer CLI Command
@app.command()
def generate(
    file_path: Annotated[str, typer.Argument(help="Path to the markdown file")],
    model: Annotated[str, typer.Option(help="LLM model to use")] = "gemini/gemini-2.0-flash",
    num_questions: Annotated[int, typer.Option(help="Number of questions to generate")] = 5,
    token_limit: Annotated[int, typer.Option(help="Token limit per batch (unused in this version)")] = 2000,
    save: Annotated[bool, typer.Option(help="Save results to JSON file")] = True
):
    """Extract facts from a markdown file and generate an educational questionnaire."""
    try:
        # Validate the file path
        if not os.path.isfile(file_path):
            typer.echo(f"Error: The file '{file_path}' does not exist.")
            raise typer.Exit(code=1)

        # Print model selection
        typer.echo(f"Selected model: {model}")

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