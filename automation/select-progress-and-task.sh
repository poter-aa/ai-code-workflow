#!/bin/bash

# ============================================================================
# 进度文档和任务选择脚本
# ============================================================================
# 用法: ./select-progress-and-task.sh <进度文档路径>
# 功能: 验证进度文档并自动选择第一个待执行任务
# 输出: 进度文档路径和任务编号（用空格分隔）
# ============================================================================

AUTOMATION_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
# 动态获取项目根目录：从 .ai/automation 向上推导到项目根目录
WORKSPACE_ROOT="$( cd "$AUTOMATION_DIR/../.." && pwd )"
ISSUE_ROOT="$WORKSPACE_ROOT/.ai/issue"
PROGRESS_DOC="$1"

# 检查是否提供了参数
if [ -z "$PROGRESS_DOC" ]; then
    echo "错误: 必须提供进度文档路径" >&2
    exit 1
fi

# 转换为相对路径（如果输入的是绝对路径）
if [[ "$PROGRESS_DOC" = /* ]]; then
    PROGRESS_DOC="${PROGRESS_DOC#$WORKSPACE_ROOT/}"
fi

# 转换为绝对路径用于验证
if [[ ! "$PROGRESS_DOC" = /* ]]; then
    PROGRESS_DOC_ABS="$WORKSPACE_ROOT/$PROGRESS_DOC"
else
    PROGRESS_DOC_ABS="$PROGRESS_DOC"
fi

# 验证文件是否存在
if [ ! -f "$PROGRESS_DOC_ABS" ]; then
    echo "错误: 进度文档不存在: $PROGRESS_DOC_ABS" >&2
    exit 1
fi

# 使用 Python 解析进度文档并自动选择第一个待执行任务
# 直接通过bash变量替换传递文件路径（转义单引号）
PROGRESS_DOC_PYTHON=$(echo "$PROGRESS_DOC_ABS" | sed "s/'/\\\\'/g")
SELECTED_TASK_NUM=$(python3 <<PYTHON_SCRIPT
import sys
import re

progress_doc = '$PROGRESS_DOC_PYTHON'
if not progress_doc:
    print('❌ 错误: 未提供进度文档路径', file=sys.stderr)
    sys.exit(1)

try:
    with open(progress_doc, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 解析任务：支持多种格式
    # 格式1: ### Phase N: 或 ### Step N:
    # 格式2: #### N. 任务名称
    tasks = []
    lines = content.split('\n')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 匹配任务标题：### Phase N: 或 ### Step N: 或 #### N. 任务名称
        match = None
        task_num = None
        task_name = None
        
        # 格式1: ### Phase N: 或 ### Step N:
        match1 = re.match(r'^###\s+(?:Phase|Step)\s+(\d+)[:：]\s*(.+)$', line)
        if match1:
            task_num = match1.group(1)
            task_name = match1.group(2).strip()
            match = match1
        
        # 格式2: #### N. 任务名称
        if not match:
            match2 = re.match(r'^####\s+(\d+)\.\s*(.+)$', line)
            if match2:
                task_num = match2.group(1)
                task_name = match2.group(2).strip()
                match = match2
        
        # 格式3: #### ⬜ Step N: 或 #### 🟡 Step N: 等（带状态图标）
        if not match:
            match3 = re.match(r'^####\s+[⬜🟡🟢🔴]\s+Step\s+(\d+)[:：]\s*(.+)$', line)
            if match3:
                task_num = match3.group(1)
                task_name = match3.group(2).strip()
                match = match3
        
        if match:
            # 查找状态行（通常在标题下方）
            status = None
            status_line_idx = i + 1
            
            # 查找状态行（最多向下查找5行）
            for j in range(status_line_idx, min(status_line_idx + 5, len(lines))):
                status_line = lines[j]
                if '**状态**' in status_line or '状态' in status_line:
                    # 提取状态
                    if '⬜' in status_line or '未开始' in status_line:
                        status = 'pending'
                    elif '🟡' in status_line or '进行中' in status_line:
                        status = 'in_progress'
                    elif '🟢' in status_line or '已完成' in status_line:
                        status = 'completed'
                    elif '🔴' in status_line or '阻塞' in status_line:
                        status = 'blocked'
                    break
            
            # 只显示待执行的任务（未开始或进行中）
            if status in ['pending', 'in_progress']:
                tasks.append({
                    'num': task_num,
                    'name': task_name,
                    'status': status
                })
        
        i += 1
    
    if not tasks:
        print('未找到待执行的任务', file=sys.stderr)
        sys.exit(1)
    
    # 自动选择第一个待执行的任务
    selected_task = tasks[0]
    
    # 输出任务编号（供调用脚本使用）
    print(selected_task['num'])
    sys.exit(0)

except Exception as e:
    print(f'解析进度文档失败: {e}', file=sys.stderr)
    sys.exit(1)
PYTHON_SCRIPT
)

if [ $? -ne 0 ] || [ -z "$SELECTED_TASK_NUM" ]; then
    echo "未找到待执行任务" >&2
    exit 1
fi

# 输出进度文档路径和任务编号（用空格分隔）
echo "$PROGRESS_DOC $SELECTED_TASK_NUM"

