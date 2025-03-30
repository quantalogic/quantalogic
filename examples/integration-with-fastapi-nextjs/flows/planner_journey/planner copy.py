from collections.abc import Callable
import os
from typing import Any, Dict, List, Optional, Union
import datetime
import json
from pathlib import Path
from pydantic import BaseModel, Field
from jinja2 import Environment, FileSystemLoader, select_autoescape
import anyio
import pyperclip
import typer
from loguru import logger
from quantalogic.flow.flow import Nodes, Workflow, WorkflowEvent, WorkflowEventType

# Configure logging
logger.remove()
logger.add(
    sink=lambda msg: print(msg, end=""),
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)

class CustomJSONEncoder(json.JSONEncoder):
    """Custom JSON encoder for Pydantic models."""
    def default(self, obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return super().default(obj)

# Base models for simpler types
class LocalPhrase(BaseModel):
    """Local phrase with translation."""
    phrase: str = Field(description="Local language phrase")
    translation: str = Field(description="English translation")

class Festival(BaseModel):
    """Festival information."""
    name: str = Field(description="Festival name")
    date: str = Field(description="Festival date or time period")
    description: str = Field(description="Festival description")

class EmergencyNumbers(BaseModel):
    """Emergency contact numbers."""
    police: str = Field(description="Police emergency number")
    ambulance: str = Field(description="Ambulance emergency number")
    fire: str = Field(description="Fire department emergency number")
    tourist_police: Optional[str] = Field(description="Tourist police number")

class Hospital(BaseModel):
    """Hospital information."""
    name: str = Field(description="Hospital name")
    address: str = Field(description="Hospital address")
    phone: str = Field(description="Hospital contact number")
    languages: List[str] = Field(description="Languages spoken")
    specialties: List[str] = Field(description="Medical specialties")
    emergency_24h: bool = Field(description="24/7 emergency services available")

class Embassy(BaseModel):
    """Embassy information."""
    country: str = Field(description="Country represented")
    address: str = Field(description="Embassy address")
    phone: str = Field(description="Embassy contact number")
    email: str = Field(description="Embassy email address")
    hours: str = Field(description="Embassy operating hours")
    emergency_contact: str = Field(description="Emergency contact")

class TransitPass(BaseModel):
    """Transit pass information."""
    name: str = Field(description="Transit pass name")
    duration: str = Field(description="Transit pass duration")
    cost: float = Field(description="Transit pass cost in USD")
    coverage: str = Field(description="Transit pass coverage")
    benefits: List[str] = Field(description="Transit pass benefits")

class TransportApp(BaseModel):
    """Transportation app information."""
    name: str = Field(description="App name")
    platform: str = Field(description="App platform (iOS/Android/Both)")
    features: List[str] = Field(description="App key features")
    download_link: str = Field(description="App download link")

class AirportTransfer(BaseModel):
    """Airport transfer information."""
    method: str = Field(description="Transfer method")
    duration: str = Field(description="Typical transfer duration")
    cost: float = Field(description="Transfer cost in USD")
    frequency: str = Field(description="Transfer service frequency")
    operating_hours: str = Field(description="Transfer operating hours")
    booking_required: bool = Field(description="Whether booking is required")

class PublicTransit(BaseModel):
    """Public transit information."""
    types: List[str] = Field(description="Available transit types")
    operating_hours: str = Field(description="General operating hours")
    payment_methods: List[str] = Field(description="Accepted payment methods")
    tips: List[str] = Field(description="Usage tips")

# Composite models that depend on base models
class CulturalInfo(BaseModel):
    """Cultural information about the destination."""
    customs: List[str] = Field(description="Important customs and etiquette")
    phrases: List[LocalPhrase] = Field(description="Essential local phrases with translations")
    dining_etiquette: List[str] = Field(description="Dining customs and etiquette")
    taboos: List[str] = Field(description="Cultural taboos to avoid")
    festivals: List[Festival] = Field(description="Notable festivals and events")

class TransportationGuide(BaseModel):
    """Detailed transportation information."""
    public_transit: PublicTransit = Field(description="Public transit options and tips")
    transit_passes: List[TransitPass] = Field(description="Available transit passes")
    local_apps: List[TransportApp] = Field(description="Useful transportation apps")
    airport_transfer: AirportTransfer = Field(description="Airport transfer options")

class EmergencyInfo(BaseModel):
    """Emergency and safety information."""
    emergency_numbers: EmergencyNumbers = Field(description="Emergency contact numbers")
    hospitals: List[Hospital] = Field(description="Nearby hospitals")
    embassy: Embassy = Field(description="Embassy information")
    safety_tips: List[str] = Field(description="General safety tips")

class VisaRequirement(BaseModel):
    """Visa requirement information."""
    required: bool = Field(description="Whether visa is required")
    type: str = Field(description="Type of visa")
    duration: str = Field(description="Duration of stay allowed")
    cost: float = Field(description="Cost in USD")
    processing_time: str = Field(description="Typical processing time")
    documents_required: List[str] = Field(description="Required documents")

# Main models that depend on composite models
class Activity(BaseModel):
    """Activity in a journey plan."""
    name: str = Field(description="Activity name")
    description: str = Field(description="Activity description")
    duration: str = Field(description="Activity duration (e.g., '2 hours')")
    cost: float = Field(description="Activity cost in USD")
    location: str = Field(description="Activity location")
    best_time: str = Field(description="Best time of day for this activity")

class Accommodation(BaseModel):
    """Accommodation in a journey plan."""
    name: str = Field(description="Accommodation name")
    type: str = Field(description="Accommodation type (e.g., hotel, hostel)")
    location: str = Field(description="Accommodation location")
    price_range: str = Field(description="Price range per night (e.g., '100-150')")
    amenities: str = Field(description="Comma-separated list of amenities")

class Transportation(BaseModel):
    """Transportation segment in a journey plan."""
    mode: str = Field(description="Transportation mode")
    from_location: str = Field(description="Starting location")
    to_location: str = Field(description="Destination location")
    duration: str = Field(description="Travel duration")
    cost: float = Field(description="Transportation cost in USD")

class DayPlan(BaseModel):
    """Daily plan in a journey."""
    activities: List[Activity] = Field(description="List of activities for the day")
    accommodation: Optional[Accommodation] = Field(description="Accommodation for the night")
    transportation: List[Transportation] = Field(description="List of transportation segments")

class DestinationAnalysis(BaseModel):
    """Enhanced destination analysis."""
    overview: str = Field(description="General overview of the destination")
    best_time_to_visit: str = Field(description="Best time of year to visit")
    weather: str = Field(description="Current weather conditions")
    local_currency: str = Field(description="Local currency information")
    language: str = Field(description="Primary language(s) spoken")
    timezone: str = Field(description="Local timezone")
    popular_areas: str = Field(description="Popular areas and neighborhoods")
    attractions: str = Field(description="Key attractions and sights")
    local_transportation: str = Field(description="Available transportation options")
    accommodation_areas: str = Field(description="Recommended areas for accommodation")
    dining_options: str = Field(description="Overview of dining options")
    safety_tips: str = Field(description="Important safety information")
    estimated_costs: str = Field(description="Estimated costs for common items")
    cultural_notes: str = Field(description="Important cultural considerations")
    cultural_info: CulturalInfo = Field(description="Cultural information")
    transportation_guide: TransportationGuide = Field(description="Transportation guide")
    emergency_info: EmergencyInfo = Field(description="Emergency information")
    visa_requirements: VisaRequirement = Field(description="Visa requirements")
    travel_insurance: List[str] = Field(description="Travel insurance recommendations")
    packing_list: List[str] = Field(description="Recommended packing list")

class JourneyPlan(BaseModel):
    """Complete journey plan."""
    destination: str = Field(description="Main destination of the journey")
    dates: List[str] = Field(description="List of dates in YYYY-MM-DD format")
    budget: float = Field(description="Total budget in USD")
    daily_plans: List[DayPlan] = Field(description="List of daily plans")
    total_cost: float = Field(description="Total cost of the journey in USD")
    recommendations: List[str] = Field(description="List of travel recommendations")

# Get the templates directory path
TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")

# Helper function to get template paths
def get_template_path(template_name):
    return os.path.join(TEMPLATES_DIR, template_name)

# Custom Observer for Workflow Events
async def journey_progress_observer(event: WorkflowEvent):
    if event.event_type == WorkflowEventType.WORKFLOW_STARTED:
        print(f"\n{'='*50}\n Starting Journey Planning \n{'='*50}")
    elif event.event_type == WorkflowEventType.NODE_STARTED:
        print(f"\n [{event.node_name}] Starting...")
    elif event.event_type == WorkflowEventType.NODE_COMPLETED:
        if event.node_name == "generate_day_plan":
            day_num = event.context.get("current_day", 0) + 1
            total_days = event.context["num_days"]
            print(f" Day {day_num}/{total_days} plan completed")
        elif event.node_name == "analyze_destination_info":
            print(f" Destination analysis completed for {event.context['destination']}")
        else:
            print(f" [{event.node_name}] Completed")
    elif event.event_type == WorkflowEventType.WORKFLOW_COMPLETED:
        print(f"\n{'='*50}\n Journey Planning Finished \n{'='*50}")

# Workflow Nodes
@Nodes.define(output=None)
async def validate_input(destination: str, start_date: str, end_date: str, budget: float) -> dict:
    """
    Validates input parameters and calculates trip duration.
    
    Args:
        destination: Name of the destination
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        budget: Total budget for the trip in USD
    
    Returns:
        dict: Validated input data with calculated dates
    """
    try:
        start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.datetime.strptime(end_date, "%Y-%m-%d")
        if end < start:
            raise ValueError("End date must be after start date")
        if budget <= 0:
            raise ValueError("Budget must be positive")
        days = (end - start).days + 1
        return {
            "destination": destination,
            "dates": [(start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)],
            "budget": budget,
            "num_days": days
        }
    except ValueError as e:
        raise ValueError(f"Invalid input: {str(e)}")

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_research_destination.j2"),
    output="destination_info",
    prompt_file=get_template_path("prompt_research_destination.j2"),
    temperature=0.7,
)
async def research_destination(model: str, destination: str) -> str:
    """
    Researches destination information using LLM.
    
    Args:
        model: LLM model to use
        destination: Name of the destination
    
    Returns:
        str: Researched information about the destination
    """
    logger.debug(f"Researching destination: {destination}")
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_destination.j2"),
    output="destination_analysis",
    response_model=DestinationAnalysis,
    prompt_file=get_template_path("prompt_analyze_destination.j2"),
    temperature=0.5,
)
async def analyze_destination_info(model: str, destination_info: str) -> DestinationAnalysis:
    """
    Analyzes destination information and structures it.
    
    Args:
        model: LLM model to use
        destination_info: Raw destination information
    
    Returns:
        DestinationAnalysis: Structured analysis of the destination
    """
    logger.debug("Analyzing destination information")
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_cultural.j2"),
    output="cultural_analysis",
    response_model=CulturalInfo,
    prompt_file=get_template_path("prompt_analyze_cultural.j2"),
    temperature=0.7,
)
async def analyze_cultural_info(model: str, destination_info: str) -> CulturalInfo:
    """Analyzes cultural aspects of the destination."""
    logger.debug("Analyzing cultural information")
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_transportation.j2"),
    output="transportation_analysis",
    response_model=TransportationGuide,
    prompt_file=get_template_path("prompt_analyze_transportation.j2"),
    temperature=0.7,
)
async def analyze_transportation(model: str, destination_info: str) -> TransportationGuide:
    """Analyzes transportation options."""
    logger.debug("Analyzing transportation options")
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_analyze_safety.j2"),
    output="safety_analysis",
    response_model=EmergencyInfo,
    prompt_file=get_template_path("prompt_analyze_safety.j2"),
    temperature=0.7,
)
async def analyze_safety_info(model: str, destination_info: str) -> EmergencyInfo:
    """Analyzes safety and emergency information."""
    logger.debug("Analyzing safety information")
    pass

