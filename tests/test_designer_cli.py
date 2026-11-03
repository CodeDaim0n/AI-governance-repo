import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fabric.workflow_cli import main


class DesignerCLITests(unittest.TestCase):
    def invoke(self, args):
        with patch("sys.argv", ["fabric-workflow", *args]), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return main()

    def test_prose_input_exports_draft_and_readable_report_without_runtime_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / "workflow.txt"
            source.write_text("A curator reviews museum loan requests.", encoding="utf-8")
            result = {"schema_version": 1, "kind": "workflow_governance_design", "status": "draft_requires_review"}
            with patch("fabric.designer.WorkflowDesigner") as designer, patch("fabric.designer.render_design_report", return_value="# Review draft\n"):
                designer.return_value.design.return_value = result
                self.invoke(["design", "--description-file", str(source), "--model", "test-model", "--output", str(root / "design.json"), "--report", str(root / "review.md")])
                designer.return_value.design.assert_called_once_with(source.read_text(encoding="utf-8"))
            self.assertEqual(json.loads((root / "design.json").read_text()), result)
            self.assertEqual((root / "review.md").read_text(), "# Review draft\n")
            self.assertFalse((root / "opa-data.json").exists())

    def test_invalid_command_combinations_fail_before_model_call(self):
        combinations = [
            ["design", "--description", "A process"],
            ["design", "--model", "test-model"],
            ["design", "--description", "A process", "--model", "test-model", "--opa-data", "unused.json"],
            ["design", "--description", "A process", "--model", "test-model", "--workflow", "unused.json"],
            ["assess"],
            ["assess", "--workflow", "unused.json", "--description", "A process"],
            ["assess", "--workflow", "unused.json", "--thinking"],
        ]
        with patch("fabric.designer.WorkflowDesigner") as designer:
            for args in combinations:
                with self.subTest(args=args), self.assertRaises(SystemExit) as error:
                    self.invoke(args)
                self.assertEqual(error.exception.code, 2)
            designer.assert_not_called()

    def test_model_failure_does_not_write_success_artifacts(self):
        from fabric.designer import DesignerError
        with tempfile.TemporaryDirectory() as folder, patch("fabric.designer.WorkflowDesigner") as designer:
            target = Path(folder) / "design.json"
            designer.return_value.design.side_effect = DesignerError("model_unavailable")
            with self.assertRaises(SystemExit) as error:
                self.invoke(["design", "--description", "A curator reviews requests.", "--model", "test-model", "--output", str(target)])
            self.assertEqual(error.exception.code, 2)
            self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
