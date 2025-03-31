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
#     "py-zerox",
#     "pdf2image",
#     "pillow",
#     "pathlib",
#     "pathspec",
#     "requests"
# ]
# ///

import asyncio
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Any, Dict
from urllib.parse import urlparse

from loguru import logger
from pydantic import BaseModel, Field, validator

from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

# Initialize logger
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

# Get templates directory
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

def get_template_path(template_name: str) -> str:
    """Get the full path for a template file."""
    return os.path.join(TEMPLATES_DIR, template_name)

# Pydantic Models
class TenderDates(BaseModel):
    submission_deadline: datetime
    start_date: Optional[datetime]
    clarification_deadline: Optional[datetime]
    project_duration: Optional[str]

class TechnicalRequirement(BaseModel):
    category: str
    description: str
    mandatory: bool
    compliance_level: str = Field(..., description="Required compliance level (full, partial, etc.)")
    specifications: Optional[List[str]]
    performance_criteria: Optional[List[str]]

class ComplianceRequirement(BaseModel):
    document_type: str
    description: str
    deadline: Optional[datetime]
    mandatory: bool
    format: Optional[str]
    additional_notes: Optional[str]

class BudgetRange(BaseModel):
    min_amount: float = Field(..., description="Minimum budget amount in euros")
    max_amount: float = Field(..., description="Maximum budget amount in euros")
    payment_terms: Optional[str]
    financial_requirements: Optional[List[str]]

class RiskAssessment(BaseModel):
    category: str
    probability: str = Field(..., description="Low, Medium, High")
    impact: str = Field(..., description="Low, Medium, High")
    description: str
    mitigation_strategy: Optional[str]

class MitigationStrategy(BaseModel):
    risk_category: str
    strategies: List[str]

class TenderAnalysis(BaseModel):
    tender_reference: str
    tender_title: str
    issuing_organization: Optional[str]
    project_scope: str
    dates: TenderDates
    technical_requirements: List[TechnicalRequirement]
    compliance_requirements: List[ComplianceRequirement]
    estimated_budget: BudgetRange
    risks: List[RiskAssessment]
    risk_level: str = Field(..., description="Low, Medium, High")
    recommendation: str
    strategic_fit: Optional[str]
    next_steps: List[str]

class ResourceRequirement(BaseModel):
    role: str
    count: int
    expertise_level: str = Field(..., description="Junior, Mid, Senior")
    availability_needed: str
    internal_available: Optional[int]

class FeasibilityScores(BaseModel):
    technical_capability: int = Field(..., ge=1, le=5, description="Score from 1-5")
    resource_availability: int = Field(..., ge=1, le=5, description="Score from 1-5")
    timeline_feasibility: int = Field(..., ge=1, le=5, description="Score from 1-5")
    budget_feasibility: int = Field(..., ge=1, le=5, description="Score from 1-5")

class FeasibilityAssessment(BaseModel):
    scores: FeasibilityScores
    overall_feasibility: str = Field(..., description="Low, Medium, High")
    required_resources: List[ResourceRequirement] = Field(default_factory=list)
    constraints: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    strategic_importance: str = Field(..., description="Low, Medium, High")
    growth_opportunity: str = Field(..., description="Low, Medium, High")

    @validator('scores')
    def validate_scores(cls, v):
        return v

class CompetitorAnalysis(BaseModel):
    name: str
    strengths: List[str]
    weaknesses: List[str]
    win_probability: str = Field(..., description="Low, Medium, High")

class RiskAnalysis(BaseModel):
    technical_risks: List[RiskAssessment]
    operational_risks: List[RiskAssessment]
    financial_risks: List[RiskAssessment]
    strategic_risks: List[RiskAssessment]
    compliance_risks: List[RiskAssessment]
    mitigation_strategies: List[MitigationStrategy]
    competitors: List[CompetitorAnalysis]
    win_strategy: List[str]
    critical_success_factors: List[str]

# Custom JSON encoder for datetime objects
class DateTimeEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

# Custom Observer for Workflow Events
async def tender_analysis_observer(event: WorkflowEvent):
    if event.event_type == WorkflowEventType.WORKFLOW_STARTED:
        print(f"\n{'='*50}\n🔍 Starting Tender Analysis\n{'='*50}")
    elif event.event_type == WorkflowEventType.NODE_STARTED:
        print(f"\n▶️ [{event.node_name}] Starting analysis phase...")
    elif event.event_type == WorkflowEventType.NODE_COMPLETED:
        print(f"✅ [{event.node_name}] Analysis phase completed")
    elif event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
        print(f"\n{'='*50}\n🎯 Tender Analysis Completed\n{'='*50}")

