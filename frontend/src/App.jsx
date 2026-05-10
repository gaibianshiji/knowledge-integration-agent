import React, { useState, useEffect } from 'react'
import axios from 'axios'
import FileUpload from './components/FileUpload'
import KnowledgeGraph from './components/KnowledgeGraph'
import RAGQuery from './components/RAGQuery'
import Chat from './components/Chat'
import IntegrationPanel from './components/IntegrationPanel'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export default function App() {
  const [textbooks, setTextbooks] = useState([])
  const [graphs, setGraphs] = useState({})
  const [selectedNode, setSelectedNode] = useState(null)
  const [activeTab, setActiveTab] = useState('integration')
  const [ragStatus, setRagStatus] = useState({ indexed_textbooks: 0, total_chunks: 0 })
  const [integrationResult, setIntegrationResult] = useState(null)
  const [loading, setLoading] = useState('')
  const [allGraphData, setAllGraphData] = useState({ nodes: [], links: [] })

  useEffect(() => {
    loadTextbooks()
    loadRagStatus()
  }, [])

  const loadTextbooks = async () => {
    try {
      const res = await axios.get(`${API_BASE}/upload/textbooks`)
      setTextbooks(res.data)
    } catch (e) {
      console.error('加载教材列表失败:', e)
    }
  }

  const loadRagStatus = async () => {
    try {
      const res = await axios.get(`${API_BASE}/rag/status`)
      setRagStatus(res.data)
    } catch (e) {
      console.error('加载RAG状态失败:', e)
    }
  }

  const handleUpload = async (file) => {
    setLoading('uploading')
    const formData = new FormData()
    formData.append('file', file)
    try {
      await axios.post(`${API_BASE}/upload/textbook`, formData)
      await loadTextbooks()
    } catch (e) {
      console.error('上传失败:', e)
      alert('上传失败: ' + (e.response?.data?.detail || e.message))
    }
    setLoading('')
  }

  const handleBlobUpload = async (file) => {
    setLoading('blob-upload')
    try {
      // Step 1: Get presigned URL
      const presignedResp = await axios.post(`${API_BASE}/upload/presigned-url`, {
        filename: file.name,
        content_type: file.type || 'application/pdf'
      })
      const { url: presignedUrl, blobUrl } = presignedResp.data

      // Step 2: Upload directly to Vercel Blob
      await axios.put(presignedUrl, file, {
        headers: { 'Content-Type': file.type || 'application/pdf' }
      })

      // Step 3: Send blob URL to backend for parsing
      await axios.post(`${API_BASE}/upload/textbook-url`, {
        blob_url: blobUrl,
        filename: file.name
      })
      await loadTextbooks()
    } catch (e) {
      console.error('大文件上传失败:', e)
      alert('上传失败: ' + (e.response?.data?.detail || e.message))
    }
    setLoading('')
  }

  const handleBuildGraph = async (textbookId) => {
    setLoading(`graph-${textbookId}`)
    try {
      await axios.post(`${API_BASE}/graph/build/${textbookId}`)
      const res = await axios.get(`${API_BASE}/graph/data/${textbookId}`)
      setGraphs(prev => ({ ...prev, [textbookId]: res.data }))
      mergeAllGraphs()
    } catch (e) {
      console.error('构建图谱失败:', e)
      alert('构建图谱失败: ' + (e.response?.data?.detail || e.message))
    }
    setLoading('')
  }

  const loadGraphData = async (textbookId) => {
    try {
      const res = await axios.get(`${API_BASE}/graph/data/${textbookId}`)
      setGraphs(prev => ({ ...prev, [textbookId]: res.data }))
      mergeAllGraphs()
    } catch (e) {
      console.error('加载图谱失败:', e)
    }
  }

  const mergeAllGraphs = () => {
    const nodes = []
    const links = []
    const colorMap = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#8b5cf6']

    Object.entries(graphs).forEach(([tbId, graph], idx) => {
      const color = colorMap[idx % colorMap.length]
      graph.nodes?.forEach(node => {
        nodes.push({ ...node, color, size: 8 })
      })
      graph.relations?.forEach(rel => {
        links.push({ source: rel.source, target: rel.target, type: rel.relation_type })
      })
    })

    setAllGraphData({ nodes, links })
  }

  useEffect(() => {
    mergeAllGraphs()
  }, [graphs])

  const handleBuildAllGraphs = async () => {
    setLoading('all-graphs')
    for (const tb of textbooks) {
      if (!graphs[tb.textbook_id]) {
        await handleBuildGraph(tb.textbook_id)
      }
    }
    setLoading('')
  }

  const handleBuildIndex = async () => {
    setLoading('index')
    try {
      await axios.post(`${API_BASE}/rag/index`)
      await loadRagStatus()
    } catch (e) {
      console.error('构建索引失败:', e)
      alert('构建索引失败: ' + (e.response?.data?.detail || e.message))
    }
    setLoading('')
  }

  const handleRunIntegration = async () => {
    setLoading('integration')
    try {
      const res = await axios.post(`${API_BASE}/integration/run`)
      setIntegrationResult(res.data)
    } catch (e) {
      console.error('整合失败:', e)
      alert('整合失败: ' + (e.response?.data?.detail || e.message))
    }
    setLoading('')
  }

  return (
    <div className="app">
      <header className="header">
        <h1>学科知识整合智能体</h1>
        <div className="header-stats">
          <span><span className="dot"></span> {textbooks.length} 本教材已加载</span>
          <span>{ragStatus.total_chunks} 个知识块已索引</span>
          {integrationResult && <span>{integrationResult.stats?.merged || 0} 个知识点已整合</span>}
        </div>
      </header>

      <div className="main-content">
        <div className="sidebar">
          <FileUpload
            textbooks={textbooks}
            onUpload={handleUpload}
            onBlobUpload={handleBlobUpload}
            onBuildGraph={handleBuildGraph}
            onBuildAll={handleBuildAllGraphs}
            loading={loading}
            graphs={graphs}
          />

          <div className="sidebar-section">
            <h3>RAG 索引</h3>
            <div className="stats-grid">
              <div className="stat-card">
                <div className="value">{ragStatus.indexed_textbooks}</div>
                <div className="label">已索引教材</div>
              </div>
              <div className="stat-card">
                <div className="value">{ragStatus.total_chunks}</div>
                <div className="label">知识块数</div>
              </div>
            </div>
            <button
              className="btn btn-primary"
              onClick={handleBuildIndex}
              disabled={loading === 'index'}
              style={{ width: '100%' }}
            >
              {loading === 'index' ? '构建中...' : '构建向量索引'}
            </button>
          </div>
        </div>

        <div className="center-panel">
          <KnowledgeGraph
            data={allGraphData}
            onNodeSelect={setSelectedNode}
            integrationResult={integrationResult}
          />
        </div>

        <div className="right-panel">
          <div className="tabs">
            <div
              className={`tab ${activeTab === 'integration' ? 'active' : ''}`}
              onClick={() => setActiveTab('integration')}
            >
              整合
            </div>
            <div
              className={`tab ${activeTab === 'rag' ? 'active' : ''}`}
              onClick={() => setActiveTab('rag')}
            >
              RAG问答
            </div>
            <div
              className={`tab ${activeTab === 'chat' ? 'active' : ''}`}
              onClick={() => setActiveTab('chat')}
            >
              对话
            </div>
          </div>

          <div className="tab-content scrollbar-thin">
            {activeTab === 'integration' && (
              <IntegrationPanel
                onRunIntegration={handleRunIntegration}
                integrationResult={integrationResult}
                loading={loading === 'integration'}
                selectedNode={selectedNode}
              />
            )}
            {activeTab === 'rag' && <RAGQuery apiBase={API_BASE} />}
            {activeTab === 'chat' && <Chat apiBase={API_BASE} />}
          </div>
        </div>
      </div>
    </div>
  )
}
