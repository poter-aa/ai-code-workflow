#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Cursor 24小时自动化任务执行管理器
功能：
1. 扫描 .ai/plan 目录中的所有任务
2. 解析任务状态和进度
3. 自动调用 Cursor 完成任务
4. 更新 progress.md 文件
"""

import os
import sys
import re
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import subprocess

#############################################################################
# 配置
#############################################################################

def get_workspace_root():
    """
    动态获取项目根目录
    从脚本所在目录（.ai/automation）向上推导到项目根目录
    """
    script_dir = Path(__file__).parent.absolute()
    # 从 .ai/automation 向上推导到项目根目录
    workspace_root = script_dir.parent.parent
    return str(workspace_root)

WORKSPACE_ROOT = get_workspace_root()
# 修改为扫描整个 issue 目录下的所有项目
PLAN_ROOT = os.path.join(
    WORKSPACE_ROOT,
    ".ai/issue"
)
AUTOMATION_DIR = os.path.join(WORKSPACE_ROOT, ".ai/automation")
LOG_DIR = os.path.join(AUTOMATION_DIR, "logs")
STATE_FILE = os.path.join(AUTOMATION_DIR, "state.json")

# 执行器配置：'cursor' 或 'claude'
# 注意：run-claude.sh 会设置 EXECUTOR_TYPE=claude，确保使用 Claude Code
EXECUTOR_TYPE = os.environ.get('EXECUTOR_TYPE', 'claude')  # 默认使用 Claude Code

# 创建必要目录
os.makedirs(LOG_DIR, exist_ok=True)

#############################################################################
# 日志配置
#############################################################################

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, 'task_manager.log')),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('TaskManager')

#############################################################################
# 数据模型
#############################################################################

class TaskStatus:
    """任务状态枚举"""
    PENDING = "⬜ 未开始"
    IN_PROGRESS = "🟡 进行中"
    COMPLETED = "🟢 已完成"
    BLOCKED = "🔴 阻塞/问题"

class Phase:
    """项目阶段"""
    def __init__(self, phase_num: int, name: str, doc_file: str):
        self.phase_num = phase_num
        self.name = name
        self.doc_file = doc_file
        self.status = TaskStatus.PENDING
        self.start_time: Optional[str] = None
        self.end_time: Optional[str] = None
        self.notes = ""
        self.estimated_hours = 0
        self.actual_hours = 0

    def to_dict(self) -> Dict:
        return {
            'phase_num': self.phase_num,
            'name': self.name,
            'doc_file': self.doc_file,
            'status': self.status,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'notes': self.notes,
            'estimated_hours': self.estimated_hours,
            'actual_hours': self.actual_hours
        }

class Project:
    """项目"""
    def __init__(self, name: str, path: str):
        self.name = name
        self.path = path
        self.phases: List[Phase] = []
        self.created_at = datetime.now().isoformat()

    def add_phase(self, phase: Phase):
        self.phases.append(phase)

    def get_pending_phases(self) -> List[Phase]:
        """获取待处理阶段"""
        return [p for p in self.phases if p.status != TaskStatus.COMPLETED]

    def get_completion_percentage(self) -> float:
        """获取完成度百分比"""
        if not self.phases:
            return 0.0
        completed = sum(1 for p in self.phases if p.status == TaskStatus.COMPLETED)
        return (completed / len(self.phases)) * 100

    def to_dict(self) -> Dict:
        return {
            'name': self.name,
            'path': self.path,
            'created_at': self.created_at,
            'completion': self.get_completion_percentage(),
            'total_phases': len(self.phases),
            'completed_phases': sum(1 for p in self.phases if p.status == TaskStatus.COMPLETED),
            'phases': [p.to_dict() for p in self.phases]
        }

#############################################################################
# 任务解析器
#############################################################################

class TaskParser:
    """解析任务文档"""

    @staticmethod
    def find_projects(root_path: str) -> List[str]:
        """递归查找所有项目目录（包含 plan 子目录的目录）"""
        projects = []

        if not os.path.exists(root_path):
            logger.error(f"路径不存在: {root_path}")
            return projects

        # 递归遍历所有目录，查找包含 plan 子目录的目录
        for root, dirs, files in os.walk(root_path):
            # 如果当前目录包含 plan 子目录
            if 'plan' in dirs:
                plan_path = os.path.join(root, 'plan')

                # 支持两种进度文件名：progress.md 和 0-进度文档.md
                progress_files = ['progress.md', '0-进度文档.md']
                progress_file_found = None

                for progress_filename in progress_files:
                    progress_file = os.path.join(plan_path, progress_filename)
                    if os.path.exists(progress_file):
                        progress_file_found = progress_filename
                        break

                # 确保找到了进度文件
                if progress_file_found:
                    projects.append(root)
                    # 显示相对路径，更易读
                    rel_path = os.path.relpath(root, root_path)
                    logger.info(f"找到项目: {rel_path} (进度文件: {progress_file_found})")

        # 按路径排序，确保执行顺序一致
        projects.sort()
        logger.info(f"共找到 {len(projects)} 个项目")

        return projects

    @staticmethod
    def parse_project(project_path: str) -> Optional[Project]:
        """解析单个项目 - 直接从进度文件中解析任务"""
        project_name = os.path.basename(project_path)
        plan_path = os.path.join(project_path, "plan")

        if not os.path.isdir(plan_path):
            logger.warning(f"项目缺少 plan 目录: {project_path}")
            return None

        # 支持两种进度文件名：progress.md 和 0-进度文档.md
        progress_files = ['progress.md', '0-进度文档.md']
        progress_file = None

        for progress_filename in progress_files:
            candidate = os.path.join(plan_path, progress_filename)
            if os.path.exists(candidate):
                progress_file = candidate
                break

        if not progress_file:
            logger.warning(f"项目缺少进度文件 (progress.md 或 0-进度文档.md): {project_path}")
            return None

        project = Project(project_name, project_path)

        # 直接从进度文件解析任务清单
        TaskParser.parse_phases_from_progress(project, plan_path)

        logger.info(f"项目 {project_name} 包含 {len(project.phases)} 个阶段")
        return project

    @staticmethod
    def parse_phase(filename: str, filepath: str) -> Optional[Phase]:
        """解析单个阶段文件"""
        try:
            # 提取阶段编号和名称
            # 支持格式: 
            #   1-状态枚举和流转规则实现.md
            #   step-1-状态枚举和流转规则实现.md
            
            # 首先尝试 step-N- 格式
            match = re.match(r'step[-_](\d+)[-_](.+)\.md', filename, re.IGNORECASE)
            if not match:
                # 然后尝试 N- 格式
                match = re.match(r'(\d+)[-_](.+)\.md', filename)
            
            if not match:
                logger.warning(f"无法解析阶段文件名: {filename}")
                return None
            
            phase_num = int(match.group(1))
            phase_name = match.group(2)
            
            # 读取文件获取预计工时
            estimated_hours = 0
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                    # 查找 "预计工时: X小时"
                    time_match = re.search(r'预计工时[：:]\s*(\d+)', content)
                    if time_match:
                        estimated_hours = int(time_match.group(1))
            except Exception as e:
                logger.warning(f"读取文件失败 {filepath}: {e}")
            
            phase = Phase(phase_num, phase_name, filename)
            phase.estimated_hours = estimated_hours
            return phase
        
        except Exception as e:
            logger.error(f"解析阶段失败: {e}")
            return None

    @staticmethod
    def parse_phases_from_progress(project: Project, plan_path: str):
        """直接从进度文件解析所有任务清单（不依赖文件名格式）"""
        # 支持两种进度文件名：progress.md 和 0-进度文档.md
        progress_files = ['progress.md', '0-进度文档.md']
        progress_file = None

        for progress_filename in progress_files:
            candidate = os.path.join(plan_path, progress_filename)
            if os.path.exists(candidate):
                progress_file = candidate
                break

        if not progress_file:
            logger.warning(f"进度文件不存在: {plan_path}")
            return
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找所有 Phase/Step 定义：### Phase N: ... 或 ### Step N: ...
            # 使用正则表达式提取 Phase/Step 编号、名称、文档链接和状态
            # 同时支持 Phase 和 Step 格式
            phase_pattern = r'### (?:Phase|Step) (\d+):\s*(.+?)\n- \*\*状态\*\*:\s*(\S*\s*[🟢🟡⬜🔴]?[^-]*)'
            
            for match in re.finditer(phase_pattern, content):
                phase_num = int(match.group(1))
                phase_name = match.group(2).strip()
                status_str = match.group(3).strip()
                
                # 从状态字符串中提取状态符号
                status = TaskStatus.PENDING  # 默认值
                if '🟢' in status_str or '已完成' in status_str:
                    status = TaskStatus.COMPLETED
                elif '🟡' in status_str or '进行中' in status_str:
                    status = TaskStatus.IN_PROGRESS
                elif '🔴' in status_str or '阻塞' in status_str:
                    status = TaskStatus.BLOCKED
                else:
                    status = TaskStatus.PENDING
                
                # 创建 Phase 对象
                phase = Phase(phase_num, phase_name, "")  # doc_file 暂时为空
                phase.status = status
                project.add_phase(phase)
                
                logger.debug(f"解析 Phase {phase_num}: {phase_name} - 状态: {status}")
            
            # 按 Phase 编号排序
            project.phases.sort(key=lambda p: p.phase_num)
            
            logger.info(f"从进度文档成功解析 {len(project.phases)} 个阶段")
        
        except Exception as e:
            logger.error(f"从 progress.md 解析阶段失败: {e}")
    
    @staticmethod
    def update_phases_from_progress(project: Project, plan_path: str):
        """从进度文件更新阶段状态（兼容旧版本）"""
        # 支持两种进度文件名：progress.md 和 0-进度文档.md
        progress_files = ['progress.md', '0-进度文档.md']
        progress_file = None

        for progress_filename in progress_files:
            candidate = os.path.join(plan_path, progress_filename)
            if os.path.exists(candidate):
                progress_file = candidate
                break

        if not progress_file:
            logger.warning(f"进度文件不存在: {plan_path}")
            return
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 查找每个 Phase/Step 的状态
            for phase in project.phases:
                phase_pattern = rf'### (?:Phase|Step) {phase.phase_num}:.*?- \*\*状态\*\*:\s*(\S+)'
                match = re.search(phase_pattern, content, re.DOTALL)
                
                if match:
                    status_str = match.group(1).strip()
                    # 匹配状态符号
                    if '🟢' in status_str or '已完成' in status_str:
                        phase.status = TaskStatus.COMPLETED
                    elif '🟡' in status_str or '进行中' in status_str:
                        phase.status = TaskStatus.IN_PROGRESS
                    elif '🔴' in status_str or '阻塞' in status_str:
                        phase.status = TaskStatus.BLOCKED
                    else:
                        phase.status = TaskStatus.PENDING
                
                # 获取完成时间
                time_pattern = rf'### (?:Phase|Step) {phase.phase_num}:.*?- \*\*完成时间\*\*:\s*(\S+)'
                time_match = re.search(time_pattern, content, re.DOTALL)
                if time_match:
                    phase.end_time = time_match.group(1).strip()
        
        except Exception as e:
            logger.error(f"更新阶段状态失败: {e}")

#############################################################################
# 进度更新器
#############################################################################

class ProgressUpdater:
    """更新 progress.md 文件"""

    @staticmethod
    def update_phase_status(project: Project, phase_num: int,
                           status: str, notes: str = "", hours: int = 0):
        """更新阶段状态"""
        plan_path = os.path.join(project.path, 'plan')

        # 支持两种进度文件名：progress.md 和 0-进度文档.md
        progress_files = ['progress.md', '0-进度文档.md']
        progress_file = None

        for progress_filename in progress_files:
            candidate = os.path.join(plan_path, progress_filename)
            if os.path.exists(candidate):
                progress_file = candidate
                break

        if not progress_file:
            logger.warning(f"进度文件不存在: {plan_path}")
            return False
        
        try:
            with open(progress_file, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # 构建新的状态行
            completion_time = datetime.now().strftime('%Y-%m-%d')
            new_status_line = f"- **状态**: {status}"
            new_time_line = f"- **完成时间**: {completion_time}"
            
            # 找到对应 Phase/Step 的部分并更新
            phase_pattern = rf'(### (?:Phase|Step) {phase_num}:.*?)(- \*\*状态\*\*:.*?\n)'
            content = re.sub(
                phase_pattern,
                rf'\1{new_status_line}\n',
                content,
                flags=re.DOTALL
            )
            
            # 如果是完成状态，也更新完成时间
            if '🟢' in status:
                time_pattern = rf'(### (?:Phase|Step) {phase_num}:.*?)(- \*\*完成时间\*\*:.*?\n)'
                content = re.sub(
                    time_pattern,
                    rf'\1{new_time_line}\n',
                    content,
                    flags=re.DOTALL
                )
            
            with open(progress_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"已更新 Phase {phase_num} 状态: {status}")
            return True
        
        except Exception as e:
            logger.error(f"更新失败: {e}")
            return False

#############################################################################
# 任务执行器
#############################################################################

class TaskExecutor:
    """执行任务"""

    def __init__(self):
        self.state = self.load_state()
        # 保持 ClaudeCodeManager 实例为单例，以便在多次任务执行之间保持终端窗口ID
        self.claude_manager = None
        self.agent_manager = None


    def _cleanup_current_session(self):
        """清理当前会话的资源（所有相关进程和终端窗口）"""
        try:
            if EXECUTOR_TYPE == 'claude':
                logger.info("🧹 清理上一个任务的资源...")

                # 如果 claude_manager 存在，使用它的清理方法（可以关闭终端窗口）
                if self.claude_manager:
                    self.claude_manager.cleanup_current_session()
                else:
                    # 如果 claude_manager 不存在（首次运行），直接清理所有进程和终端
                    logger.info("🔄 首次运行，清理所有残留的进程和终端...")

                    # 步骤1: 清理上一个任务的进程（通过 claude_manager）
                    if self.claude_manager:
                        self.claude_manager.cleanup_previous_task_processes()

                    # 步骤2: 关闭所有运行 claude 命令的终端窗口
                    logger.info("🔄 关闭所有 Claude 相关的终端窗口...")
                    applescript_close_all = '''
                    tell application "Terminal"
                        set windowList to every window
                        repeat with aWindow in windowList
                            try
                                -- 获取窗口中的所有标签页
                                set tabList to every tab of aWindow
                                set shouldClose to false

                                repeat with aTab in tabList
                                    try
                                        set tabProcesses to processes of aTab
                                        -- 检查是否有 claude 进程
                                        if tabProcesses contains "claude" then
                                            set shouldClose to true
                                            exit repeat
                                        end if
                                    end try
                                end repeat

                                if shouldClose then
                                    close aWindow
                                end if
                            end try
                        end repeat
                    end tell
                    '''
                    try:
                        subprocess.run(['osascript', '-e', applescript_close_all], timeout=10)
                        logger.info("✅ Claude 终端窗口已关闭")
                    except Exception as e:
                        logger.warning(f"关闭终端窗口失败: {e}")

            elif EXECUTOR_TYPE == 'cursor' and self.agent_manager:
                # 如果需要，也可以为 Cursor Agent 实现类似的清理
                logger.info("🧹 清理 Cursor Agent 资源...")
                # TODO: 实现 Cursor Agent 的清理逻辑
        except Exception as e:
            logger.warning(f"清理资源时出错: {e}")

    def load_state(self) -> Dict:
        """加载执行状态"""
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, 'r') as f:
                    return json.load(f)
            except:
                pass
        return {'last_run': None, 'completed_phases': []}

    def save_state(self):
        """保存执行状态"""
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)

    def execute_phase(self, project: Project, phase: Phase) -> bool:
        """执行单个阶段 - 调用 Cursor/Claude Code 执行任务"""
        logger.info(f"执行任务: {project.name} - Phase {phase.phase_num}: {phase.name}")
        logger.info(f"🤖 执行器类型: {EXECUTOR_TYPE}")
        
        # 生成指令
        instruction = self.generate_instruction(project, phase)
        
        # 保存指令到文件
        instruction_file = os.path.join(
            LOG_DIR,
            f"instruction_{project.name}_{phase.phase_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )
        
        try:
            with open(instruction_file, 'w', encoding='utf-8') as f:
                f.write(instruction)
            
            logger.info(f"指令已保存到: {instruction_file}")
            # 根据配置显示文件修改检测状态
            from automation_config import ClaudeCodeConfig
            if ClaudeCodeConfig.ENABLE_FILE_MODIFICATION_DETECTION:
                logger.info(f"💡 文件修改检测已启用，完整输出将保存到 logs/claude_output_*.log")
            else:
                logger.info(f"💡 文件修改检测已关闭，完整输出将保存到 logs/claude_output_*.log")
            
            # 调用执行器来执行任务
            return self.invoke_cursor_with_instruction(instruction, instruction_file)
        
        except Exception as e:
            logger.error(f"保存指令失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def invoke_cursor_with_instruction(self, instruction: str, instruction_file: str) -> bool:
        """自动执行任务指令 - 支持 Cursor 或 Claude Code"""
        try:
            # 导入执行器模块
            import sys
            import os
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

            # 生成任务 ID
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # 根据配置选择执行器
            if EXECUTOR_TYPE == 'claude':
                logger.info("⏳ 使用 Claude Code 执行任务...")
                from claude_executor import ClaudeCodeManager

                # 使用单例模式，保持同一个 ClaudeCodeManager 实例
                if self.claude_manager is None:
                    # 创建 ClaudeCodeManager，使用 stdin 方式（不受屏幕锁定影响）
                    self.claude_manager = ClaudeCodeManager(use_stdin_mode=True)
                    logger.info("📝 创建新的 ClaudeCodeManager 实例 (使用 stdin 方式)")
                else:
                    logger.info("♻️  复用已有的 ClaudeCodeManager 实例")

                # 使用 stdin 方式而不是交互式方式（更可靠，不受屏幕锁定影响）
                success = self.claude_manager.launch_claude_with_stdin(task_id, instruction)

                if success:
                    logger.info("✅ 任务指令已通过 stdin 发送给 Claude Code")
                    logger.info("⏳ 等待 Claude Code 处理任务（最多等待30分钟）...")
                    # 等待任务完成（最多30分钟）
                    task_completed = self.claude_manager.wait_for_task_completion(task_id, timeout=1800)
                    if task_completed:
                        logger.info("✅ Claude Code 任务执行完成")
                        return True
                    else:
                        logger.warning("⚠️  Claude Code 任务执行超时或失败")
                        return False
                else:
                    logger.warning("⚠️  Claude Code stdin 方式启动失败")
                    return False

            else:  # 默认使用 Cursor
                logger.info("⏳ 使用 Cursor Agent 执行任务...")
                from cursor_executor import AgentManager

                # 使用单例模式，保持同一个 AgentManager 实例
                if self.agent_manager is None:
                    self.agent_manager = AgentManager()
                    logger.info("📝 创建新的 AgentManager 实例")
                else:
                    logger.info("♻️  复用已有的 AgentManager 实例")

                success = self.agent_manager.launch_agent(task_id, instruction)

                if success:
                    logger.info("✅ 任务已在新 Cursor Agent 中启动")
                    logger.info("⏳ 等待 Cursor Agent 处理任务...")
                    time.sleep(15)
                    return True
                else:
                    logger.warning("⚠️  Cursor Agent 启动失败")
                    return False

        except Exception as e:
            logger.error(f"执行失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    

    def generate_autonomous_task_instruction(self, progress_doc: str, task_num: Optional[str] = None) -> str:
        """生成执行指定进度文档中任务的指令（精简版）"""
        
        if not progress_doc:
            raise ValueError("进度文档路径是必需的")
        
        # 转换为绝对路径
        if not os.path.isabs(progress_doc):
            progress_doc_abs = os.path.join(WORKSPACE_ROOT, progress_doc)
        else:
            progress_doc_abs = progress_doc
        
        progress_update_cmd = f"/issue-progress-update {progress_doc_abs}"
        
        # 根据是否指定任务编号生成不同的任务查找说明
        if task_num:
            task_instruction = f"""执行 Step {task_num} 的任务：
