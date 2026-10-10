"""Provider transport. Secrets are encrypted at rest and never returned by APIs."""
import math
import os
import re
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet

from server.core import now


def cipher(store):
    path = store.root / "master.key"
    if not path.exists():
        try:
            with path.open("xb") as out:
                out.write(Fernet.generate_key())
            os.chmod(path, 0o600)
        except FileExistsError:
            pass
    return Fernet(path.read_bytes())


def save_provider(store, payload):
    r = dict(payload)
    if not re.fullmatch(r"[\w-]{1,80}", r.get("id", "")) or r.get("kind") not in {"openai", "anthropic", "ollama"} or not r.get("model"):
        raise ValueError("请填写配置名称、接口类型和模型")
    url = urlparse(r.get("base_url", ""))
    if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password:
        raise ValueError("模型地址无效")
    if url.scheme == "http" and url.hostname not in {"localhost", "127.0.0.1", "::1"}:
        raise ValueError("远程模型接口必须使用 HTTPS")
    for key in ("input_price", "output_price"):
        if r.get(key) is not None and (not isinstance(r[key], (int, float)) or not math.isfinite(r[key]) or r[key] < 0):
            raise ValueError("价格必须为每百万 token 的非负人民币数值")
    if r.get("api_key"):
        r["api_key"] = cipher(store).encrypt(r["api_key"].encode()).decode()
    else:
        try:
            r["api_key"] = store.get("providers", r["id"]).get("api_key", "")
        except KeyError:
            r["api_key"] = ""
    r.update(updated_at=now(), price_currency="CNY", price_source=r.get("price_source", "用户配置"))
    store.save("providers", r)
    return {**{k: v for k, v in r.items() if k != "api_key"}, "has_key": bool(r.get("api_key"))}


def load_provider(store, identity):
    try:
        p = store.get("providers", identity)
    except KeyError:
        raise ValueError("尚未配置所选模型，请先到设置中添加") from None
    if p.get("api_key"):
        p["api_key"] = cipher(store).decrypt(p["api_key"].encode()).decode()
    if p["kind"] != "ollama" and not p.get("api_key"):
        raise ValueError("此模型需要 API 密钥")
    return p


def prices(provider):
    if provider["kind"] == "ollama":
        return 0, 0
    if provider.get("input_price") is None or provider.get("output_price") is None:
        raise ValueError("付费模型价格未知，请先填写输入及输出单价")
    return provider["input_price"], provider["output_price"]


async def list_models(store, identity):
    p = load_provider(store, identity)
    suffix = "/api/tags" if p["kind"] == "ollama" else "/models"
    headers = {"Authorization": "Bearer " + p["api_key"]} if p.get("api_key") else {}
    if p["kind"] == "anthropic":
        headers = {"x-api-key": p["api_key"], "anthropic-version": "2023-06-01"}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(p["base_url"].rstrip("/") + suffix, headers=headers)
        if response.is_error:
            raise ValueError(f"模型列表请求失败：HTTP {response.status_code}；检查地址和密钥")
        data = response.json()
    return {"models": [x.get("id", x.get("name")) for x in data.get("data", data.get("models", []))], "checked_at": now()}


async def completion(p, system, messages, max_output=2048, temperature=0):
    base = p["base_url"].rstrip("/")
    if p["kind"] == "anthropic":
        url = base + "/messages"
        headers = {"x-api-key": p["api_key"], "anthropic-version": "2023-06-01"}
        payload = {"model": p["model"], "system": system, "messages": messages, "max_tokens": max_output, "temperature": temperature}
    elif p["kind"] == "ollama":
        url, headers = base + "/api/chat", {}
        payload = {"model": p["model"], "messages": [{"role": "system", "content": system}, *messages], "stream": False,
                   "options": {"temperature": temperature, "num_predict": max_output}}
    else:
        url = base + "/chat/completions"
        headers = {"Authorization": "Bearer " + p["api_key"]}
        payload = {"model": p["model"], "messages": [{"role": "system", "content": system}, *messages], "max_tokens": max_output, "temperature": temperature}
    async with httpx.AsyncClient(timeout=httpx.Timeout(120, connect=15), follow_redirects=False) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.is_error:
            raise ValueError(f"模型请求失败 HTTP {response.status_code}；请检查配置或配额")
        data = response.json()
    if p["kind"] == "anthropic":
        text = "\n".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        usage = data.get("usage", {})
        return text, usage.get("input_tokens"), usage.get("output_tokens"), data.get("model", p["model"])
    if p["kind"] == "ollama":
        return data["message"]["content"], data.get("prompt_eval_count"), data.get("eval_count"), data.get("model", p["model"])
    usage = data.get("usage", {})
    return data["choices"][0]["message"].get("content") or "", usage.get("prompt_tokens"), usage.get("completion_tokens"), data.get("model", p["model"])
