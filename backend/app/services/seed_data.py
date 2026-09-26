"""
Prebuilt architecture graphs and raw facts for the 3 default demo repositories:
1. FastAPI Full-Stack Template
2. Google Online Boutique
3. OpenTelemetry Astronomy Shop
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from app.models.facts import (
    APIEndpointFact,
    BuildCommandFact,
    ClassFact,
    CoChangeFact,
    CommitFact,
    DependencyFact,
    FileInfo,
    FileOwnershipFact,
    FunctionFact,
    HotspotFact,
    ImportFact,
    Language,
    RawFacts,
    ServiceFact,
)
from app.models.graph import (
    ArchitectureGraph,
    EdgeType,
    Evidence,
    GraphEdge,
    GraphNode,
    NodeType,
)

# Deterministic IDs for the 3 seeded demo repos
FASTAPI_REPO_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/fastapi/full-stack-fastapi-template.git"))
BOUTIQUE_REPO_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/GoogleCloudPlatform/microservices-demo.git"))
OTEL_REPO_ID = str(uuid.uuid5(uuid.NAMESPACE_URL, "https://github.com/open-telemetry/opentelemetry-demo.git"))

URL_TO_REPO_ID: dict[str, str] = {
    "https://github.com/fastapi/full-stack-fastapi-template.git": FASTAPI_REPO_ID,
    "https://github.com/GoogleCloudPlatform/microservices-demo.git": BOUTIQUE_REPO_ID,
    "https://github.com/open-telemetry/opentelemetry-demo.git": OTEL_REPO_ID,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ===========================================================================
# 1. FastAPI Full-Stack Template
# ===========================================================================

def _build_fastapi_template(repo_id: str) -> tuple[RawFacts, ArchitectureGraph]:
    built_at = _now()

    nodes = [
        # Services (Tier 0)
        GraphNode(id=f"{repo_id}:svc:backend", type=NodeType.SERVICE, label="backend", file="docker-compose.yml", language="python", metadata={"ports": ["8000:8000"], "image": "fastapi-backend"}),
        GraphNode(id=f"{repo_id}:svc:frontend", type=NodeType.SERVICE, label="frontend", file="docker-compose.yml", language="typescript", metadata={"ports": ["5173:80"], "image": "vite-react-frontend"}),
        GraphNode(id=f"{repo_id}:svc:proxy", type=NodeType.SERVICE, label="proxy (traefik)", file="docker-compose.yml", language="yaml", metadata={"ports": ["80:80", "443:443"]}),
        GraphNode(id=f"{repo_id}:svc:adminer", type=NodeType.SERVICE, label="adminer", file="docker-compose.yml", language="yaml", metadata={"ports": ["8080:8080"]}),

        # Components (Tier 1)
        GraphNode(id=f"{repo_id}:comp:backend_app", type=NodeType.COMPONENT, label="backend/app", metadata={"directory": "backend/app"}),
        GraphNode(id=f"{repo_id}:comp:frontend_src", type=NodeType.COMPONENT, label="frontend/src", metadata={"directory": "frontend/src"}),

        # Modules (Tier 2)
        GraphNode(id=f"{repo_id}:mod:main", type=NodeType.MODULE, label="main.py", file="backend/app/main.py", language="python", metadata={"line_count": 65}),
        GraphNode(id=f"{repo_id}:mod:routes_items", type=NodeType.MODULE, label="items.py", file="backend/app/api/routes/items.py", language="python", metadata={"line_count": 110}),
        GraphNode(id=f"{repo_id}:mod:routes_users", type=NodeType.MODULE, label="users.py", file="backend/app/api/routes/users.py", language="python", metadata={"line_count": 140}),
        GraphNode(id=f"{repo_id}:mod:routes_login", type=NodeType.MODULE, label="login.py", file="backend/app/api/routes/login.py", language="python", metadata={"line_count": 85}),
        GraphNode(id=f"{repo_id}:mod:crud", type=NodeType.MODULE, label="crud.py", file="backend/app/crud.py", language="python", metadata={"line_count": 130}),
        GraphNode(id=f"{repo_id}:mod:models", type=NodeType.MODULE, label="models.py", file="backend/app/models.py", language="python", metadata={"line_count": 160}),
        GraphNode(id=f"{repo_id}:mod:core_db", type=NodeType.MODULE, label="db.py", file="backend/app/core/db.py", language="python", metadata={"line_count": 45}),
        GraphNode(id=f"{repo_id}:mod:core_security", type=NodeType.MODULE, label="security.py", file="backend/app/core/security.py", language="python", metadata={"line_count": 55}),
        GraphNode(id=f"{repo_id}:mod:ui_app", type=NodeType.MODULE, label="App.tsx", file="frontend/src/App.tsx", language="typescript", metadata={"line_count": 80}),
        GraphNode(id=f"{repo_id}:mod:ui_items", type=NodeType.MODULE, label="Items.tsx", file="frontend/src/components/Items.tsx", language="typescript", metadata={"line_count": 95}),
        GraphNode(id=f"{repo_id}:mod:test_items", type=NodeType.MODULE, label="test_items.py", file="backend/tests/api/routes/test_items.py", language="python", metadata={"line_count": 75}),
        GraphNode(id=f"{repo_id}:mod:test_users", type=NodeType.MODULE, label="test_users.py", file="backend/tests/api/routes/test_users.py", language="python", metadata={"line_count": 90}),

        # Classes & Functions (Tier 3)
        GraphNode(id=f"{repo_id}:cls:user", type=NodeType.CLASS, label="User", file="backend/app/models.py", language="python", metadata={"line": 15}),
        GraphNode(id=f"{repo_id}:cls:item", type=NodeType.CLASS, label="Item", file="backend/app/models.py", language="python", metadata={"line": 45}),
        GraphNode(id=f"{repo_id}:fn:get_items", type=NodeType.FUNCTION, label="get_items()", file="backend/app/crud.py", language="python", metadata={"line": 32}),
        GraphNode(id=f"{repo_id}:fn:create_item", type=NodeType.FUNCTION, label="create_item()", file="backend/app/crud.py", language="python", metadata={"line": 50}),
        GraphNode(id=f"{repo_id}:fn:init_db", type=NodeType.FUNCTION, label="init_db()", file="backend/app/core/db.py", language="python", metadata={"line": 18}),

        # API Endpoints (Tier 3)
        GraphNode(id=f"{repo_id}:api:get_items", type=NodeType.API_ENDPOINT, label="GET /api/v1/items", file="backend/app/api/routes/items.py", metadata={"method": "GET", "path": "/api/v1/items", "handler": "read_items"}),
        GraphNode(id=f"{repo_id}:api:post_items", type=NodeType.API_ENDPOINT, label="POST /api/v1/items", file="backend/app/api/routes/items.py", metadata={"method": "POST", "path": "/api/v1/items", "handler": "create_item"}),
        GraphNode(id=f"{repo_id}:api:get_users", type=NodeType.API_ENDPOINT, label="GET /api/v1/users", file="backend/app/api/routes/users.py", metadata={"method": "GET", "path": "/api/v1/users", "handler": "read_users"}),
        GraphNode(id=f"{repo_id}:api:post_login", type=NodeType.API_ENDPOINT, label="POST /api/v1/login/access-token", file="backend/app/api/routes/login.py", metadata={"method": "POST", "path": "/api/v1/login/access-token", "handler": "login_access_token"}),

        # Databases (Tier 4)
        GraphNode(id=f"{repo_id}:db:postgres", type=NodeType.DATABASE, label="PostgreSQL", file="docker-compose.yml", metadata={"engine": "PostgreSQL 16", "ports": ["5432:5432"]}),

        # Dependencies (Tier 5)
        GraphNode(id=f"{repo_id}:dep:fastapi", type=NodeType.DEPENDENCY, label="fastapi", metadata={"version": ">=0.111.0"}),
        GraphNode(id=f"{repo_id}:dep:sqlmodel", type=NodeType.DEPENDENCY, label="sqlmodel", metadata={"version": ">=0.0.18"}),
        GraphNode(id=f"{repo_id}:dep:pydantic", type=NodeType.DEPENDENCY, label="pydantic", metadata={"version": ">=2.7.0"}),
    ]

    edges = [
        GraphEdge(id=f"{repo_id}:e1", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:proxy", type=EdgeType.HTTP_CALL, confidence=1.0, evidence=[Evidence(file="docker-compose.yml", line=18, snippet="frontend depends_on proxy")]),
        GraphEdge(id=f"{repo_id}:e2", source=f"{repo_id}:svc:proxy", target=f"{repo_id}:svc:backend", type=EdgeType.HTTP_CALL, confidence=1.0, evidence=[Evidence(file="docker-compose.yml", line=32, snippet="proxy forwards /api -> backend:8000")]),
        GraphEdge(id=f"{repo_id}:e3", source=f"{repo_id}:svc:backend", target=f"{repo_id}:db:postgres", type=EdgeType.DB_QUERY, confidence=0.98, evidence=[Evidence(file="docker-compose.yml", line=48, snippet="backend depends_on db")]),
        GraphEdge(id=f"{repo_id}:e4", source=f"{repo_id}:mod:ui_items", target=f"{repo_id}:api:get_items", type=EdgeType.HTTP_CALL, confidence=0.95, evidence=[Evidence(file="frontend/src/components/Items.tsx", line=24, snippet="const res = await client.items.readItems()")]),
        GraphEdge(id=f"{repo_id}:e5", source=f"{repo_id}:mod:main", target=f"{repo_id}:mod:routes_items", type=EdgeType.IMPORTS, confidence=0.95, evidence=[Evidence(file="backend/app/main.py", line=12, snippet="from app.api.routes import items")]),
        GraphEdge(id=f"{repo_id}:e6", source=f"{repo_id}:mod:main", target=f"{repo_id}:mod:routes_users", type=EdgeType.IMPORTS, confidence=0.95, evidence=[Evidence(file="backend/app/main.py", line=13, snippet="from app.api.routes import users")]),
        GraphEdge(id=f"{repo_id}:e7", source=f"{repo_id}:mod:main", target=f"{repo_id}:mod:routes_login", type=EdgeType.IMPORTS, confidence=0.95, evidence=[Evidence(file="backend/app/main.py", line=14, snippet="from app.api.routes import login")]),
        GraphEdge(id=f"{repo_id}:e8", source=f"{repo_id}:mod:routes_items", target=f"{repo_id}:api:get_items", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="backend/app/api/routes/items.py", line=18, snippet="@router.get('/', response_model=ItemsPublic)")]),
        GraphEdge(id=f"{repo_id}:e9", source=f"{repo_id}:mod:routes_items", target=f"{repo_id}:api:post_items", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="backend/app/api/routes/items.py", line=42, snippet="@router.post('/', response_model=ItemPublic)")]),
        GraphEdge(id=f"{repo_id}:e10", source=f"{repo_id}:mod:routes_users", target=f"{repo_id}:api:get_users", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="backend/app/api/routes/users.py", line=22, snippet="@router.get('/', response_model=UsersPublic)")]),
        GraphEdge(id=f"{repo_id}:e11", source=f"{repo_id}:mod:routes_login", target=f"{repo_id}:api:post_login", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="backend/app/api/routes/login.py", line=20, snippet="@router.post('/login/access-token')")]),
        GraphEdge(id=f"{repo_id}:e12", source=f"{repo_id}:api:get_items", target=f"{repo_id}:fn:get_items", type=EdgeType.CALLS, confidence=0.92, evidence=[Evidence(file="backend/app/api/routes/items.py", line=25, snippet="items = crud.get_items(session=session)")]),
        GraphEdge(id=f"{repo_id}:e13", source=f"{repo_id}:api:post_items", target=f"{repo_id}:fn:create_item", type=EdgeType.CALLS, confidence=0.92, evidence=[Evidence(file="backend/app/api/routes/items.py", line=48, snippet="item = crud.create_item(session=session, item_in=item_in)")]),
        GraphEdge(id=f"{repo_id}:e14", source=f"{repo_id}:fn:get_items", target=f"{repo_id}:cls:item", type=EdgeType.CALLS, confidence=0.90, evidence=[Evidence(file="backend/app/crud.py", line=35, snippet="return session.exec(select(Item)).all()")]),
        GraphEdge(id=f"{repo_id}:e15", source=f"{repo_id}:fn:create_item", target=f"{repo_id}:cls:item", type=EdgeType.CALLS, confidence=0.90, evidence=[Evidence(file="backend/app/crud.py", line=55, snippet="db_item = Item.model_validate(item_in)")]),
        GraphEdge(id=f"{repo_id}:e16", source=f"{repo_id}:mod:crud", target=f"{repo_id}:mod:models", type=EdgeType.IMPORTS, confidence=0.95, evidence=[Evidence(file="backend/app/crud.py", line=4, snippet="from app.models import Item, User")]),
        GraphEdge(id=f"{repo_id}:e17", source=f"{repo_id}:mod:crud", target=f"{repo_id}:mod:core_db", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="backend/app/crud.py", line=8, snippet="from app.core.db import engine")]),
        GraphEdge(id=f"{repo_id}:e17b", source=f"{repo_id}:fn:get_items", target=f"{repo_id}:mod:core_db", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="backend/app/crud.py", line=34, snippet="session = Session(engine)")]),
        GraphEdge(id=f"{repo_id}:e18", source=f"{repo_id}:mod:core_db", target=f"{repo_id}:db:postgres", type=EdgeType.DB_QUERY, confidence=0.98, evidence=[Evidence(file="backend/app/core/db.py", line=14, snippet="engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))")]),
        GraphEdge(id=f"{repo_id}:e19", source=f"{repo_id}:mod:test_items", target=f"{repo_id}:mod:routes_items", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="backend/tests/api/routes/test_items.py", line=20, snippet="response = client.get(f'{settings.API_V1_STR}/items/')")]),
        GraphEdge(id=f"{repo_id}:e20", source=f"{repo_id}:mod:test_users", target=f"{repo_id}:mod:routes_users", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="backend/tests/api/routes/test_users.py", line=25, snippet="response = client.get(f'{settings.API_V1_STR}/users/')")]),
        GraphEdge(id=f"{repo_id}:e21", source=f"{repo_id}:mod:main", target=f"{repo_id}:dep:fastapi", type=EdgeType.DEPENDS_ON, confidence=1.0, evidence=[Evidence(file="backend/app/main.py", line=2, snippet="from fastapi import FastAPI")]),
        GraphEdge(id=f"{repo_id}:e22", source=f"{repo_id}:mod:models", target=f"{repo_id}:dep:sqlmodel", type=EdgeType.DEPENDS_ON, confidence=1.0, evidence=[Evidence(file="backend/app/models.py", line=3, snippet="from sqlmodel import Field, SQLModel, Relationship")]),
        GraphEdge(id=f"{repo_id}:e23", source=f"{repo_id}:mod:models", target=f"{repo_id}:dep:pydantic", type=EdgeType.DEPENDS_ON, confidence=1.0, evidence=[Evidence(file="backend/app/models.py", line=4, snippet="from pydantic import EmailStr")]),
        GraphEdge(id=f"{repo_id}:e24", source=f"{repo_id}:comp:backend_app", target=f"{repo_id}:mod:main", type=EdgeType.CONTAINS, confidence=1.0),
        GraphEdge(id=f"{repo_id}:e25", source=f"{repo_id}:comp:frontend_src", target=f"{repo_id}:mod:ui_app", type=EdgeType.CONTAINS, confidence=1.0),
    ]

    arch = ArchitectureGraph(
        repo_id=repo_id,
        nodes=nodes,
        edges=edges,
        built_at=built_at,
        node_count=len(nodes),
        edge_count=len(edges),
    )

    facts = RawFacts(
        repo_id=repo_id,
        language_summary={"python": 18, "typescript": 14, "yaml": 4, "dockerfile": 2},
        files=[
            FileInfo(path="backend/app/main.py", language=Language.PYTHON, line_count=65),
            FileInfo(path="backend/app/api/routes/items.py", language=Language.PYTHON, line_count=110),
            FileInfo(path="backend/app/api/routes/users.py", language=Language.PYTHON, line_count=140),
            FileInfo(path="backend/app/api/routes/login.py", language=Language.PYTHON, line_count=85),
            FileInfo(path="backend/app/crud.py", language=Language.PYTHON, line_count=130),
            FileInfo(path="backend/app/models.py", language=Language.PYTHON, line_count=160),
            FileInfo(path="backend/app/core/db.py", language=Language.PYTHON, line_count=45),
            FileInfo(path="backend/app/core/security.py", language=Language.PYTHON, line_count=55),
            FileInfo(path="backend/tests/api/routes/test_items.py", language=Language.PYTHON, line_count=75),
            FileInfo(path="backend/tests/api/routes/test_users.py", language=Language.PYTHON, line_count=90),
            FileInfo(path="frontend/src/App.tsx", language=Language.TYPESCRIPT, line_count=80),
            FileInfo(path="frontend/src/components/Items.tsx", language=Language.TYPESCRIPT, line_count=95),
            FileInfo(path="docker-compose.yml", language=Language.YAML, line_count=120),
        ],
        services=[
            ServiceFact(name="backend", source_file="docker-compose.yml", image="fastapi-backend", ports=["8000:8000"], depends_on=["db"]),
            ServiceFact(name="frontend", source_file="docker-compose.yml", image="vite-react-frontend", ports=["5173:80"], depends_on=["proxy"]),
            ServiceFact(name="db", source_file="docker-compose.yml", image="postgres:16", ports=["5432:5432"]),
            ServiceFact(name="proxy", source_file="docker-compose.yml", image="traefik:v3.0", ports=["80:80", "443:443"]),
            ServiceFact(name="adminer", source_file="docker-compose.yml", image="adminer", ports=["8080:8080"]),
        ],
        api_endpoints=[
            APIEndpointFact(file="backend/app/api/routes/items.py", line=18, method="GET", path="/api/v1/items", handler="read_items", framework="fastapi"),
            APIEndpointFact(file="backend/app/api/routes/items.py", line=42, method="POST", path="/api/v1/items", handler="create_item", framework="fastapi"),
            APIEndpointFact(file="backend/app/api/routes/users.py", line=22, method="GET", path="/api/v1/users", handler="read_users", framework="fastapi"),
            APIEndpointFact(file="backend/app/api/routes/login.py", line=20, method="POST", path="/api/v1/login/access-token", handler="login_access_token", framework="fastapi"),
        ],
        dependencies=[
            DependencyFact(manifest_file="backend/pyproject.toml", name="fastapi", version_spec=">=0.111.0"),
            DependencyFact(manifest_file="backend/pyproject.toml", name="sqlmodel", version_spec=">=0.0.18"),
            DependencyFact(manifest_file="backend/pyproject.toml", name="pydantic", version_spec=">=2.7.0"),
            DependencyFact(manifest_file="backend/pyproject.toml", name="alembic", version_spec=">=1.13.0"),
            DependencyFact(manifest_file="backend/pyproject.toml", name="pytest", version_spec=">=8.0.0", is_dev=True),
        ],
        build_commands=[
            BuildCommandFact(source_file="backend/pyproject.toml", name="test", command="pytest"),
            BuildCommandFact(source_file="frontend/package.json", name="build", command="npm run build"),
            BuildCommandFact(source_file="docker-compose.yml", name="up", command="docker compose up -d"),
        ],
        hotspots=[
            HotspotFact(file="backend/app/api/routes/items.py", change_count=28, unique_authors=5),
            HotspotFact(file="backend/app/models.py", change_count=22, unique_authors=4),
            HotspotFact(file="backend/app/crud.py", change_count=19, unique_authors=3),
        ],
        analysed_at=built_at,
    )

    return facts, arch


# ===========================================================================
# 2. Google Online Boutique
# ===========================================================================

def _build_boutique_template(repo_id: str) -> tuple[RawFacts, ArchitectureGraph]:
    built_at = _now()

    nodes = [
        # Microservices (Tier 0)
        GraphNode(id=f"{repo_id}:svc:frontend", type=NodeType.SERVICE, label="frontend", file="src/frontend/main.go", language="go", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:cartservice", type=NodeType.SERVICE, label="cartservice", file="src/cartservice/src/CartService.cs", language="csharp", metadata={"ports": ["7070:7070"]}),
        GraphNode(id=f"{repo_id}:svc:productcatalog", type=NodeType.SERVICE, label="productcatalogservice", file="src/productcatalogservice/server.go", language="go", metadata={"ports": ["3550:3550"]}),
        GraphNode(id=f"{repo_id}:svc:currencyservice", type=NodeType.SERVICE, label="currencyservice", file="src/currencyservice/server.js", language="javascript", metadata={"ports": ["7000:7000"]}),
        GraphNode(id=f"{repo_id}:svc:paymentservice", type=NodeType.SERVICE, label="paymentservice", file="src/paymentservice/index.js", language="javascript", metadata={"ports": ["50051:50051"]}),
        GraphNode(id=f"{repo_id}:svc:shippingservice", type=NodeType.SERVICE, label="shippingservice", file="src/shippingservice/main.go", language="go", metadata={"ports": ["50051:50051"]}),
        GraphNode(id=f"{repo_id}:svc:emailservice", type=NodeType.SERVICE, label="emailservice", file="src/emailservice/email_server.py", language="python", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:checkoutservice", type=NodeType.SERVICE, label="checkoutservice", file="src/checkoutservice/main.go", language="go", metadata={"ports": ["5050:5050"]}),
        GraphNode(id=f"{repo_id}:svc:recommendation", type=NodeType.SERVICE, label="recommendationservice", file="src/recommendationservice/recommendation_server.py", language="python", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:adservice", type=NodeType.SERVICE, label="adservice", file="src/adservice/src/main/java/hipstershop/AdService.java", language="java", metadata={"ports": ["9555:9555"]}),
        GraphNode(id=f"{repo_id}:svc:loadgenerator", type=NodeType.SERVICE, label="loadgenerator", file="src/loadgenerator/locustfile.py", language="python"),

        # Cache / Storage (Tier 4)
        GraphNode(id=f"{repo_id}:cache:redis", type=NodeType.CACHE, label="redis-cart", file="kubernetes-manifests/redis.yaml", metadata={"ports": ["6379:6379"]}),

        # API Endpoints / RPC handlers (Tier 3)
        GraphNode(id=f"{repo_id}:api:http_index", type=NodeType.API_ENDPOINT, label="GET /", file="src/frontend/main.go", metadata={"method": "GET", "path": "/"}),
        GraphNode(id=f"{repo_id}:api:http_cart", type=NodeType.API_ENDPOINT, label="POST /cart", file="src/frontend/handlers.go", metadata={"method": "POST", "path": "/cart"}),
        GraphNode(id=f"{repo_id}:api:http_checkout", type=NodeType.API_ENDPOINT, label="POST /cart/checkout", file="src/frontend/handlers.go", metadata={"method": "POST", "path": "/cart/checkout"}),
        GraphNode(id=f"{repo_id}:api:grpc_checkout", type=NodeType.API_ENDPOINT, label="grpc PlaceOrder", file="src/checkoutservice/main.go", metadata={"protocol": "gRPC", "method": "PlaceOrder"}),
        GraphNode(id=f"{repo_id}:api:grpc_getcart", type=NodeType.API_ENDPOINT, label="grpc GetCart", file="src/cartservice/src/CartService.cs", metadata={"protocol": "gRPC", "method": "GetCart"}),
        GraphNode(id=f"{repo_id}:api:grpc_catalog", type=NodeType.API_ENDPOINT, label="grpc ListProducts", file="src/productcatalogservice/server.go", metadata={"protocol": "gRPC", "method": "ListProducts"}),
        GraphNode(id=f"{repo_id}:api:grpc_payment", type=NodeType.API_ENDPOINT, label="grpc Charge", file="src/paymentservice/index.js", metadata={"protocol": "gRPC", "method": "Charge"}),
        GraphNode(id=f"{repo_id}:api:grpc_shipping", type=NodeType.API_ENDPOINT, label="grpc ShipOrder", file="src/shippingservice/main.go", metadata={"protocol": "gRPC", "method": "ShipOrder"}),
        GraphNode(id=f"{repo_id}:api:grpc_email", type=NodeType.API_ENDPOINT, label="grpc SendOrderConfirmation", file="src/emailservice/email_server.py", metadata={"protocol": "gRPC", "method": "SendOrderConfirmation"}),

        # Test files (Tier 2)
        GraphNode(id=f"{repo_id}:mod:test_frontend", type=NodeType.MODULE, label="frontend_test.go", file="src/frontend/main_test.go", language="go"),
        GraphNode(id=f"{repo_id}:mod:test_checkout", type=NodeType.MODULE, label="checkout_test.go", file="src/checkoutservice/main_test.go", language="go"),
        GraphNode(id=f"{repo_id}:mod:test_cart", type=NodeType.MODULE, label="CartServiceTests.cs", file="tests/cartservice/CartServiceTests.cs", language="csharp"),
    ]

    edges = [
        GraphEdge(id=f"{repo_id}:be1", source=f"{repo_id}:svc:loadgenerator", target=f"{repo_id}:api:http_index", type=EdgeType.HTTP_CALL, confidence=0.98, evidence=[Evidence(file="src/loadgenerator/locustfile.py", line=28, snippet="client.get('/')")]),
        GraphEdge(id=f"{repo_id}:be2", source=f"{repo_id}:svc:loadgenerator", target=f"{repo_id}:api:http_cart", type=EdgeType.HTTP_CALL, confidence=0.98, evidence=[Evidence(file="src/loadgenerator/locustfile.py", line=45, snippet="client.post('/cart')")]),
        GraphEdge(id=f"{repo_id}:be3", source=f"{repo_id}:api:http_index", target=f"{repo_id}:svc:frontend", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="src/frontend/main.go", line=85, snippet="r.HandleFunc('/', fh.homeHandler)")]),
        GraphEdge(id=f"{repo_id}:be4", source=f"{repo_id}:api:http_cart", target=f"{repo_id}:svc:frontend", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="src/frontend/handlers.go", line=40, snippet="r.HandleFunc('/cart', fh.addToCartHandler)")]),
        GraphEdge(id=f"{repo_id}:be5", source=f"{repo_id}:api:http_checkout", target=f"{repo_id}:api:grpc_checkout", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/handlers.go", line=215, snippet="pb.NewCheckoutServiceClient(conn).PlaceOrder(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be5a", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:checkoutservice", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/frontend/rpc.go", line=150, snippet="pb.NewCheckoutServiceClient(conn)")]),
        GraphEdge(id=f"{repo_id}:be6", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:productcatalog", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/rpc.go", line=42, snippet="pb.NewProductCatalogServiceClient(conn).ListProducts(...)")]),
        GraphEdge(id=f"{repo_id}:be7", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:currencyservice", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/rpc.go", line=68, snippet="pb.NewCurrencyServiceClient(conn).GetSupportedCurrencies(...)")]),
        GraphEdge(id=f"{repo_id}:be8", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:recommendation", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/rpc.go", line=94, snippet="pb.NewRecommendationServiceClient(conn).ListRecommendations(...)")]),
        GraphEdge(id=f"{repo_id}:be9", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:adservice", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/rpc.go", line=118, snippet="pb.NewAdServiceClient(conn).GetAds(...)")]),
        GraphEdge(id=f"{repo_id}:be10", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:api:grpc_getcart", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/rpc.go", line=140, snippet="pb.NewCartServiceClient(conn).GetCart(...)")]),
        GraphEdge(id=f"{repo_id}:be11", source=f"{repo_id}:api:grpc_checkout", target=f"{repo_id}:svc:checkoutservice", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="src/checkoutservice/main.go", line=62, snippet="pb.RegisterCheckoutServiceServer(s, &checkoutServer{})")]),
        GraphEdge(id=f"{repo_id}:be12", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:api:grpc_getcart", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=145, snippet="cs.cartService.GetCart(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be13", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:api:grpc_catalog", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=178, snippet="cs.productCatalogService.GetProduct(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be14", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:api:grpc_payment", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=210, snippet="cs.paymentService.Charge(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be14a", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:svc:paymentservice", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=212, snippet="pb.NewPaymentServiceClient(conn)")]),
        GraphEdge(id=f"{repo_id}:be14b", source=f"{repo_id}:api:grpc_payment", target=f"{repo_id}:svc:paymentservice", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/paymentservice/index.js", line=30, snippet="server.addService(HipsterShop.service)")]),
        GraphEdge(id=f"{repo_id}:be15", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:api:grpc_shipping", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=240, snippet="cs.shippingService.ShipOrder(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be16", source=f"{repo_id}:svc:checkoutservice", target=f"{repo_id}:api:grpc_email", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkoutservice/main.go", line=275, snippet="cs.emailService.SendOrderConfirmation(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be17", source=f"{repo_id}:svc:cartservice", target=f"{repo_id}:cache:redis", type=EdgeType.DB_QUERY, confidence=0.99, evidence=[Evidence(file="src/cartservice/src/redis/RedisCartStore.cs", line=58, snippet="await db.StringSetAsync(userId, json)")]),
        GraphEdge(id=f"{repo_id}:be18", source=f"{repo_id}:mod:test_frontend", target=f"{repo_id}:svc:frontend", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/main_test.go", line=25, snippet="req := httptest.NewRequest('GET', '/', nil)")]),
        GraphEdge(id=f"{repo_id}:be19", source=f"{repo_id}:mod:test_checkout", target=f"{repo_id}:svc:checkoutservice", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/checkoutservice/main_test.go", line=42, snippet="res, err := server.PlaceOrder(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:be20", source=f"{repo_id}:mod:test_cart", target=f"{repo_id}:svc:cartservice", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="tests/cartservice/CartServiceTests.cs", line=30, snippet="var response = await service.GetCart(request, null)")]),
    ]

    arch = ArchitectureGraph(
        repo_id=repo_id,
        nodes=nodes,
        edges=edges,
        built_at=built_at,
        node_count=len(nodes),
        edge_count=len(edges),
    )

    facts = RawFacts(
        repo_id=repo_id,
        language_summary={"go": 42, "python": 28, "csharp": 16, "javascript": 24, "java": 12, "yaml": 18},
        files=[
            FileInfo(path="src/frontend/main.go", language=Language.GO, line_count=210),
            FileInfo(path="src/frontend/handlers.go", language=Language.GO, line_count=320),
            FileInfo(path="src/frontend/rpc.go", language=Language.GO, line_count=180),
            FileInfo(path="src/frontend/main_test.go", language=Language.GO, line_count=90),
            FileInfo(path="src/checkoutservice/main.go", language=Language.GO, line_count=350),
            FileInfo(path="src/checkoutservice/main_test.go", language=Language.GO, line_count=110),
            FileInfo(path="src/cartservice/src/CartService.cs", language=Language.CSHARP, line_count=180),
            FileInfo(path="src/productcatalogservice/server.go", language=Language.GO, line_count=160),
            FileInfo(path="src/paymentservice/index.js", language=Language.JAVASCRIPT, line_count=140),
            FileInfo(path="src/shippingservice/main.go", language=Language.GO, line_count=130),
            FileInfo(path="src/emailservice/email_server.py", language=Language.PYTHON, line_count=110),
            FileInfo(path="src/recommendationservice/recommendation_server.py", language=Language.PYTHON, line_count=120),
            FileInfo(path="src/adservice/src/main/java/hipstershop/AdService.java", language=Language.JAVA, line_count=150),
            FileInfo(path="src/loadgenerator/locustfile.py", language=Language.PYTHON, line_count=95),
            FileInfo(path="tests/cartservice/CartServiceTests.cs", language=Language.CSHARP, line_count=85),
        ],
        services=[
            ServiceFact(name="frontend", source_file="kubernetes-manifests/frontend.yaml", ports=["8080:8080"]),
            ServiceFact(name="cartservice", source_file="kubernetes-manifests/cartservice.yaml", ports=["7070:7070"]),
            ServiceFact(name="productcatalogservice", source_file="kubernetes-manifests/productcatalogservice.yaml", ports=["3550:3550"]),
            ServiceFact(name="currencyservice", source_file="kubernetes-manifests/currencyservice.yaml", ports=["7000:7000"]),
            ServiceFact(name="paymentservice", source_file="kubernetes-manifests/paymentservice.yaml", ports=["50051:50051"]),
            ServiceFact(name="shippingservice", source_file="kubernetes-manifests/shippingservice.yaml", ports=["50051:50051"]),
            ServiceFact(name="emailservice", source_file="kubernetes-manifests/emailservice.yaml", ports=["8080:8080"]),
            ServiceFact(name="checkoutservice", source_file="kubernetes-manifests/checkoutservice.yaml", ports=["5050:5050"]),
            ServiceFact(name="recommendationservice", source_file="kubernetes-manifests/recommendationservice.yaml", ports=["8080:8080"]),
            ServiceFact(name="adservice", source_file="kubernetes-manifests/adservice.yaml", ports=["9555:9555"]),
            ServiceFact(name="loadgenerator", source_file="kubernetes-manifests/loadgenerator.yaml"),
        ],
        api_endpoints=[
            APIEndpointFact(file="src/frontend/main.go", line=85, method="GET", path="/", handler="homeHandler"),
            APIEndpointFact(file="src/frontend/handlers.go", line=40, method="POST", path="/cart", handler="addToCartHandler"),
            APIEndpointFact(file="src/frontend/handlers.go", line=215, method="POST", path="/cart/checkout", handler="checkoutHandler"),
            APIEndpointFact(file="src/checkoutservice/main.go", line=62, method="POST", path="grpc/PlaceOrder", handler="PlaceOrder"),
            APIEndpointFact(file="src/cartservice/src/CartService.cs", line=45, method="POST", path="grpc/GetCart", handler="GetCart"),
            APIEndpointFact(file="src/productcatalogservice/server.go", line=55, method="POST", path="grpc/ListProducts", handler="ListProducts"),
        ],
        dependencies=[
            DependencyFact(manifest_file="src/frontend/go.mod", name="google.golang.org/grpc", version_spec="v1.60.0"),
            DependencyFact(manifest_file="src/checkoutservice/go.mod", name="github.com/google/uuid", version_spec="v1.5.0"),
            DependencyFact(manifest_file="src/cartservice/src/cartservice.csproj", name="StackExchange.Redis", version_spec="2.7.4"),
        ],
        build_commands=[
            BuildCommandFact(source_file="Makefile", name="test", command="make test"),
            BuildCommandFact(source_file="Makefile", name="build", command="skaffold build"),
        ],
        hotspots=[
            HotspotFact(file="src/checkoutservice/main.go", change_count=35, unique_authors=8),
            HotspotFact(file="src/frontend/handlers.go", change_count=31, unique_authors=6),
            HotspotFact(file="src/cartservice/src/CartService.cs", change_count=20, unique_authors=4),
        ],
        analysed_at=built_at,
    )

    return facts, arch


# ===========================================================================
# 3. OpenTelemetry Astronomy Shop
# ===========================================================================

def _build_otel_template(repo_id: str) -> tuple[RawFacts, ArchitectureGraph]:
    built_at = _now()

    nodes = [
        # Services & Proxies (Tier 0)
        GraphNode(id=f"{repo_id}:svc:frontendproxy", type=NodeType.SERVICE, label="frontendproxy (Envoy)", file="src/frontendproxy/envoy.yaml", language="yaml", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:frontend", type=NodeType.SERVICE, label="frontend (Next.js)", file="src/frontend/pages/index.tsx", language="typescript", metadata={"ports": ["3000:3000"]}),
        GraphNode(id=f"{repo_id}:svc:checkout", type=NodeType.SERVICE, label="checkoutservice", file="src/checkout/main.go", language="go", metadata={"ports": ["5050:5050"]}),
        GraphNode(id=f"{repo_id}:svc:cart", type=NodeType.SERVICE, label="cartservice", file="src/cart/src/CartService.cs", language="csharp", metadata={"ports": ["7070:7070"]}),
        GraphNode(id=f"{repo_id}:svc:catalog", type=NodeType.SERVICE, label="productcatalogservice", file="src/productcatalog/server.go", language="go", metadata={"ports": ["3550:3550"]}),
        GraphNode(id=f"{repo_id}:svc:payment", type=NodeType.SERVICE, label="paymentservice", file="src/payment/index.js", language="javascript", metadata={"ports": ["50051:50051"]}),
        GraphNode(id=f"{repo_id}:svc:shipping", type=NodeType.SERVICE, label="shippingservice", file="src/shipping/src/main.rs", language="rust", metadata={"ports": ["50051:50051"]}),
        GraphNode(id=f"{repo_id}:svc:email", type=NodeType.SERVICE, label="emailservice", file="src/email/email_server.rb", language="ruby", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:recommendation", type=NodeType.SERVICE, label="recommendationservice", file="src/recommendation/server.py", language="python", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:ad", type=NodeType.SERVICE, label="adservice", file="src/ad/src/main/java/hipstershop/AdService.java", language="java", metadata={"ports": ["9555:9555"]}),
        GraphNode(id=f"{repo_id}:svc:fraud", type=NodeType.SERVICE, label="frauddetectionservice", file="src/frauddetection/src/main/kotlin/FraudDetector.kt", language="java", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:accounting", type=NodeType.SERVICE, label="accountingservice", file="src/accounting/main.go", language="go", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:quote", type=NodeType.SERVICE, label="quoteservice", file="src/quote/server.php", language="shell", metadata={"ports": ["8080:8080"]}),
        GraphNode(id=f"{repo_id}:svc:otelcol", type=NodeType.SERVICE, label="otelcol (OpenTelemetry Collector)", file="src/otelcollector/otelcol-config.yaml", language="yaml", metadata={"ports": ["4317:4317", "4318:4318"]}),

        # External Observability (Tier 5)
        GraphNode(id=f"{repo_id}:ext:jaeger", type=NodeType.EXTERNAL, label="jaeger", file="docker-compose.yml", metadata={"ports": ["16686:16686"]}),
        GraphNode(id=f"{repo_id}:ext:prometheus", type=NodeType.EXTERNAL, label="prometheus", file="docker-compose.yml", metadata={"ports": ["9090:9090"]}),
        GraphNode(id=f"{repo_id}:ext:grafana", type=NodeType.EXTERNAL, label="grafana", file="docker-compose.yml", metadata={"ports": ["3000:3000"]}),

        # Queues & Caches (Tier 4)
        GraphNode(id=f"{repo_id}:queue:kafka", type=NodeType.QUEUE, label="kafka (order topic)", file="docker-compose.yml", metadata={"ports": ["9092:9092"]}),
        GraphNode(id=f"{repo_id}:cache:valkey", type=NodeType.CACHE, label="valkey-cart", file="docker-compose.yml", metadata={"ports": ["6379:6379"]}),

        # API Endpoints (Tier 3)
        GraphNode(id=f"{repo_id}:api:otel_checkout", type=NodeType.API_ENDPOINT, label="POST /api/checkout", file="src/frontend/pages/api/checkout.ts", metadata={"method": "POST", "path": "/api/checkout"}),
        GraphNode(id=f"{repo_id}:api:otel_cart", type=NodeType.API_ENDPOINT, label="POST /api/cart", file="src/frontend/pages/api/cart.ts", metadata={"method": "POST", "path": "/api/cart"}),
        GraphNode(id=f"{repo_id}:api:otel_products", type=NodeType.API_ENDPOINT, label="GET /api/products", file="src/frontend/pages/api/products.ts", metadata={"method": "GET", "path": "/api/products"}),

        # Test files (Tier 2)
        GraphNode(id=f"{repo_id}:mod:test_checkout", type=NodeType.MODULE, label="checkout_test.go", file="src/checkout/main_test.go", language="go"),
        GraphNode(id=f"{repo_id}:mod:test_frontend", type=NodeType.MODULE, label="index.test.tsx", file="src/frontend/__tests__/index.test.tsx", language="typescript"),
    ]

    edges = [
        GraphEdge(id=f"{repo_id}:oe1", source=f"{repo_id}:svc:frontendproxy", target=f"{repo_id}:svc:frontend", type=EdgeType.HTTP_CALL, confidence=1.0, evidence=[Evidence(file="src/frontendproxy/envoy.yaml", line=32, snippet="route: cluster: frontend")]),
        GraphEdge(id=f"{repo_id}:oe2", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:api:otel_checkout", type=EdgeType.EXPOSES, confidence=1.0, evidence=[Evidence(file="src/frontend/pages/api/checkout.ts", line=12, snippet="export default async function handler(req, res)")]),
        GraphEdge(id=f"{repo_id}:oe3", source=f"{repo_id}:api:otel_checkout", target=f"{repo_id}:svc:checkout", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/frontend/pages/api/checkout.ts", line=35, snippet="client.PlaceOrder(req.body)")]),
        GraphEdge(id=f"{repo_id}:oe4", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:catalog", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/pages/api/products.ts", line=24, snippet="client.ListProducts({})")]),
        GraphEdge(id=f"{repo_id}:oe5", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:cart", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/pages/api/cart.ts", line=18, snippet="client.GetCart({userId})")]),
        GraphEdge(id=f"{repo_id}:oe6", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:recommendation", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/pages/index.tsx", line=48, snippet="client.ListRecommendations(...)")]),
        GraphEdge(id=f"{repo_id}:oe7", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:ad", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/pages/index.tsx", line=62, snippet="client.GetAds(...)")]),
        GraphEdge(id=f"{repo_id}:oe8", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:svc:payment", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkout/main.go", line=182, snippet="paymentClient.Charge(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:oe9", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:svc:shipping", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkout/main.go", line=204, snippet="shippingClient.ShipOrder(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:oe10", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:svc:email", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkout/main.go", line=228, snippet="emailClient.SendOrderConfirmation(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:oe11", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:svc:cart", type=EdgeType.CALLS, confidence=0.96, evidence=[Evidence(file="src/checkout/main.go", line=250, snippet="cartClient.EmptyCart(ctx, req)")]),
        GraphEdge(id=f"{repo_id}:oe12", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:queue:kafka", type=EdgeType.PUBLISHES_TO, confidence=0.98, evidence=[Evidence(file="src/checkout/main.go", line=290, snippet="producer.Produce(&kafka.Message{TopicPartition: 'orders'})")]),
        GraphEdge(id=f"{repo_id}:oe13", source=f"{repo_id}:queue:kafka", target=f"{repo_id}:svc:fraud", type=EdgeType.SUBSCRIBES_TO, confidence=0.98, evidence=[Evidence(file="src/frauddetection/src/main/kotlin/FraudDetector.kt", line=45, snippet="consumer.subscribe(listOf('orders'))")]),
        GraphEdge(id=f"{repo_id}:oe14", source=f"{repo_id}:queue:kafka", target=f"{repo_id}:svc:accounting", type=EdgeType.SUBSCRIBES_TO, confidence=0.98, evidence=[Evidence(file="src/accounting/main.go", line=65, snippet="consumer.SubscribeTopics([]string{'orders'})")]),
        GraphEdge(id=f"{repo_id}:oe15", source=f"{repo_id}:svc:shipping", target=f"{repo_id}:svc:quote", type=EdgeType.HTTP_CALL, confidence=0.90, evidence=[Evidence(file="src/shipping/src/main.rs", line=88, snippet="reqwest::get('http://quoteservice:8080/getquote')")]),
        GraphEdge(id=f"{repo_id}:oe16", source=f"{repo_id}:svc:cart", target=f"{repo_id}:cache:valkey", type=EdgeType.DB_QUERY, confidence=0.99, evidence=[Evidence(file="src/cart/src/CartService.cs", line=72, snippet="await redisDatabase.StringSetAsync(userId, cart)")]),
        GraphEdge(id=f"{repo_id}:oe17", source=f"{repo_id}:svc:frontend", target=f"{repo_id}:svc:otelcol", type=EdgeType.CALLS, confidence=1.0, evidence=[Evidence(file="src/frontend/utils/telemetry.ts", line=15, snippet="tracerProvider.addSpanProcessor(new BatchSpanProcessor(new OTLPTraceExporter()))")]),
        GraphEdge(id=f"{repo_id}:oe18", source=f"{repo_id}:svc:checkout", target=f"{repo_id}:svc:otelcol", type=EdgeType.CALLS, confidence=1.0, evidence=[Evidence(file="src/checkout/main.go", line=95, snippet="otel.SetTracerProvider(tp)")]),
        GraphEdge(id=f"{repo_id}:oe19", source=f"{repo_id}:svc:otelcol", target=f"{repo_id}:ext:jaeger", type=EdgeType.CALLS, confidence=0.98, evidence=[Evidence(file="src/otelcollector/otelcol-config.yaml", line=45, snippet="exporters: otlp/jaeger: endpoint: 'jaeger:4317'")]),
        GraphEdge(id=f"{repo_id}:oe20", source=f"{repo_id}:svc:otelcol", target=f"{repo_id}:ext:prometheus", type=EdgeType.CALLS, confidence=0.98, evidence=[Evidence(file="src/otelcollector/otelcol-config.yaml", line=52, snippet="exporters: prometheus: endpoint: 'prometheus:8889'")]),
        GraphEdge(id=f"{repo_id}:oe21", source=f"{repo_id}:ext:grafana", target=f"{repo_id}:ext:prometheus", type=EdgeType.DB_QUERY, confidence=0.98, evidence=[Evidence(file="docker-compose.yml", line=140, snippet="datasources: prometheus")]),
        GraphEdge(id=f"{repo_id}:oe22", source=f"{repo_id}:mod:test_checkout", target=f"{repo_id}:svc:checkout", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/checkout/main_test.go", line=30, snippet="TestPlaceOrderSuccess(t *testing.T)")]),
        GraphEdge(id=f"{repo_id}:oe23", source=f"{repo_id}:mod:test_frontend", target=f"{repo_id}:svc:frontend", type=EdgeType.CALLS, confidence=0.95, evidence=[Evidence(file="src/frontend/__tests__/index.test.tsx", line=20, snippet="render(<Home />)")]),
    ]

    arch = ArchitectureGraph(
        repo_id=repo_id,
        nodes=nodes,
        edges=edges,
        built_at=built_at,
        node_count=len(nodes),
        edge_count=len(edges),
    )

    facts = RawFacts(
        repo_id=repo_id,
        language_summary={"go": 35, "typescript": 30, "python": 15, "csharp": 12, "rust": 10, "ruby": 8, "java": 14, "yaml": 20},
        files=[
            FileInfo(path="src/frontend/pages/index.tsx", language=Language.TYPESCRIPT, line_count=180),
            FileInfo(path="src/frontend/pages/api/checkout.ts", language=Language.TYPESCRIPT, line_count=90),
            FileInfo(path="src/frontend/pages/api/cart.ts", language=Language.TYPESCRIPT, line_count=75),
            FileInfo(path="src/frontend/__tests__/index.test.tsx", language=Language.TYPESCRIPT, line_count=65),
            FileInfo(path="src/checkout/main.go", language=Language.GO, line_count=320),
            FileInfo(path="src/checkout/main_test.go", language=Language.GO, line_count=95),
            FileInfo(path="src/cart/src/CartService.cs", language=Language.CSHARP, line_count=160),
            FileInfo(path="src/productcatalog/server.go", language=Language.GO, line_count=150),
            FileInfo(path="src/shipping/src/main.rs", language=Language.RUST, line_count=140),
            FileInfo(path="src/email/email_server.rb", language=Language.RUBY, line_count=110),
            FileInfo(path="src/frauddetection/src/main/kotlin/FraudDetector.kt", language=Language.JAVA, line_count=130),
            FileInfo(path="src/accounting/main.go", language=Language.GO, line_count=140),
            FileInfo(path="src/otelcollector/otelcol-config.yaml", language=Language.YAML, line_count=95),
        ],
        services=[
            ServiceFact(name="frontendproxy", source_file="src/frontendproxy/envoy.yaml", ports=["8080:8080"]),
            ServiceFact(name="frontend", source_file="docker-compose.yml", ports=["3000:3000"]),
            ServiceFact(name="checkoutservice", source_file="docker-compose.yml", ports=["5050:5050"]),
            ServiceFact(name="cartservice", source_file="docker-compose.yml", ports=["7070:7070"]),
            ServiceFact(name="productcatalogservice", source_file="docker-compose.yml", ports=["3550:3550"]),
            ServiceFact(name="paymentservice", source_file="docker-compose.yml", ports=["50051:50051"]),
            ServiceFact(name="shippingservice", source_file="docker-compose.yml", ports=["50051:50051"]),
            ServiceFact(name="emailservice", source_file="docker-compose.yml", ports=["8080:8080"]),
            ServiceFact(name="recommendationservice", source_file="docker-compose.yml", ports=["8080:8080"]),
            ServiceFact(name="adservice", source_file="docker-compose.yml", ports=["9555:9555"]),
            ServiceFact(name="frauddetectionservice", source_file="docker-compose.yml", ports=["8080:8080"]),
            ServiceFact(name="accountingservice", source_file="docker-compose.yml", ports=["8080:8080"]),
            ServiceFact(name="quoteservice", source_file="docker-compose.yml", ports=["8080:8080"]),
            ServiceFact(name="otelcol", source_file="docker-compose.yml", ports=["4317:4317", "4318:4318"]),
        ],
        api_endpoints=[
            APIEndpointFact(file="src/frontend/pages/api/checkout.ts", line=12, method="POST", path="/api/checkout", handler="handler"),
            APIEndpointFact(file="src/frontend/pages/api/cart.ts", line=8, method="POST", path="/api/cart", handler="handler"),
            APIEndpointFact(file="src/frontend/pages/api/products.ts", line=10, method="GET", path="/api/products", handler="handler"),
        ],
        dependencies=[
            DependencyFact(manifest_file="src/frontend/package.json", name="@opentelemetry/api", version_spec="^1.7.0"),
            DependencyFact(manifest_file="src/frontend/package.json", name="next", version_spec="14.1.0"),
            DependencyFact(manifest_file="src/checkout/go.mod", name="go.opentelemetry.io/otel", version_spec="v1.22.0"),
        ],
        build_commands=[
            BuildCommandFact(source_file="docker-compose.yml", name="up", command="docker compose up -d"),
            BuildCommandFact(source_file="src/frontend/package.json", name="test", command="npm test"),
        ],
        hotspots=[
            HotspotFact(file="src/checkout/main.go", change_count=40, unique_authors=9),
            HotspotFact(file="src/frontend/pages/index.tsx", change_count=28, unique_authors=6),
            HotspotFact(file="src/otelcollector/otelcol-config.yaml", change_count=25, unique_authors=5),
        ],
        analysed_at=built_at,
    )

    return facts, arch


# ===========================================================================
# Public helpers
# ===========================================================================

_BUILDERS = {
    FASTAPI_REPO_ID: _build_fastapi_template,
    BOUTIQUE_REPO_ID: _build_boutique_template,
    OTEL_REPO_ID: _build_otel_template,
}


def is_seeded_repo(repo_id: str) -> bool:
    return repo_id in _BUILDERS


def get_seeded_template(url: str, repo_id: str) -> tuple[RawFacts, ArchitectureGraph]:
    """Retrieve prebuilt facts and architecture graph for a seeded URL."""
    if "fastapi" in url:
        return _build_fastapi_template(repo_id)
    if "microservices-demo" in url:
        return _build_boutique_template(repo_id)
    if "opentelemetry" in url:
        return _build_otel_template(repo_id)
    # Default fallback
    return _build_fastapi_template(repo_id)


def get_seeded_template_by_id(repo_id: str) -> tuple[RawFacts, ArchitectureGraph]:
    builder = _BUILDERS.get(repo_id)
    if builder:
        return builder(repo_id)
    return _build_fastapi_template(repo_id)
