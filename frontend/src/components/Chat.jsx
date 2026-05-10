import React, { useState, useEffect } from 'react'
import axios from 'axios'

const STORAGE_KEY = 'med-agent-chat-history'

export default function Chat({ apiBase }) {
  const [messages, setMessages] = useState(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      return saved ? JSON.parse(saved) : []
    } catch { return [] }
  })
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)

  // Persist messages to localStorage
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(messages))
    } catch {}
  }, [messages])

  const clearHistory = () => {
    setMessages([])
    localStorage.removeItem(STORAGE_KEY)
  }

  const sendMessage = async () => {
    if (!input.trim()) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    setInput('')
    setLoading(true)

    try {
      const res = await axios.post(`${apiBase}/chat/message`, {
        message: input,
        history: messages
      })
      setMessages(prev => [...prev, { role: 'assistant', content: res.data.response }])
    } catch (e) {
      console.error('发送消息失败:', e)
      setMessages(prev => [...prev, { role: 'assistant', content: '抱歉，发生了错误: ' + (e.response?.data?.detail || e.message) }])
    }
    setLoading(false)
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="chat-container">
      {messages.length > 0 && (
        <div style={{ padding: '6px 12px', borderBottom: '1px solid var(--border)', display: 'flex', justifyContent: 'flex-end' }}>
          <button onClick={clearHistory} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', fontSize: '11px' }}>
            清空对话
          </button>
        </div>
      )}
      <div className="chat-messages scrollbar-thin">
        {messages.length === 0 && (
          <div className="empty-state" style={{ height: 'auto', padding: '40px 0' }}>
            <p style={{ fontSize: '13px' }}>与智能体对话</p>
            <p style={{ fontSize: '12px', marginTop: '4px' }}>可以询问整合决策的原因，或要求调整整合方案</p>
            <div style={{ marginTop: '16px', fontSize: '12px', textAlign: 'left' }}>
              <p style={{ color: 'var(--text-secondary)', marginBottom: '8px' }}>示例问题：</p>
              <div
                style={{ padding: '8px', background: 'var(--bg-tertiary)', borderRadius: '6px', marginBottom: '6px', cursor: 'pointer' }}
                onClick={() => setInput('为什么把《生理学》里的"炎症"和《病理学》里的"炎症反应"合并了？')}
              >
                为什么把"炎症"和"炎症反应"合并了？
              </div>
              <div
                style={{ padding: '8px', background: 'var(--bg-tertiary)', borderRadius: '6px', cursor: 'pointer' }}
                onClick={() => setInput('请保留"免疫应答"这个知识点，不要删除')}
              >
                请保留"免疫应答"这个知识点
              </div>
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}

        {loading && <div className="loading">思考中...</div>}
      </div>

      <div className="chat-input">
        <input
          type="text"
          placeholder="输入消息..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
        />
        <button onClick={sendMessage} disabled={loading}>
          发送
        </button>
      </div>
    </div>
  )
}
