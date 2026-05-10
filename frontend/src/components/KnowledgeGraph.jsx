import React, { useEffect, useRef, useState, useCallback } from 'react'
import * as d3 from 'd3'

export default function KnowledgeGraph({ data, onNodeSelect, integrationResult }) {
  const svgRef = useRef(null)
  const matrixSvgRef = useRef(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterTextbook, setFilterTextbook] = useState('')
  const [viewMode, setViewMode] = useState('graph')
  const [selectedNode, setSelectedNode] = useState(null)
  const [popupPos, setPopupPos] = useState({ x: 0, y: 0 })
  const simulationRef = useRef(null)
  const highlightedRef = useRef(new Set())

  const renderGraph = useCallback(() => {
    if (!svgRef.current || !data || !data.nodes || data.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight
    if (width === 0 || height === 0) return

    svg.selectAll('*').remove()

    const g = svg.append('g')

    const defs = svg.append('defs')
    const arrowTypes = [
      { id: 'arrow-prerequisite', color: '#ef4444' },
      { id: 'arrow-parallel', color: '#22c55e' },
      { id: 'arrow-contains', color: '#f59e0b' },
      { id: 'arrow-applies_to', color: '#8b5cf6' },
      { id: 'arrow-default', color: '#6b7280' }
    ]
    arrowTypes.forEach(({ id, color }) => {
      defs.append('marker')
        .attr('id', id)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 20)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', color)
    })

    const zoom = d3.zoom()
      .scaleExtent([0.1, 4])
      .on('zoom', (event) => {
        g.attr('transform', event.transform)
      })

    svg.call(zoom)

    svg.on('click', () => {
      setSelectedNode(null)
      highlightedRef.current = new Set()
      node.selectAll('circle')
        .attr('r', d => d.size || 8)
        .attr('stroke', 'none')
    })

    const nodeMap = new Map()
    data.nodes.forEach(n => nodeMap.set(n.id, n))

    const validLinks = data.links.filter(l =>
      nodeMap.has(typeof l.source === 'string' ? l.source : l.source.id) &&
      nodeMap.has(typeof l.target === 'string' ? l.target : l.target.id)
    ).map(l => ({
      ...l,
      source: typeof l.source === 'string' ? l.source : l.source.id,
      target: typeof l.target === 'string' ? l.target : l.target.id
    }))

    const relStyles = {
      prerequisite: { color: '#ef4444', dash: '5,5', width: 2 },
      parallel: { color: '#22c55e', dash: 'none', width: 1.5 },
      contains: { color: '#f59e0b', dash: '3,3', width: 2 },
      applies_to: { color: '#8b5cf6', dash: '8,4', width: 1.5 }
    }

    const linkG = g.append('g')
    const nodeG = g.append('g')

    const link = linkG.selectAll('line')
      .data(validLinks)
      .join('line')
      .attr('stroke', d => (relStyles[d.type] || relStyles.parallel).color)
      .attr('stroke-width', d => (relStyles[d.type] || relStyles.parallel).width)
      .attr('stroke-dasharray', d => (relStyles[d.type] || relStyles.parallel).dash)
      .attr('stroke-opacity', 0.7)
      .attr('marker-end', d => `url(#arrow-${d.type || 'default'})`)

    const node = nodeG.selectAll('g')
      .data(data.nodes)
      .join('g')
      .call(d3.drag()
        .on('start', (event, d) => {
          if (!event.active) simulationRef.current.alphaTarget(0.3).restart()
          d.fx = d.x
          d.fy = d.y
        })
        .on('drag', (event, d) => {
          d.fx = event.x
          d.fy = event.y
        })
        .on('end', (event, d) => {
          if (!event.active) simulationRef.current.alphaTarget(0)
          d.fx = null
          d.fy = null
        })
      )

    const nameCount = new Map()
    data.nodes.forEach(n => {
      const name = n.name || n.id
      nameCount.set(name, (nameCount.get(name) || 0) + 1)
    })

    node.append('circle')
      .attr('r', d => {
        const count = nameCount.get(d.name || d.id) || 1
        return Math.min(20, 4 + Math.log2(count + 1) * 5)
      })
      .attr('fill', d => d.color || '#6366f1')
      .attr('stroke', 'none')
      .attr('stroke-width', 2)
      .style('cursor', 'pointer')

    node.append('text')
      .text(d => d.name)
      .attr('dx', 14)
      .attr('dy', 4)
      .attr('font-size', '11px')
      .attr('fill', '#9ca3af')
      .style('pointer-events', 'none')

    node.on('click', (event, d) => {
      event.stopPropagation()
      onNodeSelect(d)
      setSelectedNode(d)
      const svgRect = svgRef.current.getBoundingClientRect()
      setPopupPos({
        x: Math.min(event.clientX - svgRect.left + 10, svgRect.width - 280),
        y: Math.min(event.clientY - svgRect.top - 10, svgRect.height - 200)
      })
      highlightedRef.current = new Set([d.id])
      node.selectAll('circle')
        .attr('r', nd => highlightedRef.current.has(nd.id) ? 14 : (nd.size || 8))
        .attr('stroke', nd => highlightedRef.current.has(nd.id) ? '#fff' : 'none')
    })

    node.append('title').text(d => `${d.name}\n${d.definition || ''}`)

    const simulation = d3.forceSimulation(data.nodes)
      .force('link', d3.forceLink(validLinks).id(d => d.id).distance(100))
      .force('charge', d3.forceManyBody().strength(-150))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .force('collision', d3.forceCollide().radius(25))

    simulationRef.current = simulation

    simulation.on('tick', () => {
      link
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y)
      node.attr('transform', d => `translate(${d.x},${d.y})`)
    })

    window._graphSearch = (term) => {
      if (!term) {
        highlightedRef.current = new Set()
        node.selectAll('circle').attr('r', d => d.size || 8).attr('stroke', 'none')
        return
      }
      const matches = new Set()
      data.nodes.forEach(n => {
        if (n.name.includes(term) || n.definition?.includes(term)) matches.add(n.id)
      })
      highlightedRef.current = matches
      node.selectAll('circle')
        .attr('r', d => matches.has(d.id) ? 14 : 6)
        .attr('stroke', d => matches.has(d.id) ? '#fbbf24' : 'none')
        .attr('stroke-width', 2)
    }

    window._graphFilter = (textbookName) => {
      if (!textbookName) {
        node.style('opacity', 1)
        link.style('opacity', 0.7)
        return
      }
      node.style('opacity', d => d.textbook_name === textbookName ? 1 : 0.15)
      link.style('opacity', d => {
        const src = typeof d.source === 'object' ? d.source : nodeMap.get(d.source)
        const tgt = typeof d.target === 'object' ? d.target : nodeMap.get(d.target)
        return (src?.textbook_name === textbookName || tgt?.textbook_name === textbookName) ? 0.7 : 0.05
      })
    }

    return () => simulation.stop()
  }, [data, onNodeSelect])

  // Render graph when viewMode changes to 'graph' or data changes
  useEffect(() => {
    if (viewMode === 'graph') {
      // Small delay to let the SVG mount and get dimensions
      const timer = setTimeout(renderGraph, 50)
      return () => clearTimeout(timer)
    }
  }, [viewMode, renderGraph])

  useEffect(() => {
    if (window._graphSearch) window._graphSearch(searchTerm)
  }, [searchTerm])

  // Matrix heatmap rendering
  useEffect(() => {
    if (viewMode !== 'matrix' || !data || !data.nodes || data.nodes.length === 0) return

    const renderMatrix = () => {
      if (!matrixSvgRef.current) return
      const containerWidth = matrixSvgRef.current.clientWidth || 900
      const containerHeight = matrixSvgRef.current.clientHeight || 600
      if (containerWidth === 0) return

      const svg = d3.select(matrixSvgRef.current)
      svg.selectAll('*').remove()

      const textbooks = [...new Set(data.nodes.map(n => n.textbook_name).filter(Boolean))]
      if (textbooks.length === 0) return

      const conceptFreq = new Map()
      data.nodes.forEach(n => {
        const name = n.name || n.id
        conceptFreq.set(name, (conceptFreq.get(name) || 0) + 1)
      })

      const topConcepts = [...conceptFreq.entries()]
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20)
        .map(([name]) => name)

      if (topConcepts.length === 0) return

      const matrix = []
      topConcepts.forEach((concept, yi) => {
        textbooks.forEach((textbook, xi) => {
          const present = data.nodes.some(n => (n.name || n.id) === concept && n.textbook_name === textbook)
          matrix.push({ xi, yi, value: present ? 1 : 0, concept, textbook })
        })
      })

      const margin = { top: 120, right: 30, bottom: 30, left: 150 }
      const plotWidth = containerWidth - margin.left - margin.right
      const plotHeight = containerHeight - margin.top - margin.bottom
      const cellWidth = plotWidth / textbooks.length
      const cellHeight = plotHeight / topConcepts.length

      const g = svg.append('g').attr('transform', `translate(${margin.left},${margin.top})`)

      const colorScale = d3.scaleSequential()
        .domain([0, 1])
        .interpolator(d3.interpolateBlues)

      g.selectAll('rect')
        .data(matrix)
        .join('rect')
        .attr('x', d => d.xi * cellWidth)
        .attr('y', d => d.yi * cellHeight)
        .attr('width', Math.max(cellWidth - 1, 1))
        .attr('height', Math.max(cellHeight - 1, 1))
        .attr('rx', 2)
        .attr('fill', d => d.value ? colorScale(0.85) : '#1a1a2e')
        .attr('stroke', '#2a2a3e')
        .attr('stroke-width', 0.5)
        .append('title')
        .text(d => `${d.concept} / ${d.textbook}: ${d.value ? '存在' : '不存在'}`)

      g.selectAll('.x-label')
        .data(textbooks)
        .join('text')
        .attr('class', 'x-label')
        .attr('x', (d, i) => i * cellWidth + cellWidth / 2)
        .attr('y', -8)
        .attr('text-anchor', 'start')
        .attr('font-size', '10px')
        .attr('fill', '#9ca3af')
        .attr('transform', (d, i) => `rotate(-45, ${i * cellWidth + cellWidth / 2}, -8)`)
        .text(d => d.length > 12 ? d.slice(0, 12) + '...' : d)

      g.selectAll('.y-label')
        .data(topConcepts)
        .join('text')
        .attr('class', 'y-label')
        .attr('x', -8)
        .attr('y', (d, i) => i * cellHeight + cellHeight / 2 + 4)
        .attr('text-anchor', 'end')
        .attr('font-size', '11px')
        .attr('fill', '#9ca3af')
        .text(d => d.length > 16 ? d.slice(0, 16) + '...' : d)

      svg.append('text')
        .attr('x', containerWidth / 2)
        .attr('y', 24)
        .attr('text-anchor', 'middle')
        .attr('font-size', '14px')
        .attr('font-weight', '600')
        .attr('fill', '#e5e7eb')
        .text('知识概念-教材 矩阵热力图')

      const legendG = svg.append('g').attr('transform', `translate(${margin.left}, 45)`)
      const legendData = [
        { label: '存在', color: colorScale(0.85) },
        { label: '不存在', color: '#1a1a2e' }
      ]
      legendData.forEach((item, i) => {
        legendG.append('rect')
          .attr('x', i * 100)
          .attr('y', 0)
          .attr('width', 14)
          .attr('height', 14)
          .attr('rx', 2)
          .attr('fill', item.color)
          .attr('stroke', '#2a2a3e')
        legendG.append('text')
          .attr('x', i * 100 + 20)
          .attr('y', 11)
          .attr('font-size', '11px')
          .attr('fill', '#9ca3af')
          .text(item.label)
      })
    }

    // Delay to let SVG mount and get dimensions
    const timer = setTimeout(renderMatrix, 50)
    return () => clearTimeout(timer)
  }, [viewMode, data])

  const textbookNames = [...new Set(data.nodes.map(n => n.textbook_name).filter(Boolean))]

  return (
    <div className="graph-container">
      <div className="search-box">
        <input
          type="text"
          placeholder="搜索知识点..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        {textbookNames.length > 1 && (
          <select
            value={filterTextbook}
            onChange={(e) => {
              setFilterTextbook(e.target.value)
              if (window._graphFilter) window._graphFilter(e.target.value)
            }}
            style={{ marginLeft: '8px', padding: '4px 8px', borderRadius: '4px', background: 'var(--bg-tertiary)', color: 'var(--text-primary)', border: '1px solid var(--border)', fontSize: '12px' }}
          >
            <option value="">全部教材</option>
            {textbookNames.map(name => (
              <option key={name} value={name}>{name}</option>
            ))}
          </select>
        )}
        <button
          onClick={() => {
            setSelectedNode(null)
            setViewMode(viewMode === 'graph' ? 'matrix' : 'graph')
          }}
          style={{
            marginLeft: '8px',
            padding: '4px 10px',
            borderRadius: '4px',
            background: viewMode === 'matrix' ? 'var(--accent-primary, #6366f1)' : 'var(--bg-tertiary)',
            color: viewMode === 'matrix' ? '#fff' : 'var(--text-primary)',
            border: '1px solid var(--border)',
            fontSize: '12px',
            cursor: 'pointer',
            whiteSpace: 'nowrap'
          }}
        >
          {viewMode === 'graph' ? '矩阵热力图' : '图谱视图'}
        </button>
      </div>

      {viewMode === 'graph' ? (
        <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>
      ) : (
        <svg ref={matrixSvgRef} style={{ width: '100%', height: '100%' }}></svg>
      )}

      {selectedNode && viewMode === 'graph' && (
        <div
          className="node-popup"
          style={{
            position: 'absolute',
            left: popupPos.x,
            top: popupPos.y,
            zIndex: 100,
            background: 'var(--bg-secondary, #1e1e2e)',
            border: '1px solid var(--border, #3a3a4e)',
            borderRadius: '10px',
            padding: '14px 16px',
            maxWidth: '280px',
            boxShadow: '0 8px 24px rgba(0,0,0,0.4)',
            pointerEvents: 'auto'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
            <h4 style={{ margin: 0, fontSize: '14px', color: '#e5e7eb' }}>{selectedNode.name}</h4>
            <button
              onClick={() => setSelectedNode(null)}
              style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '16px', padding: '0 4px' }}
            >×</button>
          </div>
          <span style={{
            display: 'inline-block',
            padding: '2px 8px',
            borderRadius: '4px',
            background: 'var(--accent-primary, #6366f1)',
            color: '#fff',
            fontSize: '11px',
            marginBottom: '8px'
          }}>{selectedNode.category}</span>
          {selectedNode.definition && (
            <p style={{ margin: '8px 0', fontSize: '12px', color: '#d1d5db', lineHeight: '1.5' }}>
              {selectedNode.definition}
            </p>
          )}
          <div style={{ fontSize: '11px', color: '#9ca3af', borderTop: '1px solid var(--border, #3a3a4e)', paddingTop: '8px', marginTop: '4px' }}>
            <div>教材：{selectedNode.textbook_name}</div>
            <div>章节：{selectedNode.chapter}</div>
            {selectedNode.confidence && <div>置信度：{(selectedNode.confidence * 100).toFixed(0)}%</div>}
          </div>
        </div>
      )}

      {viewMode === 'graph' && data.nodes.length > 0 && (
        <div className="graph-legend">
          <div style={{ fontWeight: 600, marginBottom: '8px', fontSize: '12px' }}>图例</div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#ef4444' }}></div>
            <span>前置依赖</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#22c55e' }}></div>
            <span>并列关系</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#f59e0b' }}></div>
            <span>包含关系</span>
          </div>
          <div className="legend-item">
            <div className="legend-color" style={{ background: '#8b5cf6' }}></div>
            <span>应用场景</span>
          </div>
          <div style={{ marginTop: '8px', borderTop: '1px solid var(--border)', paddingTop: '8px' }}>
            <div style={{ fontWeight: 600, marginBottom: '4px', fontSize: '11px' }}>教材</div>
            {[...new Set(data.nodes.map(n => n.textbook_name))].slice(0, 7).map((name, i) => {
              const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#ec4899', '14b8a6', '#8b5cf6']
              return (
                <div key={i} className="legend-item">
                  <div className="legend-color" style={{ background: colors[i % colors.length] }}></div>
                  <span>{name}</span>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {data.nodes.length === 0 && (
        <div className="empty-state">
          <div className="icon">🔗</div>
          <p>上传教材并构建知识图谱</p>
          <p style={{ fontSize: '12px', marginTop: '8px', color: 'var(--text-secondary)' }}>
            支持 PDF / Markdown / TXT 格式
          </p>
        </div>
      )}
    </div>
  )
}