# Workflow Nodes
@Nodes.define(output="document_content")
async def read_tender_document(file_path: str) -> str:
    """Read and process the tender document from URL or local file."""
    try:
        import requests

        # Check if the path is a URL
        parsed = urlparse(file_path)
        is_url = bool(parsed.scheme and parsed.netloc)

        if is_url:
            # Download from URL
            response = requests.get(file_path)
            response.raise_for_status()
            content = response.text

            # If it's a PDF URL, save temporarily and process
            if file_path.lower().endswith('.pdf'):
                with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                    temp_file.write(response.content)
                    temp_path = temp_file.name
                try:
                    from pyzerox import zerox
                    content = await zerox(file_path=temp_path)
                finally:
                    os.unlink(temp_path)
            
            logger.info(f"Successfully processed document from URL: {file_path}")
            return str(content)
        else:
            # Local file processing
            if file_path.lower().endswith('.pdf'):
                from pyzerox import zerox
                content = await zerox(file_path=file_path)
                if not content:
                    raise ValueError("Failed to extract content from PDF")
                logger.info(f"Successfully processed PDF document: {file_path}")
                return str(content)
            else:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                logger.info(f"Successfully read document: {file_path}")
                return content
    except Exception as e:
        logger.error(f"Error reading document {file_path}: {str(e)}")
        raise

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_tender.j2"),
    output="initial_analysis",
    response_model=TenderAnalysis,
    prompt_file=get_template_path("prompt_analyze_tender.j2"),
    temperature=0.3,
    max_tokens=3000
)
async def analyze_tender_document(document_content: str) -> TenderAnalysis:
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_assess_feasibility.j2"),
    output="feasibility_assessment",
    response_model=FeasibilityAssessment,
    prompt_file=get_template_path("prompt_assess_feasibility.j2"),
    temperature=0.3,
    max_tokens=3000
)
async def assess_feasibility(
    initial_analysis: TenderAnalysis,
    company_capabilities: dict
) -> FeasibilityAssessment:
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_risks.j2"),
    output="risk_analysis",
    response_model=RiskAnalysis,
    prompt_file=get_template_path("prompt_analyze_risks.j2"),
    temperature=0.4,
    max_tokens=3000
)
async def analyze_risks(
    initial_analysis: TenderAnalysis,
    feasibility_assessment: FeasibilityAssessment
) -> RiskAnalysis:
    pass

@Nodes.define(output="final_report")
async def generate_final_report(
    initial_analysis: TenderAnalysis,
    feasibility_assessment: FeasibilityAssessment,
    risk_analysis: RiskAnalysis
) -> dict:
    """Generate a comprehensive final report."""
    # Convert mitigation strategies to a more readable format
    mitigation_dict = {
        strategy.risk_category: strategy.strategies 
        for strategy in risk_analysis.mitigation_strategies
    }
    
    # Extract scores for better readability
    scores = feasibility_assessment.scores
    
    report = {
        "tender_summary": initial_analysis.model_dump(),
        "feasibility": {
            **feasibility_assessment.model_dump(),
            "scores": {
                "technical_capability": scores.technical_capability,
                "resource_availability": scores.resource_availability,
                "timeline_feasibility": scores.timeline_feasibility,
                "budget_feasibility": scores.budget_feasibility,
            }
        },
        "risk_analysis": {
            **risk_analysis.model_dump(),
            "mitigation_strategies": mitigation_dict
        },
        "generated_at": datetime.now().isoformat(),
        "executive_summary": {
            "tender_title": initial_analysis.tender_title,
            "overall_feasibility": feasibility_assessment.overall_feasibility,
            "risk_level": initial_analysis.risk_level,
            "strategic_importance": feasibility_assessment.strategic_importance,
            "key_recommendations": feasibility_assessment.recommendations[:3],
            "critical_success_factors": risk_analysis.critical_success_factors[:3]
        }
    }
    return report

@Nodes.define(output="output_path")
async def save_report(final_report: dict, output_dir: str) -> str:
    """Save the analysis report to a JSON file."""
    try:
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"tender_analysis_{timestamp}.json")
        
        # Save report with datetime handling
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_report, f, indent=2, cls=DateTimeEncoder)
        
        logger.info(f"Report saved to: {output_file}")
        return output_file
        
    except Exception as e:
        logger.error(f"Error saving report: {str(e)}")
        raise

# Create Workflow
def create_tender_analysis_workflow() -> Workflow:
    """Create the workflow for tender document analysis."""
    workflow = (
        Workflow("read_tender_document")
        .add_observer(tender_analysis_observer)
        .then("analyze_tender_document")
        .then("assess_feasibility")
        .then("analyze_risks")
        .then("generate_final_report")
        .then("save_report")
    )
    
    logger.info("Created tender analysis workflow")
    return workflow