@Nodes.structured_llm_node(
    system_prompt_file=get_template_path("system_generate_day_plan.j2"),
    output="day_plan",
    response_model=DayPlan,
    prompt_file=get_template_path("prompt_generate_day_plan.j2"),
    temperature=0.7,
)
async def generate_day_plan(
    model: str,
    destination: str,
    date: str,
    destination_analysis: DestinationAnalysis,
    budget_per_day: float,
    previous_day_plan: Optional[DayPlan] = None
) -> DayPlan:
    """
    Generates a daily plan with activities, accommodation, and transportation.
    
    Args:
        model: LLM model to use
        destination: Name of the destination
        date: Date for this plan in YYYY-MM-DD format
        destination_analysis: Analyzed destination information
        budget_per_day: Budget allocated for this day
        previous_day_plan: Previous day's plan for continuity
    
    Returns:
        DayPlan: Structured plan for the day
    """
    logger.debug(f"Generating plan for {date}")
    pass

@Nodes.define(output="current_day")
async def update_journey_plan(
    journey_plan: Optional[JourneyPlan],
    day_plan: DayPlan,
    current_day: int,
    destination: str,
    dates: List[str],
    budget: float
) -> int:
    """
    Updates the journey plan with a new day plan.
    
    Args:
        journey_plan: Current journey plan or None if first day
        day_plan: New day plan to add
        current_day: Current day index
        destination: Name of the destination
        dates: List of all dates
        budget: Total budget
    
    Returns:
        int: Updated current day index
    """
    if journey_plan is None:
        journey_plan = JourneyPlan(
            destination=destination,
            dates=dates,
            budget=budget,
            daily_plans=[],
            total_cost=0.0,
            recommendations=[]
        )
    
    journey_plan.daily_plans.append(day_plan)
    
    # Update total cost
    day_cost = sum(activity.cost for activity in day_plan.activities)
    day_cost += sum(transport.cost for transport in day_plan.transportation)
    if day_plan.accommodation:
        # Extract numeric value from price range (e.g., "100-150" -> 125)
        price_range = day_plan.accommodation.price_range
        avg_price = sum(float(x) for x in price_range.replace('$', '').split('-')) / 2
        day_cost += avg_price
    
    journey_plan.total_cost += day_cost
    
    logger.debug(f"Updated journey plan for day {current_day + 1}. Total cost: ${journey_plan.total_cost:.2f}")
    return current_day + 1

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_generate_recommendations.j2"),
    output="recommendations",
    prompt_file=get_template_path("prompt_generate_recommendations.j2"),
    temperature=0.7,
)
async def generate_recommendations(
    model: str,
    journey_plan: JourneyPlan,
    destination_analysis: DestinationAnalysis
) -> List[str]:
    """
    Generates final recommendations based on the journey plan.
    
    Args:
        model: LLM model to use
        journey_plan: Complete journey plan
        destination_analysis: Analyzed destination information
    
    Returns:
        List[str]: List of travel recommendations
    """
    logger.debug("Generating final recommendations")
    pass

