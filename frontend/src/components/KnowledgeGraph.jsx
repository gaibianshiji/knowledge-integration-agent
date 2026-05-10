import React, { useEffect, useRef, useState } from 'react'
import * as d3 from 'd3'

export default function KnowledgeGraph({ data, onNodeSelect, integrationResult }) {
  const svgRef = useRef(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [filterTextbook, setFilterTextbook] = useState('')
  const simulationRef = useRef(null)
  const highlightedRef = useRef(new Set())

  useEffect(() => {
    if (!data || !data.nodes || data.nodes.length === 0) return

    const svg = d3.select(svgRef.current)
    const width = svgRef.current.clientWidth
    const height = svgRef.current.clientHeight

    svg.selectAll('*').remove()

    const g = svg.append('g')

    // Add arrow markers for each relationship type
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

    // Relationship type styles
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
      .attr('stroke', d => {
        const style = relStyles[d.type] || relStyles.parallel
        return style.color
      })
      .attr('stroke-width', d => {
        const style = relStyles[d.type] || relStyles.parallel
        return style.width
      })
      .attr('stroke-dasharray', d => {
        const style = relStyles[d.type] || relStyles.parallel
        return style.dash
      })
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

    // Calculate node frequency (how many textbooks it appears in)
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
      // Update highlight without re-rendering
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
        node.selectAll('circle')
          .attr('r', d => d.size || 8)
          .attr('stroke', 'none')
        return
      }

      const matches = new Set()
      data.nodes.forEach(n => {
        if (n.name.includes(term) || n.definition?.includes(term)) {
          matches.add(n.id)
        }
      })
      highlightedRef.current = matches

      node.selectAll('circle')
        .attr('r', d => matches.has(d.id) ? 14 : 6)
        .attr('stroke', d => matches.has(d.id) ? '#fbbf24' : 'none')
        .attr('stroke-width', 2)
    }

    window._graphFilter = (textbookName) => {
      if (!textbookName) {
        // Show all nodes and links
        node.style('opacity', 1)
        link.style('opacity', 0.7)
        return
      }
      // Dim nodes not from selected textbook
      node.style('opacity', d => d.textbook_name === textbookName ? 1 : 0.15)
      link.style('opacity', d => {
        const src = typeof d.source === 'object' ? d.source : nodeMap.get(d.source)
        const tgt = typeof d.target === 'object' ? d.target : nodeMap.get(d.target)
        return (src?.textbook_name === textbookName || tgt?.textbook_name === textbookName) ? 0.7 : 0.05
      })
    }

    return () => {
      simulation.stop()
    }
  }, [data])

  useEffect(() => {
    if (window._graphSearch) window._graphSearch(searchTerm)
  }, [searchTerm])

  // Get unique textbook names for filter
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
      </div>

      <svg ref={svgRef} style={{ width: '100%', height: '100%' }}></svg>

      {data.nodes.length > 0 && (
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
              const colors = ['#6366f1', '#22c55e', '#f59e0b', '#ef4444', '#ec4899', '#14b8a6', '#8b5cf6']
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
