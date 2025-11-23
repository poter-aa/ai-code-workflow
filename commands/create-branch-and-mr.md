# 创建分支并提交 MR

## ⚠️ 前置要求

**必须配置 GitLab MCP 才能使用此工作流程！**

在使用此工作流程之前，请确保：
1. 已在 Cursor 中配置 GitLab MCP 服务器
2. MCP 服务器已正确连接到 GitLab 实例（gitlab-ee.zhenguanyu.com）
3. 已配置必要的认证信息（Token 等）

## 🚀 自动执行模式

**此命令会自动执行所有步骤，无需用户确认！**

执行此命令时，系统会：
1. **自动检查**：检查当前分支的所有改动（包括已暂存和未暂存的）
2. **自动暂存**：使用 `git add -A` 自动暂存所有改动（包括新增、修改、删除的文件）
3. **自动提交**：提交所有改动（使用最新提交的标题，或生成默认提交信息）
4. **自动提取**：从最新提交信息中提取标题和描述
5. **自动生成**：基于提交信息自动生成分支名（格式：`feature/提交信息转kebab-case`）
6. **自动创建**：创建新分支、推送到远程、创建 MR、切换回原分支
7. **默认配置**：
   - 目标分支：当前分支（原分支，即 `CURRENT_BRANCH`）
   - 项目名：`bolt-logistics2`（自动搜索项目 ID）

## 工作流程说明

此工作流程用于完成以下 Git 和 GitLab 操作：
1. **自动处理所有改动**：自动暂存所有改动（包括未暂存的），然后提交
2. 基于当前分支创建新分支（新分支会包含刚才的提交和所有代码变更）
3. 将新分支推送到远程仓库
4. 在 GitLab 上创建 Merge Request（自动使用提交信息作为标题和描述）
5. 切换回原分支

**重要**：系统会自动处理所有改动（包括未暂存的），确保新分支包含完整的代码变更。

## 自动执行步骤

### 步骤 1: 检查并提交改动（自动）

**系统会自动执行：**
1. 检查当前分支的所有改动（包括已暂存和未暂存的）：`git status`
2. **自动暂存所有改动**：`git add -A`（包括新增、修改、删除的文件）
3. 检查是否有改动需要提交：
   - 如果有改动，自动提交（使用最新提交的标题，或生成默认提交信息）
   - 如果没有改动，检查是否有已提交的提交，如果有则继续下一步
4. **重要**：确保所有代码变更都被提交，包括未暂存的改动，这样新分支才会包含完整的代码变更

### 步骤 2: 提取提交信息并生成分支名（自动）

**系统会自动执行：**
1. 获取最新提交信息（`git log -1 --pretty=%B`）
2. 从提交信息中提取标题（第一行）
3. 自动生成分支名：
   - 格式：`feature/{提交标题转kebab-case}`
   - 示例：`feat: 采购单行状态优化` → `feature/purchase-order-status-optimize`
   - 移除类型前缀（feat/fix/docs等）和特殊字符
   - 转换为小写并用连字符连接

### 步骤 3: 创建新分支（自动）

**系统会自动执行：**
```bash
# 获取当前分支名
CURRENT_BRANCH=$(git branch --show-current)

# 创建新分支（包含刚才的提交）
git checkout -b $NEW_BRANCH
```

### 步骤 4: 推送到远程仓库（自动）

**系统会自动执行：**
```bash
git push -u origin $NEW_BRANCH
```

### 步骤 5: 在 GitLab 上创建 Merge Request（自动）

**系统会自动执行：**

1. **搜索项目获取项目 ID**：
   - 使用 MCP 工具 `mcp_gitlab_search_repositories`
   - 参数：`search: "bolt-logistics2"`
   - 从返回结果中获取项目 ID（`id` 字段）

2. **创建 Merge Request**：
   - 使用 MCP 工具 `mcp_gitlab_create_merge_request`
   - `project_id`: 从步骤 5.1 获取的项目 ID
   - `title`: 使用最新提交的标题
   - `description`: 自动生成结构化描述（功能说明 + 主要改动）
   - `source_branch`: 新分支名
   - `target_branch`: 当前分支（原分支，即 `CURRENT_BRANCH`）

### 步骤 6: 切换回原分支（自动）

**系统会自动执行：**
```bash
git checkout $CURRENT_BRANCH
```

## 完整操作流程示例

### 用户操作（只需一步）

```bash
# 1. 在当前分支进行改动（用户手动执行代码修改）
# 注意：无需手动暂存或提交，系统会自动处理

# 2. 执行命令（系统自动完成所有步骤）
/create-branch-and-mr
```

**说明**：
- 系统会自动暂存所有改动（`git add -A`），包括未暂存的改动
- 系统会自动提交所有改动（使用最新提交的标题，或生成默认提交信息）
- 无需手动执行 `git add` 或 `git commit`，系统会自动处理