1. 调用 `{progress_update_cmd}` 更新进度文档
2. 读取进度文档 `{progress_doc_abs}`，查看 Step {task_num} 的状态
3. 查找任务文档：根据进度文档中的任务信息，找到对应的任务文档（任务文档位于各子任务目录下的 `plan/` 目录，格式：`{{子任务目录}}/plan/step-{task_num}-*.md` 或 `{{子任务目录}}/plan/{task_num}-*.md`）
4. **重要**：读取任务文档后，查找文档中所有待完成的步骤（标记为 ☐ 或 ⬜ 的步骤），按顺序执行所有步骤，一次性完成整个任务
5. 直接执行所有待完成步骤（无论状态如何，都要验证并执行）"""
        else:
            task_instruction = f"""自动选择并执行第一个待执行任务：
1. 调用 `{progress_update_cmd}` 更新进度文档
2. 读取进度文档 `{progress_doc_abs}`
3. 解析任务状态：查找 `### Phase N:` 或 `### Step N:`，状态为 `⬜ 未开始` 或 `🟡 进行中`
4. 按编号排序，选择第一个待执行任务
5. 查找任务文档：根据进度文档中的任务信息，找到对应的任务文档（任务文档位于各子任务目录下的 `plan/` 目录，格式：`{{子任务目录}}/plan/step-N-*.md` 或 `{{子任务目录}}/plan/N-*.md`，N 是任务编号）
6. **重要**：读取任务文档后，查找文档中所有待完成的步骤（标记为 ☐ 或 ⬜ 的步骤），按顺序执行所有步骤，一次性完成整个任务"""
        
        instruction = f"""# 任务执行

