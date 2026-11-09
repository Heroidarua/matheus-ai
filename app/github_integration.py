from __future__ import annotations

import base64
import os
import re
import secrets
import time
from typing import Any

import httpx
import jwt
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/github", tags=["GitHub"])

API_ROOT = "https://api.github.com"
API_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "ADA-M-GitHub-App",
}
PROPOSAL_TTL_SECONDS = 15 * 60
PENDING_PROPOSALS: dict[str, dict[str, Any]] = {}


def _config() -> tuple[str, str, str, str]:
    app_id = os.getenv("GITHUB_APP_ID", "").strip()
    slug = os.getenv("GITHUB_APP_SLUG", "").strip()
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n").strip()
    public_url = os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
    session_secret = os.getenv("GITHUB_SESSION_SECRET", "").strip()
    if not all((app_id, slug, private_key, public_url, session_secret)):
        raise HTTPException(
            status_code=503,
            detail="Integração GitHub não configurada. Configure GITHUB_APP_ID, GITHUB_APP_SLUG, GITHUB_APP_PRIVATE_KEY, GITHUB_SESSION_SECRET e PUBLIC_APP_URL no Render.",
        )
    if not public_url.startswith("https://") and not public_url.startswith("http://localhost"):
        raise HTTPException(status_code=503, detail="PUBLIC_APP_URL deve ser uma URL HTTPS pública.")
    return app_id, slug, private_key, public_url


def _app_jwt() -> str:
    app_id, _, private_key, _ = _config()
    now = int(time.time())
    try:
        return jwt.encode({"iat": now - 60, "exp": now + 8 * 60, "iss": app_id}, private_key, algorithm="RS256")
    except Exception as exc:
        print(f"GitHub App JWT creation failed ({type(exc).__name__})")
        raise HTTPException(status_code=503, detail="Não foi possível autenticar o GitHub App. Confira a chave privada configurada.")


async def _github_request(
    method: str,
    path: str,
    *,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    headers = dict(API_HEADERS)
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(25.0, connect=8.0)) as client:
            response = await client.request(method, API_ROOT + path, headers=headers, json=json_body, params=params)
    except httpx.HTTPError as exc:
        print(f"GitHub API connection failed ({type(exc).__name__})")
        raise HTTPException(status_code=502, detail="Não foi possível conectar à API do GitHub.")
    if response.status_code >= 400:
        detail = "A API do GitHub recusou a solicitação."
        try:
            detail = str(response.json().get("message") or detail)
        except (ValueError, AttributeError):
            pass
        print(f"GitHub API HTTP {response.status_code}: {detail[:250]}")
        if response.status_code == 404:
            raise HTTPException(status_code=404, detail="Repositório/arquivo não encontrado ou não autorizado para este aplicativo.")
        if response.status_code in (401, 403):
            raise HTTPException(status_code=403, detail="A instalação do GitHub não tem as permissões necessárias ou foi removida. Confira as permissões do aplicativo.")
        if response.status_code == 422:
            raise HTTPException(status_code=409, detail=f"O GitHub não aceitou a alteração: {detail[:250]}")
        raise HTTPException(status_code=502, detail=f"Erro da API do GitHub ({response.status_code}): {detail[:250]}")
    if response.status_code == 204 or not response.content:
        return {}
    try:
        data = response.json()
        return data if isinstance(data, dict) else {"items": data}
    except ValueError:
        return {}


async def _installation_token(installation_id: int, write: bool = False, pull_requests: bool = False) -> str:
    permissions: dict[str, str] = {"contents": "write" if write else "read"}
    if pull_requests:
        permissions["pull_requests"] = "write"
    data = await _github_request(
        "POST",
        f"/app/installations/{installation_id}/access_tokens",
        token=_app_jwt(),
        json_body={"permissions": permissions},
    )
    token = data.get("token")
    if not isinstance(token, str) or not token:
        raise HTTPException(status_code=502, detail="O GitHub não retornou um token de instalação válido.")
    return token


