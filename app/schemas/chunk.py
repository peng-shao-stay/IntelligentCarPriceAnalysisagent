"""
Typed Chunk Schema — Semantic Structured Chunking for Car Domain.

Every chunk is strongly typed with a structured chunk_id, typed metadata,
and an embedding_content field optimized for vector search.
"""
from __future__ import annotations

from enum import StrEnum
from typing import List, Optional
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════
#  Enums
# ═══════════════════════════════════════════════════════════════

class ChunkType(StrEnum):
    BRAND = "brand"           # Brand overview / summary
    MODEL = "model"           # Core model chunk — one per model
    FEATURE = "feature"       # Single feature / aspect extraction
    COMPARISON = "comparison" # Cross-model / brand comparison


class VehicleType(StrEnum):
    SEDAN = "轿车"
    SUV = "SUV"
    MPV = "MPV"
    SPORTS = "跑车"
    PICKUP = "皮卡"
    COUPE = "轿跑"


class PowerType(StrEnum):
    BEV = "纯电动"
    EREV = "增程式"
    PHEV = "插电混动"
    ICE = "燃油"
    HYDROGEN = "氢能"


class SmartDriveLevel(StrEnum):
    L2 = "L2"
    L2_PLUS = "L2+"
    L2_PLUS_PLUS = "L2++"
    L3 = "L3"
    L4 = "L4"


class PriceRange(StrEnum):
    BUDGET = "0-15万"
    MID = "15-25万"
    PREMIUM = "25-40万"
    LUXURY = "40-60万"
    ULTRA = "60万+"


# ═══════════════════════════════════════════════════════════════
#  Metadata Models
# ═══════════════════════════════════════════════════════════════

class CarMetadata(BaseModel):
    """Structured metadata for every car-domain chunk.

    This is the canonical metadata schema. Every chunk MUST populate
    as many fields as possible. Missing fields default to empty/None.
    """
    brand: str = ""
    model: str = ""
    price_range: str = ""                     # e.g. "23-34万"
    vehicle_type: str = ""                    # VehicleType value
    power_type: List[str] = Field(default_factory=list)  # PowerType values
    smart_drive: str = ""                     # SmartDriveLevel value
    year: str = ""                            # e.g. "2024"
    source: str = ""                          # source_type: car_price | user_saved | pdf | crawler

    class Config:
        use_enum_values = True


class ChunkMetadata(BaseModel):
    """Extended metadata stored alongside the chunk in the database.

    Includes retrieval signals (keywords, embedding_content) and
    provenance info (source document, chunk position).
    """
    # Core identity
    chunk_id: str = ""                        # e.g. "model:tesla:model3:2024"
    chunk_type: ChunkType = ChunkType.MODEL
    chunk_index: int = 0

    # Car domain metadata
    car: CarMetadata = Field(default_factory=CarMetadata)

    # Retrieval signals
    retrieval_keywords: List[str] = Field(default_factory=list)
    embedding_content: str = ""               # What gets embedded
    topic: str = ""                           # Feature topic if type=feature

    # Provenance
    document_id: Optional[int] = None
    source_uri: str = ""

    class Config:
        use_enum_values = True


# ═══════════════════════════════════════════════════════════════
#  Chunk Models
# ═══════════════════════════════════════════════════════════════

class BrandChunk(BaseModel):
    """Brand-level overview chunk.

    Generated once per brand by aggregating across all model chunks.
    Contains: brand positioning, lineup summary, technology highlights.

    chunk_id format: "brand:{brand}"
    Example: "brand:特斯拉"
    """
    chunk_id: str
    chunk_type: ChunkType = ChunkType.BRAND
    brand: str
    metadata: CarMetadata
    embedding_content: str
    retrieval_keywords: List[str]
    content: str                              # Original brand overview text

    @classmethod
    def build_chunk_id(cls, brand: str) -> str:
        return f"brand:{brand}"


