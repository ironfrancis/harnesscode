<p align="center">
  <img src="https://readme-typing-svg.demolab.com?font=Courier+New&weight=900&size=40&pause=1000&color=FF6A00&center=true&vCenter=true&repeat=true&width=400&lines=HARNESSCODE" alt="HARNESSCODE">
</p>

<p align="center">
  <em>AI 驱动的人机协作开发框架</em>
</p>

<p align="center">
  <b>简体中文</b> | <a href="README.md">English</a>
</p>

<p align="center">
  <a href="#特性">特性</a> •
  <a href="#安装">安装</a> •
  <a href="#架构">架构</a> •
  <a href="#命令">命令</a> •
  <a href="#贡献">贡献</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.8+-blue.svg" alt="Python Version">
  <img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License">
  <img src="https://img.shields.io/badge/OpenCode-supported-purple.svg" alt="OpenCode">
  <img src="https://img.shields.io/badge/Claude%20Code-supported-orange.svg" alt="Claude Code">
</p>

---

## 特性

### 🚀 全自动开发
只要 PRD 完整、技术规范足够，全程可自动开发无需值守。配置好后让它自己跑就行。

### 🔄 Human-in-the-Loop
人在回路设计哲学 - AI 执行，人类决策。每个关键节点都可暂停等待人工干预，确保开发过程可控可预期。

### 🛠️ Harness 架构
可扩展的 Agent 框架 - Orchestrator、Coder、Tester、Fixer、Reviewer 五大专业化 Agent 协作，通过状态文件驱动开发循环。

