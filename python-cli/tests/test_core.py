"""核心逻辑测试：创建 / 推进 / 跳过 / 清单 / 轻量流程。"""

import unittest

from reqpipe.errors import CreateError, InvalidStageError, NotFoundError, SkipError, StageError
from reqpipe.pipeline import STAGES, create_pipeline, list_pipelines, load_pipeline, next_id

from helpers import ReqPipeTestCase


class CreateTests(ReqPipeTestCase):
    def test_create_basic_structure(self):
        m = create_pipeline(self.root, "登录模块改造")
        req_id = m["id"]
        self.assertEqual(req_id, "REQ-001")
        d = self.root / req_id
        self.assertTrue(d.is_dir())
        for s in STAGES:
            self.assertTrue((d / s["dir"]).is_dir(), s["dir"])
        req_doc = d / "01-requirement" / "REQUIREMENT.md"
        self.assertTrue(req_doc.is_file())
        self.assertIn("登录模块改造", req_doc.read_text(encoding="utf-8"))
        self.assertEqual(len(m["stages"]), 4)
        self.assertTrue(all(s["status"] == "pending" for s in m["stages"]))
        self.assertFalse(m["light"])

    def test_auto_id_increments(self):
        a = create_pipeline(self.root, "A")
        b = create_pipeline(self.root, "B")
        self.assertEqual((a["id"], b["id"]), ("REQ-001", "REQ-002"))

    def test_next_id_skips_existing_numbers(self):
        create_pipeline(self.root, "A", req_id="REQ-005")
        self.assertEqual(next_id(self.root), "REQ-006")

    def test_custom_id_and_light(self):
        m = create_pipeline(self.root, "小需求", req_id="FEAT-1", light=True)
        self.assertEqual(m["id"], "FEAT-1")
        self.assertTrue(m["light"])

    def test_duplicate_id_raises(self):
        create_pipeline(self.root, "A", req_id="REQ-9")
        with self.assertRaises(CreateError):
            create_pipeline(self.root, "B", req_id="REQ-9")

    def test_blank_title_raises(self):
        with self.assertRaises(CreateError):
            create_pipeline(self.root, "   ")

    def test_illegal_id_raises(self):
        with self.assertRaises(CreateError):
            create_pipeline(self.root, "A", req_id="bad/id")

    def test_create_failure_cleans_up(self):
        # 非法 ID 在创建目录前就报错，不遗留目录
        with self.assertRaises(CreateError):
            create_pipeline(self.root, "A", req_id="a/b")
        self.assertEqual(list(self.root.iterdir()), [])


class AdvanceTests(ReqPipeTestCase):
    def setUp(self):
        super().setUp()
        create_pipeline(self.root, "登录模块", req_id="REQ-1")

    def test_advance_marks_done_and_scaffolds_next(self):
        p = load_pipeline(self.root, "REQ-1")
        msgs = p.advance()
        self.assertEqual(p.stage("requirement")["status"], "done")
        self.assertEqual(p.stage("design")["status"], "pending")
        self.assertTrue((p.dir / "02-design" / "DESIGN.md").is_file())
        self.assertEqual(p.current()["name"], "design")
        self.assertTrue(any("需求 阶段已完成" in m for m in msgs))

    def test_advance_requires_doc(self):
        p = load_pipeline(self.root, "REQ-1")
        (p.dir / "01-requirement" / "REQUIREMENT.md").unlink()
        with self.assertRaises(StageError):
            p.advance()
        p.advance(force=True)
        self.assertEqual(p.stage("requirement")["status"], "done")

    def test_full_flow_to_completion(self):
        p = load_pipeline(self.root, "REQ-1")
        for _ in range(4):
            p.advance()
        self.assertTrue(p.completed())
        self.assertIsNone(p.current())
        with self.assertRaises(StageError):
            p.advance()


