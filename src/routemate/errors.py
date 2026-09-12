"""RouteMate 领域异常。"""


class RouteMateError(Exception):
    """RouteMate 可预期异常基类。"""


class ConfigurationError(RouteMateError):
    """配置缺失或格式不合法。"""


class SandboxViolation(RouteMateError, ValueError):
    """文件路径或内容不满足沙箱约束。"""

