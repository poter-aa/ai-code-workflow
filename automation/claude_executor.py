#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Claude Code 执行器
功能：
1. 在新的终端窗口中启动 Claude Code
2. 关闭之前的 Claude Code 终端
3. 自动发送任务指令
"""

import os
import sys
import time
import subprocess
import logging
from datetime import datetime
from typing import Optional

# 导入配置
from automation_config import ClaudeCodeConfig

logger = logging.getLogger('ClaudeExecutor')

#############################################################################
# Claude Code 管理器
#############################################################################

class ClaudeCodeManager:
    """管理 Claude Code 的启动和生命周期"""

    def __init__(self, workspace_path: str = None, use_stdin_mode: bool = True):
        self.workspace_path = workspace_path or ClaudeCodeConfig.WORKSPACE_PATH
        self.active_sessions = {}  # task_id -> session_info
        self.claude_command = ClaudeCodeConfig.CLAUDE_COMMAND
        # 使用配置文件中的权限模式,实现完全无人值守
        self.claude_args = ClaudeCodeConfig.get_claude_args()
        self.last_terminal_window_id = None  # 记录上一个终端窗口ID
        self.last_claude_pids = []  # 记录上一个窗口关联的 claude 进程 PID
        self.last_task_pids = set()  # 记录上一个任务启动的所有进程（包括子进程）
        self.use_stdin_mode = use_stdin_mode  # 是否使用 stdin 方式（不依赖键盘或剪贴板）
        logger.info(f"Claude Code 配置: {self.claude_command} {self.claude_args}")
        logger.info(f"传输模式: {'stdin（不受屏幕锁定影响）' if use_stdin_mode else '键盘事件（可能受屏幕锁定影响）'}")
        logger.info(f"详细输出模式: {'已启用（显示所有输出）' if ClaudeCodeConfig.SHOW_DETAILED_OUTPUT else '已关闭（只显示前50行）'}")
        logger.info(f"文件修改检测: {'已启用' if ClaudeCodeConfig.ENABLE_FILE_MODIFICATION_DETECTION else '已关闭'}")

    def _get_process_tree(self, root_pid):
        """
        获取进程树：包括指定进程及其所有子进程
        """
        pids = set([str(root_pid)])
        
        try:
            # 使用 pstree 或递归查找子进程
            # macOS 没有 pstree，使用 ps 和 pgrep 来查找子进程
            def find_children(parent_pid):
                try:
                    # 查找所有进程，检查 PPID (父进程ID)
                    result = subprocess.run(
                        ['ps', '-eo', 'pid,ppid'],
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        for line in result.stdout.strip().split('\n')[1:]:  # 跳过标题行
                            parts = line.strip().split()
                            if len(parts) >= 2:
                                pid, ppid = parts[0], parts[1]
                                if ppid == parent_pid and pid not in pids:
                                    pids.add(pid)
                                    # 递归查找子进程的子进程
                                    find_children(pid)
                except Exception as e:
                    logger.debug(f"查找子进程失败: {e}")
            
            find_children(str(root_pid))
        except Exception as e:
            logger.debug(f"获取进程树失败: {e}")
        
        return pids

    def cleanup_previous_task_processes(self):
        """
        清理上一个任务启动的进程及其所有子进程
        只清理记录的进程，不影响其他进程
        """
        try:
            if not self.last_task_pids:
                logger.info("🧹 没有需要清理的上一个任务的进程")
                return
            
            logger.info(f"🧹 清理上一个任务启动的进程: {len(self.last_task_pids)} 个进程")
            
            # 步骤1: 优雅关闭所有进程（SIGTERM）
            logger.info(f"🔄 优雅关闭进程...")
            for pid in self.last_task_pids:
                try:
                    # 检查进程是否还存在
                    result = subprocess.run(
                        ['ps', '-p', pid],
                        capture_output=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    if result.returncode == 0:
                        subprocess.run(['kill', '-15', pid], timeout=2, 
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                except Exception as e:
                    logger.debug(f"关闭进程 {pid} 失败: {e}")
            
            # 等待进程关闭
            time.sleep(2)
            
            # 步骤2: 检查并强制关闭未关闭的进程（SIGKILL）
            remaining_pids = []
            for pid in self.last_task_pids:
                try:
                    result = subprocess.run(
                        ['ps', '-p', pid],
                        capture_output=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                    if result.returncode == 0:
                        remaining_pids.append(pid)
                except Exception:
                    pass
            
            if remaining_pids:
                logger.warning(f"⚠️  还有 {len(remaining_pids)} 个进程未终止，使用 SIGKILL 强制终止...")
                for pid in remaining_pids:
                    try:
                        subprocess.run(['kill', '-9', pid], timeout=2,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger.info(f"✅ 强制关闭进程: {pid}")
                    except Exception as e:
                        logger.warning(f"强制关闭进程 {pid} 失败: {e}")
                
                # 再次等待，确保强制终止生效
                time.sleep(1)
                
                # 最终检查：确认所有进程都已终止
                final_check_pids = []
                for pid in remaining_pids:
                    try:
                        result = subprocess.run(
                            ['ps', '-p', pid],
                            capture_output=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL
                        )
                        if result.returncode == 0:
                            final_check_pids.append(pid)
                    except Exception:
                        pass
                
                if final_check_pids:
                    logger.error(f"❌ 仍有 {len(final_check_pids)} 个进程无法终止: {final_check_pids}")
                else:
                    logger.info(f"✅ 所有进程已成功终止")
            
            total_cleaned = len(self.last_task_pids)
            logger.info(f"✅ 已清理上一个任务的 {total_cleaned} 个进程")
            # 清空记录
            self.last_task_pids = set()
                
        except Exception as e:
            logger.warning(f"清理进程时出错: {e}")

    def cleanup_current_session(self):
        """
        清理当前会话：先关闭上一个任务的进程，再关闭终端窗口
        在任务结束时调用
        """
        try:
            logger.info("🧹 清理当前会话...")

            # 步骤1: 清理上一个任务启动的进程
            self.cleanup_previous_task_processes()

            # 步骤2: 关闭终端窗口
            if self.last_terminal_window_id:
                logger.info(f"🔄 关闭终端窗口 (ID: {self.last_terminal_window_id})...")
                applescript_close = f'''
                tell application "Terminal"
                    try
                        close window id {self.last_terminal_window_id}
                    end try
                end tell
                '''
                try:
                    subprocess.run(['osascript', '-e', applescript_close], timeout=5)
                    logger.info("✅ 终端窗口已关闭")
                except Exception as e:
                    logger.warning(f"关闭终端窗口失败: {e}")
                finally:
                    self.last_terminal_window_id = None

            logger.info("✅ 会话清理完成")

        except Exception as e:
            logger.warning(f"清理会话时出错: {e}")

    def launch_claude_with_stdin(self, task_id: str, instruction: str) -> bool:
        """
        使用 stdin 方式启动 Claude Code 并发送指令

        优势：
        1. 完全不受屏幕锁定影响
        2. 不需要剪贴板
        3. 不需要键盘事件（System Events）
        4. 最可靠的方式

        原理：
        - 使用 --print 模式进行非交互式执行
        - 直接通过管道 (pipe) 将指令写入 Claude 进程的 stdin
        - 完全绕过了 macOS 安全机制的限制
        - 处理完指令后进程会自动退出，不会一直等待输入

        参数:
            task_id: 任务ID
            instruction: 要发送的指令

        返回:
            True: 成功发送并启动监控
            False: 失败
        """
        try:
            logger.info(f"🚀 使用 stdin 方式启动 Claude Code: {task_id}")
            logger.info("💡 优势: 完全不受屏幕锁定影响，无需键盘或剪贴板")

            # 构建 Claude 命令
            claude_cmd = [self.claude_command] + self.claude_args.split()

            logger.info(f"📝 命令: {' '.join(claude_cmd)}")
            logger.info(f"📂 工作目录: {self.workspace_path}")

            # 启动 Claude Code 进程，保持 stdin 开放
            logger.info("🖥️  启动 Claude Code 进程...")
            process = subprocess.Popen(
                claude_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                cwd=self.workspace_path,
                bufsize=0  # 无缓冲，确保实时输出
            )

            logger.info(f"✅ Claude Code 已启动 (PID: {process.pid})")

            # 记录进程 PID 并开始跟踪进程树
            main_pid = process.pid
            self.active_sessions[task_id] = {
                'pid': main_pid,
                'process': process,
                'start_time': datetime.now().isoformat()
            }
            
            # 启动后台线程定期收集进程树（包括子进程）
            import threading
            tracker_done = threading.Event()  # 用于标记跟踪线程完成
            
            def track_process_tree():
                """定期收集进程树"""
                try:
                    while process.poll() is None:  # 进程还在运行
                        # 获取进程树
                        tree_pids = self._get_process_tree(main_pid)
                        # 更新记录的上一个任务的进程集合
                        self.last_task_pids.update(tree_pids)
                        time.sleep(5)  # 每5秒检查一次
                    # 进程退出前最后一次收集
                    tree_pids = self._get_process_tree(main_pid)
                    self.last_task_pids.update(tree_pids)
                    logger.info(f"📊 任务进程跟踪完成，共记录 {len(self.last_task_pids)} 个进程")
                    tracker_done.set()  # 标记跟踪完成
                except Exception as e:
                    logger.debug(f"跟踪进程树失败: {e}")
                    tracker_done.set()  # 即使出错也标记完成
            
            tracker_thread = threading.Thread(target=track_process_tree, daemon=True)
            tracker_thread.start()
            
            # 保存 tracker_done 事件到 session_info，以便后续等待
            self.active_sessions[task_id]['tracker_done'] = tracker_done

            # 发送指令到 stdin
            logger.info("📤 发送指令到 stdin...")
            logger.info(f"📄 指令长度: {len(instruction)} 字符")
            try:
                process.stdin.write(instruction)
                process.stdin.write('\n')
                process.stdin.flush()
                logger.info("✅ 指令已发送")
            except Exception as e:
                logger.error(f"❌ 发送指令失败: {e}")
                process.stdin.close()
                process.kill()
                return False

            # 关闭 stdin 以通知 Claude 指令发送完成
            logger.info("🔄 关闭 stdin...")
            process.stdin.close()

            # 记录任务开始时的文件状态（用于检测文件修改）
            import os
            from pathlib import Path
            
            # 根据配置决定是否启用文件修改检测
            enable_file_detection = ClaudeCodeConfig.ENABLE_FILE_MODIFICATION_DETECTION
            workspace_path_obj = Path(self.workspace_path)
            java_files_before = {}
            
            if enable_file_detection:
                # 获取工作目录下所有Java文件的修改时间（用于检测代码修改）
                try:
                    for java_file in workspace_path_obj.rglob("*.java"):
                        if java_file.is_file():
                            java_files_before[str(java_file.relative_to(workspace_path_obj))] = java_file.stat().st_mtime
                    logger.info(f"📝 记录任务开始时的文件状态: {len(java_files_before)} 个Java文件")
                except Exception as e:
                    logger.warning(f"⚠️  记录文件状态失败: {e}")
                    java_files_before = {}
            else:
                logger.debug("💡 文件修改检测已关闭")
            
            # 保存完整输出的文件路径
            automation_dir = os.path.dirname(os.path.abspath(__file__))
            output_file = os.path.join(
                automation_dir,
                "logs",
                f"claude_output_{task_id}.log"
            )
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            
            # 启动后台线程监控进程输出
            import threading
            def monitor_output():
                """监控进程输出"""
                # 在函数内部重新获取配置，确保可以访问
                enable_file_detection = ClaudeCodeConfig.ENABLE_FILE_MODIFICATION_DETECTION
                show_detailed_output = ClaudeCodeConfig.SHOW_DETAILED_OUTPUT
                output_lines = []
                return_code = None
                full_output = ""
                first_output_received = False
                
                try:
                    # 先等待一下，给进程时间启动
                    time.sleep(2)
                    
                    # 如果进程已经退出，直接读取剩余输出
                    if process.poll() is not None:
                        remaining = process.stdout.read()
                        if remaining:
                            with open(output_file, 'w', encoding='utf-8') as f:
                                for line in remaining.splitlines(True):
                                    if line.strip():
                                        output_lines.append(line.strip())
                                        full_output += line
                                        f.write(line)
                                        f.flush()
                                        
                                        if not first_output_received:
                                            first_output_received = True
                                            logger.info("✅ Claude Code 已开始输出")
                                        
                                        if show_detailed_output:
                                            logger.info(f"📊 Claude Code 输出: {line.strip()[:200]}")
                                        else:
                                            if len(output_lines) <= 50:
                                                logger.info(f"📊 Claude Code 输出 [{len(output_lines)}]: {line.strip()[:200]}")
                                            elif len(output_lines) == 51:
                                                logger.info("📊 ... (更多输出已省略，完整输出已保存到文件)")
                    else:
                        # 进程还在运行，实时读取输出
                        logger.info("⏳ Claude Code 正在处理中，等待输出...")
                        logger.info(f"💡 完整输出将实时保存到: {output_file}")
                        
                        # 读取所有输出并保存到文件
                        with open(output_file, 'w', encoding='utf-8') as f:
                            for i, line in enumerate(process.stdout):
                                if line:
                                    output_lines.append(line.strip())
                                    full_output += line
                                    f.write(line)
                                    f.flush()  # 实时写入文件
                                    
                                    if not first_output_received:
                                        first_output_received = True
                                        logger.info("✅ Claude Code 已开始输出")
                                    
                                    # 根据配置决定是否显示详细输出
                                    if show_detailed_output:
                                        # 显示所有输出行
                                        logger.info(f"📊 Claude Code 输出 [{i+1}]: {line.strip()[:200]}")
                                    else:
                                        # 只显示前50行输出
                                        if i < 50:
                                            logger.info(f"📊 Claude Code 输出 [{i+1}]: {line.strip()[:200]}")
                                        elif i == 50:
                                            logger.info("📊 ... (更多输出已省略，完整输出已保存到文件)")
                    
                    logger.info(f"📄 完整输出已保存到: {output_file}")
                    
                    # 等待进程完成（如果还没有退出）
                    # 当 stdout 关闭时，进程可能已经退出，wait() 会立即返回
                    return_code = process.wait()
                    
                except Exception as e:
                    # 如果读取输出时出错，尝试获取退出码
                    logger.warning(f"⚠️  读取输出时出错: {e}")
                    try:
                        return_code = process.poll()
                        if return_code is None:
                            # 进程还在运行，等待它退出
                            return_code = process.wait()
                    except Exception as wait_error:
                        logger.warning(f"⚠️  获取进程退出码失败: {wait_error}")
                        return_code = -1
                
                # 记录进程退出状态
                if return_code is not None:
                    logger.info(f"📊 Claude Code 进程已退出，退出码: {return_code}")
                    if return_code == 0:
                        logger.info("✅ Claude Code 任务执行成功")
                        
                        # 只有在启用文件修改检测时才执行检测逻辑
                        if enable_file_detection:
                            # 方法1: 检查输出中是否有代码修改的迹象
                            output_has_modification = False
                            if output_lines:
                                output_text = "\n".join(output_lines).lower()
                                modification_keywords = [
                                    "edit", "write", "create", "修改", "创建", "写入", 
                                    "search_replace", "write_file", "已修改", "已创建",
                                    "已更新", "updated", "created", "modified", "changed"
                                ]
                                if any(keyword in output_text for keyword in modification_keywords):
                                    output_has_modification = True
                                    logger.info("✅ 输出中检测到代码修改相关关键字")
                            
                            # 方法2: 检查实际文件是否被修改（更可靠）
                            files_modified = []
                            try:
                                for java_file_path, mtime_before in java_files_before.items():
                                    java_file = workspace_path_obj / java_file_path
                                    if java_file.exists():
                                        mtime_after = java_file.stat().st_mtime
                                        if mtime_after > mtime_before:
                                            files_modified.append(java_file_path)
                            except Exception as e:
                                logger.warning(f"⚠️  检查文件修改时间失败: {e}")
                            
                            # 方法3: 检查git状态（如果有git仓库）
                            git_changes = []
                            try:
                                git_result = subprocess.run(
                                    ['git', 'status', '--porcelain'],
                                    cwd=self.workspace_path,
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                if git_result.returncode == 0:
                                    git_changes = [line.strip() for line in git_result.stdout.strip().split('\n') if line.strip()]
                            except Exception as e:
                                logger.debug(f"检查git状态失败（可能不是git仓库）: {e}")
                            
                            # 综合判断
                            if files_modified:
                                logger.info(f"✅ 检测到 {len(files_modified)} 个文件被修改:")
                                for f in files_modified[:10]:  # 只显示前10个
                                    logger.info(f"   - {f}")
                                if len(files_modified) > 10:
                                    logger.info(f"   ... 还有 {len(files_modified) - 10} 个文件")
                            elif git_changes:
                                logger.info(f"✅ Git检测到 {len(git_changes)} 个文件变更:")
                                for change in git_changes[:10]:
                                    logger.info(f"   - {change}")
                                if len(git_changes) > 10:
                                    logger.info(f"   ... 还有 {len(git_changes) - 10} 个变更")
                            elif output_has_modification:
                                logger.info("✅ 输出中检测到修改迹象，但未检测到实际文件修改")
                                logger.warning("⚠️  建议检查输出文件确认是否真的执行了代码修改")
                            else:
                                logger.warning("⚠️  未检测到代码修改操作")
                                logger.warning(f"⚠️  请检查输出文件: {output_file}")
                                logger.warning("⚠️  可能的原因:")
                                logger.warning("   1. Claude Code 只输出了对话内容，未实际执行工具调用")
                                logger.warning("   2. 任务指令不够明确，Claude Code 没有理解需要修改代码")
                                logger.warning("   3. --print 模式可能不支持实际执行代码修改")
                    else:
                        logger.warning(f"⚠️  Claude Code 任务执行异常，退出码: {return_code}")
                        # 输出错误信息
                        if output_lines:
                            logger.warning(f"⚠️  最后几行输出: {output_lines[-5:]}")
                        logger.warning(f"⚠️  完整输出已保存到: {output_file}")
                else:
                    logger.warning("⚠️  无法获取进程退出码")
            
            # 启动监控线程（不阻塞主线程）
            monitor_thread = threading.Thread(target=monitor_output, daemon=False)  # 改为非 daemon，确保线程完成
            monitor_thread.start()
            logger.info("✅ 已启动输出监控线程")

            logger.info("✅ stdin 方式执行成功")
            logger.info("💡 Claude Code 正在处理指令（--print 模式，完成后会自动退出）...")
            logger.info("💡 监控线程将等待任务完成...")

            return True

        except Exception as e:
            logger.error(f"❌ stdin 方式启动失败: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
    
    def wait_for_task_completion(self, task_id: str, timeout: int = 1800) -> bool:
        """
        等待指定任务完成
        
        参数:
            task_id: 任务ID
            timeout: 超时时间（秒），默认30分钟
        
        返回:
            True: 任务完成
            False: 超时或任务不存在
        """
        if task_id not in self.active_sessions:
            logger.warning(f"⚠️  任务 {task_id} 不存在")
            return False
        
        session_info = self.active_sessions[task_id]
        process = session_info.get('process')
        
        if not process:
            logger.warning(f"⚠️  任务 {task_id} 的进程不存在")
            return False
        
        try:
            logger.info(f"⏳ 等待任务 {task_id} 完成（最多等待 {timeout} 秒）...")
            # 等待进程完成，设置超时
            process.wait(timeout=timeout)
            return_code = process.returncode
            
            # 等待进程跟踪线程完成最后一次收集（最多等待5秒）
            tracker_done = session_info.get('tracker_done')
            if tracker_done:
                logger.info("⏳ 等待进程跟踪线程完成最后一次收集...")
                tracker_done.wait(timeout=5)
                logger.info(f"📊 进程跟踪完成，共记录 {len(self.last_task_pids)} 个进程")
            
            if return_code == 0:
                logger.info(f"✅ 任务 {task_id} 执行成功")
                return True
            else:
                logger.warning(f"⚠️  任务 {task_id} 执行异常，退出码: {return_code}")
                return False
        except subprocess.TimeoutExpired:
            logger.warning(f"⚠️  任务 {task_id} 执行超时（已等待 {timeout} 秒）")
            # 即使超时，也尝试等待进程跟踪线程完成
            tracker_done = session_info.get('tracker_done')
            if tracker_done:
                tracker_done.wait(timeout=2)
            return False
        except Exception as e:
            logger.error(f"❌ 等待任务完成时出错: {e}")
            return False

    def launch_claude_interactive(self, task_id: str, instruction: str) -> bool:
        """
        在新终端中启动 Claude Code（交互式方式）
        使用键盘模拟输入指令以避免 stdin raw mode 问题

        执行顺序：
        1. 保存旧窗口ID和关联的进程PID（用于关闭旧窗口）
        2. 先关闭旧终端窗口（先 kill 旧进程，再关窗口）
        3. 打开新终端并启动 Claude Code
        4. 等待 Claude Code 启动完成
        5. 粘贴指令并执行
        """
        try:
            logger.info(f"🚀 启动交互式 Claude Code 会话: {task_id}")

            # 步骤1: 保存旧窗口ID和关联的进程PID（用于关闭旧窗口）
            old_window_id = self.last_terminal_window_id
            
            if old_window_id:
                logger.info(f"📝 发现旧窗口ID: {old_window_id}")
                # 在新窗口打开之前，获取所有 claude 进程（这些应该是旧窗口的进程）
                old_claude_pids = self._get_claude_pids()
                if old_claude_pids:
                    logger.info(f"📝 旧窗口关联的 claude 进程: {old_claude_pids}")
                else:
                    old_claude_pids = []
            else:
                logger.info("💡 没有旧窗口需要关闭（首次启动）")
                old_claude_pids = []

            # 步骤2: 先关闭旧终端窗口（先 kill 旧进程，再关窗口）
            if old_window_id:
                logger.info(f"🧹 关闭旧终端窗口 (ID: {old_window_id})...")
                self._close_terminal_window(old_window_id, old_claude_pids)
                # 清空旧窗口ID记录
                self.last_terminal_window_id = None
                # 等待一下，确保窗口完全关闭
                time.sleep(1)

            # 步骤3: 打开新终端并启动 claude，获取窗口ID
            applescript = f'''
            tell application "Terminal"
                activate
                do script "cd {self.workspace_path} && {self.claude_command} {self.claude_args}"
                return id of window 1
            end tell
            '''

            logger.info("🖥️  正在打开新终端窗口并启动 Claude Code...")
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=15
            )

            if result.returncode == 0:
                # 保存新窗口的ID
                new_window_id = result.stdout.strip()
                if new_window_id:
                    self.last_terminal_window_id = new_window_id
                    logger.info(f"✅ 新终端窗口已打开 (新窗口ID: {new_window_id})")
                else:
                    logger.warning("⚠️  无法获取新窗口ID")

                logger.info("💡 等待 Claude Code 启动完成 (15秒)...")
                time.sleep(15)  # 增加等待时间，确保 Claude Code 完全启动并准备好接收输入

                # 步骤4: 将指令保存到临时文件（备用方案）
                import tempfile
                temp_file = None
                try:
                    temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8')
                    temp_file.write(instruction)
                    temp_file.close()
                    logger.info(f"📝 指令已保存到临时文件: {temp_file.name}")
                except Exception as e:
                    logger.warning(f"保存临时文件失败: {e}")

                # 步骤5: 在粘贴之前将指令复制到剪贴板（确保内容正确）
                logger.info("📋 将指令复制到剪贴板...")
                try:
                    p = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
                    p.communicate(instruction.encode('utf-8'))
                    p.wait()  # 等待复制完成
                    
                    # 验证剪贴板内容
                    verify_result = subprocess.run(
                        ['pbpaste'],
                        capture_output=True,
                        text=True,
                        timeout=2
                    )
                    if verify_result.returncode == 0:
                        clipboard_content = verify_result.stdout
                        # 检查剪贴板内容是否匹配（至少前200字符）
                        check_len = min(200, len(instruction), len(clipboard_content))
                        if instruction[:check_len] == clipboard_content[:check_len]:
                            logger.info(f"✅ 剪贴板内容验证通过 ({len(clipboard_content)} 字符)")
                        else:
                            logger.warning("⚠️  剪贴板内容可能不正确，但继续执行")
                            logger.debug(f"期望前100字符: {instruction[:100]}")
                            logger.debug(f"实际前100字符: {clipboard_content[:100]}")
                    else:
                        logger.warning("⚠️  无法验证剪贴板内容")
                except Exception as e:
                    logger.warning(f"剪贴板操作失败: {e}")

                # 步骤6: 激活终端窗口并粘贴指令（使用改进的方法）
                logger.info("⌨️  激活终端窗口并粘贴指令...")
                
                # 使用更可靠的 AppleScript 粘贴方法
                applescript_paste = f'''
                tell application "Terminal"
                    activate
                    -- 激活指定窗口
                    try
                        set front window to window id {new_window_id}
                    end try
                end tell
                delay 1.5
                tell application "System Events"
                    -- 确保 Terminal 进程处于活动状态
                    set terminalProcess to first application process whose name is "Terminal"
                    set frontmost of terminalProcess to true
                    delay 0.5
                    -- 粘贴指令（使用 Command+V）
                    keystroke "v" using command down
                    delay 2.0
                    -- 按回车发送
                    key code 36
                end tell
                '''
                
                paste_result = subprocess.run(
                    ['osascript', '-e', applescript_paste],
                    capture_output=True,
                    text=True,
                    timeout=15
                )

                if paste_result.returncode == 0:
                    logger.info("✅ 指令已粘贴并发送")
                    logger.info(f"💡 如果 Claude Code 显示 '[Pasted text...]'，请检查临时文件: {temp_file.name if temp_file else 'N/A'}")
                else:
                    logger.error(f"⚠️  粘贴指令失败: {paste_result.stderr}")
                    if temp_file:
                        logger.info(f"💡 请手动读取文件并粘贴: {temp_file.name}")
                    else:
                        logger.info("💡 请手动粘贴指令 (Cmd+V)")

                return True
            else:
                logger.error(f"❌ AppleScript 执行失败: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"启动异常: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _get_claude_pids(self):
        """
        获取当前所有 claude 进程的 PID
        """
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'claude'],
                capture_output=True,
                text=True
            )

            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip().split('\n')
            return []

        except Exception as e:
            logger.warning(f"获取 claude 进程失败: {e}")
            return []


    def _close_terminal_window(self, window_id: str, old_pids: list):
        """
        关闭指定ID的终端窗口
        
        使用多种方法尝试关闭窗口，按优先级顺序：
        1. 方法1: 通过窗口ID关闭 (close window id)
        2. 方法2: 通过进程查找窗口并关闭 (遍历所有窗口，查找包含指定进程的窗口)
        3. 方法3: 通过窗口标题查找并关闭 (如果窗口有特定标题)
        4. 方法4: 使用键盘快捷键关闭 (Cmd+W)

        步骤：
        1. 先 kill 掉旧窗口关联的 claude 进程（避免弹出确认对话框）
        2. 等待进程完全终止
        3. 尝试多种方法关闭窗口

        参数：
            window_id: 终端窗口ID
            old_pids: 该窗口关联的 claude 进程 PID 列表
        """
        try:
            # 步骤1: Kill 掉旧窗口的 claude 进程
            if old_pids:
                logger.info(f"🔄 终止旧窗口的 claude 进程: {old_pids}")
                for pid in old_pids:
                    try:
                        # 先尝试 SIGTERM (15)
                        subprocess.run(['kill', '-15', pid], timeout=2)
                        logger.debug(f"  - 已发送 SIGTERM 到进程 {pid}")
                    except Exception as e:
                        logger.warning(f"  - 终止进程 {pid} 失败: {e}")

                # 等待进程终止
                logger.debug("⏳ 等待 1 秒让进程完全终止...")
                time.sleep(1)

                # 检查是否还有进程存活
                current_pids = self._get_claude_pids()
                remaining_pids = [pid for pid in old_pids if pid in current_pids]

                if remaining_pids:
                    logger.warning(f"⚠️  还有 {len(remaining_pids)} 个进程未终止，使用 SIGKILL 强制终止...")
                    for pid in remaining_pids:
                        try:
                            subprocess.run(['kill', '-9', pid], timeout=2)
                            logger.debug(f"  - 已发送 SIGKILL 到进程 {pid}")
                        except Exception as e:
                            logger.warning(f"  - 强制终止进程 {pid} 失败: {e}")

                    time.sleep(0.5)

                logger.info("✅ 旧窗口的 claude 进程已终止")
            else:
                logger.debug("没有需要终止的 claude 进程")

            # 步骤2: 尝试多种方法关闭窗口
            success = False
            
            # 方法1: 通过窗口ID关闭 (当前使用的方法)
            if window_id and not success:
                logger.debug(f"🔹 方法1: 通过窗口ID关闭窗口 (ID: {window_id})...")
                success = self._close_window_by_id(window_id)
                if success:
                    logger.info(f"✅ 方法1成功: 窗口已关闭 (ID: {window_id})")
            
            # 方法2: 通过进程查找窗口并关闭 (遍历所有窗口，查找包含 claude 进程的窗口)
            if not success:
                logger.debug("🔹 方法2: 通过进程查找窗口并关闭...")
                success = self._close_window_by_process(old_pids)
                if success:
                    logger.info("✅ 方法2成功: 通过进程找到并关闭了窗口")
            
            # 方法3: 通过窗口标题查找并关闭 (查找包含 "claude" 的窗口)
            if not success:
                logger.debug("🔹 方法3: 通过窗口标题查找并关闭...")
                success = self._close_window_by_title("claude")
                if success:
                    logger.info("✅ 方法3成功: 通过标题找到并关闭了窗口")
            
            # 方法4: 使用键盘快捷键关闭 (Cmd+W) - 关闭最前面的终端窗口
            if not success:
                logger.debug("🔹 方法4: 使用键盘快捷键关闭窗口 (Cmd+W)...")
                success = self._close_window_by_shortcut()
                if success:
                    logger.info("✅ 方法4成功: 使用快捷键关闭了窗口")
            
            if not success:
                logger.warning("⚠️  所有关闭窗口的方法都失败了，窗口可能已经关闭或不存在")

        except Exception as e:
            logger.warning(f"关闭终端窗口时出错: {e}")
    
    def _close_window_by_id(self, window_id: str) -> bool:
        """方法1: 通过窗口ID关闭窗口"""
        try:
            applescript = f'''
            tell application "Terminal"
                try
                    close window id {window_id} saving no
                    return true
                on error
                    return false
                end try
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception as e:
            logger.debug(f"方法1失败: {e}")
            return False
    
    def _close_window_by_process(self, pids: list) -> bool:
        """方法2: 通过进程查找窗口并关闭 (遍历所有窗口，查找包含 claude 进程的窗口)"""
        try:
            # 注意：AppleScript 的 processes 返回的是进程名称列表，不是PID
            # 所以我们查找包含 "claude" 的进程名称
            applescript = '''
            tell application "Terminal"
                set windowList to every window
                repeat with aWindow in windowList
                    try
                        set tabList to every tab of aWindow
                        repeat with aTab in tabList
                            try
                                set tabProcesses to processes of aTab
                                -- 检查是否有 claude 进程
                                repeat with aProcess in tabProcesses
                                    if aProcess contains "claude" then
                                        close aWindow saving no
                                        return true
                                    end if
                                end repeat
                            end try
                        end repeat
                    end try
                end repeat
                return false
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception as e:
            logger.debug(f"方法2失败: {e}")
            return False
    
    def _close_window_by_title(self, keyword: str) -> bool:
        """方法3: 通过窗口标题查找并关闭 (查找包含关键字的窗口)"""
        try:
            applescript = f'''
            tell application "Terminal"
                set windowList to every window
                repeat with aWindow in windowList
                    try
                        set windowName to name of aWindow
                        if windowName contains "{keyword}" then
                            close aWindow saving no
                            return true
                        end if
                    end try
                end repeat
                return false
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0 and result.stdout.strip() == "true"
        except Exception as e:
            logger.debug(f"方法3失败: {e}")
            return False
    
    def _close_window_by_shortcut(self) -> bool:
        """方法4: 使用键盘快捷键关闭窗口 (Cmd+W) - 关闭最前面的终端窗口"""
        try:
            # 先激活 Terminal 应用
            applescript_activate = '''
            tell application "Terminal"
                activate
            end tell
            '''
            subprocess.run(['osascript', '-e', applescript_activate], timeout=3)
            time.sleep(0.3)
            
            # 使用 Cmd+W 关闭最前面的窗口
            applescript_close = '''
            tell application "System Events"
                tell application process "Terminal"
                    keystroke "w" using command down
                end tell
            end tell
            '''
            result = subprocess.run(
                ['osascript', '-e', applescript_close],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug(f"方法4失败: {e}")
            return False
