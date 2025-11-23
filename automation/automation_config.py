#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
自动化执行配置文件
管理 Claude Code 和 Cursor 的自动化参数
"""

import os
from pathlib import Path

#############################################################################
# 工具函数：动态获取路径
#############################################################################

def get_workspace_root():
    """
    动态获取项目根目录
    从脚本所在目录（.ai/automation）向上推导到项目根目录
    """
    # 获取当前脚本所在目录
    script_dir = Path(__file__).parent.absolute()
    # 从 .ai/automation 向上推导到项目根目录
    workspace_root = script_dir.parent.parent
    return str(workspace_root)

def get_claude_command():
    """
    动态获取 Claude Code 可执行文件路径
    优先级：环境变量 > 默认路径（~/.claude/local/claude）
    """
    # 优先使用环境变量
    env_path = os.environ.get('CLAUDE_COMMAND')
    if env_path and os.path.exists(env_path):
        return env_path
    
    # 使用默认路径（用户主目录）
    default_path = os.path.expanduser("~/.claude/local/claude")
    if os.path.exists(default_path):
        return default_path
    
    # 如果都不存在，返回默认路径（让验证函数报错）
    return default_path

#############################################################################
# Claude Code 配置
#############################################################################

class ClaudeCodeConfig:
    """Claude Code 执行器配置"""

    # Claude Code 可执行文件路径（动态获取）
    CLAUDE_COMMAND = get_claude_command()

    # 权限模式选项:
    # - "bypassPermissions": 绕过权限检查,完全无人值守 ✅ 推荐用于24小时自动化
    # - "acceptEdits": 只自动接受编辑操作,其他操作需要确认
    # - "default": 所有操作都需要确认(默认)
    # - "plan": 计划模式
    PERMISSION_MODE = "bypassPermissions"

    # 是否使用 --dangerously-skip-permissions 来跳过确认提示
    # 启用此选项可以避免 "Yes, I accept" 的交互式确认
    USE_DANGEROUS_SKIP = True

    # 工作目录（动态获取）
    WORKSPACE_PATH = get_workspace_root()

    # Claude Code 启动等待时间(秒)
    STARTUP_WAIT_TIME = 5

    # 自动粘贴指令的延迟时间(秒)
    PASTE_DELAY = 0.5

    # 是否启用文件修改检测
    # False: 关闭文件修改检测，不记录文件状态，不检测文件变更
    # True: 启用文件修改检测，记录任务开始时的文件状态，任务结束后检测文件变更
    ENABLE_FILE_MODIFICATION_DETECTION = False

    # 是否显示 Claude Code 的详细执行过程输出
    # False: 只显示前50行输出，然后省略（默认，减少日志量）
    # True: 显示所有输出行，实时查看 Claude Code 的完整执行过程
    SHOW_DETAILED_OUTPUT = False

    @classmethod
    def get_claude_args(cls) -> str:
        """获取 Claude Code 命令行参数"""
        args = []

        # 使用 --print 模式进行非交互式执行（适合管道和自动化）
        # 这会跳过工作区信任对话框，直接从 stdin 读取指令并执行
        # 处理完指令后会自动退出，不会一直等待输入
        args.append("--print")

        # 设置权限模式为 bypassPermissions，完全无人值守
        # 这会自动接受所有操作：编辑、写入、bash、删除等
        args.append(f"--permission-mode {cls.PERMISSION_MODE}")

        # 如果启用了危险跳过模式,同时使用 --dangerously-skip-permissions
        # 这会直接跳过所有权限检查,包括确认提示，确保完全无需确认
        if cls.USE_DANGEROUS_SKIP:
            args.append("--dangerously-skip-permissions")

        return " ".join(args)

    @classmethod
    def get_full_command(cls) -> str:
        """获取完整的 Claude Code 命令"""
        return f"{cls.CLAUDE_COMMAND} {cls.get_claude_args()}"


#############################################################################
# Cursor 配置
#############################################################################

class CursorConfig:
    """Cursor 执行器配置"""

    # 工作目录（动态获取）
    WORKSPACE_PATH = get_workspace_root()

    # 智能等待队列配置
    MAX_WAIT_TIME = 300  # 最大等待时间(秒)
    MAX_RETRIES = 10     # 最大重试次数

    # 任务完成检测配置
    COMPLETION_CHECK_INTERVAL = 5   # 完成状态检查间隔(秒)
    COMPLETION_TIMEOUT = 300        # 完成检测超时时间(秒)

    # Agent 启动配置
    NEW_AGENT_WAIT_TIME = 2.0       # 打开新 Agent 后的等待时间(秒)
    INSTRUCTION_PASTE_DELAY = 0.5   # 粘贴指令的延迟时间(秒)


#############################################################################
# 任务管理器配置
#############################################################################

class TaskManagerConfig:
    """任务管理器配置"""

    # 项目路径（动态获取）
    WORKSPACE_ROOT = get_workspace_root()
    # 修改为扫描整个 issue 目录下的所有项目
    PLAN_ROOT = os.path.join(
        WORKSPACE_ROOT,
        ".ai/issue"
    )
    AUTOMATION_DIR = os.path.join(WORKSPACE_ROOT, ".ai/automation")
    LOG_DIR = os.path.join(AUTOMATION_DIR, "logs")
    STATE_FILE = os.path.join(AUTOMATION_DIR, "state.json")

    # 执行器类型: 'cursor' 或 'claude'
    EXECUTOR_TYPE = os.environ.get('EXECUTOR_TYPE', 'claude')  # 默认使用 Claude Code

    # 监控循环配置
    MONITOR_INTERVAL = 900           # 监控间隔(秒) = 15分钟
    MAX_MONITOR_DURATION = 24 * 60 * 60  # 最大运行时间(秒) = 24小时

    # 任务执行配置
    TASK_STARTUP_WAIT = {
        'claude': 20,  # Claude Code 需要更长启动时间
        'cursor': 15   # Cursor 启动时间
    }


#############################################################################
# 24小时无人值守模式配置
#############################################################################

class AutomationMode:
    """自动化模式配置"""

    # 是否启用完全自动化模式
    FULLY_AUTOMATED = True

    # 自动确认所有操作(包括 mvn test、git commit 等)
    AUTO_CONFIRM_ALL = True

    # 错误处理策略
    # - "skip": 跳过失败的任务,继续执行下一个
    # - "retry": 重试失败的任务(最多 N 次)
    # - "halt": 遇到错误立即停止
    ERROR_STRATEGY = "skip"
    MAX_RETRY_COUNT = 3

    # 日志级别
    LOG_LEVEL = "INFO"  # DEBUG, INFO, WARNING, ERROR

    # 是否在任务执行前显示预览
    SHOW_TASK_PREVIEW = True

    # 任务执行超时配置
    TASK_TIMEOUT = {
        'default': 900,  # 默认15分钟
        'test': 3600,     # 测试任务60分钟
        'build': 3600     # 构建任务60分钟
    }


#############################################################################
# 导出配置
#############################################################################

__all__ = [
    'ClaudeCodeConfig',
    'CursorConfig',
    'TaskManagerConfig',
    'AutomationMode'
]


#############################################################################
# 配置验证
#############################################################################

def validate_config():
    """验证配置是否正确"""
    errors = []

    # 检查 Claude Code 可执行文件
    if not os.path.exists(ClaudeCodeConfig.CLAUDE_COMMAND):
        errors.append(f"Claude Code 可执行文件不存在: {ClaudeCodeConfig.CLAUDE_COMMAND}")

    # 检查工作目录
    if not os.path.exists(ClaudeCodeConfig.WORKSPACE_PATH):
        errors.append(f"工作目录不存在: {ClaudeCodeConfig.WORKSPACE_PATH}")

    # 检查权限模式
    valid_modes = ["bypassPermissions", "acceptEdits", "default", "plan"]
    if ClaudeCodeConfig.PERMISSION_MODE not in valid_modes:
        errors.append(f"无效的权限模式: {ClaudeCodeConfig.PERMISSION_MODE}. "
                     f"有效值: {', '.join(valid_modes)}")

    return errors


if __name__ == '__main__':
    """配置验证脚本"""
    print("=" * 60)
    print("自动化配置验证")
    print("=" * 60)

    print("\n1. Claude Code 配置:")
    print(f"   - 命令: {ClaudeCodeConfig.CLAUDE_COMMAND}")
    print(f"   - 权限模式: {ClaudeCodeConfig.PERMISSION_MODE}")
    print(f"   - 工作目录: {ClaudeCodeConfig.WORKSPACE_PATH}")
    print(f"   - 完整命令: {ClaudeCodeConfig.get_full_command()}")

    print("\n2. Cursor 配置:")
    print(f"   - 工作目录: {CursorConfig.WORKSPACE_PATH}")
    print(f"   - 最大等待时间: {CursorConfig.MAX_WAIT_TIME}秒")

    print("\n3. 任务管理器配置:")
    print(f"   - 执行器类型: {TaskManagerConfig.EXECUTOR_TYPE}")
    print(f"   - 计划根目录: {TaskManagerConfig.PLAN_ROOT}")
    print(f"   - 日志目录: {TaskManagerConfig.LOG_DIR}")

    print("\n4. 自动化模式配置:")
    print(f"   - 完全自动化: {AutomationMode.FULLY_AUTOMATED}")
    print(f"   - 自动确认所有操作: {AutomationMode.AUTO_CONFIRM_ALL}")
    print(f"   - 错误处理策略: {AutomationMode.ERROR_STRATEGY}")

    print("\n5. 配置验证:")
    errors = validate_config()
    if errors:
        print("   ❌ 发现以下配置错误:")
        for error in errors:
            print(f"      - {error}")
    else:
        print("   ✅ 配置验证通过")

    print("=" * 60)
