"""
生成知识成果导出文件：
- 7 份单本教材 Markdown 报告
- 1 份整合报告 Markdown
- 9 个可交互 HTML 知识图谱

用法：cd backend && python generate_reports.py
"""
import json
import os
import sys
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

OUTPUT_DIR = Path(__file__).parent.parent / "output"
REPORT_DIR = OUTPUT_DIR / "报告"
GRAPH_HTML_DIR = OUTPUT_DIR / "图谱"
DATA_DIR = Path(__file__).parent / "data"
PARSED_DIR = DATA_DIR / "parsed"
GRAPH_DIR = DATA_DIR / "graphs"
INTEGRATION_FILE = DATA_DIR / "integration" / "integration_result.json"

REPORT_DIR.mkdir(parents=True, exist_ok=True)
GRAPH_HTML_DIR.mkdir(parents=True, exist_ok=True)


def build_tree(nodes: list[dict], relations: list[dict]) -> list[dict]:
    """Build a tree structure from nodes using contains relations"""
    node_map = {n["id"]: n for n in nodes}
    children_map = {}  # parent_id -> [child_ids]
    child_ids_set = set()

    for r in relations:
        if r["relation_type"] == "contains":
            parent = r["source"]
            child = r["target"]
            if parent in node_map and child in node_map:
                children_map.setdefault(parent, []).append(child)
                child_ids_set.add(child)

    # Root nodes are those that are not children of any contains relation
    roots = [n for n in nodes if n["id"] not in child_ids_set]

    def build_subtree(node_id, depth=0, visited=None):
        if visited is None:
            visited = set()
        if node_id in visited or depth > 20:
            return None
        visited.add(node_id)
        node = node_map[node_id]
        result = {
            "id": node_id,
            "name": node["name"],
            "category": node.get("category", ""),
            "definition": node.get("definition", ""),
            "chapter": node.get("chapter", ""),
            "confidence": node.get("confidence", 0),
            "depth": depth,
            "children": []
        }
        for child_id in children_map.get(node_id, []):
            child = build_subtree(child_id, depth + 1, visited)
            if child:
                result["children"].append(child)
        return result

    tree = [t for n in roots if (t := build_subtree(n["id"])) is not None]
    return tree


def render_tree(tree: list[dict], indent: int = 0) -> str:
    """Render tree as text with box-drawing characters"""
    lines = []
    for i, node in enumerate(tree):
        is_last = (i == len(tree) - 1)
        prefix = "    " * indent
        if indent > 0:
            prefix = "    " * (indent - 1) + ("└── " if is_last else "├── ")

        conf = f"{node['confidence']*100:.0f}%" if node['confidence'] else ""
        defn = node['definition'][:60] + "..." if len(node['definition']) > 60 else node['definition']
        line = f"{prefix}**{node['name']}** [{node['category']}] — {defn}"
        if node['chapter']:
            line += f"（{node['chapter']}"
            if conf:
                line += f"，置信度 {conf}"
            line += "）"
        lines.append(line)

        if node['children']:
            lines.extend(render_tree(node['children'], indent + 1))
    return "\n".join(lines)