def _installation_id(request: Request) -> int:
    value = request.session.get("github_installation_id")
    if not isinstance(value, int) or value < 1:
        raise HTTPException(status_code=401, detail="Conecte primeiro uma instalação do GitHub.")
    return value


def _selected_repo(request: Request) -> str:
    repo = request.session.get("github_selected_repo")
    if not isinstance(repo, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise HTTPException(status_code=400, detail="Selecione um repositório autorizado antes de continuar.")
    return repo


def _same_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if not origin:
        return
    _, _, _, public_url = _config()
    if origin.rstrip("/") != public_url:
        raise HTTPException(status_code=403, detail="Origem inválida para esta operação.")


def _session_owner(request: Request) -> str:
    owner = request.session.get("github_proposal_owner")
    if not isinstance(owner, str):
        owner = secrets.token_urlsafe(24)
        request.session["github_proposal_owner"] = owner
    return owner


class SelectRepository(BaseModel):
    repository: str = Field(min_length=3, max_length=200)


class PrepareChanges(BaseModel):
    branch_name: str = Field(min_length=1, max_length=80)
    commit_message: str = Field(min_length=3, max_length=200)
    files: list[dict[str, str]] = Field(min_length=1, max_length=20)


class ConfirmProposal(BaseModel):
    proposal_id: str = Field(min_length=20, max_length=100)


class CreatePullRequest(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    body: str = Field(default="", max_length=10000)


@router.get("/connect")
async def connect_github(request: Request):
    _, slug, _, public_url = _config()
    state = secrets.token_urlsafe(32)
    request.session["github_oauth_state"] = state
    install_url = f"https://github.com/apps/{slug}/installations/new?state={state}"
    return RedirectResponse(install_url, status_code=302)


@router.get("/callback")
async def github_setup_callback(
    request: Request,
    installation_id: int = Query(gt=0),
    setup_action: str = "install",
    state: str = "",
):
    expected = request.session.pop("github_oauth_state", None)
    if not expected or not state or not secrets.compare_digest(str(expected), state):
        raise HTTPException(status_code=400, detail="Estado de autorização inválido ou expirado. Inicie a conexão novamente.")
    if setup_action not in {"install", "update"}:
        raise HTTPException(status_code=400, detail="Instalação do GitHub não concluída.")
    installation = await _github_request("GET", f"/app/installations/{installation_id}", token=_app_jwt())
    account = installation.get("account") or {}
    if not account.get("login"):
        raise HTTPException(status_code=403, detail="Não foi possível validar a instalação do GitHub.")
    request.session["github_installation_id"] = installation_id
    request.session["github_account"] = str(account["login"])[:100]
    request.session.pop("github_selected_repo", None)
    _, _, _, public_url = _config()
    return RedirectResponse(public_url + "/?github=connected", status_code=303)


@router.get("/status")
async def github_status(request: Request) -> dict[str, Any]:
    configured = all(os.getenv(k, "").strip() for k in (
        "GITHUB_APP_ID", "GITHUB_APP_SLUG", "GITHUB_APP_PRIVATE_KEY", "GITHUB_SESSION_SECRET", "PUBLIC_APP_URL"
    ))
    return {
        "configured": configured,
        "connected": isinstance(request.session.get("github_installation_id"), int),
        "account": request.session.get("github_account"),
        "selected_repository": request.session.get("github_selected_repo"),
        "last_branch": request.session.get("github_last_branch"),
    }


@router.get("/repositories")
async def github_repositories(request: Request) -> dict[str, Any]:
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", "/installation/repositories", token=token, params={"per_page": 100})
    repositories = []
    for item in data.get("repositories", []):
        if isinstance(item, dict) and item.get("full_name"):
            repositories.append({
                "full_name": str(item["full_name"]),
                "default_branch": str(item.get("default_branch") or "main"),
                "private": bool(item.get("private", False)),
                "html_url": str(item.get("html_url") or ""),
            })
    return {"repositories": repositories}


@router.post("/select-repository")
async def select_repository(body: SelectRepository, request: Request) -> dict[str, str]:
    _same_origin(request)
    installation_id = _installation_id(request)
    repo = body.repository.strip()
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise HTTPException(status_code=400, detail="Nome de repositório inválido.")
    token = await _installation_token(installation_id)
    data = await _github_request("GET", "/installation/repositories", token=token, params={"per_page": 100})
    allowed = {str(item.get("full_name", "")).casefold() for item in data.get("repositories", []) if isinstance(item, dict)}
    if repo.casefold() not in allowed:
        raise HTTPException(status_code=403, detail="Este repositório não foi autorizado na instalação da ADA-M.")
    request.session["github_selected_repo"] = repo
    request.session.pop("github_last_branch", None)
    return {"selected_repository": repo}


@router.get("/repository")
async def repository_details(request: Request) -> dict[str, Any]:
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}", token=token)
    return {
        "full_name": data.get("full_name"),
        "description": data.get("description"),
        "default_branch": data.get("default_branch"),
        "private": data.get("private"),
        "html_url": data.get("html_url"),
        "updated_at": data.get("updated_at"),
    }


@router.get("/tree")
async def repository_tree(request: Request, path: str = Query(default="", max_length=500)):
    repo = _selected_repo(request)
    clean_path = path.strip().strip("/")
    if clean_path and (".." in clean_path.split("/") or clean_path.startswith(".git/")):
        raise HTTPException(status_code=400, detail="Caminho inválido.")
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}/contents/{clean_path}" if clean_path else f"/repos/{repo}/contents", token=token)
    items = data.get("items", []) if isinstance(data, dict) else []
    if isinstance(data, dict) and data.get("type"):
        items = [data]
    return {"repository": repo, "path": clean_path, "items": [
        {"name": str(item.get("name", "")), "path": str(item.get("path", "")),
         "type": str(item.get("type", "")), "size": int(item.get("size") or 0),
         "html_url": str(item.get("html_url") or "")}
        for item in items if isinstance(item, dict)
    ]}