自动化模式：直接执行，不要询问确认。

进度文档：`{progress_doc_abs}`

**重要说明**：
- **执行维度**：每次执行任务的维度是一个 plan 目录下的任务文档（如 `step-N-*.md`）
- **执行范围**：一次性执行该任务文档中的所有待完成步骤（标记为 ☐ 或 ⬜），完成整个任务后更新所有相关步骤的状态
- **⚠️ 禁止提交代码**：**绝对不要执行 `git commit`、`git add` 或任何 git 提交相关操作**。只完成代码实现和测试，不要提交代码到 git 仓库。

{task_instruction}

## 执行步骤
1. **读取任务文档**：根据任务查找步骤找到的 plan 目录下的任务文档（如 `plan/step-N-*.md`）
2. **识别待完成步骤**：在任务文档中查找所有标记为 ☐ 或 ⬜ 的待完成步骤（通常在"详细实施步骤"、"小步骤清单"或"待完成步骤"部分），按顺序执行这些步骤
3. **代码实现**：按每个步骤的要求完成，遵循 `.cursor/rules/` 规范，分层架构 Controller → Logic → Service → Storage
4. **编写测试**：为每个步骤的核心方法编写单元测试，确保本次引入的测试通过
5. **编译验证**：每完成一个步骤后，运行 `mvn install -DskipTests -pl <修改的模块名>` 只编译相关模块。所有步骤完成后，如需编译全部模块，使用 `mvn clean install -DskipTests`
6. **更新任务文档**：每完成一个步骤后，使用 `search_replace` 更新任务文档中该步骤的状态为 ☑ 或 ✅，表示已完成
7. **更新进度文档**：所有步骤完成后，更新进度文档中该 Step 的状态为已完成
8. **⚠️ 禁止提交**：**绝对不要执行任何 git 提交操作**（包括 `git commit`、`git add`、`git push` 等）。即使任务文档中要求提交，也不要执行。

