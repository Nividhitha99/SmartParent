"""Exercise the endpoint with isolated external services and a real worker thread."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock
from agent_workflow import PlanGenerationError


class HTTPException(Exception):
    def __init__(self, status_code, detail):
        self.status_code = status_code


class EndpointTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        source = Path(__file__).resolve().parents[1] / "main.py"
        node = next(n for n in ast.parse(source.read_text()).body
                    if isinstance(n, ast.AsyncFunctionDef) and n.name == "plan_from_text")
        node.decorator_list = []
        node.args.defaults = []
        self.db = SimpleNamespace(insert_one=AsyncMock())
        self.generator = Mock(return_value={"kind": "food", "steps": []})
        self.publisher = Mock()
        scope = dict(HTTPException=HTTPException, PlanGenerationError=PlanGenerationError,
                     run_in_threadpool=asyncio.to_thread, generate_agent_plan=self.generator,
                     plans=self.db, publish_plan_event=self.publisher,
                     _finalize_plan=lambda plan: dict(plan, plan_id="test-id", done=False),
                     JSONResponse=lambda plan: plan)
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(source), "exec"), scope)
        self.endpoint = scope["plan_from_text"]

    async def test_success_persists_and_publishes_once(self):
        result = await self.endpoint("Lunch note")
        self.db.insert_one.assert_awaited_once_with(result)
        self.publisher.assert_called_once_with(result)
        self.assertEqual(result["plan_id"], "test-id")

    async def test_generation_failure_has_no_side_effects(self):
        self.generator.side_effect = PlanGenerationError("failure")
        with self.assertRaises(HTTPException) as caught:
            await self.endpoint("Lunch note")
        self.assertEqual(caught.exception.status_code, 502)
        self.db.insert_one.assert_not_awaited()
        self.publisher.assert_not_called()

    async def test_blank_input_has_no_side_effects(self):
        with self.assertRaises(HTTPException) as caught:
            await self.endpoint(" ")
        self.assertEqual(caught.exception.status_code, 422)
        self.generator.assert_not_called()
        self.db.insert_one.assert_not_awaited()
        self.publisher.assert_not_called()