@router.get("/file")
async def read_repository_file(request: Request, path: str = Query(min_length=1, max_length=500)):
    repo = _selected_repo(request)
    clean_path = path.strip().lstrip("/")
    if not clean_path or ".." in clean_path.split("/") or clean_path.startswith(".git/"):
        raise HTTPException(status_code=400, detail="Caminho de arquivo inválido.")
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}/contents/{clean_path}", token=token)
    if data.get("type") != "file":
        raise HTTPException(status_code=400, detail="O caminho selecionado não é um arquivo.")
    try:
        raw = base64.b64decode(data.get("content", "").replace("\n", ""))
        content = raw.decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(status_code=415, detail="Este arquivo não é texto UTF-8 legível.")
    if len(content) > 250_000:
        raise HTTPException(status_code=413, detail="Arquivo muito grande para editar no chat (limite de 250 KB).")
    return {"repository": repo, "path": clean_path, "content": content, "sha": data.get("sha"), "html_url": data.get("html_url")}


@router.get("/search")
async def search_repository_code(request: Request, q: str = Query(min_length=1, max_length=200)):
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", "/search/code", token=token, params={"q": f"{q} repo:{repo}", "per_page": 20})
    return {"repository": repo, "total_count": data.get("total_count", 0), "items": [
        {"name": str(item.get("name", "")), "path": str(item.get("path", "")),
         "html_url": str(item.get("html_url", ""))}
        for item in data.get("items", []) if isinstance(item, dict)
    ]}


@router.get("/branches")
async def repository_branches(request: Request):
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}/branches", token=token, params={"per_page": 100})
    return {"branches": [{"name": str(item.get("name", "")), "protected": bool(item.get("protected", False))}
                         for item in data.get("items", []) if isinstance(item, dict)]}


@router.get("/commits")
async def repository_commits(request: Request):
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}/commits", token=token, params={"per_page": 20})
    return {"commits": [{"sha": str(item.get("sha", ""))[:7],
                         "message": str(((item.get("commit") or {}).get("message") or "")).splitlines()[0][:200],
                         "url": str(item.get("html_url", ""))}
                        for item in data.get("items", []) if isinstance(item, dict)]}


