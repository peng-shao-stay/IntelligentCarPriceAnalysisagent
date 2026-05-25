"""
Semantic Structured Chunking Engine — Car Domain.

Produces typed chunks: Brand → Model (core) → Feature → Comparison.
Every chunk has: chunk_id, chunk_type, brand, model, metadata,
embedding_content, retrieval_keywords.

Rules enforced:
  - NO RecursiveCharacterTextSplitter
  - NO fixed-size character splitting
  - One model → one core ModelChunk
  - Features extracted as standalone FeatureChunks
  - Brand summaries auto-generated
  - Metadata auto-populated
  - Multi-model content split into separate model chunks
"""
from __future__ import annotations

import hashlib
import re
from typing import Dict, List, Optional, Tuple

from app.core.logging import logger
from app.schemas.chunk import (
    BrandChunk, ModelChunk, FeatureChunk, ComparisonChunk,
    CarMetadata, ChunkingResult,
    ChunkType, VehicleType, PowerType, SmartDriveLevel,
)


# ═══════════════════════════════════════════════════════════════
#  Token Estimation
# ═══════════════════════════════════════════════════════════════

def estimate_tokens(text: str) -> int:
    """Estimate token count for mixed Chinese/English text.

    Chinese chars ~0.5 tokens, English/non-CJK ~0.25 tokens each.
    """
    if not text:
        return 0
    cjk = sum(1 for c in text if '一' <= c <= '鿿')
    other = len(text) - cjk
    return (cjk // 2) + (other // 4)


# ═══════════════════════════════════════════════════════════════
#  Brand / Model Detection
# ═══════════════════════════════════════════════════════════════

_BRAND_MAP: Dict[str, str] = {
    # English → Chinese
    "tesla": "特斯拉", "byd": "比亚迪", "nio": "蔚来", "xpeng": "小鹏",
    "li auto": "理想", "zeekr": "极氪", "aito": "问界", "xiaomi": "小米",
    "audi": "奥迪", "bmw": "宝马", "benz": "奔驰", "vw": "大众",
    "toyota": "丰田", "honda": "本田", "nissan": "日产",
    "geely": "吉利", "gwm": "长城", "changan": "长安", "chery": "奇瑞",
    "gac": "广汽", "saic": "上汽", "lynk": "领克",
    "voyah": "岚图", "im": "智己", "avatr": "阿维塔",
    "deepal": "深蓝", "leapmotor": "零跑", "neta": "哪吒",
    "seres": "赛力斯", "denza": "腾势", "yangwang": "仰望",
    "方程豹": "方程豹",
    # Chinese → Chinese (self-map)
    "特斯拉": "特斯拉", "比亚迪": "比亚迪", "蔚来": "蔚来",
    "小鹏": "小鹏", "理想": "理想", "极氪": "极氪", "问界": "问界",
    "小米": "小米", "奥迪": "奥迪", "宝马": "宝马", "奔驰": "奔驰",
    "大众": "大众", "丰田": "丰田", "本田": "本田", "日产": "日产",
    "吉利": "吉利", "长城": "长城", "长安": "长安", "奇瑞": "奇瑞",
    "广汽": "广汽", "上汽": "上汽", "领克": "领克",
    "岚图": "岚图", "智己": "智己", "阿维塔": "阿维塔",
    "深蓝": "深蓝", "零跑": "零跑", "哪吒": "哪吒",
    "享界": "享界", "智界": "智界", "尊界": "尊界",
    "赛力斯": "赛力斯", "腾势": "腾势", "仰望": "仰望",
}

_BRAND_DETECT_RE = re.compile(
    '|'.join(re.escape(b) for b in sorted(_BRAND_MAP.keys(), key=len, reverse=True)),
    re.IGNORECASE,
)

# Model patterns — ordered by specificity (longer patterns first)
_MODEL_PATTERNS: List[Tuple[str, str]] = [
    # (regex, brand_hint)
    (r'model\s*[3ysx3YSX]', "特斯拉"),
    (r'cybertruck', "特斯拉"),
    # BYD dynasty / ocean series — single-char names require context
    (r'海豹|海狮|海豚|海鸥', "比亚迪"),
    # 汉/秦/宋/唐/元 MUST have brand prefix OR a model suffix (EV, DM-i, PLUS, etc.)
    # to avoid matching standalone chars like 元 in prices (￥231,900 元)
    (r'比亚迪\s*(?:汉|秦|宋|唐|元)', "比亚迪"),
    (r'(?:汉|秦|宋|唐|元)\s*(?:EV|DM[-\s]?i|PLUS|PRO|MAX|荣耀|冠军|创世|千山翠)', "比亚迪"),
    (r'驱逐舰\s*0[5-7]', "比亚迪"),
    (r'护卫舰\s*0[7-9]', "比亚迪"),
    (r'仰望\s*[uU]?[89]', "仰望"),
    (r'腾势\s*[DNZdnz]?\d+', "腾势"),
    (r'方程豹\s*(?:豹)?[358]', "方程豹"),
    # NIO
    (r'et[579]|es[68]|ec[67]|ep\d+', "蔚来"),
    # XPeng
    (r'p[57][\+]?|g[369]|x9|mona', "小鹏"),
    # Li Auto
    (r'l[6789]|mega|one', "理想"),
    # AITO / Harmony
    (r'(?:问界|aito)\s*m[579]', "问界"),
    (r'(?:智界|zhijie)\s*s7', "智界"),
    (r'(?:享界|xiangjie)\s*s9', "享界"),
    (r'(?:尊界|zunjie)\s*s\d+', "尊界"),
    # Xiaomi
    (r'su7(?:\s*ultra)?', "小米"),
    # Zeekr
    (r'(?:极氪\s*)?00[1-9]|009|x\b|fr\b', "极氪"),
    # IM
    (r'智己\s*[Ll][Ss]?[67]', "智己"),
    # Avatr
    (r'阿维塔\s*1[12]', "阿维塔"),
    # Deepal
    (r'深蓝\s*[SsLl]?0?[357]', "深蓝"),
    # Leapmotor
    (r'零跑\s*[CTc]\d+', "零跑"),
    # Neta
    (r'哪吒\s*[SUVXHsuvxh]?\d*', "哪吒"),
    # Generic patterns
    (r'(?<!\w)[A-Z]{1,2}\d{2,3}(?!\w)', ""),  # S90, G63, X5
]

_MODEL_RE = re.compile(
    '|'.join(f'(?:{p})' for p, _ in _MODEL_PATTERNS),
    re.IGNORECASE,
)

# Sentence boundary detection
_SENTENCE_END_RE = re.compile(r'(?<=[。！？；.!?])\s*')

# Car-domain topic boundary patterns (for feature extraction)
_TOPIC_PATTERNS: Dict[str, re.Pattern] = {
    "价格": re.compile(r'(?:价格|售价|报价|定价|指导价|落地价|裸车价|优惠|降价|行情|经销商报价|二手价)'),
    "续航": re.compile(r'(?:续航|电池|能耗|充电|电量|百公里能耗|电耗|电池容量|快充|慢充|续航里程|CLTC|NEDC|WLTC|充电桩|换电)'),
    "动力": re.compile(r'(?:马力|加速|动力|性能|百公里|扭矩|极速|驱动|电机|功率|零百|0-100|四驱|后驱|前驱|双电机|单电机)'),
    "智驾": re.compile(r'(?:智驾|辅助驾驶|自动驾驶|ADAS|NOA|NGP|NOP|FSD|自动泊车|车道保持|自适应巡航|领航|智驾芯片|算力|激光雷达|毫米波|摄像头|传感器|端到端)'),
    "空间": re.compile(r'(?:空间|座椅|内饰|舒适|底盘|悬架|NVH|静音|空调|天窗|乘坐|储物|后备箱|行李箱|轴距|车身尺寸)'),
    "安全": re.compile(r'(?:安全|碰撞|气囊|AEB|主动安全|被动安全|五星|C-NCAP|中保研|Euro NCAP|IIHS|刹车|制动)'),
    "外观": re.compile(r'(?:外观|设计|颜色|车灯|轮毂|天幕|风阻|车身尺寸|长宽高)'),
    "座舱": re.compile(r'(?:座舱|芯片|屏幕|音响|语音|车机|OTA|导航|HUD|仪表|中控|骁龙|8155|8295|HyperOS|DiLink|智能座舱)'),
}


# ═══════════════════════════════════════════════════════════════
#  Detection Functions
# ═══════════════════════════════════════════════════════════════

def identify_brand(text: str) -> Optional[str]:
    """Identify the primary car brand from text. Returns canonical Chinese name."""
    lowered = text.lower()
    # Sort by key length descending to match longest alias first
    for alias, canonical in sorted(_BRAND_MAP.items(), key=lambda x: -len(x[0])):
        if alias.lower() in lowered:
            return canonical
    return None


def identify_all_brands(text: str) -> List[str]:
    """Identify ALL car brands mentioned in text (for comparison detection)."""
    found = []
    lowered = text.lower()
    for alias, canonical in sorted(_BRAND_MAP.items(), key=lambda x: -len(x[0])):
        if alias.lower() in lowered and canonical not in found:
            found.append(canonical)
    return found


def identify_model(text: str, brand: Optional[str] = None) -> Optional[str]:
    """Extract car model name from text."""
    match = _MODEL_RE.search(text)
    if not match:
        return None
    raw = match.group(0).strip()
    normalized = _normalize_model_name(raw)
    # Strip leading brand name if known
    if brand and normalized.startswith(brand):
        normalized = normalized[len(brand):].strip()
    return normalized


def identify_all_models(text: str) -> List[Tuple[str, str]]:
    """Extract all (brand, model) pairs from text."""
    pairs = []
    seen: set = set()
    for m in _MODEL_RE.finditer(text):
        raw = _normalize_model_name(m.group(0).strip())
        brand = _resolve_brand_for_model(raw, text)
        key = (brand or "", raw)
        if not _is_duplicate_model(key, seen):
            pairs.append((brand, raw))
            seen.add(key)
    return pairs


def _is_duplicate_model(key: tuple, seen: set) -> bool:
    """Check if a (brand, model) key is a duplicate, handling partial matches.

    e.g. ('比亚迪', '汉') and ('比亚迪', '汉 EV') should be deduped to keep '汉 EV'.
    Case-insensitive: ('理想', 'L8') and ('理想', 'l8') are duplicates.
    """
    b, m = key
    b_lower = b.lower()
    m_lower = m.lower()
    for sb, sm in seen:
        if sb.lower() != b_lower:
            continue
        if m_lower == sm.lower():
            return True
        # Partial match: one is substring of the other
        if m_lower in sm.lower() or sm.lower() in m_lower:
            return True
    return False


def _normalize_model_name(raw: str) -> str:
    """Normalize model name variations to a canonical form.

    e.g. 'model3' → 'Model 3', '比亚迪汉' → '汉', '汉 EV' → '汉 EV'
    """
    raw = raw.strip()
    # Strip known brand prefixes from model names
    for brand_name in _BRAND_MAP.values():
        if raw.startswith(brand_name) and len(raw) > len(brand_name):
            raw = raw[len(brand_name):].strip()
            break

    # Tesla: normalize spacing/formatting
    m = re.match(r'model\s*([3ysx3YSX])', raw, re.IGNORECASE)
    if m:
        suffix = m.group(1).upper()
        return f"Model {suffix}"

    # Uppercase single-letter+number model names: l8 → L8, s7 → S7, x9 → X9
    m = re.match(r'([a-z])(\d+)', raw, re.IGNORECASE)
    if m and len(raw) <= 5:
        return f"{m.group(1).upper()}{m.group(2)}"

    # Uppercase all-caps model names: et5 → ET5, es6 → ES6
    if re.match(r'^[a-z]{2,3}\d+$', raw, re.IGNORECASE):
        return raw.upper()

    return raw


def _resolve_brand_for_model(model_text: str, full_text: str) -> Optional[str]:
    """Try to resolve which brand a model pattern belongs to."""
    for pattern, brand_hint in _MODEL_PATTERNS:
        if re.search(pattern, model_text, re.IGNORECASE):
            if brand_hint:
                return brand_hint
            break
    # Fallback: find nearest brand mention in text
    return identify_brand(full_text)


# ═══════════════════════════════════════════════════════════════
#  Metadata Extraction
# ═══════════════════════════════════════════════════════════════

_VEHICLE_TYPE_MAP = {
    "轿车": ["轿车", "轿跑", "sedan", "三厢", "两厢"],
    "SUV": ["suv", "越野", "城市suv", "轿跑suv", "coupe suv"],
    "MPV": ["mpv", "商务车", "保姆车"],
    "跑车": ["跑车", "coupe", "超跑", "敞篷", "roadster"],
    "皮卡": ["皮卡", "pickup", "卡车"],
}

_POWER_TYPE_MAP = {
    "纯电动": ["纯电", "纯电动", "电动", "bev", "ev", "电池", "充电"],
    "增程式": ["增程", "增程式", "erev", "增程器", "增程电动"],
    "插电混动": ["插电", "插混", "phev", "混动"],
    "燃油": ["燃油", "汽油", "柴油", "ice", "油车", "内燃机"],
    "氢能": ["氢", "燃料电池", "fcev", "氢能"],
}

_SMART_DRIVE_MAP = {
    "L2": ["l2", "车道保持", "自适应巡航", "acc", "lka", "辅助驾驶", "adas",
           "自动泊车", "apa", "aeb", "主动安全"],
    "L2+": ["l2+", "高速noa", "高速ngp", "高速nop", "领航辅助", "导航辅助",
            "高速辅助", "自动变道", "自动超车", "自动上下匝道"],
    "L2++": ["l2++", "城市noa", "城市ngp", "城市nop", "城区辅助", "城市智驾",
             "全场景", "通勤模式", "记忆泊车", "代客泊车", "端到端"],
    "L3": ["l3", "fsd", "完全自动驾驶", "full self-driving", "有条件自动驾驶"],
    "L4": ["l4", "无人驾驶", "全自动驾驶", "robotaxi", "高度自动驾驶"],
}

_PRICE_RE = re.compile(
    r'(\d[\d,.]*)\s*(?:万|万元|w|W)\s*(?:[-~到至]\s*(\d[\d,.]*)\s*(?:万|万元|w|W))?'
    r'|'
    r'(\d[\d,.]*)\s*(?:元|块|yuan)\s*(?:[-~到至]\s*(\d[\d,.]*)\s*(?:元|块|yuan))?'
)


def extract_metadata(text: str, brand: str = "", model: str = "", source: str = "") -> CarMetadata:
    """Extract structured CarMetadata from text.

    Uses provided brand/model if given; otherwise auto-detects from text.
    """
    if not brand:
        brand = identify_brand(text) or ""
    if not model:
        model = identify_model(text, brand=brand) or ""

    price_range = _extract_price_range(text)
    vehicle_type = _extract_vehicle_type(text)
    power_type = _extract_power_type(text)
    smart_drive = _extract_smart_drive(text)
    year = _extract_year(text)

    return CarMetadata(
        brand=brand,
        model=model,
        price_range=price_range,
        vehicle_type=vehicle_type,
        power_type=power_type,
        smart_drive=smart_drive,
        year=year,
        source=source,
    )


def _extract_price_range(text: str) -> str:
    matches = _PRICE_RE.findall(text)
    if not matches:
        return ""
    for m in matches:
        if m[0]:
            lo = float(m[0].replace(",", ""))
            hi = float(m[1].replace(",", "")) if m[1] else lo
        elif m[2]:
            lo = float(m[2].replace(",", "")) / 10000
            hi = float(m[3].replace(",", "")) / 10000 if m[3] else lo
        else:
            continue
        lo_int, hi_int = int(lo), int(hi)
        if lo_int == hi_int:
            return f"{lo_int}万"
        return f"{lo_int}-{hi_int}万"
    return ""


def _extract_vehicle_type(text: str) -> str:
    lowered = text.lower()
    for vtype, keywords in _VEHICLE_TYPE_MAP.items():
        for kw in keywords:
            if kw in lowered:
                return vtype
    return ""


def _extract_power_type(text: str) -> List[str]:
    found = []
    lowered = text.lower()
    for ptype, keywords in _POWER_TYPE_MAP.items():
        for kw in keywords:
            if kw in lowered:
                found.append(ptype)
                break
    return found


def _extract_smart_drive(text: str) -> str:
    lowered = text.lower()
    for level, keywords in sorted(_SMART_DRIVE_MAP.items(), reverse=True):
        for kw in keywords:
            if kw in lowered:
                return level
    return ""


def _extract_year(text: str) -> str:
    m = re.search(r'(20\d{2})\s*(?:款|年|式|model|型)', text)
    if m:
        return m.group(1)
    m = re.search(r'(20\d{2})', text)
    return m.group(1) if m else ""


# ═══════════════════════════════════════════════════════════════
#  Keyword Generation
# ═══════════════════════════════════════════════════════════════

def generate_keywords(brand: str, model: str, metadata: CarMetadata, topic: str = "") -> List[str]:
    """Generate weighted retrieval keywords for hybrid search.

    Ordered by retrieval importance: brand > model > type > specs.
    """
    keywords: List[str] = []

    # Tier 1: Brand
    if brand:
        keywords.append(brand)
        for alias, canonical in _BRAND_MAP.items():
            if canonical == brand and alias != brand:
                keywords.append(alias)

    # Tier 2: Model
    if model:
        keywords.append(model)

    # Tier 3: Topic (for feature chunks)
    if topic:
        keywords.append(topic)

    # Tier 4: Vehicle type
    if metadata.vehicle_type:
        keywords.append(metadata.vehicle_type)

    # Tier 5: Power/energy
    for pt in metadata.power_type:
        keywords.append(pt)

    # Tier 6: Price bucket
    if metadata.price_range:
        keywords.append(metadata.price_range)

    # Tier 7: Smart drive
    if metadata.smart_drive:
        keywords.append(f"{metadata.smart_drive}智驾")
        keywords.append(metadata.smart_drive)

    # Tier 8: Year
    if metadata.year:
        keywords.append(metadata.year)
        keywords.append(f"{metadata.year}款")

    return keywords


# ═══════════════════════════════════════════════════════════════
#  Embedding Content Builder
# ═══════════════════════════════════════════════════════════════

def build_embedding_content(
    brand: str = "",
    model: str = "",
    metadata: Optional[CarMetadata] = None,
    original_text: str = "",
    topic: str = "",
) -> str:
    """Build dense embedding text with keyword enrichment.

    Structure: [品牌 车型 类型 价格 动力 智驾] — [topic] — [原文] — [keywords]

    Prefix/suffix keyword saturation biases the embedding toward the
    most important retrieval dimensions without semantic distortion.
    """
    prefix_parts = []
    if brand:
        prefix_parts.append(brand)
    if model:
        prefix_parts.append(model)
    if topic:
        prefix_parts.append(topic)
    if metadata:
        if metadata.vehicle_type:
            prefix_parts.append(metadata.vehicle_type)
        if metadata.price_range:
            prefix_parts.append(metadata.price_range)
        power = "/".join(metadata.power_type)
        if power:
            prefix_parts.append(power)
        if metadata.smart_drive:
            prefix_parts.append(metadata.smart_drive)
        if metadata.year:
            prefix_parts.append(metadata.year)

    prefix = " ".join(prefix_parts)

    kg = generate_keywords(brand, model, metadata or CarMetadata(), topic)
    suffix = " ; ".join(kg)

    return f"{prefix}\n{original_text}\n[{suffix}]"


# ═══════════════════════════════════════════════════════════════
#  Feature Extraction
# ═══════════════════════════════════════════════════════════════

def _extract_features_from_model_text(
    text: str,
    brand: str,
    model: str,
    metadata: CarMetadata,
    source: str,
) -> List[FeatureChunk]:
    """Extract individual feature chunks from a model's full text.

    Scans for car-domain topic boundaries and isolates sections that
    focus on a single aspect (智驾, 续航, 价格, 空间, etc.).
    Only creates feature chunks for sections with sufficient content.
    """
    features: List[FeatureChunk] = []

    # Split text into paragraphs
    paragraphs = re.split(r'\n\s*\n', text)
    if len(paragraphs) <= 1:
        # Try sentence-level extraction
        sentences = _SENTENCE_END_RE.split(text)
        sentences = [s.strip() for s in sentences if s.strip() and len(s.strip()) > 10]
        if len(sentences) <= 2:
            return features
        paragraphs = sentences

    # Group consecutive paragraphs by topic
    current_topic = ""
    current_text = ""

    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 5:
            continue

        topic = _detect_primary_topic(para)

        if topic and topic != current_topic and current_text.strip():
            # Save previous topic group
            if estimate_tokens(current_text) >= 30:
                features.append(_build_feature_chunk(
                    text=current_text.strip(),
                    brand=brand,
                    model=model,
                    topic=current_topic,
                    parent_metadata=metadata,
                    source=source,
                ))
            current_text = para
            current_topic = topic
        else:
            if not current_topic:
                current_topic = topic or ""
            current_text += "\n" + para

    # Don't forget the last group
    if current_text.strip() and current_topic and estimate_tokens(current_text) >= 30:
        features.append(_build_feature_chunk(
            text=current_text.strip(),
            brand=brand,
            model=model,
            topic=current_topic,
            parent_metadata=metadata,
            source=source,
        ))

    return features


def _detect_primary_topic(text: str) -> Optional[str]:
    """Detect the primary car-domain topic of a text segment."""
    for topic, pattern in _TOPIC_PATTERNS.items():
        if pattern.search(text):
            return topic
    return None


def _build_feature_chunk(
    text: str,
    brand: str,
    model: str,
    topic: str,
    parent_metadata: CarMetadata,
    source: str,
) -> FeatureChunk:
    """Build a FeatureChunk from extracted feature text."""
    chunk_id = FeatureChunk.build_chunk_id(brand, model, topic)
    feat_meta = CarMetadata(
        brand=brand,
        model=model,
        price_range=parent_metadata.price_range,
        vehicle_type=parent_metadata.vehicle_type,
        power_type=parent_metadata.power_type,
        smart_drive=parent_metadata.smart_drive if topic == "智驾" else "",
        year=parent_metadata.year,
        source=source,
    )
    embedding_content = build_embedding_content(
        brand=brand, model=model, metadata=feat_meta,
        original_text=text, topic=topic,
    )
    keywords = generate_keywords(brand, model, feat_meta, topic)

    return FeatureChunk(
        chunk_id=chunk_id,
        brand=brand,
        model=model,
        topic=topic,
        metadata=feat_meta,
        embedding_content=embedding_content,
        retrieval_keywords=keywords,
        content=text,
    )


# ═══════════════════════════════════════════════════════════════
#  Brand Summary Generator
# ═══════════════════════════════════════════════════════════════

def _build_brand_chunk(
    brand: str,
    model_chunks: List[ModelChunk],
    feature_chunks: List[FeatureChunk],
    source: str,
) -> BrandChunk:
    """Generate a brand-level summary chunk from constituent model/feature chunks.

    Aggregates key information: which models exist, price range, technology
    highlights, brand positioning signals.
    """
    models_list = sorted(set(
        c.model for c in model_chunks if c.brand == brand
    ))
    features_list = sorted(set(
        f"{f.model}:{f.topic}" for f in feature_chunks if f.brand == brand
    ))

    # Build synthetic brand overview
    parts = [f"{brand}品牌概览"]
    if models_list:
        parts.append(f"在售车型: {', '.join(models_list)}")

    # Aggregate price range
    prices = [
        m.metadata.price_range for m in model_chunks
        if m.brand == brand and m.metadata.price_range
    ]
    if prices:
        parts.append(f"价格区间: {', '.join(sorted(set(prices)))}")

    # Aggregate power types
    power_types = set()
    for m in model_chunks:
        if m.brand == brand:
            for pt in m.metadata.power_type:
                power_types.add(pt)
    if power_types:
        parts.append(f"动力类型: {', '.join(sorted(power_types))}")

    # Aggregate smart drive levels
    sd_levels = set()
    for m in model_chunks:
        if m.brand == brand and m.metadata.smart_drive:
            sd_levels.add(m.metadata.smart_drive)
    if sd_levels:
        parts.append(f"最高智驾等级: {max(sd_levels)}")

    # Feature highlights
    if features_list:
        parts.append(f"特色亮点: {'; '.join(features_list[:8])}")

    content = "\n".join(parts)
    chunk_id = BrandChunk.build_chunk_id(brand)
    meta = CarMetadata(brand=brand, source=source)

    # Collect vehicle types
    for m in model_chunks:
        if m.brand == brand and m.metadata.vehicle_type:
            meta.vehicle_type = m.metadata.vehicle_type
            break

    embedding_content = build_embedding_content(
        brand=brand, metadata=meta, original_text=content,
    )
    keywords = generate_keywords(brand, "", meta)

    return BrandChunk(
        chunk_id=chunk_id,
        brand=brand,
        metadata=meta,
        embedding_content=embedding_content,
        retrieval_keywords=keywords,
        content=content,
    )


# ═══════════════════════════════════════════════════════════════
#  Comparison Detection & Generation
# ═══════════════════════════════════════════════════════════════

def _build_comparison_chunk(
    text: str,
    brands: List[str],
    models: List[str],
    source: str,
) -> Optional[ComparisonChunk]:
    """Build a ComparisonChunk when multiple brands/models are discussed together."""
    if len(brands) < 2:
        return None

    primary_brand = brands[0]
    primary_model = models[0] if models else ""

    meta = extract_metadata(text, brand=primary_brand, model=primary_model, source=source)

    # Detect comparison dimensions
    dimensions = []
    for topic, pattern in _TOPIC_PATTERNS.items():
        if pattern.search(text):
            dimensions.append(topic)

    chunk_id = ComparisonChunk.build_chunk_id(brands)
    embedding_content = build_embedding_content(
        brand=primary_brand, model=primary_model,
        metadata=meta, original_text=text,
    )
    keywords = []
    for b in brands:
        keywords.append(b)
    keywords.extend(models)
    keywords.extend(dimensions)

    return ComparisonChunk(
        chunk_id=chunk_id,
        brands=brands,
        models=models,
        metadata=meta,
        embedding_content=embedding_content,
        retrieval_keywords=keywords,
        content=text,
        comparison_dimensions=dimensions,
    )


# ═══════════════════════════════════════════════════════════════
#  Main Pipeline: structured_chunk()
# ═══════════════════════════════════════════════════════════════

def structured_chunk(
    text: str,
    source_brand: str = "",
    source_model: str = "",
    source: str = "car_price",
    extract_features: bool = True,
    max_tokens_per_chunk: int = 1200,
) -> ChunkingResult:
    """The main Semantic Structured Chunking pipeline.

    Pipeline:
      1. Detect all brands and models in the text
      2. For each brand+model pair, build a core ModelChunk
      3. Extract FeatureChunks from each model's content
      4. Generate BrandChunk summaries from aggregated model data
      5. Detect and build ComparisonChunks for multi-brand sections
      6. Return typed ChunkingResult

    Rules enforced:
      - One model → one core ModelChunk
      - Features extracted as standalone FeatureChunks
      - Brand summaries auto-generated
      - Multi-model content split into separate chunks
      - NO RecursiveCharacterTextSplitter
      - NO fixed-size character splitting

    Args:
        text: Raw car-domain text (structured car JSON text or free text)
        source_brand: Known brand from ingestion context
        source_model: Known model from ingestion context
        source: Source type identifier
        extract_features: Whether to extract feature chunks
        max_tokens_per_chunk: Max tokens per chunk (triggers sentence split)

    Returns:
        ChunkingResult with typed brand/model/feature/comparison chunks
    """
    if not text or not text.strip():
        return ChunkingResult(
            document_title="",
            brand=source_brand,
            model=source_model,
            total_chunks=0,
        )

    text = text.strip()

    # ── Step 1: Detect brands and models ──
    all_brands = identify_all_brands(text)
    if not all_brands and source_brand:
        all_brands = [source_brand]

    # Resolve brand for each model mention
    model_brand_pairs: List[Tuple[str, str]] = []  # (brand, model)
    seen_models: set = set()
    for m in _MODEL_RE.finditer(text):
        raw = _normalize_model_name(m.group(0).strip())
        b = _resolve_brand_for_model(raw, text) or source_brand or (all_brands[0] if all_brands else "")
        key = (b, raw)
        if not _is_duplicate_model(key, seen_models):
            model_brand_pairs.append((b, raw))
            seen_models.add(key)

    # If models found from text, use those; otherwise fall back to source hints
    if not model_brand_pairs and source_brand and source_model:
        model_brand_pairs = [(source_brand, source_model)]
    elif not model_brand_pairs and all_brands:
        model_brand_pairs = [(all_brands[0], "")]

    # ── Step 2: Split text into per-model sections ──
    model_sections = _split_by_model(text, model_brand_pairs, all_brands)

    if not model_sections and source_brand:
        # Fallback: treat entire text as one model section
        model_sections = [{"brand": source_brand, "model": source_model or "", "text": text}]

    # ── Step 3: Build core ModelChunks ──
    model_chunks: List[ModelChunk] = []
    feature_chunks: List[FeatureChunk] = []
    comparison_chunks: List[ComparisonChunk] = []
    all_models_seen: Dict[str, List[str]] = {}  # brand → [models]

    for sec in model_sections:
        brand_name = sec["brand"]
        model_name = sec["model"]
        sec_text = sec["text"]

        if not sec_text.strip():
            continue

        # Track models per brand (for brand summary)
        if brand_name not in all_models_seen:
            all_models_seen[brand_name] = []
        if model_name and model_name not in all_models_seen[brand_name]:
            all_models_seen[brand_name].append(model_name)

        # Extract metadata for this model
        meta = extract_metadata(sec_text, brand=brand_name, model=model_name, source=source)

        # Build core ModelChunk
        chunk_id = ModelChunk.build_chunk_id(brand_name, model_name, meta.year)

        # Handle oversized content: split at sentence boundaries
        core_text = sec_text
        if estimate_tokens(core_text) > max_tokens_per_chunk:
            core_text = _truncate_at_sentence(core_text, max_tokens_per_chunk)

        embedding_content = build_embedding_content(
            brand=brand_name, model=model_name,
            metadata=meta, original_text=core_text,
        )
        keywords = generate_keywords(brand_name, model_name, meta)

        model_chunk = ModelChunk(
            chunk_id=chunk_id,
            brand=brand_name,
            model=model_name,
            metadata=meta,
            embedding_content=embedding_content,
            retrieval_keywords=keywords,
            content=core_text,
        )
        model_chunks.append(model_chunk)

        # ── Step 4: Extract FeatureChunks ──
        if extract_features:
            features = _extract_features_from_model_text(
                sec_text, brand_name, model_name, meta, source,
            )
            feature_chunks.extend(features)

    # ── Step 5: Generate BrandChunks ──
    brand_chunks: List[BrandChunk] = []
    brands_processed = set()
    for mc in model_chunks:
        if mc.brand and mc.brand not in brands_processed:
            brand_chunks.append(_build_brand_chunk(
                brand=mc.brand,
                model_chunks=[m for m in model_chunks if m.brand == mc.brand],
                feature_chunks=[f for f in feature_chunks if f.brand == mc.brand],
                source=source,
            ))
            brands_processed.add(mc.brand)

    # ── Step 6: Detect ComparisonChunks ──
    if len(all_brands) >= 2:
        # Extract sections that discuss multiple brands
        comp_sections = _extract_comparison_sections(text, all_brands)
        for comp_text, comp_brands, comp_models in comp_sections:
            comp_chunk = _build_comparison_chunk(
                comp_text, comp_brands, comp_models, source,
            )
            if comp_chunk:
                comparison_chunks.append(comp_chunk)

    # ── Assemble result ──
    doc_title = f"{source_brand} {source_model}".strip() or "未命名文档"
    all_chunks_count = (
        len(brand_chunks) + len(model_chunks) + len(feature_chunks) + len(comparison_chunks)
    )

    logger.info(
        f"Chunking complete: {doc_title} → "
        f"{len(brand_chunks)}B + {len(model_chunks)}M + "
        f"{len(feature_chunks)}F + {len(comparison_chunks)}C "
        f"= {all_chunks_count} total chunks"
    )

    return ChunkingResult(
        document_title=doc_title,
        brand=source_brand,
        model=source_model,
        total_chunks=all_chunks_count,
        brand_chunks=brand_chunks,
        model_chunks=model_chunks,
        feature_chunks=feature_chunks,
        comparison_chunks=comparison_chunks,
    )


# ═══════════════════════════════════════════════════════════════
#  Model Section Splitting
# ═══════════════════════════════════════════════════════════════

def _split_by_model(
    text: str,
    model_brand_pairs: List[Tuple[str, str]],
    all_brands: List[str],
) -> List[Dict[str, str]]:
    """Split text into per-model sections.

    Detects boundaries where a new model is introduced and isolates
    each model's content. Prevents multi-model chunks.
    """
    if len(model_brand_pairs) <= 1:
        b = model_brand_pairs[0][0] if model_brand_pairs else ""
        m = model_brand_pairs[0][1] if model_brand_pairs else ""
        return [{"brand": b, "model": m, "text": text}]

    sections: List[Dict[str, str]] = []

    # Build boundary markers: brand name + model pattern
    boundary_patterns = []
    for brand, model in model_brand_pairs:
        # Escape special chars, build alternation
        b_pat = re.escape(brand)
        m_pat = re.escape(model)
        boundary_patterns.append(rf'(?:{b_pat}\s*{m_pat})' if b_pat and m_pat else
                                 rf'(?:{b_pat})' if b_pat else rf'(?:{m_pat})')

    if not boundary_patterns:
        return [{"brand": all_brands[0] if all_brands else "",
                 "model": "", "text": text}]

    boundary_re = re.compile('|'.join(boundary_patterns))

    # Find boundary positions
    boundaries = [(0, model_brand_pairs[0][0], model_brand_pairs[0][1])]
    for m in boundary_re.finditer(text):
        matched = m.group(0)
        # Find which pair this matches
        for b, mod in model_brand_pairs:
            if b in matched or mod in matched:
                boundaries.append((m.start(), b, mod))
                break

    boundaries.sort()

    # Extract sections
    for i, (pos, brand, model) in enumerate(boundaries):
        start = pos
        end = boundaries[i + 1][0] if i + 1 < len(boundaries) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append({"brand": brand, "model": model, "text": section_text})

    return sections


def _extract_comparison_sections(
    text: str,
    all_brands: List[str],
) -> List[Tuple[str, List[str], List[str]]]:
    """Extract text sections where multiple brands are compared.

    Returns list of (text, brands, models) tuples.
    """
    if len(all_brands) < 2:
        return []

    # Look for comparison keywords
    comp_indicators = [
        r'(?:vs|VS|对比|比较|和|与|跟|及|还是|还是说)',
        r'(?:哪个更好|有什么区别|怎么选|选哪个)',
    ]
    comp_re = re.compile('|'.join(comp_indicators))

    # Split into paragraphs and find comparison spans
    paragraphs = re.split(r'\n\s*\n', text)
    comp_sections = []

    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        brands_here = [b for b in all_brands if b in para]

        if len(brands_here) >= 2 or (len(brands_here) >= 1 and comp_re.search(para)):
            # This is a comparison paragraph — include surrounding context
            start = max(0, i - 1)
            end = min(len(paragraphs), i + 3)

            # Check adjacent paragraphs for additional brand mentions
            context_brands = set(brands_here)
            context_texts = []
            for j in range(start, end):
                context_texts.append(paragraphs[j])
                for b in all_brands:
                    if b in paragraphs[j]:
                        context_brands.add(b)

            if len(context_brands) >= 2:
                combined = "\n\n".join(context_texts)
                models_here = []
                for b_brand, b_model in identify_all_models(combined):
                    models_here.append(b_model)

                comp_sections.append((combined, list(context_brands), models_here))
                i = end
                continue

        i += 1

    return comp_sections


def _truncate_at_sentence(text: str, max_tokens: int) -> str:
    """Truncate text at the nearest sentence boundary under max_tokens."""
    sentences = _SENTENCE_END_RE.split(text)
    sentences = [s.strip() for s in sentences if s.strip()]

    result = ""
    token_count = 0
    for sent in sentences:
        st = estimate_tokens(sent)
        if token_count + st > max_tokens:
            break
        result += sent + "。"
        token_count += st

    return result.strip() or text[:max_tokens * 3]  # fallback: char-based truncation


# ═══════════════════════════════════════════════════════════════
#  BM25 Keyword Search (for Hybrid Retrieval)
# ═══════════════════════════════════════════════════════════════

class BM25Scorer:
    """Lightweight BM25 scorer for hybrid search.

    Used as a pre-filter / scoring layer before vector search.
    Does keyword-based retrieval using retrieval_keywords as the
    inverted index.
    """

    def __init__(self, k1: float = 1.2, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def score(self, query_terms: List[str], doc_keywords: List[str],
              doc_length: int, avg_doc_length: float) -> float:
        """Compute BM25 score for a document given query terms."""
        if not query_terms or not doc_keywords:
            return 0.0

        doc_kw_lower = [k.lower() for k in doc_keywords]
        score = 0.0
        for term in query_terms:
            term_lower = term.lower()
            tf = doc_kw_lower.count(term_lower)
            if tf == 0:
                # Check substring match
                tf = sum(1 for k in doc_kw_lower if term_lower in k)
            if tf == 0:
                continue

            # Simplified BM25: just tf saturation
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * (doc_length / max(avg_doc_length, 1)))
            score += numerator / denominator

        return score


def tokenize_query(query: str) -> List[str]:
    """Tokenize a query for BM25 search.

    Extracts: Chinese bigrams + English words + Chinese words (2-4 chars).
    """
    tokens = []

    # Chinese bigrams
    for i in range(len(query) - 1):
        bigram = query[i:i+2]
        if all('一' <= c <= '鿿' for c in bigram):
            tokens.append(bigram)

    # Chinese trigrams
    for i in range(len(query) - 2):
        trigram = query[i:i+3]
        if all('一' <= c <= '鿿' for c in trigram):
            tokens.append(trigram)

    # English/alpha words
    for word in re.findall(r'[a-zA-Z0-9]+', query):
        if len(word) > 1:
            tokens.append(word.lower())

    # Brand/model names (longest match)
    for brand_name in _BRAND_MAP:
        if brand_name in query:
            tokens.append(brand_name)

    return list(set(tokens))  # dedup


# ═══════════════════════════════════════════════════════════════
#  Hybrid Score Fusion
# ═══════════════════════════════════════════════════════════════

def fuse_scores(
    vector_similarity: float,
    bm25_score: float,
    max_bm25: float = 1.0,
    vector_weight: float = 0.6,
    bm25_weight: float = 0.4,
) -> float:
    """Fuse vector similarity and BM25 scores.

    Uses weighted linear combination with BM25 normalization.
    Default: 60% vector + 40% BM25 (tunable per query type).
    """
    # Normalize BM25 to [0, 1]
    norm_bm25 = min(bm25_score / max(max_bm25, 0.001), 1.0)
    return vector_weight * vector_similarity + bm25_weight * norm_bm25
