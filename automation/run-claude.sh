#!/bin/bash

# ============================================================================
# Claude Code 24小时无人值守自动化执行脚本
# ============================================================================
# 用法: ./run-claude.sh [进度文档路径]
# 示例: ./run-claude.sh .ai/issue/xxx/plan/0-进度文档.md
# 特性:
#   - 使用 Claude Code (新终端窗口) 执行任务
#   - 完全自动化: --permission-mode bypassPermissions
#   - 自动接受所有操作: 编辑、写入、bash、删除等
#   - 自动运行: mvn test, git commit, npm install 等命令
#   - 24小时持续运行,每次循环只执行一个任务
#   - 单个任务最多执行30分钟，超时后自动进入下一个任务
#   - 监控线程监控任务完成状态，完成后立即进入下一个循环
# ============================================================================

AUTOMATION_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
LOG_DIR="$AUTOMATION_DIR/logs"
LOG_FILE="$LOG_DIR/claude.log"

# 创建日志目录
mkdir -p "$LOG_DIR"

# 解析参数
PROGRESS_DOC="$1"

# 调用选择脚本（选择进度文档和任务）
SELECTION_RESULT=$("$AUTOMATION_DIR/select-progress-and-task.sh" "$PROGRESS_DOC" 2>/dev/null)
if [ $? -ne 0 ] || [ -z "$SELECTION_RESULT" ]; then
    echo "选择失败" >&2
    exit 1
fi

# 解析选择结果（格式：进度文档路径 任务编号）
PROGRESS_DOC=$(echo "$SELECTION_RESULT" | awk '{print $1}')
SELECTED_TASK_NUM=$(echo "$SELECTION_RESULT" | awk '{print $2}')

echo "进度文档: $PROGRESS_DOC" | tee -a "$LOG_FILE"
echo "任务: Step $SELECTED_TASK_NUM" | tee -a "$LOG_FILE"
echo "" | tee -a "$LOG_FILE"

# 配置参数
MAX_DURATION=$((24 * 60 * 60))  # 24小时
TASK_TIMEOUT=1800                # 单个任务最多执行30分钟（1800秒）
START_TIME=$(date +%s)
ROUND=0

# 设置执行器类型为 claude
export EXECUTOR_TYPE=claude

# 24小时循环
while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))

    # 检查是否超过24小时
    if [ $ELAPSED -gt $MAX_DURATION ]; then
        echo "已运行超过24小时，停止执行" | tee -a "$LOG_FILE"
        break
    fi

    # 在每次循环开始时，重新检查是否还有待执行的任务
    SELECTION_RESULT=$("$AUTOMATION_DIR/select-progress-and-task.sh" "$PROGRESS_DOC" 2>/dev/null)
    SELECTION_EXIT_CODE=$?
    
    # 如果没有找到待执行任务，跳出循环
    if [ $SELECTION_EXIT_CODE -ne 0 ] || [ -z "$SELECTION_RESULT" ]; then
        echo "✅ 所有任务已完成，停止执行" | tee -a "$LOG_FILE"
        break
    fi

    # 解析选择结果（格式：进度文档路径 任务编号）
    PROGRESS_DOC=$(echo "$SELECTION_RESULT" | awk '{print $1}')
    SELECTED_TASK_NUM=$(echo "$SELECTION_RESULT" | awk '{print $2}')

    ROUND=$((ROUND + 1))
    ELAPSED_MINUTES=$((ELAPSED / 60))

    echo "[第 $ROUND 轮] $(date '+%H:%M:%S')" | tee -a "$LOG_FILE"
    echo "进度文档: $PROGRESS_DOC" | tee -a "$LOG_FILE"
    echo "任务: Step $SELECTED_TASK_NUM" | tee -a "$LOG_FILE"
    echo "任务超时限制: $((TASK_TIMEOUT / 60)) 分钟" | tee -a "$LOG_FILE"

    # 删除之前生成的日志文件
    echo "🧹 清理之前的日志文件..." | tee -a "$LOG_FILE"
    find "$LOG_DIR" -name "claude_output_*.log" -type f -delete 2>/dev/null
    find "$LOG_DIR" -name "instruction_*.md" -type f -delete 2>/dev/null
    echo "✅ 日志文件清理完成" | tee -a "$LOG_FILE"

    # 记录任务开始时间
    TASK_START_TIME=$(date +%s)

    # 执行任务（每次只执行一个任务，最多30分钟）
    cd "$AUTOMATION_DIR"
    python3 task_manager.py --execute --progress-doc "$PROGRESS_DOC" --task-num "$SELECTED_TASK_NUM" 2>&1 | tee -a "$LOG_FILE"
    TASK_EXIT_CODE=${PIPESTATUS[0]}

    # 计算任务执行时间
    TASK_END_TIME=$(date +%s)
    TASK_DURATION=$((TASK_END_TIME - TASK_START_TIME))
    TASK_DURATION_MINUTES=$((TASK_DURATION / 60))

    echo "任务执行时间: ${TASK_DURATION_MINUTES} 分钟" | tee -a "$LOG_FILE"

    # 检查任务是否超时
    if [ $TASK_DURATION -ge $TASK_TIMEOUT ]; then
        echo "⚠️  任务执行时间达到超时限制（${TASK_DURATION_MINUTES} 分钟），进入下一个循环" | tee -a "$LOG_FILE"
    elif [ $TASK_EXIT_CODE -eq 0 ]; then
        echo "✅ 任务执行完成，立即进入下一个循环" | tee -a "$LOG_FILE"
    else
        echo "⚠️  任务执行异常（退出码: $TASK_EXIT_CODE），进入下一个循环" | tee -a "$LOG_FILE"
    fi

    # 任务完成后立即进入下一个循环（不等待）
    echo "准备执行下一个任务..." | tee -a "$LOG_FILE"
    echo "" | tee -a "$LOG_FILE"
done

echo "执行完成" | tee -a "$LOG_FILE"