@router.get("/pull-requests")
async def repository_pull_requests(request: Request, state: str = Query(default="open", pattern="^(open|closed|all)$")):
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request), pull_requests=True)
    data = await _github_request("GET", f"/repos/{repo}/pulls", token=token, params={"state": state, "per_page": 30})
    return {"pull_requests": [{"number": item.get("number"), "title": item.get("title"),
                               "state": item.get("state"), "html_url": item.get("html_url"),
                               "head": (item.get("head") or {}).get("ref"), "base": (item.get("base") or {}).get("ref")}
                              for item in data.get("items", []) if isinstance(item, dict)]}


@router.get("/issues")
async def repository_issues(request: Request, state: str = Query(default="open", pattern="^(open|closed|all)$")):
    repo = _selected_repo(request)
    token = await _installation_token(_installation_id(request))
    data = await _github_request("GET", f"/repos/{repo}/issues", token=token, params={"state": state, "per_page": 30})
    return {"issues": [{"number": item.get("number"), "title": item.get("title"),
                        "state": item.get("state"), "html_url": item.get("html_url")}
                       for item in data.get("items", []) if isinstance(item, dict) and "pull_request" not in item]}


@router.post("/prepare")
async def prepare_repository_changes(body: PrepareChanges, request: Request) -> dict[str, Any]:
    _same_origin(request)
    installation_id = _installation_id(request)
    repo = _selected_repo(request)
    branch = body.branch_name.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,78}[A-Za-z0-9]", branch) or ".." in branch.split("/") or branch in {"main", "master", "develop"}:
        raise HTTPException(status_code=400, detail="Use uma branch separada, como ada-m/correcao-login.")
    files: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in body.files:
        path = str(item.get("path", "")).strip().lstrip("/")
        content = item.get("content")
        if not path or not isinstance(content, str) or len(content) > 500_000:
            raise HTTPException(status_code=400, detail="Cada arquivo precisa de caminho e conteúdo de texto com até 500 KB.")
        if ".." in path.split("/") or path.startswith(".git/") or path in seen:
            raise HTTPException(status_code=400, detail="Caminho inválido ou repetido na lista de alterações.")
        seen.add(path)
        files.append({"path": path, "content": content})
    token = await _installation_token(installation_id)
    repo_info = await _github_request("GET", f"/repos/{repo}", token=token)
    default_branch = str(repo_info.get("default_branch") or "main")
    existing_branches = await _github_request("GET", f"/repos/{repo}/branches", token=token, params={"per_page": 100})
    if branch in {str(item.get("name")) for item in existing_branches.get("items", []) if isinstance(item, dict)}:
        raise HTTPException(status_code=409, detail="Essa branch já existe. Escolha outro nome para evitar sobrescrever trabalho anterior.")
    proposal_id = secrets.token_urlsafe(24)
    owner = _session_owner(request)
    now = time.time()
    for key in list(PENDING_PROPOSALS):
        if PENDING_PROPOSALS[key].get("expires_at", 0) <= now:
            PENDING_PROPOSALS.pop(key, None)
    if len(PENDING_PROPOSALS) >= 100:
        oldest = min(PENDING_PROPOSALS, key=lambda key: PENDING_PROPOSALS[key].get("created_at", 0))
        PENDING_PROPOSALS.pop(oldest, None)
    PENDING_PROPOSALS[proposal_id] = {
        "owner": owner, "repo": repo, "branch": branch, "message": body.commit_message.strip(),
        "files": files, "base": default_branch, "created_at": now, "expires_at": now + PROPOSAL_TTL_SECONDS,
    }
    return {
        "proposal_id": proposal_id, "repository": repo, "branch": branch, "base": default_branch,
        "files": [{"path": item["path"], "characters": len(item["content"])} for item in files],
        "expires_in_seconds": PROPOSAL_TTL_SECONDS,
        "message": "Prévia criada. Nenhum arquivo foi alterado. Confirme explicitamente para gravar somente na nova branch.",
    }


