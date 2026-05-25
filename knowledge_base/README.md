# knowledge_base/ — RAG 知识库文件组织规范

> 此目录存放用于 RAG 向量化索引的原始文档。

## 目录结构

```
knowledge_base/
├── cars/                   # 汽车数据文档
│   ├── brands/             # 按品牌分类
│   │   ├── tesla.md        # 特斯拉
│   │   ├── byd.md          # 比亚迪
│   │   └── ...
│   ├── models/             # 按车型分类
│   └── comparisons/        # 对比评测
├── news/                   # 行业新闻归档
├── policies/               # 政策法规
├── technical/              # 技术文档（电池、自动驾驶等）
└── README.md               # 本文件
```

## 文件格式要求

- **格式**: Markdown (`.md`) 或纯文本 (`.txt`)
- **编码**: UTF-8
- **命名**: 小写英文 + 连字符，如 `tesla-model-3.md`
- **元数据**: 每个文件头部应包含：

```markdown
---
brand: 特斯拉
model: Model 3
type: car_spec
source: https://example.com
language: zh
---
```

## 入库流程

1. 将文档放入对应目录
2. 调用 `POST /api/v1/rag/ingest` 或通过管理面板上传
3. 系统自动分块 → 向量化 → 存入 pgvector
4. 搜索时通过 `POST /api/v1/rag/search` 检索

## 注意事项

- 不要放入敏感数据（API Key、密码等）
- 单个文件建议不超过 100KB
- 支持的语言：中文、英文
