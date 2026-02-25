"""AST node data models."""

from typing import List, Optional

from pydantic import BaseModel


class ASTNode(BaseModel):
    """Abstract Syntax Tree node representation."""

    node_type: str
    start_line: int
    end_line: int
    start_column: int
    end_column: int
    children: List['ASTNode'] = []
    text: Optional[str] = None


# Enable forward references for recursive model
ASTNode.model_rebuild()
