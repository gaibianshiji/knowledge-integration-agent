import React, { useRef, useState } from 'react'

export default function FileUpload({ textbooks, onUpload, onBuildGraph, onBuildAll, loading, graphs }) {
  const fileInputRef = useRef(null)
  const [selected, setSelected] = useState(new Set())

  const handleDrop = (e) => {
    e.preventDefault()
    const files = e.dataTransfer.files
    for (const file of files) {
      onUpload(file)
    }
  }

  const handleDragOver = (e) => {
    e.preventDefault()
  }

  const handleFileSelect = (e) => {
    const files = e.target.files
    for (const file of files) {
      onUpload(file)
    }
  }

  const toggleSelect = (id) => {
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(textbooks.map(t => t.textbook_id)))
  const deselectAll = () => setSelected(new Set())

  return (
    <div className="sidebar-section">
      <h3>教材管理</h3>
      <div
        className="upload-area"
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onClick={() => fileInputRef.current?.click()}
      >
        <div style={{ fontSize: '24px', marginBottom: '8px' }}>📚</div>
        <p>拖拽上传或点击选择</p>
        <p style={{ fontSize: '11px', marginTop: '4px' }}>支持 PDF / Markdown / TXT</p>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          accept=".pdf,.md,.txt"
          onChange={handleFileSelect}
          style={{ display: 'none' }}
        />
      </div>

      {loading === 'uploading' && (
        <div className="upload-progress">
          <div className="progress-bar"><div className="progress-fill"></div></div>
          <span className="progress-text">上传中...</span>
        </div>
      )}

      {textbooks.length > 0 && (
        <>
          <div className="selection-controls">
            <button className="btn btn-secondary" onClick={selectAll} style={{ fontSize: '11px', padding: '4px 8px' }}>全选</button>
            <button className="btn btn-secondary" onClick={deselectAll} style={{ fontSize: '11px', padding: '4px 8px' }}>取消</button>
            <span style={{ fontSize: '11px', color: 'var(--text-secondary)' }}>已选 {selected.size}/{textbooks.length}</span>
          </div>

          <ul className="file-list">
            {textbooks.map(tb => (
              <li key={tb.textbook_id} className="file-item">
                <input
                  type="checkbox"
                  className="file-checkbox"
                  checked={selected.has(tb.textbook_id)}
                  onChange={() => toggleSelect(tb.textbook_id)}
                />
                <span className="name" title={tb.filename}>{tb.title}</span>
                <button
                  className={`btn ${graphs[tb.textbook_id] ? 'btn-done' : 'btn-build'}`}
                  onClick={() => onBuildGraph(tb.textbook_id)}
                  disabled={loading === `graph-${tb.textbook_id}`}
                >
                  {loading === `graph-${tb.textbook_id}` ? '...' : graphs[tb.textbook_id] ? '✓' : '构建'}
                </button>
              </li>
            ))}
          </ul>

          <div style={{ marginTop: '12px' }}>
            <button
              className="btn btn-primary"
              onClick={onBuildAll}
              disabled={loading === 'all-graphs'}
              style={{ width: '100%' }}
            >
              {loading === 'all-graphs' ? '构建中...' : '全部构建'}
            </button>
          </div>
        </>
      )}
    </div>
  )
}