@Nodes.llm_node(
    system_prompt_file=get_template_path("system_generate_html.j2"),
    output="html_content",
    prompt_file=get_template_path("prompt_generate_html.j2"),
    temperature=0.7,
)
async def generate_html_content(
    model: str,
    journey_plan: JourneyPlan,
    destination_analysis: DestinationAnalysis,
    cultural_analysis: CulturalInfo,
    transportation_analysis: TransportationGuide,
    safety_analysis: EmergencyInfo
) -> str:
    """Generates a beautiful HTML page using Tailwind CSS."""
    logger.debug("Generating HTML content")
    
    # Pre-serialize all data using our CustomJSONEncoder
    serialized_data = json.dumps({
        "journey_plan": journey_plan.model_dump(),
        "destination_analysis": destination_analysis.model_dump(),
        "cultural_analysis": cultural_analysis.model_dump(),
        "transportation_analysis": transportation_analysis.model_dump(),
        "safety_analysis": safety_analysis.model_dump()
    }, cls=CustomJSONEncoder)
    
    # Parse back to dict to ensure it's fully serialized
    context = json.loads(serialized_data)
    return context

@Nodes.define(output=None)
async def save_journey_plan(
    journey_plan: Dict[str, Any],
    recommendations: List[str],
    html_content: str
) -> None:
    """Saves the journey plan and generates a beautiful HTML page."""
    journey_plan_dict = journey_plan if isinstance(journey_plan, dict) else journey_plan.model_dump()
    destination_analysis_dict = journey_plan_dict.get("destination_analysis", {}).model_dump()

    # Create output directory if it doesn't exist
    output_dir = Path.cwd()
    output_dir.mkdir(exist_ok=True)

    # Save JSON output
    json_path = output_dir / f"{journey_plan_dict['destination'].lower().replace(' ', '_')}_plan.json"
    with open(json_path, "w") as f:
        json.dump({
            "journey_plan": journey_plan_dict,
            "destination_analysis": destination_analysis_dict
        }, f, indent=2)

    # Load Jinja2 template
    env = Environment(
        loader=FileSystemLoader(TEMPLATES_DIR),
        autoescape=select_autoescape(['html', 'xml'])
    )
    
    # Add custom filter to handle JSON serialization
    def safe_json(obj):
        if isinstance(obj, BaseModel):
            return obj.model_dump()
        return obj
    env.filters['safe_json'] = safe_json
    
    template = env.get_template("html_template.j2")

    # Render HTML
    html_content = template.render(
        journey_plan=journey_plan_dict,
        destination_analysis=destination_analysis_dict,
        current_date=datetime.now().strftime("%Y-%m-%d")
    )

    # Save HTML output
    html_path = output_dir / f"{journey_plan_dict['destination'].lower().replace(' ', '_')}_plan.html"
    with open(html_path, "w") as f:
        f.write(html_content)

    logger.info(f"Journey plan saved as JSON: {json_path}")
    logger.info(f"Journey plan saved as HTML: {html_path}")

    # Display summary
    print("\n" + "="*50)
    print(f" Journey Plan for {journey_plan_dict['destination']}")
    print("="*50)
    print(f" Dates: {journey_plan_dict['dates'][0]} to {journey_plan_dict['dates'][-1]}")
    print(f" Total Cost: ${journey_plan_dict['total_cost']:.2f} (Budget: ${journey_plan_dict['budget']:.2f})")
    print("\n Key Recommendations:")
    for i, rec in enumerate(recommendations[:5], 1):
        print(f"  {i}. {rec}")
    print("\n Files saved:")
    print(f"  JSON Plan: {json_path}")
    print(f"  HTML Guide: {html_path}")
    print("="*50)