### 系统自动执行流程

执行 `/create-branch-and-mr` 后，系统会自动：

1. **检查并提交所有改动**
   - 自动暂存所有改动：`git add -A`（包括未暂存的改动）
   - 自动提交所有改动（使用最新提交的标题）
   - 确保所有代码变更都被提交，新分支才会包含完整的代码变更

2. **提取提交信息**
   - 获取最新提交：`feat: 采购单行状态和提交到小件作业单功能优化`
   - 生成分支名：`feature/purchase-order-status-optimize`

3. **创建并推送分支**
   ```bash
   CURRENT_BRANCH=$(git branch --show-current)  # feature/auto_print_to_purchase
   git checkout -b feature/purchase-order-status-optimize
   git push -u origin feature/purchase-order-status-optimize
   ```

4. **创建 MR**
   - 搜索项目：`mcp_gitlab_search_repositories("bolt-logistics2")` → 项目 ID: 1174
   - 创建 MR：`mcp_gitlab_create_merge_request`
     - project_id: 1174
     - title: "feat: 采购单行状态和提交到小件作业单功能优化"
     - source_branch: "feature/purchase-order-status-optimize"
     - target_branch: "feature/auto_print_to_purchase"（原分支）

5. **切换回原分支**
   ```bash
   git checkout feature/auto_print_to_purchase
   ```

**结果**：MR 创建成功，链接：https://gitlab-ee.zhenguanyu.com/yuanli/bolt-logistics2/-/merge_requests/1426

## 注意事项

1. **自动执行**: 此命令会自动执行所有步骤，无需用户确认或输入额外信息
2. **自动处理所有改动**: 
   - 系统会自动暂存所有改动（`git add -A`），包括未暂存的改动
   - 确保所有代码变更都被提交，新分支才会包含完整的代码变更
   - 无需手动暂存改动，系统会自动处理
3. **提交信息**: 
   - 如果有未提交的改动，系统会自动提交（使用最新提交的标题，或生成默认提交信息）
   - 如果已有提交，系统会基于最新提交创建新分支
4. **提交信息格式**: 建议使用规范的提交信息格式（如 Conventional Commits），系统会基于提交信息自动生成分支名和 MR 标题
5. **分支命名**: 分支名会自动从提交信息生成，格式为 `feature/{提交标题转kebab-case}`
6. **默认配置**: 
   - 目标分支默认为当前分支（原分支，即 `CURRENT_BRANCH`）
   - 项目名默认为 `bolt-logistics2`（会自动搜索项目 ID）
7. **权限检查**: 确保有权限推送到远程仓库和创建 MR
8. **MCP 工具**: 创建 MR 的步骤使用 MCP GitLab 工具自动执行
9. **分支切换**: 创建 MR 后会自动切换回原分支，方便继续在原分支工作
10. **错误处理**: 如果任何步骤失败，系统会显示错误信息，但不会回滚已完成的步骤

## 工作流程对比

### 原流程（手动，已废弃）
- 暂存改动 → 创建新分支 → 在新分支提交 → 推送 → 手动创建 MR（需要填写信息）

### 新流程（自动执行）
- 在当前分支进行代码改动 → **执行 `/create-branch-and-mr`** → 系统自动完成所有步骤
  - 自动暂存所有改动（包括未暂存的）
  - 自动提交所有改动
  - 自动创建分支、推送、创建 MR

**自动化优势**：
- ✅ **无需确认**：所有步骤自动执行，无需用户输入
- ✅ **自动处理所有改动**：自动暂存所有改动（包括未暂存的），确保新分支包含完整的代码变更
- ✅ **智能提取**：自动从提交信息提取标题和生成分支名
- ✅ **自动创建**：自动搜索项目 ID、创建分支、推送、创建 MR
- ✅ **安全可靠**：改动先保存在当前分支，新分支基于已提交代码
- ✅ **自动回退**：操作完成后自动切换回原分支，方便继续工作
- ✅ **减少错误**：避免手动输入错误，提高效率
- ✅ **无需手动暂存**：系统自动处理所有改动，无需手动执行 `git add`

## 故障排查

### 问题 1: 推送失败
- 检查是否有远程仓库的推送权限
- 确认远程仓库地址正确：`git remote -v`

### 问题 2: MCP 工具无法使用
- 确认已在 Cursor 中配置 GitLab MCP
- 检查 MCP 服务器连接状态
- 验证认证信息是否正确

### 问题 3: 找不到项目
- 确认项目名称正确
- 检查是否有访问该项目的权限
- 验证 GitLab 实例地址是否正确

### 问题 4: 切换分支失败
- 确认分支名正确：`git branch --show-current`
- 检查是否有未提交的改动：`git status`

## 相关资源

- GitLab API 文档: https://docs.gitlab.com/ee/api/
- Git 工作流程: https://git-scm.com/book