### ⚡ 双引擎支持
同时支持 [OpenCode](https://opencode.ai) 和 [Claude Code](https://www.anthropic.com/claude-code)，一键切换 AI 执行引擎。

### 🌐 技术栈无关
Java/Spring Boot、Python、Node.js、React、Vue... 任意技术栈，只需定义 `tech-stack.md` 即可开始。

---

## 安装

### 前置要求

- Python 3.8+
- [OpenCode](https://opencode.ai) 或 [Claude Code](https://www.anthropic.com/claude-code) 已安装

### OpenCode 安装

**Windows**:
```powershell
scoop install opencode
# 或
npm install -g opencode-ai
```

**macOS**:
```bash
brew install anomalyco/tap/opencode
# 或
npm install -g opencode-ai
```

**Linux**:
```bash
curl -fsSL https://opencode.ai/install | bash
# 或
npm install -g opencode-ai
```

### Claude Code 安装

```bash
npm install -g @anthropic-ai/claude-code
claude auth login
```

### HarnessCode 安装

**Windows**:
```powershell
python -m pip install --upgrade pip
python -m pip install -e .
hc --version
```

**macOS / Linux**:
```bash
python3 -m pip install --upgrade pip
python3 -m pip install -e .
hc --version
```

<details>
<summary>🔧 常见问题</summary>

**Q: `hc` 命令找不到**

Windows: 将 Python Scripts 目录添加到 PATH
```powershell
python -c "import sysconfig; print(sysconfig.get_path('scripts'))"
# 将输出的路径添加到系统 PATH
```

macOS/Linux:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

**Q: `externally-managed-environment` 错误**

使用 venv:
```bash
python3 -m venv ~/.hc-venv
source ~/.hc-venv/bin/activate
pip install harnesscode
```

</details>

---

## 架构

```
┌─────────────────────────────────────────────────────────┐
│                    Orchestrator                         │
│         读取状态 → 决策下一步 → 调度 Agent              │
└─────────────────────┬───────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
┌───────────┐  ┌───────────┐  ┌───────────┐
│  Coder    │  │  Tester   │  │  Fixer    │
│ 实现功能  │  │ 运行测试  │  │ 修复问题  │
└───────────┘  └───────────┘  └───────────┘
        │             │             │
        └─────────────┼─────────────┘
                      │
                      ▼
              ┌───────────┐
              │ Reviewer  │
              │ 代码审查  │
              └───────────┘
```

### Agent 职责

| Agent | 职责 |
|-------|------|
| **Orchestrator** | 读取项目状态，决策下一步执行哪个 Agent |
| **Initializer** | 项目初始设置，检查技术栈定义，生成 feature_list |
| **Coder** | 实现功能代码 |
| **Tester** | 多层测试：静态分析 → 单元测试 → 编译检查 |
| **Fixer** | 根据测试/审查报告修复代码 |
| **Reviewer** | 代码规范审查 |

### 状态文件

```
.your-project/
├── .harnesscode/                 # 运行数据（自动生成）
│   ├── feature_list.json         # 功能列表
│   ├── test_report.json          # 测试报告
│   ├── review_report.json        # 审查报告
│   ├── missing_info.json         # 阻塞项（需人工处理）
│   └── config.yaml               # 项目配置
├── input/                        # 输入文件
│   ├── prd/                      # 需求文档
│   │   └── tech-stack.md         # 技术栈定义（必须）
│   └── techspec/                 # 技术规范文件
└── dev-log.txt                   # 运行日志
```

### 输入文件

#### `input/prd/` - 需求文档

包含产品需求和技术栈定义。

| 文件 | 必须 | 说明 |
|------|------|------|
| `tech-stack.md` | ✅ 是 | 技术栈定义。文件名必须一致，格式不限 |

项目中包含的 `tech-stack.md` 是示例（Java + React），请根据实际项目修改。

#### `input/techspec/` - 技术规范

代码规范和标准。每个文件定义特定类别的规则。

**Java 规范**（可作为参考，也可修改后直接使用）：
- `tech-spec-checkstyle.md` - 代码风格（Checkstyle）
- `tech-spec-entity.md` - Entity 类规范
- `tech-spec-dto.md` - DTO 规范
- `tech-spec-service.md` - Service 层规范
- `tech-spec-controller.md` - Controller 规范
- `tech-spec-mapper.md` - MyBatis Mapper 规范
- `tech-spec-enum.md` - 枚举规范
- `tech-spec-exception.md` - 异常处理
- `tech-spec-response.md` - API 响应格式
- `tech-spec-database.md` - 数据库规范

**React/TypeScript 规范**：
- `tech-spec-react-component.md` - React 组件规范
- `tech-spec-typescript.md` - TypeScript 规范
- `tech-spec-antd-usage.md` - Ant Design 使用规范
- `tech-spec-api-request.md` - API 请求规范
- `tech-spec-frontend-*.md` - 前端路由、样式、表单、性能、安全
- `tech-spec-redux.md` - 状态管理
- `tech-spec-i18n.md` - 国际化

---

## 命令

| 命令 | 说明 |
|-----|------|
| `hc init` | 初始化项目配置（交互式） |
| `hc start` | 启动开发循环 |
| `hc status` | 显示项目状态和指标 |
| `hc restore` | 从备份恢复配置文件 |
| `hc uninstall` | 卸载 HarnessCode |
| `hc config` | 查看或修改配置设置 |
| `hc --version` | 显示版本信息 |

### 选项

```bash
hc init --backend claude    # 指定 Claude Code 引擎
hc start --backend opencode # 指定 OpenCode 引擎
```

### 配置

```bash
hc config                   # 查看当前配置
hc config language zh       # 切换为中文
hc config language en       # 切换为英文
hc config backend claude    # 设置后端为 Claude
```

---

## 环境变量

| 变量 | 说明 |
|------|------|
| `HARNESSCODE_BACKEND` | 默认 AI 引擎 (opencode/claude) |
| `HARNESSCODE_LANGUAGE` | 默认语言 (en/zh) |
| `OPENCODE_PATH` | 自定义 opencode 命令路径 |
| `CLAUDE_PATH` | 自定义 claude 命令路径 |

---

## 项目结构

```
harnesscode/
├── pyproject.toml          # 包配置
├── src/harnesscode/
│   ├── cli.py              # CLI 入口
│   ├── infinite_dev.py     # 主循环脚本
│   ├── installer.py        # 初始化/卸载模块
│   ├── backend.py          # AI 引擎抽象层
│   ├── agents/             # Agent 定义
│   │   ├── orchestrator.md
│   │   ├── initializer.md
│   │   ├── coder.md
│   │   ├── tester.md
│   │   ├── fixer.md
│   │   └── reviewer.md
│   └── utils/              # 工具模块
└── input/                  # 输入文件示例
```

---

## 卸载

```bash
# 清理 agent 文件和配置
hc uninstall

# 卸载 Python 包
pip uninstall harnesscode
```

---

## 贡献

欢迎贡献！请查看 [Contributing Guide](CONTRIBUTING.md)。

### 开发

```bash
git clone https://github.com/yzddp/harnesscode.git
cd harnesscode
python -m pip install -e .
```

---

## License

[MIT](LICENSE)

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/yzddp">油炸电灯泡 (yzddp)</a>
</p>