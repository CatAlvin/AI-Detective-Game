# AI Detective Game

AI 动态生成案件、玩家自由审问 NPC，并通过核验证据构建完整指控理论的单人推理游戏。

*An AI-assisted single-player detective game featuring generated cases, free-form NPC interrogation, evidence verification, and structured accusation building.*

## 版本与进度

- 当前版本：**V2**
- 状态：可运行原型，审问、调查、证据核验、检方预审与最终指控闭环已实现
- 技术栈：React 19、TypeScript、FastAPI、SQLAlchemy、MySQL 8

## 核心功能

- 案件事实生成后会被冻结，NPC 回答始终受既定世界状态约束。
- 自由提问支持时间、人物、旧口供和已核验证据等上下文。
- 口供先作为线索，完成调查后才能转为可用于指控的证据。
- 最终指控需要分别提交动机、手段和机会证据链。
- AI 服务不可用时可使用本地保底案件继续完整流程。

## 使用方式

需要 Python 3.11+、Node.js 20+ 和 MySQL 8。

```powershell
Copy-Item .env.example .env
# 编辑 .env，填写 MySQL 配置；如使用 Kimi，再填写 KIMI_API_KEY

python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
.\scripts\create_database.ps1

cd frontend
npm install
cd ..
.\start-dev.ps1
```

打开游戏：<http://127.0.0.1:5173>

API 文档：<http://127.0.0.1:8765/api/docs>

不使用 Kimi 时，将 `.env` 中的 `KIMI_ENABLED` 设为 `false`。

## AI 辅助

运行时由 Kimi 生成结构化候选案件并润色受约束的 NPC 回答，案件校验、证据状态和胜负判定由本地规则完成。开发过程也使用 AI 辅助需求拆解、实现和测试，最终功能取舍由作者确认。

## 验证

```powershell
.\.venv\Scripts\python.exe -m pytest backend\tests
cd frontend
npm run lint
npm run build
```

产品范围与体验记录见 [PRD-V2.md](PRD-V2.md) 和 [V2 体验审计](docs/V2-PLAYTEST-AUDIT.md)。
