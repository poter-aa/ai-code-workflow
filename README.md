# AI Code Workflow

> 面向文档+代码规范的 AI Code 工作流系统，通过需求分析+技术分析 → 子任务拆分 → 分步骤设计 → 最终执行的一套完整 AI Code 方法，支持自动化+不间断后台执行生成设计文档。

## 📖 项目简介

AI Code Workflow 是一个**面向文档+代码规范**的 AI Code 工作流系统，提供了一套完整的 AI 辅助开发方法论：

### 核心工作流

```
需求分析 + 技术分析 → 子任务拆分 → 分步骤设计 → 最终执行
```

1. **需求分析 + 技术分析**：深入理解业务需求，分析技术实现方案
2. **子任务拆分**：将复杂需求拆分为可执行的子任务
3. **分步骤设计**：为每个子任务设计详细的实施步骤
4. **最终执行**：按照设计文档逐步实现代码

### 核心能力

- 📚 **文档驱动**：所有工作流都基于标准化文档，确保信息不丢失
- 🎯 **代码规范**：严格遵循代码规范，保证代码质量
- 🤖 **自动化执行**：支持 24 小时不间断后台执行，自动生成设计文档
- 🔄 **完整闭环**：从需求到代码交付的全流程自动化

### 核心特性

- 📚 **文档+代码规范**：所有工作流基于标准化文档，严格遵循代码规范
- 🔄 **完整工作流**：需求分析 → 技术分析 → 子任务拆分 → 分步骤设计 → 执行
- 🤖 **自动化执行**：集成 Claude Code 和 Cursor，支持 24 小时不间断后台执行
- 📊 **自动生成文档**：自动化工作流自动生成设计文档、分析报告、任务计划等
- 🎯 **命令驱动**：通过 `/issue-create`、`/issue-plan` 等命令管理整个开发流程
- 📁 **规范管理**：标准化的目录结构和文档模板，确保信息不丢失

## 🏗️ 项目结构

```
ai-code-workflow/
├── README.md                    # 项目说明文档
├── automation/                  # 自动化脚本目录
│   ├── automation_config.py     # 自动化配置管理
│   ├── claude_executor.py       # Claude Code 执行器
│   ├── task_manager.py          # 任务管理器（核心）
│   ├── run-claude.sh            # 24小时自动化执行脚本
│   └── select-progress-and-task.sh  # 任务选择脚本
└── commands/                     # Claude 命令文档目录
    ├── README.md                # 命令使用指南
    ├── issue-create.md          # 创建需求命令
    ├── issue-sub-create.md      # 创建子需求命令
    ├── issue-analysis.md        # 需求分析命令
    ├── issue-plan.md            # 任务规划命令
    ├── issue-plan-detail.md     # 执行细节命令
    ├── issue-execute.md         # 执行任务命令
    ├── issue-progress-update.md # 更新进度命令
    └── create-branch-and-mr.md  # 创建分支和MR命令
```

## 🔄 核心工作流

本项目提供了一套完整的 **文档+代码规范驱动的 AI Code 工作流**：

### 工作流步骤

```
1. 需求分析 + 技术分析
   ↓
2. 子任务拆分
   ↓
3. 分步骤设计
   ↓
4. 最终执行
```

#### 1️⃣ 需求分析 + 技术分析
- **需求分析**：深入理解业务背景、用户场景、功能需求
- **技术分析**：分析现有系统架构、技术约束、实现方案
- **输出文档**：生成技术分析报告、需求分析报告、分析总结

#### 2️⃣ 子任务拆分
- 将复杂需求拆分为可执行的子任务
- 明确子任务间的依赖关系
- 预估每个子任务的工作量

#### 3️⃣ 分步骤设计
- 为每个子任务设计详细的实施步骤
- 明确每个步骤的输入、输出、验收标准
- 生成任务计划文档和进度跟踪文档

#### 4️⃣ 最终执行
- 按照设计文档逐步实现代码
- 遵循代码规范，编写单元测试
- 自动更新进度文档

### 🤖 自动化执行

系统支持 **24 小时不间断后台执行**，自动完成：
- ✅ 自动选择待执行任务
- ✅ 自动生成设计文档
- ✅ 自动执行代码实现
- ✅ 自动更新进度文档
- ✅ 循环执行直到所有任务完成

## 🚀 快速开始

### 前置要求

1. **Claude Code**：已安装并配置 Claude Code CLI
   - 默认路径：`~/.claude/local/claude`
   - 或通过环境变量 `CLAUDE_COMMAND` 指定路径

2. **Python 3**：用于运行自动化脚本

3. **GitLab MCP**（可选）：用于自动创建 MR
   - 需要在 Cursor 中配置 GitLab MCP 服务器

