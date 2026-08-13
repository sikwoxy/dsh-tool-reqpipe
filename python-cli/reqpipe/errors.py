"""reqpipe 自定义异常。"""


class ReqPipeError(Exception):
    """所有 reqpipe 错误的基类。"""


class CreateError(ReqPipeError):
    """创建需求失败。"""


class NotFoundError(ReqPipeError):
    """需求不存在。"""


class StageError(ReqPipeError):
    """阶段推进失败。"""


class SkipError(ReqPipeError):
    """跳过阶段失败。"""


class InvalidStageError(ReqPipeError):
    """未知阶段。"""