def generate_single_report(textbook_id: str):
    """Generate a single textbook report"""
    # Load graph
    graph_path = GRAPH_DIR / f"{textbook_id}_graph.json"
    if not graph_path.exists():
        print(f"  [SKIP] 未找到图谱：{textbook_id}")
        return

    with open(graph_path, 'r', encoding='utf-8') as f:
        graph = json.load(f)

    # Load parsed textbook for chapter info
    parsed_path = PARSED_DIR / f"{textbook_id}.json"
    total_chapters = 0
    if parsed_path.exists():
        with open(parsed_path, 'r', encoding='utf-8') as f:
            tb = json.load(f)
            total_chapters = len(tb["chapters"])

    nodes = graph["nodes"]
    relations = graph["relations"]
    stats = graph.get("stats", {})
    textbook_name = graph.get("textbook_name", textbook_id)

    # Count chapters covered
    chapters_covered = set()
    for n in nodes:
        ch = n.get("chapter", "")
        if ch:
            chapters_covered.add(ch)

    processed = stats.get("chapters_processed", len(chapters_covered))
    coverage = (processed / total_chapters * 100) if total_chapters > 0 else 0

    # Build tree
    tree = build_tree(nodes, relations)
    tree_text = render_tree(tree)

    # Group relations by type
    rel_by_type = {}
    for r in relations:
        t = r["relation_type"]
        rel_by_type.setdefault(t, []).append(r)

    # Build chapter coverage table
    chapter_stats = {}
    for n in nodes:
        ch = n.get("chapter", "未知")
        chapter_stats[ch] = chapter_stats.get(ch, 0) + 1

    # Generate report
    report = f"""# 《{textbook_name}》知识图谱报告

## 概览

| 指标 | 数值 |
|------|------|
| 教材名称 | {textbook_name} |
| 总章节数 | {total_chapters} |
| 已提取章节 | {processed} |
| 覆盖率 | {coverage:.1f}% |
| 知识点数 | {len(nodes)} |
| 关系数 | {len(relations)} |

## 知识点体系

{tree_text if tree_text else "暂无知识点数据"}

## 关系网络

"""

    type_names = {
        "prerequisite": "前置依赖",
        "parallel": "并列关系",
        "contains": "包含关系",
        "applies_to": "应用场景"
    }

    for rel_type, name in type_names.items():
        rels = rel_by_type.get(rel_type, [])
        if not rels:
            continue
        report += f"### {name}（{len(rels)} 条）\n\n"
        report += "| 源知识点 | 目标知识点 | 描述 |\n"
        report += "|----------|------------|------|\n"
        node_map = {n["id"]: n["name"] for n in nodes}
        for r in rels[:30]:  # Limit to 30 per type
            src = node_map.get(r["source"], r["source"])
            tgt = node_map.get(r["target"], r["target"])
            desc = r.get("description", "")
            report += f"| {src} | {tgt} | {desc} |\n"
        report += "\n"

    # Chapter coverage
    report += "## 章节覆盖分析\n\n"
    report += "| 章节 | 知识点数 |\n"
    report += "|------|----------|\n"
    for ch, count in sorted(chapter_stats.items(), key=lambda x: -x[1])[:50]:
        report += f"| {ch} | {count} |\n"

    # Write report
    output_path = REPORT_DIR / f"{textbook_name}_知识图谱报告.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  ✅ 报告已生成：{output_path.name}")