# Define the enhanced Workflow
workflow = (
    Workflow("validate_input")
    .then("research_destination")
    .then("analyze_destination_info")
    .then("analyze_cultural_info")
    .then("analyze_transportation")
    .then("analyze_safety_info")
    .then("generate_day_plan")
    .node("generate_day_plan", inputs_mapping={
        "destination": "destination",
        "date": lambda ctx: ctx["dates"][ctx.get("current_day", 0)],
        "destination_analysis": "destination_analysis",
        "budget_per_day": lambda ctx: ctx["budget"] / len(ctx["dates"]),
        "previous_day_plan": lambda ctx: (
            ctx["journey_plan"].daily_plans[-1] if ctx.get("journey_plan") and ctx["journey_plan"].daily_plans 
            else None
        ),
        "model": "model"
    })
    .then("update_journey_plan")
    .branch([
        ("generate_day_plan", lambda ctx: ctx["current_day"] < ctx["num_days"]),
        ("generate_recommendations", lambda ctx: ctx["current_day"] >= ctx["num_days"])
    ])
    .node("generate_recommendations", inputs_mapping={
        "model": "model",
        "journey_plan": lambda ctx: ctx.get("journey_plan"),
        "destination_analysis": lambda ctx: ctx.get("destination_analysis")
    })
    .then("generate_html_content")
    .node("generate_html_content", inputs_mapping={
        "model": "model",
        "journey_plan": "journey_plan",
        "destination_analysis": "destination_analysis",
        "cultural_analysis": "cultural_analysis",
        "transportation_analysis": "transportation_analysis",
        "safety_analysis": "safety_analysis"
    })
    .node("save_journey_plan", inputs_mapping={
        "journey_plan": lambda ctx: ctx.get("journey_plan"),
        "recommendations": lambda ctx: ctx.get("recommendations", []),
        "html_content": "html_content"
    })
)

