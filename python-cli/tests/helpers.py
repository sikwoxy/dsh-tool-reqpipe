"""测试公共基类：临时根目录 + CLI 调用封装。"""

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from reqpipe import cli


class ReqPipeTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="reqpipe-test-")
        self.root = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def run_cli(self, *argv, root=None):
        """调用 cli.main，返回 (退出码, stdout, stderr)。root 为 None 时不传 --root。"""
        args = list(argv)
        if root is not None:
            args = ["--root", str(root)] + args
        out, err = io.StringIO(), io.StringIO()
        code = None
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(args)
        except SystemExit as exc:  # argparse（--help/--version/用法错误）
            code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        return code, out.getvalue(), err.getvalue()