## 完成标准
- [ ] 任务文档中的所有待完成步骤已执行完成
- [ ] 代码实现完成
- [ ] 单元测试通过
- [ ] 符合工程规范
- [ ] 相关文件编译通过
- [ ] 任务文档中的步骤状态已更新
- [ ] 进度文档中的 Step 状态已更新为已完成
- [ ] **未执行任何 git 提交操作**

## 重要路径
- 项目根目录: `{WORKSPACE_ROOT}`（自动检测，当前为：{WORKSPACE_ROOT}）
- 编码规范: `.cursor/rules/`
- 进度文档: `{progress_doc_abs}`
- 任务文档: 各子任务目录下的 `plan/` 目录（如 `4-采购单创建/plan/step-N-*.md`）

## ⚠️ 重要限制
**禁止执行以下操作**：
- ❌ `git commit` - 禁止提交代码
- ❌ `git add` - 禁止暂存文件（除非是任务文档明确要求的文件操作）
- ❌ `git push` - 禁止推送到远程仓库
- ❌ 任何其他 git 提交相关的命令

**允许的操作**：
- ✅ 代码编写和修改
- ✅ 运行测试和编译
- ✅ 更新任务文档和进度文档
- ✅ `git status` - 查看状态（只读操作）

**再次强调**：
1. 一次性执行任务文档中的所有待完成步骤，完成后更新任务文档和进度文档中所有相关步骤的状态
2. **绝对不要提交代码**，即使任务文档中要求提交也不要执行

