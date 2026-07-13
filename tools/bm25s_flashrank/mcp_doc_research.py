import os
import sys
import time
from mcp.server.fastmcp import FastMCP
import bm25s
from flashrank import Ranker, RerankRequest

mcp = FastMCP("Monorepo-Markdown-Search")
MD_EXTENSIONS = {'.md', '.mdx'}

# Configurar caché temporal de FlashRank en el perfil del usuario de Windows
user_profile = os.environ.get("USERPROFILE", "C:\\")
flashrank_cache = os.path.join(user_profile, ".cache", "flashrank")

try:
    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2", cache_dir=flashrank_cache)
except Exception:
    ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")

_INDEX_CACHE = {
    "last_project": None,
    "last_check_time": 0,
    "max_mtime": 0,
    "retriever": None,
    "indexed_data": []
}

def extract_text(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception:
        return ""

def get_monorepo_state(repo_path, project_filter):
    max_mtime = 0
    ignored_dirs = {'.git', 'node_modules', 'venv', '.mcp_venv', '__pycache__', 'dist', 'build', '.turbo', '.nx'}
    
    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        if project_filter and project_filter not in root and root != repo_path:
            continue
        for file in files:
            if os.path.splitext(file.lower())[1] in MD_EXTENSIONS:
                try:
                    mtime = os.path.getmtime(os.path.join(root, file))
                    if mtime > max_mtime:
                        max_mtime = mtime
                except Exception:
                    pass
    return max_mtime

def build_monorepo_index(repo_path, project_filter=None):
    global _INDEX_CACHE
    cache_key = f"{repo_path}_{project_filter}"
    current_time = time.time()
    
    if _INDEX_CACHE["last_project"] == cache_key and (current_time - _INDEX_CACHE["last_check_time"]) < 5:
        return _INDEX_CACHE["retriever"], _INDEX_CACHE["indexed_data"]
        
    current_max_mtime = get_monorepo_state(repo_path, project_filter)
    
    if (_INDEX_CACHE["last_project"] == cache_key and 
        _INDEX_CACHE["max_mtime"] == current_max_mtime and 
        _INDEX_CACHE["retriever"] is not None):
        _INDEX_CACHE["last_check_time"] = current_time
        return _INDEX_CACHE["retriever"], _INDEX_CACHE["indexed_data"]

    documents = []
    file_paths = []
    ignored_dirs = {'.git', 'node_modules', 'venv', '.mcp_venv', '__pycache__', 'dist', 'build', '.turbo', '.nx'}

    for root, dirs, files in os.walk(repo_path):
        dirs[:] = [d for d in dirs if d not in ignored_dirs]
        if project_filter and project_filter not in root and root != repo_path:
            continue
                
        for file in files:
            if os.path.splitext(file.lower())[1] in MD_EXTENSIONS:
                full_path = os.path.join(root, file)
                text = extract_text(full_path)
                if text.strip():
                    documents.append(text)
                    file_paths.append(full_path)
                    
    if not documents:
        return None, []
        
    corpus_tokens = bm25s.tokenize(documents, stopwords="english")
    # BM25 constructor signature may vary across versions. Try common variants
    # and fall back to a parameterless constructor to avoid TypeError.
    try:
        retriever = bm25s.BM25(corpus_size=len(documents))
    except TypeError:
        try:
            retriever = bm25s.BM25(len(documents))
        except TypeError:
            retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    
    _INDEX_CACHE["last_project"] = cache_key
    _INDEX_CACHE["last_check_time"] = current_time
    _INDEX_CACHE["max_mtime"] = current_max_mtime
    _INDEX_CACHE["retriever"] = retriever
    _INDEX_CACHE["indexed_data"] = list(zip(file_paths, documents))
    
    return retriever, _INDEX_CACHE["indexed_data"]

@mcp.tool()
def search_documentation(query: str, subproject: str = None, force_refresh: bool = False) -> str:
    """
    Search across all Markdown (.md, .mdx) files in the monorepo.
    
    Args:
        query: The search term or question.
        subproject: Optional. Specific folder/package name (e.g., "apps/api").
        force_refresh: Optional. Set to True to manually bypass cache and force re-indexing.
    """
    global _INDEX_CACHE
    if force_refresh:
        _INDEX_CACHE["last_project"] = None
        
    repo_path = os.getcwd()
    retriever, indexed_data = build_monorepo_index(repo_path, project_filter=subproject)
    
    if not retriever or not indexed_data:
        return f"No markdown documentation found (Filter: {subproject})."
        
    query_tokens = bm25s.tokenize([query], stopwords="english")
    results, _ = retriever.retrieve(query_tokens, k=min(10, len(indexed_data)))

    flash_passages = []
    for raw_idx in results:
        idx = raw_idx
        if not isinstance(idx, int):
            try:
                idx = int(idx)
            except Exception:
                try:
                    idx = int(idx.item())
                except Exception as exc:
                    raise TypeError(f"Unable to convert search result index {raw_idx!r} to int") from exc

        path, text = indexed_data[idx]
        rel_path = os.path.relpath(path, repo_path)
        flash_passages.append({"id": rel_path, "text": text[:4000]})
        
    if not flash_passages:
        return "No relevant markdown documentation matched."
        
    rerank_request = RerankRequest(query=query, passages=flash_passages)
    reranked_results = ranker.rerank(rerank_request)
    
    output = [f"### RELEVANT MARKDOWN (Subproject: {subproject or 'None'}):\n"]
    for item in reranked_results[:3]:
        output.append(f"**File:** {item['id']}")
        output.append(f"**Match Confidence:** {item['score']:.4f}")
        output.append(f"**Content:**\n```markdown\n{item['text']}\n```")
        output.append("-" * 50)
        
    return "\n".join(output)

if __name__ == "__main__":
    mcp.run()
