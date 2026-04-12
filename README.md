# aiDirector

一个面向短视频创作的 AI 导演工作台示例项目。

## 技术栈

- 后端：FastAPI + SQLAlchemy + PostgreSQL
- 前端：Vue 3 + Vite + Element Plus
- 中间件：Redis + Docker Compose

## 核心功能

- AI 分镜管理：创建、运行并查看分镜进度
- LLM 模型配置：维护模型接口与密钥参数
- 提示词模板管理：维护可复用模板
- 提示词模板支持「提示词正文」「返回格式（JSON / 纯文本 / Markdown）」「输出格式示例」分栏存储，调用模型时自动拼接；后端启动时会插入缺失的 `分镜-*` 五条模板，并对**输出格式示例仍为空**的旧记录自动套用拆分后的正文与示例（已填写格式区则不再覆盖）

## 快速启动（推荐 Docker）

```bash
docker compose up -d --build
```

启动后访问：

- 前端：`http://localhost:5173`
- 后端 API 文档：`http://localhost:8000/docs`

## 本地启动（不使用 Docker）

### 后端

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
uvicorn app.main:app --reload --port 8000
```

### 前端

```bash
cd frontend
npm install
npm run dev
```
