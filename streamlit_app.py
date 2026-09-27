"""
Bob the Onboarder — Streamlit demo

Deploy this file from the repository root on Streamlit Community Cloud.

The app reuses the project's existing deterministic analysis pipeline instead
of starting the FastAPI/React services.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any

import networkx as nx
import streamlit as st

# The repository's Python package lives under ./backend.
ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.core.graph_store import graph_store
from app.models.graph import NodeType
from app.models.repo import IngestRequest
from app.services.analysis_orchestrator import run_analysis
from app.services.graph_builder import build_graph
from app.services.graph_serializer import graph_to_architecture
from app.services.repo_service import clone_repo, register_repo
from app.api.query import get_summary as _get_summary
from app.api.query import get_impact as _get_impact
from app.api.query import get_paths as _get_paths
from app.api.analysis import _facts_store


st.set_page_config(
    page_title="Bob the Onboarder",
    page_icon="🧭",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container { padding-top: 2rem; }
    div[data-testid="stMetric"] { border: 1px solid #e5e7eb; border-radius: 8px; padding: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def analyze_repository(repo_url: str, branch: str) -> dict[str, Any]:
    """Clone and analyze a public Git repository once per URL/branch."""
    request = IngestRequest(url=repo_url, branch=branch)
    repo = register_repo(request)

    clone_repo(repo)
    if repo.status.value == "error":
        raise RuntimeError(repo.error or "Repository clone failed.")

    repo_path = Path(repo.local_path or "")
    if not repo_path.exists():
        raise RuntimeError("The repository was cloned but its local path is missing.")

    facts = run_analysis(repo.repo_id, repo_path)
    _facts_store[repo.repo_id] = facts

    graph = build_graph(facts)
    architecture = graph_to_architecture(
        repo.repo_id,
        graph,
        built_at=facts.analysed_at or "",
    )
    graph_store.set_graph(repo.repo_id, architecture)

    return {
        "repo_id": repo.repo_id,
        "name": repo.name,
        "url": repo.url,
        "branch": repo.branch,
        "facts": facts,
        "graph": architecture,
        "repo_path": str(repo_path),
    }


def graph_to_networkx(architecture: Any) -> nx.DiGraph:
    """Convert the project's ArchitectureGraph into a NetworkX graph."""
    g = nx.DiGraph()

    for node in architecture.nodes:
        g.add_node(
            node.id,
            label=node.label,
            type=node.type.value if hasattr(node.type, "value") else str(node.type),
            file=node.file or "",
        )

    for edge in architecture.edges:
        g.add_edge(
            edge.source,
            edge.target,
            label=edge.type.value if hasattr(edge.type, "value") else str(edge.type),
            confidence=edge.confidence,
        )

    return g


def render_graph(architecture: Any, max_nodes: int = 100) -> None:
    """Render a readable architecture graph using Streamlit's native charting."""
    nodes = architecture.nodes
    edges = architecture.edges

    if len(nodes) > max_nodes:
        st.warning(
            f"This repository has {len(nodes)} graph nodes. "
            f"Showing the first {max_nodes} nodes to keep the browser responsive."
        )
        visible_ids = {n.id for n in nodes[:max_nodes]}
        nodes = nodes[:max_nodes]
        edges = [
            e for e in edges
            if e.source in visible_ids and e.target in visible_ids
        ]

    g = nx.DiGraph()
    for node in nodes:
        g.add_node(node.id, label=node.label)

    for edge in edges:
        g.add_edge(edge.source, edge.target)

    if not g.nodes:
        st.info("No graph nodes were produced.")
        return

    # NetworkX layout → Plotly scatter graph.
    import plotly.graph_objects as go

    pos = nx.spring_layout(g, seed=42, k=1.2)

    edge_x: list[float | None] = []
    edge_y: list[float | None] = []
    for source, target in g.edges():
        x0, y0 = pos[source]
        x1, y1 = pos[target]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    node_x = [pos[n][0] for n in g.nodes]
    node_y = [pos[n][1] for n in g.nodes]
    labels = [g.nodes[n]["label"] for n in g.nodes]

    edge_trace = go.Scatter(
        x=edge_x,
        y=edge_y,
        mode="lines",
        hoverinfo="none",
        line={"width": 0.7},
    )

    node_trace = go.Scatter(
        x=node_x,
        y=node_y,
        mode="markers+text",
        text=labels,
        textposition="top center",
        hovertext=[
            f"{g.nodes[n]['label']}<br>{n}"
            for n in g.nodes
        ],
        hoverinfo="text",
        marker={
            "size": 14,
            "line": {"width": 1},
        },
    )

    fig = go.Figure(data=[edge_trace, node_trace])
    fig.update_layout(
        height=700,
        margin={"l": 10, "r": 10, "t": 10, "b": 10},
        showlegend=False,
        xaxis={"visible": False},
        yaxis={"visible": False},
        hovermode="closest",
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True})


