# 海外仓采购管理系统

基于企业微信采购表的智能管理系统，支持多人在线编辑、AI分析、API对接。

## 功能

- 📋 **产品管理** - 在线编辑采购表，支持SKU、价格、库存、状态管理
- 📄 **采购单管理** - 创建和管理采购订单
- 🤖 **AI智能分析** - 接入大模型进行价格分析、库存预警、采购建议
- 🔌 **REST API** - 完整API接口，可对接企业微信等办公系统
- 👥 **多用户支持** - 多人同时在线编辑，权限管理
- ⚡ **无容量限制** - 使用数据库存储，不再受企业微信文档容量限制

## 快速部署

### 方式一：Render免费云部署

1. 注册 [Render](https://render.com) 账号（GitHub登录）
2. 点击 **New +** → **Web Service**
3. 连接你的GitHub仓库，或在[Dashboard]直接部署
4. 选择 `Python` 环境，Build Command 填：
   ```
   pip install -r requirements.txt
   ```
5. Start Command 填：
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. 在 Environment Variables 中配置：
   - `PYTHON_VERSION`: `3.11.0`

### 方式二：本地运行

```bash
# 安装依赖
pip install -r requirements.txt

# 运行
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

访问 http://localhost:8000

### 方式三：Docker

```bash
docker build -t procurement-system .
docker run -p 8000:8000 procurement-system
```

## 默认账号

- 用户名: `admin`
- 密码: `admin123`

## 从企业微信迁移数据

1. 导出旧表格数据为JSON格式
2. 在新系统"数据导入"页面粘贴JSON
3. 一键导入

## API文档

启动后访问 `/api` 查看所有可用端点。

## 环境变量

| 变量 | 说明 | 必填 |
|------|------|------|
| OPENAI_API_KEY | OpenAI API Key | 否（AI功能） |
| OPENAI_API_BASE | API地址 | 否 |
| WECOM_WEBHOOK_URL | 企微群机器人Webhook | 否（通知功能） |