### 基本使用流程

#### 1. 创建需求

```bash
# 在 Cursor/Claude 对话中使用命令
/issue-create 用户认证系统优化
```

系统会引导你：
- 选择需求类型（根需求/子需求）
- 收集需求信息（标题、负责人、时间线等）
- 自动创建标准化的目录结构

#### 2. 拆分任务

```bash
# 创建子需求
/issue-sub-create
```

#### 3. 需求分析

```bash
# 生成技术分析和需求分析文档
/issue-analysis
```

#### 4. 任务规划

```bash
# 生成任务拆解和进度文档
/issue-plan
```

#### 5. 执行任务

**手动执行**：
```bash
# 在 Cursor/Claude 中执行
/execute
```

**自动化执行**（24小时无人值守）：
```bash
# 执行自动化脚本
cd automation
./run-claude.sh .ai/issue/xxx/plan/0-进度文档.md
```

#### 6. 更新进度

```bash
# 自动更新进度文档
/issue-progress-update
```

#### 7. 创建 MR

```bash
# 自动创建分支并提交 MR
/create-branch-and-mr
```

## 📋 完整工作流

```mermaid
graph TD
    A[准备上下文<br/>收集资料] --> B[/issue-create<br/>创建根需求]
    B --> C[/issue-sub-create<br/>拆出子需求]
    C --> D[/issue-analysis<br/>输出三份分析]
    D --> E[/issue-plan<br/>生成任务拆解]
    E --> F[/issue-detail<br/>补充执行细节]
    F --> G[/execute<br/>按步骤开发]
    G --> H[/issue-progress-update<br/>更新进度]
    H --> I[/create-branch-and-mr<br/>自动生成分支与MR]
```

### 工作流说明

| 阶段 | 命令 | 输入 | 输出 |
|------|------|------|------|
| 需求立项 | `/issue-create` | PRD、负责人、时间线 | 根需求目录、基本信息 |
| 任务拆分 | `/issue-sub-create` | 父需求目录、子任务描述 | 子需求目录结构 |
| 深度理解 | `/issue-analysis` | 需求资料、现状代码 | 技术/需求分析、分析总结 |
| 任务规划 | `/issue-plan` | 分析文档、设计思路 | `plan/step-*`、`0-进度文档.md` |
| 执行细化 | `/issue-detail` | 任务步骤、代码骨架 | 补充执行要点、上线准备 |
| 实际开发 | `/execute` | 详细步骤、目标模块 | 代码提交、测试记录 |
| 进度同步 | `/issue-progress-update` | `plan/` 目录现状 | 最新进度文档 |
| 交付合并 | `/create-branch-and-mr` | 最新提交 | 新分支、GitLab MR |

## 🤖 自动化执行

### 24小时无人值守模式

系统支持完全自动化的任务执行，可以持续运行 24 小时，自动选择并执行待办任务。

#### 启动自动化

```bash
cd automation
./run-claude.sh .ai/issue/xxx/plan/0-进度文档.md
```

#### 自动化特性

- ✅ **自动选择任务**：自动从进度文档中选择第一个待执行任务
- ✅ **自动执行**：使用 Claude Code 自动执行任务，无需人工干预
- ✅ **自动更新进度**：任务完成后自动更新进度文档
- ✅ **循环执行**：自动进入下一个任务，持续运行
- ✅ **超时保护**：单个任务最多执行 30 分钟，超时自动进入下一个
- ✅ **日志记录**：所有执行过程记录到日志文件

#### 配置说明

自动化配置位于 `automation/automation_config.py`：

```python
# 权限模式：完全无人值守
PERMISSION_MODE = "bypassPermissions"

# 执行器类型：claude 或 cursor
EXECUTOR_TYPE = 'claude'

# 监控间隔：15分钟
MONITOR_INTERVAL = 900

# 任务超时：30分钟
TASK_TIMEOUT = 1800
```

### 任务管理器

`task_manager.py` 是自动化执行的核心组件，负责：

- 📂 **扫描任务**：自动扫描 `.ai/issue` 目录下的所有项目
- 📊 **解析进度**：从进度文档中解析任务状态
- 🤖 **执行任务**：调用 Claude Code 或 Cursor 执行任务
- 📝 **更新进度**：任务完成后自动更新进度文档

#### 使用方式

```bash
# 单次执行指定任务
python3 task_manager.py --execute --progress-doc .ai/issue/xxx/plan/0-进度文档.md --task-num 1

# 显示所有任务状态
python3 task_manager.py --status

# 24小时监控模式
python3 task_manager.py --monitor --progress-doc .ai/issue/xxx/plan/0-进度文档.md
```

## 📁 目录结构规范