def node_options(architecture: Any) -> list[str]:
    return sorted(
        {
            node.label
            for node in architecture.nodes
            if node.label
        }
    )


st.title("🧭 Bob the Onboarder")
st.caption(
    "Repository intelligence: ingest a Git repository, analyze its architecture, "
    "explore dependencies, and inspect change impact."
)

with st.sidebar:
    st.header("Repository")

    repo_url = st.text_input(
        "Public Git repository URL",
        value="https://github.com/fastapi/full-stack-fastapi-template",
        help="The Streamlit app clones the repository into temporary storage.",
    )
    branch = st.text_input("Branch", value="main")

    analyze_clicked = st.button(
        "Analyze repository",
        type="primary",
        use_container_width=True,
    )

    st.divider()
    st.markdown(
        """
        **Pipeline**

        1. Clone repository
        2. Parse source files
        3. Analyze Git history
        4. Analyze configuration
        5. Build architecture graph
        6. Enable summary / path / impact queries
        """
    )

if analyze_clicked:
    if not repo_url.strip():
        st.error("Enter a repository URL.")
        st.stop()

    with st.status("Analyzing repository...", expanded=True) as status:
        try:
            st.write("Cloning repository...")
            result = analyze_repository(repo_url.strip(), branch.strip() or "main")
            st.write("Parsing source and Git history...")
            st.write("Building architecture graph...")
            status.update(label="Analysis complete", state="complete")
            st.session_state["analysis"] = result
        except Exception as exc:
            status.update(label="Analysis failed", state="error")
            st.exception(exc)
            st.stop()

result = st.session_state.get("analysis")

if not result:
    st.info(
        "Enter a public GitHub repository in the sidebar and click **Analyze repository**."
    )
    st.stop()

architecture = result["graph"]
repo_id = result["repo_id"]

# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

st.subheader(f"📦 {result['name']}")
st.caption(f"{result['url']} · branch `{result['branch']}`")

m1, m2, m3, m4 = st.columns(4)
m1.metric("Files analyzed", len(result["facts"].files))
m2.metric("Graph nodes", architecture.node_count)
m3.metric("Graph edges", architecture.edge_count)
m4.metric("Functions", len(result["facts"].functions))

tab_overview, tab_graph, tab_explore, tab_impact = st.tabs(
    ["Overview", "Architecture Graph", "Explore Paths", "Impact Analysis"]
)

with tab_overview:
    try:
        # The backend query implementation is synchronous in practice, but is
        # exposed as an async FastAPI endpoint. Calling its logic directly here
        # keeps the Streamlit app independent of a running HTTP server.
        import asyncio

        summary = asyncio.run(_get_summary(repo_id))
    except Exception as exc:
        st.error(f"Could not generate the repository summary: {exc}")
        summary = None

    if summary:
        left, right = st.columns(2)

        with left:
            st.markdown("### Languages")
            st.dataframe(
                [
                    {"Language": language, "Files": count}
                    for language, count in summary.language_breakdown.items()
                ],
                hide_index=True,
                use_container_width=True,
            )

            st.markdown("### Entry points")
            for entry in summary.entry_points[:20]:
                st.code(entry)

        with right:
            st.markdown("### Services")
            if summary.services:
                for service in summary.services[:30]:
                    st.markdown(f"- `{service}`")
            else:
                st.caption("No services detected.")

            st.markdown("### Build commands")
            for command in summary.build_commands[:15]:
                st.code(command["command"], language="bash")

        st.markdown("### Dependencies")
        if summary.dependencies:
            st.write(", ".join(f"`{d}`" for d in summary.dependencies))
        else:
            st.caption("No external dependencies detected.")

        st.markdown("### Hotspots")
        if summary.hotspots:
            st.write(", ".join(f"`{h}`" for h in summary.hotspots))
        else:
            st.caption("No Git hotspots detected.")