# Run Workflow
async def run_workflow(
    file_path: str,
    output_dir: str,
    model: str,
    company_capabilities: dict
) -> dict:
    """Execute the workflow with the given parameters."""
    initial_context = {
        "file_path": file_path,
        "output_dir": output_dir,
        "model": model,
        "company_capabilities": company_capabilities
    }
    
    workflow = create_tender_analysis_workflow()
    engine = workflow.build()
    result = await engine.run(initial_context)
    
    logger.info("Workflow execution completed")
    return result

# Define Viveris capabilities
VIVERIS_CAPABILITIES = {
    "company_name": "Viveris",
    "employees": 800,
    "locations": ["France", "Belgium"],
    "core_expertise": [
        "Digital Transformation",
        "Embedded Systems",
        "Scientific Computing",
        "IT Infrastructure"
    ],
    "technical_domains": [
        "Agile Development",
        "Embedded Systems",
        "B2B E-commerce",
        "Information Governance",
        "Master Data Management (MDM)",
        "Cybersecurity",
        "Testing and Simulation",
        "Open Source",
        "Data Science",
        "SAP",
        "Internet of Things (IoT)",
        "Networks and Telecommunications",
        "Functional Safety",
        "Mobility"
    ],
    "industry_sectors": [
        "Automotive",
        "Energy",
        "Transport",
        "Healthcare",
        "Aerospace",
        "Telecommunications",
        "Retail",
        "Insurance",
        "Banking",
        "Public Administration"
    ],
    "certifications": [
        "ISO 9001",
        "ISO 27001"
    ],
    "resources": {
        "technical_staff": 650,
        "project_managers": 80,
        "consultants": 70
    },
    "project_capabilities": {
        "max_concurrent_projects": 50,
        "typical_project_size": "Medium to Large",
        "min_project_budget": 50000,
        "max_project_budget": 10000000
    }
}

async def analyze_tender_for_viveris(
    tender_source: str,  # Can be URL or local file path
    output_dir: str = "./output",
    model: str = "gemini/gemini-2.0-flash"
) -> dict:
    """
    Analyze a tender document specifically for Viveris company.
    
    Args:
        tender_source: URL or path to the tender document (PDF or text)
        output_dir: Directory to save analysis results
        model: LLM model to use for analysis
    
    Returns:
        dict: Analysis results including tender summary, feasibility assessment, and risk analysis
    """
    try:
        # Run the analysis workflow
        result = await run_workflow(
            file_path=tender_source,
            output_dir=output_dir,
            model=model,
            company_capabilities=VIVERIS_CAPABILITIES
        )
        
        # Extract and display key information
        if result and result.get("final_report"):
            report = result["final_report"]
            tender_summary = report.get("tender_summary", {})
            feasibility = report.get("feasibility", {})
            
            print("\nTender Analysis Results")
            print("=" * 50)
            print(f"Tender: {tender_summary.get('tender_title', 'N/A')}")
            print(f"Reference: {tender_summary.get('tender_reference', 'N/A')}")
            print(f"Overall Feasibility: {feasibility.get('overall_feasibility', 'N/A')}")
            print(f"Risk Level: {tender_summary.get('risk_level', 'N/A')}")
            print("\nDetailed report saved to:", result.get("output_path"))
            print("=" * 50)
            
            return result
        
        raise ValueError("No analysis results generated")
        
    except Exception as e:
        logger.error(f"Error analyzing tender: {str(e)}")
        raise

async def main():
    """Example usage with a sample tender document."""
    # Example tender URL - you can replace this with your actual tender URL or file path
    tender_source = "https://example.com/tenders/example.pdf"  # Replace with actual URL
    
    try:
        # For testing purposes, if no URL is provided, create a local example
        if tender_source.startswith("https://example.com"):
            example_content = """
Sample Call for Tender
=====================

Reference: CFT-2025-001
Title: Implementation of Enterprise IoT Platform

1. Project Overview
-------------------
Implementation of an enterprise-wide IoT platform for industrial monitoring and control.

2. Technical Requirements
------------------------
- IoT device integration and management
- Real-time data processing
- Cybersecurity measures
- Cloud infrastructure setup
- Mobile application development

3. Timeline
-----------
- Submission Deadline: 2025-05-15
- Project Start: 2025-07-01
- Duration: 18 months

4. Budget Range
--------------
€500,000 - €1,000,000
            """
            # Save example content to a temporary file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as temp_file:
                temp_file.write(example_content)
                tender_source = temp_file.name
        
        # Run the analysis
        await analyze_tender_for_viveris(tender_source)
        
    except Exception as e:
        logger.error(f"Error in main: {str(e)}")
    finally:
        # Cleanup temporary file if it was created
        if tender_source.startswith(tempfile.gettempdir()):
            try:
                os.remove(tender_source)
            except:
                pass

if __name__ == "__main__":
    asyncio.run(main())