def generate_integration_report():
    """Generate the integration report"""
    if not INTEGRATION_FILE.exists():
        print("  [SKIP] 未找到整合结果")
        return

    with open(INTEGRATION_FILE, 'r', encoding='utf-8') as f:
        integ = json.load(f)

    nodes = integ["merged_nodes"]
    decisions = integ["decisions"]
    conflicts = integ["conflicts"]
    stats = integ["stats"]

    # Count textbooks
    textbooks = set()
    for n in nodes:
        tb = n.get("textbook_name", "")
        if tb:
            textbooks.add(tb)

    merge_count = sum(1 for d in decisions if d["action"] == "merge")
    keep_count = sum(1 for d in decisions if d["action"] == "keep")
    remove_count = sum(1 for d in decisions if d["action"] == "remove")

    report = f"""# 跨教材知识整合报告

## 整合概览

| 指标 | 数值 |
|------|------|
| 教材数量 | {len(textbooks)} 本 |
| 原始知识点总数 | {stats.get('original', 'N/A')} |
| 整合后知识点数 | {len(nodes)} |
| 压缩比 | {stats.get('compression_ratio', 0):.1%} |
| 整合决策数 | {len(decisions)} |
| 冲突检测数 | {len(conflicts)} |

## 整合决策摘要

| 决策类型 | 数量 |
|----------|------|
| 合并 | {merge_count} |
| 保留 | {keep_count} |
| 删除 | {remove_count} |

## 冲突检测（{len(conflicts)} 个）

以下概念在不同教材中有不同的定义表述：

"""

    for i, c in enumerate(conflicts):
        report += f"### 冲突 {i+1}：{c['concept']}\n\n"
        report += "| 教材 | 定义 |\n"
        report += "|------|------|\n"
        for s in c.get("sources", []):
            report += f"| {s['textbook']} | {s['definition']} |\n"
        report += f"\n**冲突类型**：{c.get('type', '定义差异')}\n\n"

    # Merge decisions
    report += "## 合并决策（{} 个）\n\n".format(merge_count)
    report += "| 决策ID | 涉及节点 | 理由 | 置信度 |\n"
    report += "|--------|----------|------|--------|\n"

    node_map = {n["id"]: n["name"] for n in nodes}
    for d in decisions:
        if d["action"] != "merge":
            continue
        affected = ", ".join(node_map.get(a, a) for a in d.get("affected_nodes", []))
        reason = d.get("reason", "")[:60]
        conf = f"{d.get('confidence', 0):.0%}"
        report += f"| {d['decision_id']} | {affected} | {reason} | {conf} |\n"

    # Keep decisions
    report += "\n## 保留决策（{} 个）\n\n".format(keep_count)
    report += "| 决策ID | 涉及节点 | 理由 | 置信度 |\n"
    report += "|--------|----------|------|--------|\n"
    for d in decisions:
        if d["action"] != "keep":
            continue
        affected = ", ".join(node_map.get(a, a) for a in d.get("affected_nodes", []))
        reason = d.get("reason", "")[:60]
        conf = f"{d.get('confidence', 0):.0%}"
        report += f"| {d['decision_id']} | {affected} | {reason} | {conf} |\n"

    # Cross-textbook concept table
    report += "\n## 跨教材概念对照表\n\n"
    tb_names = sorted(textbooks)

    # Find concepts that appear in multiple textbooks
    concept_books = {}
    for n in nodes:
        name = n.get("name", "")
        tb = n.get("textbook_name", "")
        if name and tb:
            concept_books.setdefault(name, set()).add(tb)

    multi_concepts = {name: books for name, books in concept_books.items() if len(books) > 1}

    if multi_concepts:
        report += "| 概念 |" + "|".join(tb_names) + "|\n"
        report += "|------|" + "|".join(["---"] * len(tb_names)) + "|\n"
        for name, books in sorted(multi_concepts.items(), key=lambda x: -len(x[1])):
            row = f"| {name} |"
            for tb in tb_names:
                row += " ✅ |" if tb in books else " - |"
            report += row + "\n"

    # Write report
    output_path = REPORT_DIR / "跨教材整合报告.md"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)
    print(f"  ✅ 整合报告已生成：{output_path.name}")


