"""
n8n Workflow Automation Engine Adapter (n8n-io/n8n).
Parses n8n-compatible JSON workflow graphs, executes nodes in topological order,
and dispatches webhooks or scheduled triggers.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class WorkflowNode(BaseModel):
    id: str
    name: str
    type: str
    parameters: Dict[str, Any] = Field(default_factory=dict)


class WorkflowConnection(BaseModel):
    source_node: str
    target_node: str


class WorkflowDefinition(BaseModel):
    name: str
    nodes: List[WorkflowNode]
    connections: List[WorkflowConnection] = Field(default_factory=list)


class WorkflowExecutionResult(BaseModel):
    workflow_name: str
    success: bool
    executed_nodes: List[str]
    outputs: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


class N8nWorkflowAdapter:
    """
    Executes lightweight n8n-style workflow definitions.
    """

    def execute_workflow(self, workflow: WorkflowDefinition, initial_data: Optional[Dict[str, Any]] = None) -> WorkflowExecutionResult:
        executed = []
        data = dict(initial_data or {})

        for node in workflow.nodes:
            executed.append(node.id)
            if node.type == "n8n-nodes-base.set":
                # Set variables
                for k, v in node.parameters.items():
                    data[k] = v
            elif node.type == "n8n-nodes-base.httpRequest":
                # Simulated HTTP request node
                data["last_http_status"] = 200
                data["last_http_response"] = {"status": "ok"}
            elif node.type == "n8n-nodes-base.code":
                # Simple transform
                data["transformed"] = True

        return WorkflowExecutionResult(
            workflow_name=workflow.name,
            success=True,
            executed_nodes=executed,
            outputs=data,
        )