### 根需求目录结构

```
.ai/issue/YYYY-MM-issue-需求名称/
├── analysis/                # 需求分析文档目录
│   ├── 技术分析报告.md
│   ├── 需求分析报告.md
│   └── 分析总结.md
├── plan/                    # 计划文档目录
│   ├── 0-进度文档.md        # 进度跟踪文档
│   ├── step-1-任务1.md      # 任务文档
│   ├── step-2-任务2.md
│   └── 上线准备.md
├── docs/                    # 需求相关文档
└── sub-issues/              # 子需求目录
    ├── 1-子需求1/
    ├── 2-子需求2/
    └── ...
```

### 进度文档格式

进度文档（`0-进度文档.md`）采用标准格式：

```markdown
### Step 1: 任务名称
- **状态**: ⬜ 未开始
- **预计工时**: 8小时
- **完成时间**: -

### Step 2: 任务名称
- **状态**: 🟡 进行中
- **预计工时**: 4小时
- **完成时间**: -
```

状态说明：
- ⬜ 未开始
- 🟡 进行中
- 🟢 已完成
- 🔴 阻塞/问题

## 🔧 配置说明

### Claude Code 配置

在 `automation/automation_config.py` 中配置：

```python
class ClaudeCodeConfig:
    # Claude Code 可执行文件路径
    CLAUDE_COMMAND = get_claude_command()  # 自动检测或使用环境变量
    
    # 权限模式：bypassPermissions（完全无人值守）
    PERMISSION_MODE = "bypassPermissions"
    
    # 工作目录
    WORKSPACE_PATH = get_workspace_root()  # 自动检测项目根目录
```

### 环境变量

```bash
# 指定 Claude Code 路径
export CLAUDE_COMMAND=/path/to/claude

# 指定执行器类型
export EXECUTOR_TYPE=claude  # 或 cursor
```

## 📊 日志和监控

### 日志位置

所有日志文件位于 `automation/logs/` 目录：

- `claude.log`：主执行日志
- `task_manager.log`：任务管理器日志
- `claude_output_*.log`：每次任务执行的完整输出
- `instruction_*.md`：每次任务的指令文件

### 查看日志

```bash
# 查看主日志
tail -f automation/logs/claude.log

# 查看任务管理器日志
tail -f automation/logs/task_manager.log

# 查看最近的任务输出
ls -lt automation/logs/claude_output_*.log | head -1
```

## 💡 最佳实践

### 1. 需求创建

- ✅ 使用 `/issue-create` 创建根需求，确保目录结构规范
- ✅ 及时补充背景资料到 `docs/` 目录
- ✅ 明确需求类型、负责人和时间线

### 2. 任务拆分

- ✅ 子需求粒度控制在 1-3 天完成
- ✅ 每个子需求独立可测试
- ✅ 明确子需求间的依赖关系

### 3. 任务执行

- ✅ 使用 `/issue-plan` 生成详细的任务步骤
- ✅ 使用 `/issue-detail` 补充执行细节
- ✅ 任务完成后及时更新进度文档

### 4. 自动化执行

- ✅ 夜间使用自动化脚本批量执行文档任务
- ✅ 定期检查日志，确保任务正常执行
- ✅ 重要任务建议手动执行，确保质量

### 5. 代码交付

- ✅ 使用 `/create-branch-and-mr` 自动创建 MR
- ✅ 确保提交信息规范（Conventional Commits）
- ✅ MR 描述包含功能说明和主要改动

## 🐛 故障排查

### 问题 1: Claude Code 无法启动

**检查项**：
- Claude Code 路径是否正确：`echo $CLAUDE_COMMAND`
- 是否有执行权限：`ls -l ~/.claude/local/claude`
- 运行配置验证：`python3 automation_config.py`

### 问题 2: 任务执行失败

**检查项**：
- 查看任务输出日志：`automation/logs/claude_output_*.log`
- 检查任务文档格式是否正确
- 确认工作目录路径正确

### 问题 3: 进度文档未更新

**检查项**：
- 确认进度文档路径正确
- 检查任务状态格式是否符合规范
- 查看任务管理器日志：`automation/logs/task_manager.log`

### 问题 4: MR 创建失败

**检查项**：
- 确认已配置 GitLab MCP
- 检查 GitLab 项目访问权限
- 确认分支推送成功

## 📚 相关文档

- [命令使用指南](commands/README.md)：详细的命令使用说明
- [自动化配置](automation/automation_config.py)：配置参数说明
- [任务管理器](automation/task_manager.py)：任务执行逻辑

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

本项目采用 MIT 许可证。

---

**提示**：首次使用建议先阅读 [命令使用指南](commands/README.md)，了解完整的工作流程和最佳实践。