# HTML template for standalone knowledge graph
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; overflow: hidden; }}
#graph {{ width: 100vw; height: 100vh; }}
.node-label {{ font-size: 11px; fill: #8b949e; pointer-events: none; }}
.link {{ stroke-opacity: 0.5; }}
.tooltip {{
  position: absolute; display: none; background: #161b22; border: 1px solid #30363d;
  border-radius: 8px; padding: 12px 16px; max-width: 320px; font-size: 13px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4); z-index: 100;
}}
.tooltip h4 {{ color: #e6edf3; margin-bottom: 6px; font-size: 14px; }}
.tooltip .def {{ color: #c9d1d9; line-height: 1.5; margin: 6px 0; }}
.tooltip .meta {{ color: #8b949e; font-size: 11px; border-top: 1px solid #30363d; padding-top: 6px; margin-top: 6px; }}
.tag {{ display: inline-block; padding: 1px 6px; border-radius: 3px; font-size: 10px; color: #fff; margin-right: 4px; }}
.legend {{ position: absolute; top: 16px; right: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px; font-size: 12px; }}
.legend-item {{ display: flex; align-items: center; gap: 6px; margin: 3px 0; }}
.legend-color {{ width: 12px; height: 12px; border-radius: 3px; }}
h1 {{ position: absolute; top: 16px; left: 16px; font-size: 16px; color: #e6edf3; background: #161b22; padding: 8px 16px; border-radius: 8px; border: 1px solid #30363d; }}
.stats {{ position: absolute; bottom: 16px; left: 16px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 10px 14px; font-size: 12px; color: #8b949e; }}
</style>
</head>
<body>
<h1>{title}</h1>
<div class="tooltip" id="tooltip"></div>
<svg id="graph"></svg>
<div class="legend" id="legend"></div>
<div class="stats" id="stats"></div>
<script src="https://d3js.org/d3.v7.min.js"></script>
<script>
const data = {data_json};

const svg = d3.select("#graph");
const width = window.innerWidth;
const height = window.innerHeight;
svg.attr("width", width).attr("height", height);

const g = svg.append("g");
const zoom = d3.zoom().scaleExtent([0.1, 4]).on("zoom", e => g.attr("transform", e.transform));
svg.call(zoom);

const defs = svg.append("defs");
["#ef4444","#22c55e","#f59e0b","#8b5cf6","#6b7280"].forEach((c, i) => {{
  const types = ["prerequisite","parallel","contains","applies_to","default"];
  defs.append("marker").attr("id","arrow-"+types[i]).attr("viewBox","0 -5 10 10")
    .attr("refX",20).attr("refY",0).attr("markerWidth",6).attr("markerHeight",6)
    .attr("orient","auto").append("path").attr("d","M0,-5L10,0L0,5").attr("fill",c);
}});

const nodeMap = new Map(data.nodes.map(n => [n.id, n]));
const validLinks = data.links.filter(l => nodeMap.has(l.source) && nodeMap.has(l.target));
const relColors = {{ prerequisite:"#ef4444", parallel:"#22c55e", contains:"#f59e0b", applies_to:"#8b5cf6" }};

const link = g.append("g").selectAll("line").data(validLinks).join("line")
  .attr("stroke", d => relColors[d.type] || "#6b7280")
  .attr("stroke-width", d => d.type === "contains" ? 2 : 1.5)
  .attr("stroke-dasharray", d => d.type === "prerequisite" ? "5,5" : d.type === "contains" ? "3,3" : "none")
  .attr("stroke-opacity", 0.6)
  .attr("marker-end", d => "url(#arrow-" + (d.type || "default") + ")");

const categories = [...new Set(data.nodes.map(n => n.category).filter(Boolean))];
const catColor = d3.scaleOrdinal().domain(categories).range(["#6366f1","#22c55e","#f59e0b","#ef4444","#ec4899","#14b8a6","#8b5cf6","#f97316"]);

const node = g.append("g").selectAll("g").data(data.nodes).join("g")
  .call(d3.drag().on("start",(e,d)=>{{if(!e.active)sim.alphaTarget(0.3).restart();d.fx=d.x;d.fy=d.y;}})
  .on("drag",(e,d)=>{{d.fx=e.x;d.fy=e.y;}}).on("end",(e,d)=>{{if(!e.active)sim.alphaTarget(0);d.fx=null;d.fy=null;}}));

node.append("circle")
  .attr("r", d => d.size || 8)
  .attr("fill", d => d.color || catColor(d.category))
  .attr("stroke", "none").attr("stroke-width", 2).style("cursor", "pointer");

node.append("text").text(d => d.name)
  .attr("dx", 14).attr("dy", 4).attr("font-size", "11px").attr("fill", "#8b949e")
  .style("pointer-events", "none");

const tooltip = d3.select("#tooltip");
node.on("click", (e, d) => {{
  e.stopPropagation();
  tooltip.style("display", "block")
    .style("left", Math.min(e.clientX + 10, width - 340) + "px")
    .style("top", Math.min(e.clientY - 10, height - 200) + "px")
    .html("<h4>" + d.name + "</h4>"
      + (d.category ? '<span class="tag" style="background:' + catColor(d.category) + '">' + d.category + "</span>" : "")
      + (d.definition ? '<p class="def">' + d.definition + "</p>" : "")
      + '<div class="meta">' + (d.textbook ? "教材：" + d.textbook + "<br>" : "")
      + (d.chapter ? "章节：" + d.chapter + "<br>" : "")
      + (d.confidence ? "置信度：" + Math.round(d.confidence*100) + "%" : "") + "</div>");
}});

svg.on("click", () => tooltip.style("display", "none"));

const sim = d3.forceSimulation(data.nodes)
  .force("link", d3.forceLink(validLinks).id(d => d.id).distance(120))
  .force("charge", d3.forceManyBody().strength(-200))
  .force("center", d3.forceCenter(width/2, height/2))
  .force("collision", d3.forceCollide().radius(30));

sim.on("tick", () => {{
  link.attr("x1",d=>d.source.x).attr("y1",d=>d.source.y).attr("x2",d=>d.target.x).attr("y2",d=>d.target.y);
  node.attr("transform", d => "translate("+d.x+","+d.y+")");
}});

// Legend
const legendDiv = d3.select("#legend");
categories.forEach(c => {{
  legendDiv.append("div").attr("class","legend-item")
    .html('<div class="legend-color" style="background:'+catColor(c)+'"></div><span>'+c+'</span>');
}});

// Stats
d3.select("#stats").html("节点：" + data.nodes.length + " | 关系：" + validLinks.length);
</script>
</body>
</html>"""


def generate_html_graph(graph_data: dict, title: str, filename: str, is_integration: bool = False):
    """Generate a standalone HTML knowledge graph file"""
    nodes = graph_data.get("nodes", [])
    relations = graph_data.get("relations", [])

    # Build node data
    cat_colors = {
        "核心概念": "#6366f1", "生理机制": "#22c55e", "病理变化": "#f59e0b",
        "临床表现": "#ef4444", "治疗方法": "#ec4899", "解剖结构": "#14b8a6",
        "微生物": "#8b5cf6"
    }

    html_nodes = []
    for n in nodes:
        html_nodes.append({
            "id": n["id"],
            "name": n.get("name", ""),
            "category": n.get("category", ""),
            "definition": n.get("definition", ""),
            "chapter": n.get("chapter", ""),
            "textbook": n.get("textbook_name", ""),
            "confidence": n.get("confidence", 0),
            "color": cat_colors.get(n.get("category", ""), "#6b7280"),
            "size": 8
        })

    html_links = []
    for r in relations:
        html_links.append({
            "source": r["source"],
            "target": r["target"],
            "type": r.get("relation_type", ""),
            "description": r.get("description", "")
        })

    data_json = json.dumps({"nodes": html_nodes, "links": html_links}, ensure_ascii=False)
    html = HTML_TEMPLATE.format(title=title, data_json=data_json)

    output_path = GRAPH_HTML_DIR / filename
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✅ 图谱已生成：{filename}")


def generate_all():
    """Generate all reports and HTML graphs"""
    print("=" * 60)
    print("开始生成知识成果导出文件")
    print("=" * 60)

    # 1. Single textbook reports + HTML graphs
    print("\n📊 生成单本教材报告...")
    parsed_files = sorted(PARSED_DIR.glob("*.json"))
    for f in parsed_files:
        with open(f, 'r', encoding='utf-8') as fh:
            tb = json.load(fh)
        tid = tb["textbook_id"]
        tname = tb["title"]

        # Report
        generate_single_report(tid)

        # HTML graph
        graph_path = GRAPH_DIR / f"{tid}_graph.json"
        if graph_path.exists():
            with open(graph_path, 'r', encoding='utf-8') as gh:
                graph = json.load(gh)
            generate_html_graph(graph, f"《{tname}》知识图谱", f"{tname}.html")

    # 2. Integration report
    print("\n📊 生成整合报告...")
    generate_integration_report()

    # 3. Integration HTML graph
    print("\n📊 生成整合图谱...")
    if INTEGRATION_FILE.exists():
        with open(INTEGRATION_FILE, 'r', encoding='utf-8') as f:
            integ = json.load(f)
        generate_html_graph(
            {"nodes": integ["merged_nodes"], "relations": []},
            "跨教材知识整合图谱",
            "整合图谱.html",
            is_integration=True
        )

    # 4. Overview page
    print("\n📊 生成总览页面...")
    generate_overview()

    print("\n" + "=" * 60)
    print("全部完成！文件输出到：")
    print(f"  报告：{REPORT_DIR}")
    print(f"  图谱：{GRAPH_HTML_DIR}")
    print("=" * 60)


def generate_overview():
    """Generate an overview HTML page"""
    # Gather stats from all graphs
    graph_stats = []
    for f in sorted(GRAPH_DIR.glob("*_graph.json")):
        with open(f, 'r', encoding='utf-8') as fh:
            g = json.load(fh)
        graph_stats.append({
            "name": g.get("textbook_name", f.stem),
            "nodes": len(g.get("nodes", [])),
            "relations": len(g.get("relations", [])),
            "chapters": g.get("stats", {}).get("chapters_processed", 0),
            "total_chapters": g.get("stats", {}).get("chapters_total", 0)
        })

    # Integration stats
    integ_stats = {}
    if INTEGRATION_FILE.exists():
        with open(INTEGRATION_FILE, 'r', encoding='utf-8') as f:
            integ = json.load(f)
        integ_stats = {
            "nodes": len(integ.get("merged_nodes", [])),
            "decisions": len(integ.get("decisions", [])),
            "conflicts": len(integ.get("conflicts", []))
        }

    cards_html = ""
    for g in graph_stats:
        coverage = (g["chapters"] / g["total_chapters"] * 100) if g["total_chapters"] > 0 else 0
        cards_html += f"""
        <div class="card">
          <h3>{g['name']}</h3>
          <div class="stat-row"><span>知识点</span><strong>{g['nodes']}</strong></div>
          <div class="stat-row"><span>关系</span><strong>{g['relations']}</strong></div>
          <div class="stat-row"><span>章节覆盖</span><strong>{g['chapters']}/{g['total_chapters']} ({coverage:.0f}%)</strong></div>
          <a href="图谱/{g['name']}.html" target="_blank">查看图谱 →</a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>知识整合成果总览</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ background: #0d1117; color: #c9d1d9; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 40px; }}
h1 {{ color: #e6edf3; font-size: 24px; margin-bottom: 8px; }}
.subtitle {{ color: #8b949e; margin-bottom: 32px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; }}
.card h3 {{ color: #e6edf3; margin-bottom: 12px; font-size: 16px; }}
.stat-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 13px; }}
.stat-row span {{ color: #8b949e; }}
.stat-row strong {{ color: #e6edf3; }}
.card a {{ display: inline-block; margin-top: 12px; color: #58a6ff; text-decoration: none; font-size: 13px; }}
.card a:hover {{ text-decoration: underline; }}
.section {{ margin-top: 40px; }}
.section h2 {{ color: #e6edf3; font-size: 18px; margin-bottom: 16px; }}
.integ-card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 20px; max-width: 400px; }}
</style>
</head>
<body>
<h1>📚 学科知识整合智能体 — 成果总览</h1>
<p class="subtitle">7 本医学教材的知识图谱构建与跨教材整合</p>

<div class="section">
<h2>单本教材知识图谱</h2>
<div class="grid">{cards_html}</div>
</div>

<div class="section">
<h2>跨教材整合</h2>
<div class="integ-card">
  <div class="stat-row"><span>整合后知识点</span><strong>{integ_stats.get('nodes', 'N/A')}</strong></div>
  <div class="stat-row"><span>整合决策</span><strong>{integ_stats.get('decisions', 'N/A')}</strong></div>
  <div class="stat-row"><span>检测到冲突</span><strong>{integ_stats.get('conflicts', 'N/A')}</strong></div>
  <a href="图谱/整合图谱.html" target="_blank">查看整合图谱 →</a>
</div>
</div>

<div class="section">
<h2>报告文档</h2>
<ul style="list-style: none;">
  {"".join(f'<li style="margin:4px 0"><a href="报告/{g["name"]}_知识图谱报告.md" style="color:#58a6ff;text-decoration:none">{g["name"]} 知识图谱报告</a></li>' for g in graph_stats)}
  <li style="margin:4px 0"><a href="报告/跨教材整合报告.md" style="color:#58a6ff;text-decoration:none">跨教材整合报告</a></li>
</ul>
</div>
</body>
</html>"""

    output_path = OUTPUT_DIR / "总览.html"
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  ✅ 总览页面已生成：总览.html")


if __name__ == "__main__":
    generate_all()
