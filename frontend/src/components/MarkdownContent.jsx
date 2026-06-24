import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/** 模块级常量，避免每次渲染重新创建数组 */
const remarkPlugins = [remarkGfm]

/**
 * AI 生成的 Markdown 内容渲染组件。
 *
 * 仅对 assistant 消息使用；用户消息直接渲染纯文本。
 * 使用 React.memo 避免无关状态变化触发昂贵的 Markdown 解析。
 */
const MarkdownContent = React.memo(function MarkdownContent({ children, plaintext }) {
  if (plaintext || !children) {
    return <>{children}</>
  }
  return (
    <ReactMarkdown remarkPlugins={remarkPlugins}>
      {children}
    </ReactMarkdown>
  )
})

export default MarkdownContent
