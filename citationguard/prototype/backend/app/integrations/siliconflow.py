import base64
import os
from dataclasses import dataclass
from typing import Any

import httpx
from langchain_core.embeddings import Embeddings
from langchain_core.messages import HumanMessage


DEFAULT_BASE_URL = "https://api.siliconflow.cn/v1"


@dataclass(frozen=True)
class SiliconFlowSettings:
    api_key: str
    base_url: str
    embedding_model: str
    reranker_model: str
    claim_model: str
    audit_model: str
    reviewer_model: str

    @classmethod
    def from_env(cls) -> "SiliconFlowSettings":
        api_key = os.getenv("SILICONFLOW_API_KEY", "")
        if not api_key:
            raise ValueError("SILICONFLOW_API_KEY is required for SiliconFlow providers")
        return cls(
            api_key=api_key,
            base_url=os.getenv("SILICONFLOW_BASE_URL", DEFAULT_BASE_URL).rstrip("/"),
            embedding_model=os.getenv("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"),
            reranker_model=os.getenv("SILICONFLOW_RERANKER_MODEL", "BAAI/bge-reranker-v2-m3"),
            claim_model=os.getenv("SILICONFLOW_CLAIM_MODEL", "Qwen/Qwen3.5-35B-A3B"),
            audit_model=os.getenv("SILICONFLOW_AUDIT_MODEL", "Qwen/Qwen3.5-122B-A10B"),
            reviewer_model=os.getenv("SILICONFLOW_REVIEWER_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
        )


class SiliconFlowEmbeddings(Embeddings):
    """BGE-M3 embeddings through SiliconFlow's OpenAI-compatible endpoint."""

    def __init__(self, settings: SiliconFlowSettings | None = None) -> None:
        self.settings = settings or SiliconFlowSettings.from_env()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        return self._embed(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text])[0]

    def _embed(self, inputs: list[str]) -> list[list[float]]:
        response = _post_json(
            settings=self.settings,
            path="/embeddings",
            payload={"model": self.settings.embedding_model, "input": inputs, "encoding_format": "float"},
        )
        items = sorted(response["data"], key=lambda item: item.get("index", 0))
        return [item["embedding"] for item in items]


class SiliconFlowReranker:
    def __init__(self, settings: SiliconFlowSettings | None = None) -> None:
        self.settings = settings or SiliconFlowSettings.from_env()

    def rerank(self, query: str, documents: list[str], top_n: int) -> list[tuple[int, float]]:
        if not documents:
            return []
        response = _post_json(
            settings=self.settings,
            path="/rerank",
            payload={
                "model": self.settings.reranker_model,
                "query": query,
                "documents": documents,
                "top_n": min(top_n, len(documents)),
                "return_documents": False,
            },
        )
        return [
            (int(item["index"]), float(item.get("relevance_score", 0)))
            for item in response.get("results", [])
            if 0 <= int(item["index"]) < len(documents)
        ]


class SiliconFlowOcr:
    """Page-level OCR fallback for sparse, scanned PDF pages only."""

    def __init__(self, settings: SiliconFlowSettings | None = None) -> None:
        self.settings = settings or SiliconFlowSettings.from_env()
        self.model_name = os.getenv("SILICONFLOW_OCR_MODEL", "PaddlePaddle/PaddleOCR-VL-1.5")
        from langchain_openai import ChatOpenAI

        self.model = ChatOpenAI(
            model=self.model_name,
            api_key=self.settings.api_key,
            base_url=self.settings.base_url,
            temperature=0,
        )

    def extract_page(self, pdf_path: str, page_index: int) -> str:
        import fitz

        document = fitz.open(pdf_path)
        try:
            page = document.load_page(page_index)
            image = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
            image_data = base64.b64encode(image.tobytes("png")).decode("ascii")
        finally:
            document.close()
        response = self.model.invoke(
            [
                HumanMessage(
                    content=[
                        {
                            "type": "text",
                            "text": "Extract all readable text from this academic PDF page. Preserve paragraph breaks. Return only extracted text; do not summarize or explain.",
                        },
                        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_data}"}},
                    ]
                )
            ]
        )
        return str(response.content).strip()


def _post_json(settings: SiliconFlowSettings, path: str, payload: dict[str, Any]) -> dict[str, Any]:
    response = httpx.post(
        f"{settings.base_url}{path}",
        headers={"Authorization": f"Bearer {settings.api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    return response.json()
