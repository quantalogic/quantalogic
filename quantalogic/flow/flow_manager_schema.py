# quantalogic/flow/flow_manager_schema.py

from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class FunctionDefinition(BaseModel):
    type: str
    code: Optional[str] = None
    module: Optional[str] = None
    function: Optional[str] = None

class NodeDefinition(BaseModel):
    function: str
    output: str
    retries: int = 3
    delay: float = 1.0
    timeout: Optional[float] = None
    parallel: bool = False

class TransitionDefinition(BaseModel):
    from_: str
    to: Union[str, List[str]]
    condition: Optional[str] = None

class WorkflowStructure(BaseModel):
    start: Optional[str] = None
    transitions: List[TransitionDefinition] = []

class WorkflowDefinition(BaseModel):
    functions: Dict[str, FunctionDefinition] = {}
    nodes: Dict[str, NodeDefinition] = {}
    workflow: WorkflowStructure = WorkflowStructure()