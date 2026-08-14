"""CLI 端到端测试：子命令、错误处理、环境变量、子进程冒烟。"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from helpers import ReqPipeTestCase


class CliBasicsTests(ReqPipeTestCase):
    def test_version(self):
        code, out, _ = self.run_cli("--version", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("reqpipe", out)

    def test_help_lists_commands(self):
        code, out, _ = self.run_cli("--help", root=self.root)
        self.assertEqual(code, 0)
        for cmd in ("init", "create", "advance", "skip", "review", "list", "show", "checklist"):
            self.assertIn(cmd, out)

    def test_init(self):
        code, out, _ = self.run_cli("init", root=self.root)
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "README.md").is_file())

    def test_unknown_command_fails(self):
        code, _, _ = self.run_cli("frobnicate", root=self.root)
        self.assertEqual(code, 2)


class CliFlowTests(ReqPipeTestCase):
    def test_create_and_advance(self):
        code, out, _ = self.run_cli("create", "登录模块", "--id", "REQ-1", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("REQ-1", out)
        code, out, _ = self.run_cli("advance", "REQ-1", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("需求 阶段已完成", out)

    def test_light_flow_via_cli(self):
        self.run_cli("create", "小需求", "--id", "REQ-1", "--light", root=self.root)
        self.run_cli("advance", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("skip", "REQ-1", "design", "--reason", "轻量", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("已跳过", out)
        self.run_cli("skip", "REQ-1", "review", "--reason", "轻量", root=self.root)
        self.run_cli("advance", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("list", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("已完成", out)
        self.assertIn("轻量", out)

    def test_skip_with_chinese_stage_label(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("skip", "REQ-1", "方案", "--reason", "r", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("已跳过", out)

    def test_skip_without_reason_rejected(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, _, _ = self.run_cli("skip", "REQ-1", "design", root=self.root)
        self.assertNotEqual(code, 0)

    def test_skip_requirement_rejected(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, _, err = self.run_cli("skip", "REQ-1", "requirement", "--reason", "r", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("不允许跳过", err)

    def test_show(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("show", "REQ-1", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("REQ-1", out)

    def test_show_missing_id_fails(self):
        code, _, err = self.run_cli("show", "NOPE", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("未找到", err)

    def test_list_json(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("list", "--json", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn('"id": "REQ-1"', out)

    def test_list_json_empty_root(self):
        code, out, _ = self.run_cli("list", "--json", root=self.root)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), [])

    def test_checklist_stdout_and_file(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("checklist", "REQ-1", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("提交清单", out)
        out_file = self.root / "CHECK.md"
        code, out, _ = self.run_cli("checklist", "REQ-1", "-o", str(out_file), root=self.root)
        self.assertEqual(code, 0)
        self.assertTrue(out_file.is_file())
        self.assertIn("提交清单", out_file.read_text(encoding="utf-8"))

    def test_create_json(self):
        code, out, _ = self.run_cli("create", "登录模块", "--id", "REQ-1", "--light", "--json", root=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertEqual(data["id"], "REQ-1")
        self.assertTrue(data["light"])
        self.assertEqual(len(data["stages"]), 4)

    def test_advance_json(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("advance", "REQ-1", "--json", root=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("pipeline", data)
        self.assertIn("messages", data)
        self.assertEqual(data["pipeline"]["stages"][0]["status"], "done")
        self.assertTrue(any("需求 阶段已完成" in m for m in data["messages"]))

    def test_skip_json_records_reason(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("skip", "REQ-1", "design", "--reason", "太简单", "--json", root=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        design = data["pipeline"]["stages"][1]
        self.assertEqual(design["status"], "skipped")
        self.assertEqual(design["reason"], "太简单")

    def test_checklist_json(self):
        self.run_cli("create", "x", "--id", "REQ-1", root=self.root)
        code, out, _ = self.run_cli("checklist", "REQ-1", "--json", root=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("markdown", data)
        self.assertIn("# 提交清单", data["markdown"])

    def test_root_flag_position_agnostic(self):
        code, out, _ = self.run_cli("create", "x", "--id", "REQ-1", "--root", str(self.root))
        self.assertEqual(code, 0)
        self.assertTrue((self.root / "REQ-1").is_dir())

    def test_env_root(self):
        os.environ["REQPIPE_ROOT"] = str(self.root)
        try:
            code, out, _ = self.run_cli("create", "env需求", "--id", "REQ-1")
            self.assertEqual(code, 0)
            self.assertTrue((self.root / "REQ-1").is_dir())
        finally:
            del os.environ["REQPIPE_ROOT"]

    def test_module_smoke(self):
        repo = Path(__file__).resolve().parents[1]
        env = dict(os.environ)
        env["PYTHONPATH"] = str(repo)
        r = subprocess.run(
            [sys.executable, "-m", "reqpipe", "--version"],
            cwd=str(repo), env=env, capture_output=True, text=True,
        )
        self.assertEqual(r.returncode, 0)
        self.assertIn("reqpipe", r.stdout)


class CliReviewTests(ReqPipeTestCase):
    """评审闸门：评审人 ≠ 方案作者，reject 打回返工。"""

    def _create_and_advance_to_review(self):
        self.run_cli("create", "导出优化", "--id", "REQ-1", root=self.root)
        self.run_cli("advance", "REQ-1", "--by", "alice", root=self.root)
        self.run_cli("advance", "REQ-1", "--by", "alice", root=self.root)

    def test_advance_review_stage_rejected(self):
        self._create_and_advance_to_review()
        code, _, err = self.run_cli("advance", "REQ-1", "--by", "alice", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("review 动作", err)

    def test_review_requires_reviewer(self):
        self._create_and_advance_to_review()
        code, _, err = self.run_cli("review", "REQ-1", "--verdict", "approve", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("评审人身份", err)

    def test_self_review_rejected(self):
        self._create_and_advance_to_review()
        code, _, err = self.run_cli("review", "REQ-1", "--by", "alice", "--verdict", "approve", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("不能评审自己的方案", err)

    def test_review_approve_enters_development(self):
        self._create_and_advance_to_review()
        code, out, _ = self.run_cli("review", "REQ-1", "--by", "bob", "--verdict", "approve", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("评审通过", out)
        code, out, _ = self.run_cli("list", "--json", root=self.root)
        data = json.loads(out)
        review = data[0]["stages"][2]
        self.assertEqual(review["status"], "done")
        self.assertEqual(review["done_by"], "bob")
        self.assertEqual(data[0]["current_stage"], "development")

    def test_reject_sends_back_to_rework(self):
        self._create_and_advance_to_review()
        code, out, _ = self.run_cli(
            "review", "REQ-1", "--by", "bob", "--verdict", "reject",
            "--comment", "选型有风险", root=self.root,
        )
        self.assertEqual(code, 0)
        self.assertIn("打回返工", out)
        code, out, _ = self.run_cli("list", "--json", root=self.root)
        data = json.loads(out)
        self.assertEqual(data[0]["stages"][1]["status"], "rejected")
        self.assertEqual(data[0]["current_stage"], "design")
        self.assertEqual(len(data[0]["stages"][2]["reviews"]), 1)
        self.assertIn("选型有风险", data[0]["stages"][2]["reviews"][0]["comment"])

    def test_review_json_shape(self):
        self._create_and_advance_to_review()
        code, out, _ = self.run_cli("review", "REQ-1", "--by", "bob", "--verdict", "approve", "--json", root=self.root)
        self.assertEqual(code, 0)
        data = json.loads(out)
        self.assertIn("pipeline", data)
        self.assertIn("messages", data)
        self.assertTrue(any("评审通过" in m for m in data["messages"]))

    def test_author_cannot_skip_own_review_via_cli(self):
        self._create_and_advance_to_review()
        code, _, err = self.run_cli("skip", "REQ-1", "review", "--reason", "不需要", "--by", "alice", root=self.root)
        self.assertEqual(code, 1)
        self.assertIn("不能跳过自己方案的评审", err)

    def test_show_displays_review_records(self):
        self._create_and_advance_to_review()
        self.run_cli("review", "REQ-1", "--by", "bob", "--verdict", "reject", "--comment", "需返工", root=self.root)
        code, out, _ = self.run_cli("show", "REQ-1", root=self.root)
        self.assertEqual(code, 0)
        self.assertIn("需返工", out)
        self.assertIn("bob", out)


if __name__ == "__main__":
    unittest.main()