@router.post("/confirm")
async def confirm_repository_changes(body: ConfirmProposal, request: Request) -> dict[str, Any]:
    _same_origin(request)
    installation_id = _installation_id(request)
    owner = _session_owner(request)
    proposal = PENDING_PROPOSALS.get(body.proposal_id)
    if not proposal or proposal.get("expires_at", 0) <= time.time():
        PENDING_PROPOSALS.pop(body.proposal_id, None)
        raise HTTPException(status_code=410, detail="A prévia expirou. Gere uma nova prévia antes de confirmar.")
    if not secrets.compare_digest(str(proposal.get("owner", "")), owner):
        raise HTTPException(status_code=403, detail="Esta prévia pertence a outra sessão.")
    if proposal["repo"] != _selected_repo(request):
        raise HTTPException(status_code=409, detail="O repositório selecionado mudou. Gere a prévia novamente.")
    # Consome a autorização antes de iniciar as escritas, evitando replay do mesmo pedido.
    PENDING_PROPOSALS.pop(body.proposal_id, None)
    token = await _installation_token(installation_id, write=True)
    repo = proposal["repo"]
    base = proposal["base"]
    ref = await _github_request("GET", f"/repos/{repo}/git/ref/heads/{base}", token=token)
    base_sha = str((ref.get("object") or {}).get("sha") or "")
    if not base_sha:
        raise HTTPException(status_code=502, detail="Não foi possível localizar o commit-base do repositório.")
    branch = proposal["branch"]
    await _github_request("POST", f"/repos/{repo}/git/refs", token=token,
                          json_body={"ref": f"refs/heads/{branch}", "sha": base_sha})
    committed: list[str] = []
    for item in proposal["files"]:
        encoded = base64.b64encode(item["content"].encode("utf-8")).decode("ascii")
        existing_sha = None
        try:
            existing = await _github_request("GET", f"/repos/{repo}/contents/{item['path']}", token=token,
                                             params={"ref": branch})
            existing_sha = existing.get("sha")
        except HTTPException as exc:
            if exc.status_code != 404:
                raise
        payload: dict[str, Any] = {"message": proposal["message"], "content": encoded, "branch": branch}
        if existing_sha:
            payload["sha"] = existing_sha
        await _github_request("PUT", f"/repos/{repo}/contents/{item['path']}", token=token, json_body=payload)
        committed.append(item["path"])
    request.session["github_last_branch"] = branch
    return {
        "repository": repo, "branch": branch, "files": committed,
        "url": f"https://github.com/{repo}/tree/{branch}",
        "message": "Alterações gravadas somente na nova branch. A branch principal não foi modificada.",
    }


@router.post("/pull-request")
async def create_repository_pull_request(body: CreatePullRequest, request: Request) -> dict[str, Any]:
    _same_origin(request)
    installation_id = _installation_id(request)
    repo = _selected_repo(request)
    branch = request.session.get("github_last_branch")
    if not isinstance(branch, str) or not branch or branch in {"main", "master", "develop"}:
        raise HTTPException(status_code=409, detail="Primeiro confirme uma proposta de alterações para criar a branch.")
    token = await _installation_token(installation_id, pull_requests=True)
    repo_info = await _github_request("GET", f"/repos/{repo}", token=token)
    default_branch = str(repo_info.get("default_branch") or "main")
    result = await _github_request("POST", f"/repos/{repo}/pulls", token=token, json_body={
        "title": body.title.strip(), "body": body.body.strip(),
        "head": branch, "base": default_branch, "draft": False,
    })
    return {"number": result.get("number"), "html_url": result.get("html_url"),
            "title": result.get("title"), "state": result.get("state"), "base": default_branch, "head": branch}


@router.post("/disconnect")
async def disconnect_github(request: Request) -> dict[str, bool]:
    _same_origin(request)
    for key in ("github_installation_id", "github_account", "github_selected_repo",
                "github_last_branch", "github_oauth_state", "github_proposal_owner"):
        request.session.pop(key, None)
    return {"disconnected": True}