立即执行，无需确认。"""
        return instruction

    def generate_instruction(self, project: Project, phase: Phase) -> str:
        """生成 Cursor 执行指令（保留用于兼容性）"""
        phase_doc = os.path.join(project.path, 'plan', phase.doc_file)
        
        instruction = f"""# 自动化任务指令

## 项目信息
- **项目**: {project.name}
- **当前任务**: Phase {phase.phase_num}: {phase.name}
- **预计工时**: {phase.estimated_hours} 小时
- **生成时间**: {datetime.now().isoformat()}

## 任务要求
请根据以下文档完成实现：

**文档路径**: {phase_doc}

### 实现步骤
1. 仔细阅读文档中的所有要求和实现细节
2. 按照文档中的"完成检查清单"逐项完成实现
3. 确保所有代码符合工程规范
4. 编写并运行单元测试
5. 完成后，在 progress.md 中标记此 Phase 为 🟢 已完成
6. **⚠️ 禁止提交**：**绝对不要执行任何 git 提交操作**（包括 `git commit`、`git add`、`git push` 等）

### 完成标准
- [ ] 实现代码编写完成
- [ ] 单元测试通过
- [ ] 代码符合工程规范
- [ ] progress.md 已更新
- [ ] **未执行任何 git 提交操作**

## ⚠️ 重要限制
**禁止执行以下操作**：
- ❌ `git commit` - 禁止提交代码
- ❌ `git add` - 禁止暂存文件
- ❌ `git push` - 禁止推送到远程仓库
- ❌ 任何其他 git 提交相关的命令

