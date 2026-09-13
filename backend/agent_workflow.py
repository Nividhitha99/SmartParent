"""Bounded LangGraph supervisor workflow for school-note planning.

The classifier selects a specialist; agents reuse existing Claude/NLP tools.
No database writes or event publication happen inside the graph.
"""
from functools import lru_cache
from typing import Callable, Literal, TypedDict
from langgraph.graph import StateGraph, START, END
from pydantic import BaseModel, ConfigDict


class PlanGenerationError(RuntimeError):
    """Planning failed before persistence."""


class PlanEnvelope(BaseModel):
    model_config = ConfigDict(extra="allow", strict=True)
    kind: Literal["food", "activity", "other"]
    raw_text: str
    steps: list[dict]
    shopping_list: list[str]
    recipes: list[dict]
    materials: list[dict]
    daily_plan: list[dict]
    solutions: list[dict]


class PlannerState(TypedDict, total=False):
    text: str
    kind: str
    plan: dict


def build_agent_workflow(classify: Callable, specialists: dict[str, Callable]):
    """Inject tools so routing can be tested without providers or databases."""
    kinds = ("food", "activity", "other")
    if set(specialists) != set(kinds):
        raise ValueError("Provide food, activity, and other specialists")

    def supervisor(state):
        kind = classify(state["text"])
        return {"kind": kind if kind in kinds else "other"}

    def specialist_node(kind):
        def run(state):
            return {"plan": specialists[kind](state["text"])}
        return run

    def validate(state):
        plan = state["plan"]
        PlanEnvelope.model_validate(plan)
        if plan["kind"] != state["kind"]:
            raise ValueError("Specialist returned the wrong plan kind")
        # Validate without dropping existing frontend fields.
        return {"plan": plan}

    graph = StateGraph(PlannerState)
    graph.add_node("supervisor", supervisor)
    graph.add_edge(START, "supervisor")
    for kind in kinds:
        graph.add_node(kind + "_agent", specialist_node(kind))
        graph.add_edge(kind + "_agent", "validate")
    graph.add_conditional_edges("supervisor", lambda state: state["kind"],
                                {kind: kind + "_agent" for kind in kinds})
    graph.add_node("validate", validate)
    graph.add_edge("validate", END)
    return graph.compile()


@lru_cache(maxsize=1)
def _default_workflow():
    from project_planner import classify_circular
    from planning_tools import plan_food, plan_activity, plan_other
    return build_agent_workflow(classify_circular, {
        "food": plan_food, "activity": plan_activity, "other": plan_other,
    })


def generate_agent_plan(text: str, *, workflow=None) -> dict:
    if not text.strip() or len(text) > 20000:
        raise ValueError("Note must contain 1–20000 characters")
    try:
        graph = workflow if workflow is not None else _default_workflow()
        return graph.invoke({"text": text}, {"recursion_limit": 8})["plan"]
    except Exception as exc:
        raise PlanGenerationError("Unable to generate a valid plan") from exc
