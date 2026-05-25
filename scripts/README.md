# scripts/ — 脚本工具目录规范

## 目录结构

```
scripts/
├── README.md               # 本文件
├── dev/                     # 开发辅助脚本
│   ├── test_db_connection.py    # 数据库连接测试
│   ├── test_tavily.py           # Tavily API 测试
│   └── show_db_schema.py        # 查看数据库结构
├── migrations/              # 数据库迁移脚本
│   └── migrate_chunk_schema.py  # RAG chunk schema 迁移
└── deploy/                  # 部署脚本（待添加）
    ├── start.sh
    └── docker-compose.yml
```

## 分类规则

| 分类 | 用途 | 示例 |
|------|------|------|
| `dev/` | 开发调试工具，一次性辅助脚本 | 连接测试、API 测试、schema 查看 |
| `migrations/` | 数据库 schema 迁移，需按序号命名 | `001_add_xxx.py` |
| `deploy/` | 部署、CI/CD、环境初始化 | 启动脚本、Docker 配置 |

## 命名规范

- 小写 + 下划线：`test_db_connection.py`
- 迁移脚本带序号：`001_add_user_role.py`
- Shell 脚本：`.sh` 后缀

## 原则

- 脚本应该是自包含的（不依赖其他脚本）
- 不在项目中保留已完成的一次性脚本
- 重要脚本添加注释说明用途和用法
- 不提交包含敏感信息的脚本（API Key、密码等）