class ModelChunk(BaseModel):
    """Core model chunk — ONE per model variant.

    Contains the full model description: price, specs, features, positioning.
    This is the primary retrieval target for user queries.

    chunk_id format: "model:{brand}:{model}:{year}"
    Example: "model:特斯拉:Model 3:2024"
    """
    chunk_id: str
    chunk_type: ChunkType = ChunkType.MODEL
    brand: str
    model: str
    metadata: CarMetadata
    embedding_content: str
    retrieval_keywords: List[str]
    content: str                              # Full model description

    @classmethod
    def build_chunk_id(cls, brand: str, model: str, year: str = "") -> str:
        base = f"model:{brand}:{model}"
        return f"{base}:{year}" if year else base


class FeatureChunk(BaseModel):
    """Single-aspect feature extraction from a model.

    Extracts one dimension (智驾/续航/价格/空间/安全/座舱 etc.)
    into a standalone chunk for precise aspect-level retrieval.

    chunk_id format: "feature:{brand}:{model}:{topic}"
    Example: "feature:问界:M9:智驾"
    """
    chunk_id: str
    chunk_type: ChunkType = ChunkType.FEATURE
    brand: str
    model: str
    topic: str                                # e.g. "智驾", "续航", "价格"
    metadata: CarMetadata
    embedding_content: str
    retrieval_keywords: List[str]
    content: str                              # Feature-specific text

    @classmethod
    def build_chunk_id(cls, brand: str, model: str, topic: str) -> str:
        return f"feature:{brand}:{model}:{topic}"


class ComparisonChunk(BaseModel):
    """Cross-model or cross-brand comparison chunk.

    Generated when multiple brands/models are discussed together.
    Used for comparison queries like "Model 3 vs 汉 EV".

    chunk_id format: "comparison:{brand1}+{brand2}"
    Example: "comparison:特斯拉+比亚迪"
    """
    chunk_id: str
    chunk_type: ChunkType = ChunkType.COMPARISON
    brands: List[str]                         # All brands compared
    models: List[str]                         # All models compared
    metadata: CarMetadata                     # Primary brand/model in metadata
    embedding_content: str
    retrieval_keywords: List[str]
    content: str                              # Comparison text
    comparison_dimensions: List[str] = Field(default_factory=list)  # e.g. ["价格","续航"]

    @classmethod
    def build_chunk_id(cls, brands: List[str]) -> str:
        return f"comparison:{'+'.join(sorted(brands))}"


# ═══════════════════════════════════════════════════════════════
#  Search / Retrieval Models
# ═══════════════════════════════════════════════════════════════

class SearchFilters(BaseModel):
    """Typed metadata filters for structured retrieval."""
    brand: Optional[str] = None
    model: Optional[str] = None
    chunk_type: Optional[ChunkType] = None
    vehicle_type: Optional[str] = None
    power_type: Optional[str] = None
    smart_drive: Optional[str] = None
    price_range: Optional[str] = None
    year: Optional[str] = None
    topic: Optional[str] = None               # For feature chunk filtering

    class Config:
        use_enum_values = True


class SearchResult(BaseModel):
    """Typed search result from structured retrieval."""
    chunk_id: str
    chunk_type: ChunkType
    brand: str
    model: str
    content: str
    similarity: float                         # Vector similarity score
    bm25_score: float = 0.0                   # BM25 keyword score
    combined_score: float = 0.0               # Fused hybrid score
    metadata: CarMetadata
    retrieval_keywords: List[str] = Field(default_factory=list)
    document_id: Optional[int] = None
    title: str = ""
    source_url: str = ""

    class Config:
        use_enum_values = True


class ChunkingResult(BaseModel):
    """Result of the chunking pipeline for a single document."""
    document_title: str
    brand: str
    model: str
    total_chunks: int
    brand_chunks: List[BrandChunk] = Field(default_factory=list)
    model_chunks: List[ModelChunk] = Field(default_factory=list)
    feature_chunks: List[FeatureChunk] = Field(default_factory=list)
    comparison_chunks: List[ComparisonChunk] = Field(default_factory=list)

    @property
    def all_chunks(self) -> list:
        """Flatten all chunk types into a single sequence for embedding."""
        chunks = []
        chunks.extend(self.brand_chunks)
        chunks.extend(self.model_chunks)
        chunks.extend(self.feature_chunks)
        chunks.extend(self.comparison_chunks)
        return chunks
