import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import Mock
from agent_workflow import build_agent_workflow, generate_agent_plan, PlanGenerationError


def plan(kind, text="note"):
    return dict(kind=kind, raw_text=text, steps=[], shopping_list=[], recipes=[],
                materials=[], daily_plan=[], solutions=[], title="Example")


class AgentWorkflowTests(unittest.TestCase):
    def workflow(self, kind):
        self.tools = {k: Mock(side_effect=lambda text, k=k: plan(k, text))
                      for k in ("food", "activity", "other")}
        return build_agent_workflow(lambda text: kind, self.tools)

    def test_routes_to_only_selected_specialist(self):
        for kind in ("food", "activity", "other"):
            with self.subTest(kind=kind):
                result = generate_agent_plan("note", workflow=self.workflow(kind))
                self.assertEqual(result, plan(kind))
                for name, tool in self.tools.items():
                    self.assertEqual(tool.call_count, int(name == kind))

    def test_unknown_route_uses_general_note(self):
        result = generate_agent_plan("note", workflow=self.workflow("unknown"))
        self.assertEqual(result["kind"], "other")

    def test_malformed_plan_is_rejected(self):
        graph = self.workflow("food")
        self.tools["food"].side_effect = lambda text: {"kind": "food"}
        with self.assertRaises(PlanGenerationError):
            generate_agent_plan("note", workflow=graph)

    def test_mismatched_plan_is_rejected(self):
        graph = self.workflow("food")
        self.tools["food"].side_effect = lambda text: plan("activity")
        with self.assertRaises(PlanGenerationError):
            generate_agent_plan("note", workflow=graph)

    def test_provider_exception_does_not_leak(self):
        graph = self.workflow("food")
        self.tools["food"].side_effect = RuntimeError("provider details")
        with self.assertRaisesRegex(PlanGenerationError, "^Unable to generate a valid plan$"):
            generate_agent_plan("note", workflow=graph)

    def test_invalid_input_never_calls_tools(self):
        graph = self.workflow("food")
        for text in (" ", "x" * 20001):
            with self.assertRaises(ValueError):
                generate_agent_plan(text, workflow=graph)
        self.assertTrue(all(tool.call_count == 0 for tool in self.tools.values()))

    def test_shared_graph_keeps_requests_isolated(self):
        graph = self.workflow("food")
        notes = ["note " + str(i) for i in range(12)]
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda text: generate_agent_plan(text, workflow=graph), notes))
        self.assertEqual([result["raw_text"] for result in results], notes)


if __name__ == "__main__":
    unittest.main()
