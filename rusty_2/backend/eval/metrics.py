"""Evaluation metrics and result structures."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class EvalResult:
    """
    Result of evaluating a DevAgent task execution.
    
    This dataclass captures the key metrics for evaluating whether
    the DevAgent successfully completed a task:
    - Compilation/runtime success
    - Test suite success
    - Behavioral correctness (solving the original task)
    - Static analysis success (linters, SCA)
    
    Attributes:
        task_id: Unique identifier for the task
        success_compile: Whether the code compiles/runs successfully
        success_tests: Whether the test suite passes
        success_behaviour: Whether the task was solved correctly
        success_static: Whether static checks pass
        steps: Number of agent steps executed
        notes: Optional notes or summary of changes
        chat_path: Optional path to saved conversation JSON file
    """
    
    task_id: str
    success_compile: bool
    success_tests: bool
    success_behaviour: bool
    success_static: bool
    steps: int
    notes: Optional[str] = None
    chat_path: Optional[str] = None
    
    def to_dict(self) -> dict:
        """
        Convert EvalResult to dictionary for serialization.
        
        Returns:
            dict: Dictionary representation of the result
        """
        return {
            "task_id": self.task_id,
            "success_compile": self.success_compile,
            "success_tests": self.success_tests,
            "success_behaviour": self.success_behaviour,
            "success_static": self.success_static,
            "steps": self.steps,
            "notes": self.notes,
            "chat_path": self.chat_path,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "EvalResult":
        """
        Create EvalResult from dictionary.
        
        Args:
            data: Dictionary containing result data
            
        Returns:
            EvalResult: Instance created from dictionary
        """
        return cls(
            task_id=data["task_id"],
            success_compile=data["success_compile"],
            success_tests=data["success_tests"],
            success_behaviour=data["success_behaviour"],
            success_static=data["success_static"],
            steps=data["steps"],
            notes=data.get("notes"),
            chat_path=data.get("chat_path"),
        )