## 进度追踪
完成后请在 {os.path.join(project.path, 'plan/progress.md')} 中更新对应 Phase 的状态。

---

**任务ID**: {phase.phase_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}
"""
        return instruction

    def monitor_loop(self, interval: int = 900, max_duration: int = 24 * 60 * 60):
        """监控循环（24小时）"""
        logger.info("=" * 60)
        logger.info("启动 24 小时监控模式")
        logger.info(f"检查间隔: {interval} 秒 ({interval / 60:.1f} 分钟)")
        logger.info(f"最大运行时间: {max_duration} 秒 ({max_duration / 3600:.1f} 小时)")
        logger.info("=" * 60)
        
        start_time = time.time()
        loop_count = 0
        
        try:
            while True:
                loop_count += 1
                elapsed = time.time() - start_time
                
                logger.info(f"\n[循环 #{loop_count}] 已运行: {elapsed / 60:.1f} 分钟")
                
                # 扫描所有项目
                self.scan_and_execute_tasks()
                
                # 检查是否超时
                if elapsed > max_duration:
                    logger.warning(f"已运行 {max_duration / 3600:.1f} 小时，停止监控")
                    break
                
                logger.info(f"将在 {interval} 秒后进行下一次检查...")
                time.sleep(interval)
        
        except KeyboardInterrupt:
            logger.info("监控被中断")
        except Exception as e:
            logger.error(f"监控出错: {e}")
        finally:
            logger.info("监控已停止")

    def scan_and_execute_tasks(self, progress_doc: str, task_num: Optional[str] = None):
        """执行指定进度文档中的待处理任务"""
        logger.info("=" * 80)
        logger.info("🤖 执行指定进度文档中的任务")
        logger.info("=" * 80)
        logger.info(f"🤖 执行器类型: {EXECUTOR_TYPE}")
        logger.info(f"📄 进度文档: {progress_doc}")
        if task_num:
            logger.info(f"📋 指定任务: Step {task_num}")

        # 在执行新任务前，先清理上一个任务的进程和资源
        logger.info("🧹 执行前清理：关闭上一个任务的进程...")
        self._cleanup_current_session()

        # 生成执行任务的指令
        instruction = self.generate_autonomous_task_instruction(progress_doc=progress_doc, task_num=task_num)

        # 保存指令到文件
        instruction_file = os.path.join(
            LOG_DIR,
            f"instruction_autonomous_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        )

        try:
            with open(instruction_file, 'w', encoding='utf-8') as f:
                f.write(instruction)

            logger.info(f"指令已保存到: {instruction_file}")

            # 调用执行器来执行任务
            if self.invoke_cursor_with_instruction(instruction, instruction_file):
                logger.info(f"✅ AI自主任务查找指令已提交到执行器")
                # 根据配置显示文件修改检测状态
                from automation_config import ClaudeCodeConfig
                if ClaudeCodeConfig.ENABLE_FILE_MODIFICATION_DETECTION:
                    logger.info(f"💡 文件修改检测已启用，完整输出将保存到 logs/claude_output_*.log")
                else:
                    logger.info(f"💡 文件修改检测已关闭，完整输出将保存到 logs/claude_output_*.log")
            else:
                logger.warning(f"⚠️ 指令提交失败")

        except Exception as e:
            logger.error(f"保存指令失败: {e}")
            import traceback
            logger.error(traceback.format_exc())

    def show_status(self):
        """显示所有项目的任务状态"""
        logger.info("=" * 60)
        logger.info("项目任务状态")
        logger.info("=" * 60)
        
        project_paths = TaskParser.find_projects(PLAN_ROOT)
        
        if not project_paths:
            logger.warning("未找到任何项目")
            return
        
        for project_path in project_paths:
            project = TaskParser.parse_project(project_path)
            if not project:
                continue
            
            print(f"\n📦 {project.name}")
            print(f"   完成度: {project.get_completion_percentage():.1f}% "
                  f"({sum(1 for p in project.phases if p.status == TaskStatus.COMPLETED)}"
                  f"/{len(project.phases)})")
            
            for phase in project.phases:
                status_emoji = phase.status.split()[0]
                print(f"   {status_emoji} Phase {phase.phase_num}: {phase.name}")

#############################################################################
# 主程序
#############################################################################

def main():
    """主程序入口"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Cursor 24小时自动化任务执行管理器',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 启动 24 小时监控模式
  python task_manager.py --monitor
  
  # 单次执行所有待处理任务
  python task_manager.py --execute
  
  # 显示任务状态
  python task_manager.py --status
  
  # 显示帮助
  python task_manager.py --help
        """
    )
    
    parser.add_argument(
        '-m', '--monitor',
        action='store_true',
        help='启动 24 小时监控模式（每 5 分钟检查一次）'
    )
    
    parser.add_argument(
        '-e', '--execute',
        action='store_true',
        help='单次执行所有待处理任务'
    )
    
    parser.add_argument(
        '-s', '--status',
        action='store_true',
        help='显示所有项目的任务状态'
    )
    
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=900,
        help='监控间隔（秒），默认 900（15分钟）'
    )
    
    parser.add_argument(
        '-p', '--progress-doc',
        type=str,
        default=None,
        help='指定进度文档路径（执行模式必需）'
    )
    
    parser.add_argument(
        '-t', '--task-num',
        type=str,
        default=None,
        help='指定任务编号（可选，如果指定则直接执行该任务）'
    )
    
    args = parser.parse_args()
    
    executor = TaskExecutor()
    
    if args.monitor:
        # 监控模式需要进度文档
        if not args.progress_doc:
            logger.error("监控模式需要指定进度文档路径，使用 -p 参数")
            sys.exit(1)
        executor.monitor_loop(interval=args.interval)
    elif args.execute:
        # 执行模式需要进度文档
        if not args.progress_doc:
            logger.error("执行模式需要指定进度文档路径，使用 -p 参数")
            sys.exit(1)
        logger.info("启动单次执行模式")
        executor.scan_and_execute_tasks(progress_doc=args.progress_doc, task_num=args.task_num)
        logger.info("执行完成")
    elif args.status:
        executor.show_status()
    else:
        # 默认行为：单次执行
        if not args.progress_doc:
            logger.error("执行模式需要指定进度文档路径，使用 -p 参数")
            sys.exit(1)
        logger.info("启动单次执行模式（默认）")
        executor.scan_and_execute_tasks(progress_doc=args.progress_doc, task_num=args.task_num)
        logger.info("执行完成")

if __name__ == '__main__':
    main()