async def generate_journey_plan(
    destination: str,
    start_date: str,
    end_date: str,
    budget: float,
    model: str = "gemini/gemini-2.0-flash",
    task_id: str = "default",
    _handle_event: Optional[Callable[[str, Dict[str, Any]], None]] = None
) -> JourneyPlan:
    """
    Generate a detailed journey plan.
    
    Args:
        destination: Name of the destination
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
        budget: Total budget for the trip in USD
        model: LLM model to use
        task_id: Unique identifier for the task
        _handle_event: Optional callback for event handling
    
    Returns:
        JourneyPlan: Complete journey plan with daily activities
    """
    initial_context = {
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "budget": budget,
        "model": model,
        "current_day": 0
    }
 

    logger.info(f"Starting journey planning for {destination}")
    engine = workflow.build()

    
    # Create custom observer that uses _handle_event if provided
    async def event_observer(event: WorkflowEvent):
        if not _handle_event:
            return

        # Base event data that's common across all events
        base_event_data = {
            "task_id": task_id,
            "agent_id": "default",
            "timestamp": datetime.datetime.now().isoformat(),
            "event_type": event.event_type.value
        }

        # Handle streaming chunks immediately
        logger.info(f"=========================== Event type: {event.event_type}  ============================")


        if event.event_type == WorkflowEventType.STREAMING_CHUNK:
            _handle_event("streaming_chunk", {
                **base_event_data,
                "content": event.result,  # Changed from event.context.get("result", "")
                "node_name": event.node_name,
                "message": "Streaming content chunk"
            })
            return

        # Event type specific handling
        event_mapping = {
            WorkflowEventType.WORKFLOW_STARTED: {
                "event": "workflow_started",
                "data": {
                    **base_event_data,
                    "message": "Starting tutorial generation", 
                }
            },
            WorkflowEventType.WORKFLOW_COMPLETED: {
                "event": "workflow_completed",
                "data": {
                    **base_event_data,
                    "message": "Tutorial generation completed",
                    "result": event.result
                }
            },
            WorkflowEventType.NODE_STARTED: {
                "event": "node_started",
                "data": {
                    **base_event_data,
                    "node_name": event.node_name,
                    "message": f"Starting node: {event.node_name}"
                }
            },
            WorkflowEventType.NODE_COMPLETED: {
                "event": "node_completed",
                "data": {
                    **base_event_data,
                    "node_name": event.node_name,
                    "result": event.result,
                    "message": f"Completed node: {event.node_name}"
                }
            },
            WorkflowEventType.NODE_FAILED: {
                "event": "node_failed",
                "data": {
                    **base_event_data,
                    "node_name": event.node_name,
                    "error": str(event.exception),
                    "message": f"Node failed: {event.node_name}"
                }
            },
            WorkflowEventType.TRANSITION_EVALUATED: {
                "event": "transition_evaluated",
                "data": {
                    **base_event_data,
                    "from_node": event.transition_from,
                    "to_node": event.transition_to,
                    "message": f"Transition: {event.transition_from} -> {event.transition_to}"
                }
            }
        }

        # Get the event configuration
        event_config = event_mapping.get(event.event_type)
        if event_config:
            # Special handling for specific nodes
            if event.event_type == WorkflowEventType.NODE_COMPLETED:
                if event.node_name == "compile_book":
                    _handle_event("workflow_completed", {
                        **base_event_data,
                        "message": "Tutorial compilation completed",
                        "result": event.result
                    })
                elif event.node_name == "update_chapters":
                    chapter_num = event.result
                    total_chapters = len(event.context["structure"].chapters)
                    _handle_event("task_progress", {
                        **base_event_data,
                        "message": f"Generated chapter {chapter_num} of {total_chapters}",
                        "progress": {
                            "current": chapter_num,
                            "total": total_chapters,
                            "percentage": round((chapter_num / total_chapters) * 100)
                        },
                        "preview": "\n".join(event.context["completed_chapters"][-1].split('\n')[:3])
                    })
            
            # Send the event
            _handle_event(event_config["event"], event_config["data"])

    if _handle_event:
        engine.add_observer(event_observer)

    # engine.add_observer(journey_progress_observer)
    
    result = await engine.run(initial_context)
    logger.info("Journey planning completed successfully ")
    logger.debug(f"Journey plan: {result}")
    return result

if __name__ == "__main__":
    import asyncio
    
    async def main():
        # Test the journey planner with a sample trip to Paris
        try:
            logger.debug("Starting journey planning for Paris")
            result = await generate_journey_plan(
                destination="Paris",
                start_date="2025-04-01",
                end_date="2025-04-03",  # 3-day trip
                budget=1500.0,  # Budget in USD
                model="gemini/gemini-2.0-flash"
            )
            print("\nJourney plan generated successfully! ")
            print(f"Check the journey_plans directory for the detailed plan.")
        except Exception as e:
            print(f"Error generating journey plan: {str(e)}")
    
    asyncio.run(main())