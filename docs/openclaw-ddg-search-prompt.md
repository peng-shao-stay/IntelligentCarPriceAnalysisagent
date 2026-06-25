# OpenClaw 联网搜索 — DuckDuckGo 自建 Python 脚本

## 工具定义（粘贴到 OpenClaw Tools 配置）

```json
{
  "name": "web_search",
  "description": "使用 DuckDuckGo 搜索互联网实时信息。完全免费，无需 API Key。用于查询最新新闻、车价、技术动态等。",
  "parameters": {
    "type": "object",
    "properties": {
      "query": {
        "type": "string",
        "description": "搜索关键词，支持中文。例如：'比亚迪秦L 最新价格 2025'"
      },
      "max_results": {
        "type": "integer",
        "description": "返回结果数（1-10），默认 5",
        "default": 5
      }
    },
    "required": ["query"]
  }
}
```

## Python 脚本（search_ddg.py）

保存到项目根目录，`pip install ddgs` 后即可使用：

```python
# search_ddg.py
# pip install ddgs
from ddgs import DDGS
import time

def search_web(query: str, max_results: int = 5) -> str:
    """使用 DuckDuckGo 搜索互联网实时信息。完全免费，无需 API Key。"""
    if not query or len(query.strip()) == 0:
        return "❌ 错误：请提供搜索关键词"

    print(f"🔍 [Search Tool] 正在搜索: '{query}' ...")
    
    try:
        time.sleep(1)  # 礼貌延时
        
        results = []
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query, 
                max_results=max_results, 
                region="cn-zh" 
            )
            
            if not search_results:
                return f"⚠️ 未找到关于 '{query}' 的相关信息。"

            for i, r in enumerate(search_results, 1):
                title = r.get('title', '无标题')
                href = r.get('href', '无链接')
                body = r.get('body', '无摘要')
                
                result_str = (
                    f"[{i}] **{title}**\n"
                    f"   🔗 来源: {href}\n"
                    f"   📝 摘要: {body}\n"
                )
                results.append(result_str)
        
        final_output = (
            f"✅ 找到 {len(results)} 条关于 '{query}' 的结果：\n\n" 
            + "\n".join(results)
        )
        return final_output

    except Exception as e:
        error_msg = str(e)
        if "timeout" in error_msg.lower() or "connection" in error_msg.lower():
            hint = "💡 提示：无法连接 DuckDuckGo，请检查网络代理。"
        else:
            hint = "💡 提示：搜索过于频繁，稍等后重试。"
            
        return f"❌ 搜索出错: {error_msg}\n{hint}"

if __name__ == "__main__":
    print(search_web("2026年最省钱的 AI 方案"))
```

## System Prompt 片段（粘贴到 OpenClaw System Prompt）

```
## 联网搜索能力

你拥有联网搜索能力。当需要查询最新信息（价格、新闻、技术动态等）时，
使用 `web_search` 工具。

**何时使用搜索：**
- 用户询问最新价格、行情、优惠 → 搜索 "[品牌] [车型] 价格 报价 最新"
- 用户询问汽车新闻、行业动态 → 搜索 "[关键词] 汽车 最新新闻"
- 用户要求对比车型 → 搜索 "[车型A] vs [车型B] 对比 配置"
- 用户询问任何你训练数据之后发生的事情
- 不确定的信息，优先搜索验证

**何时不用搜索：**
- 纯闲聊（"你好"、"今天天气"）
- 通用知识问题（"什么是涡轮增压"）
- 用户明确说"不需要联网"

**搜索结果使用规则：**
1. 引用搜索到的信息时，标注来源链接
2. 如果搜索结果互相矛盾，指出矛盾并给出综合判断
3. 搜索结果可能包含广告/软文，保持批判性思维
4. 结合你的训练知识综合分析，不要机械复述搜索结果
```

## 使用方式

```bash
# 1. 安装依赖
pip install ddgs

# 2. 测试搜索
python search_ddg.py

# 3. 将 search_ddg.py 路径配置到 OpenClaw 的工具调用中
# 4. 粘贴上述 System Prompt 片段到 OpenClaw 配置
```

## 对比：为什么不用 Tavily / Serper

| | DuckDuckGo | Tavily | Serper |
|---|---|---|---|
| 费用 | **免费** | $0 / 1000次后有配额 | 付费 |
| API Key | **不需要** | 需要 | 需要 |
| 中文搜索 | ✅ cn-zh | ✅ | ✅ |
| 稳定性 | 良好 | 好 | 好 |
| 速度 | 快 | 快 | 快 |