class SkipTests(ReqPipeTestCase):
    def setUp(self):
        super().setUp()
        create_pipeline(self.root, "登录模块", req_id="REQ-1")

    def test_skip_requires_reason(self):
        p = load_pipeline(self.root, "REQ-1")
        with self.assertRaises(SkipError):
            p.skip("design", "  ")

    def test_skip_design_records_reason(self):
        p = load_pipeline(self.root, "REQ-1")
        msgs = p.skip("design", "交互简单，无需方案文档")
        st = p.stage("design")
        self.assertEqual(st["status"], "skipped")
        self.assertEqual(st["reason"], "交互简单，无需方案文档")
        self.assertIsNotNone(st["skipped_at"])
        self.assertTrue(any("已跳过" in m for m in msgs))

    def test_skip_by_chinese_label(self):
        p = load_pipeline(self.root, "REQ-1")
        p.skip("方案", "原因")
        self.assertEqual(p.stage("design")["status"], "skipped")

    def test_skip_requirement_and_development_forbidden(self):
        p = load_pipeline(self.root, "REQ-1")
        with self.assertRaises(SkipError):
            p.skip("requirement", "r")
        with self.assertRaises(SkipError):
            p.skip("development", "r")

    def test_skip_unknown_stage(self):
        p = load_pipeline(self.root, "REQ-1")
        with self.assertRaises(InvalidStageError):
            p.skip("nope", "r")

    def test_skip_twice_forbidden(self):
        p = load_pipeline(self.root, "REQ-1")
        p.skip("design", "r1")
        with self.assertRaises(SkipError):
            p.skip("design", "r2")

    def test_skip_after_done_forbidden(self):
        p = load_pipeline(self.root, "REQ-1")
        p.advance()
        p.advance()
        with self.assertRaises(SkipError):
            p.skip("design", "r")

    def test_skip_records_history(self):
        p = load_pipeline(self.root, "REQ-1")
        p.skip("design", "太简单")
        actions = [h["action"] for h in p.data["history"]]
        self.assertIn("skip", actions)
        detail = next(h["detail"] for h in p.data["history"] if h["action"] == "skip")
        self.assertIn("太简单", detail)


class ListingTests(ReqPipeTestCase):
    def test_list_pipelines_sorted(self):
        create_pipeline(self.root, "A", req_id="REQ-1")
        create_pipeline(self.root, "B", req_id="REQ-2")
        ids = [p.id for p in list_pipelines(self.root)]
        self.assertEqual(ids, ["REQ-1", "REQ-2"])

    def test_list_empty_root(self):
        self.assertEqual(list_pipelines(self.root), [])

    def test_load_missing_raises(self):
        with self.assertRaises(NotFoundError):
            load_pipeline(self.root, "NOPE")


class ChecklistTests(ReqPipeTestCase):
    def setUp(self):
        super().setUp()
        create_pipeline(self.root, "导出优化", req_id="REQ-1")

    def test_checklist_mentions_files_and_skips(self):
        p = load_pipeline(self.root, "REQ-1")
        p.skip("design", "改动极小")
        text = p.checklist()
        self.assertIn("# 提交清单", text)
        self.assertIn("REQ-1", text)
        self.assertIn("01-requirement/REQUIREMENT.md", text)
        self.assertIn("已跳过，原因：改动极小", text)

    def test_checklist_summary_counts(self):
        p = load_pipeline(self.root, "REQ-1")
        p.skip("design", "r")
        text = p.checklist()
        self.assertIn("已完成：0 个阶段；已跳过：1 个；待完成：3 个", text)

    def test_checklist_lists_done_stage_files(self):
        p = load_pipeline(self.root, "REQ-1")
        p.advance()
        text = p.checklist()
        self.assertIn("02-design/DESIGN.md", text)


class LightFlowTests(ReqPipeTestCase):
    def test_light_flow_skips_design_and_review(self):
        create_pipeline(self.root, "小需求", req_id="REQ-1", light=True)
        p = load_pipeline(self.root, "REQ-1")
        p.advance()                        # 需求 → done
        p.skip("design", "轻量流程，无需方案")
        p.skip("review", "轻量流程，无需评审")
        p.advance()                        # 开发 → done
        self.assertTrue(p.completed())
        self.assertEqual(p.stage("requirement")["status"], "done")
        self.assertEqual(p.stage("design")["status"], "skipped")
        self.assertEqual(p.stage("review")["status"], "skipped")
        self.assertEqual(p.stage("development")["status"], "done")
        self.assertTrue(p.light)

    def test_standard_flow_stays_complete(self):
        create_pipeline(self.root, "标准需求", req_id="REQ-1", light=False)
        p = load_pipeline(self.root, "REQ-1")
        for _ in range(4):
            p.advance()
        self.assertTrue(p.completed())
        self.assertFalse(p.light)


if __name__ == "__main__":
    unittest.main()