with tab_graph:
    st.markdown(
        f"**{architecture.node_count} nodes · {architecture.edge_count} relationships**"
    )
    max_nodes = st.slider(
        "Maximum nodes to render",
        min_value=20,
        max_value=min(200, max(20, architecture.node_count)),
        value=min(100, max(20, architecture.node_count)),
        step=10,
    )
    render_graph(architecture, max_nodes=max_nodes)

    with st.expander("Raw graph data"):
        st.json(
            {
                "nodes": [
                    {
                        "id": n.id,
                        "type": n.type.value if hasattr(n.type, "value") else str(n.type),
                        "label": n.label,
                        "file": n.file,
                    }
                    for n in architecture.nodes
                ],
                "edges": [
                    {
                        "source": e.source,
                        "target": e.target,
                        "type": e.type.value if hasattr(e.type, "value") else str(e.type),
                        "confidence": e.confidence,
                    }
                    for e in architecture.edges
                ],
            }
        )

with tab_explore:
    options = node_options(architecture)
    if len(options) < 2:
        st.info("Not enough graph nodes to trace a path.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            source = st.selectbox("From", options, key="path_source")
        with col2:
            target = st.selectbox(
                "To",
                options,
                index=min(1, len(options) - 1),
                key="path_target",
            )

        if st.button("Trace paths", type="primary"):
            try:
                import asyncio

                response = asyncio.run(
                    _get_paths(repo_id, from_=source, to=target)
                )
                if not response.paths:
                    st.warning("No path was found between those nodes.")
                else:
                    st.success(f"Found {len(response.paths)} path(s).")
                    for i, path in enumerate(response.paths, start=1):
                        with st.expander(f"Path {i} · {path.length} hops", expanded=i == 1):
                            for hop in path.hops:
                                node = hop.node
                                st.markdown(
                                    f"**{node.label}**  \n"
                                    f"`{node.type.value if hasattr(node.type, 'value') else node.type}`"
                                    + (f" · `{node.file}`" if node.file else "")
                                )
                                if hop.edge:
                                    edge_type = (
                                        hop.edge.type.value
                                        if hasattr(hop.edge.type, "value")
                                        else hop.edge.type
                                    )
                                    st.caption(
                                        f"↓ {edge_type} · confidence "
                                        f"{hop.edge.confidence:.2f}"
                                    )
            except Exception as exc:
                st.error(f"Path analysis failed: {exc}")

with tab_impact:
    options = node_options(architecture)
    if not options:
        st.info("No nodes are available for impact analysis.")
    else:
        target = st.selectbox("Node to change", options, key="impact_target")

        if st.button("Analyze impact", type="primary"):
            try:
                import asyncio

                impact = asyncio.run(_get_impact(repo_id, node=target))

                a, b, c = st.columns(3)
                a.metric("Directly affected", len(impact.direct))
                b.metric("Transitively affected", len(impact.transitive))
                c.metric("Total affected", impact.total_affected)

                if impact.tests_to_run:
                    st.markdown("### Suggested tests")
                    for test in impact.tests_to_run:
                        st.code(test)

                if impact.direct:
                    st.markdown("### Direct dependencies")
                    st.dataframe(
                        [
                            {
                                "Node": item.node.label,
                                "Type": (
                                    item.node.type.value
                                    if hasattr(item.node.type, "value")
                                    else str(item.node.type)
                                ),
                                "File": item.node.file or "",
                                "Confidence": item.max_confidence,
                            }
                            for item in impact.direct
                        ],
                        hide_index=True,
                        use_container_width=True,
                    )

                if impact.transitive:
                    st.markdown("### Transitive dependencies")
                    st.dataframe(
                        [
                            {
                                "Node": item.node.label,
                                "Distance": item.distance,
                                "File": item.node.file or "",
                                "Confidence": item.max_confidence,
                            }
                            for item in impact.transitive
                        ],
                        hide_index=True,
                        use_container_width=True,
                    )

            except Exception as exc:
                st.error(f"Impact analysis failed: {exc}")

st.divider()
st.caption(
    "Bob the Onboarder · deterministic repository intelligence · "
    "source parsing + Git history + configuration analysis"
)
