"""Creative Sync — Import ads from Meta API into Creative Library.

Flow:
  Meta API → fetch ad creatives (headline, body, image_url)
           → auto-create creative_copies
           → auto-create creative_materials
           → auto-create ad_combos (copy × material)
           → link meta_ad_name for nightly ROAS sync

Deduplication:
  - Copies: matched by (branch_id, headline, primary_text hash)
  - Materials: matched by (branch_id, image_url or video_thumb)
  - Combos: UNIQUE(copy_id, material_id) — skips if exists
"""
import hashlib
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.creative_copy import CreativeCopy
from app.models.creative_material import CreativeMaterial
from app.models.ad_combo import AdCombo
from app.models.creative_angle import CreativeAngle
from app.services.id_generator import generate_code
from app.services.meta_ads import fetch_ad_creatives, parse_campaign_name
from app.config import settings

logger = logging.getLogger(__name__)

# ── Branch → Meta token/account mapping ──────────────────────────────────
BRANCH_META_MAP = {
    "saigon":  ("META_ACCESS_TOKEN_SAIGON",  "META_AD_ACCOUNT_SAIGON"),
    "sgn":     ("META_ACCESS_TOKEN_SAIGON",  "META_AD_ACCOUNT_SAIGON"),
    "taipei":  ("META_ACCESS_TOKEN_TAIPEI",  "META_AD_ACCOUNT_TAIPEI"),
    "1948":    ("META_ACCESS_TOKEN_1948",     "META_AD_ACCOUNT_1948"),
    "osaka":   ("META_ACCESS_TOKEN_OSAKA",    "META_AD_ACCOUNT_OSAKA"),
    "oani":    ("META_ACCESS_TOKEN_OANI",     "META_AD_ACCOUNT_OANI"),
}


def _get_meta_creds(branch_name: str) -> tuple[str, str] | None:
    """Resolve branch name to (access_token, ad_account_id)."""
    key = branch_name.lower().strip()
    for prefix, (tok_attr, acc_attr) in BRANCH_META_MAP.items():
        if prefix in key:
            token = getattr(settings, tok_attr, "")
            account = getattr(settings, acc_attr, "")
            if token and account:
                return (token, account)
            break
    return None


def _text_hash(text: str) -> str:
    """Short hash of text for dedup matching."""
    return hashlib.md5(text.strip().lower().encode()).hexdigest()[:16]


def _detect_language(text: str) -> str:
    """Simple heuristic to detect ad copy language."""
    if not text:
        return "English"
    # Vietnamese markers
    vn_chars = set("ắằẳẵặấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵđ")
    if any(c in vn_chars for c in text.lower()):
        return "Vietnamese"
    # Japanese markers (hiragana/katakana/kanji)
    if re.search(r'[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9fff]', text):
        return "Japanese"
    # Korean
    if re.search(r'[\uac00-\ud7af]', text):
        return "Korean"
    # Thai
    if re.search(r'[\u0e00-\u0e7f]', text):
        return "Thai"
    # Indonesian/Malay heuristic (common words)
    indo_words = {"dengan", "untuk", "dari", "yang", "anda", "kami", "dan", "atau", "ini", "itu"}
    words = set(text.lower().split())
    if len(words & indo_words) >= 2:
        return "Indonesian"
    return "English"


def _detect_ad_format(ad: dict) -> str:
    """Detect ad format from creative data."""
    if ad.get("has_video"):
        return "Video"
    return "Single Image"


def _detect_material_type(ad: dict) -> str:
    """Detect material type from creative data."""
    if ad.get("has_video"):
        return "video"
    return "image"


def _find_or_create_copy(
    db: Session,
    branch_id: UUID,
    headline: str,
    primary_text: str,
    ad: dict,
) -> CreativeCopy:
    """Find existing copy by content match or create new one."""
    if not primary_text:
        primary_text = headline or "(no text)"

    # Dedup: match on branch + text hash
    text_key = _text_hash(f"{headline}||{primary_text}")

    existing = db.query(CreativeCopy).filter(
        CreativeCopy.branch_id == branch_id,
        CreativeCopy.is_active == True,
    ).all()

    for c in existing:
        existing_key = _text_hash(f"{c.headline or ''}||{c.primary_text}")
        if existing_key == text_key:
            return c

    # Create new
    code = generate_code(db, "CPY", "creative_copies", "copy_code")
    language = _detect_language(primary_text or headline)
    ad_format = _detect_ad_format(ad)

    copy = CreativeCopy(
        copy_code=code,
        branch_id=branch_id,
        channel="Meta",
        ad_format=ad_format,
        target_audience=ad.get("target_audience") or "Generic",
        country_target=ad.get("country"),
        language=language,
        headline=headline[:500] if headline else None,
        primary_text=primary_text,
        landing_page_url=ad.get("link_url") or None,
        tags=["meta-import"],
    )
    db.add(copy)
    db.flush()
    logger.info("Created copy %s: %s", code, (headline or primary_text)[:60])
    return copy


def _find_or_create_material(
    db: Session,
    branch_id: UUID,
    ad: dict,
) -> CreativeMaterial | None:
    """Find existing material by URL match or create new one."""
    file_url = ad.get("image_url") or ad.get("video_thumb_url") or ""
    if not file_url:
        return None

    # Dedup: match on branch + file URL
    existing = db.query(CreativeMaterial).filter(
        CreativeMaterial.branch_id == branch_id,
        CreativeMaterial.file_link == file_url,
        CreativeMaterial.is_active == True,
    ).first()
    if existing:
        return existing

    code = generate_code(db, "MAT", "creative_materials", "material_code")
    mat_type = _detect_material_type(ad)
    language = _detect_language(ad.get("primary_text", ""))

    material = CreativeMaterial(
        material_code=code,
        branch_id=branch_id,
        material_type=mat_type,
        design_type="Short Video (<30s)" if mat_type == "video" else "Static",
        channel="Meta",
        target_audience=ad.get("target_audience") or "Generic",
        language=language,
        file_link=file_url,
        tags=["meta-import"],
    )
    db.add(material)
    db.flush()
    logger.info("Created material %s: %s (%s)", code, mat_type, file_url[:60])
    return material


def _find_or_create_combo(
    db: Session,
    copy: CreativeCopy,
    material: CreativeMaterial,
    ad_name: str,
) -> AdCombo | None:
    """Create ad_combo linking copy + material. Returns None if already exists."""
    # Check existing by copy+material pair
    existing = db.query(AdCombo).filter(
        AdCombo.copy_id == copy.id,
        AdCombo.material_id == material.id,
    ).first()
    if existing:
        # Update meta_ad_name if not set yet
        if not existing.meta_ad_name and ad_name:
            existing.meta_ad_name = ad_name
            existing.updated_at = datetime.now(timezone.utc)
        return None  # signal: not newly created

    # Also check if meta_ad_name already used by another combo
    if ad_name:
        existing_by_name = db.query(AdCombo).filter(
            AdCombo.meta_ad_name == ad_name,
        ).first()
        if existing_by_name:
            # Same ad name but different copy+material — append ad_id suffix
            ad_name = f"{ad_name} #{copy.copy_code}"

    code = generate_code(db, "CMB", "ad_combos", "combo_code")
    combo = AdCombo(
        combo_code=code,
        copy_id=copy.id,
        material_id=material.id,
        branch_id=copy.branch_id,
        target_audience=copy.target_audience,
        channel=copy.channel,
        language=copy.language,
        country_target=copy.country_target,
        angle_id=copy.angle_id,
        meta_ad_name=ad_name if ad_name else None,
        run_status="Active",
    )
    db.add(combo)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        logger.warning("Combo %s already exists or meta_ad_name conflict, skipping", code)
        return None
    logger.info("Created combo %s: %s + %s → %s",
                code, copy.copy_code, material.material_code, ad_name[:40] if ad_name else "no-ad-name")
    return combo


def import_meta_creatives(
    db: Session,
    branch_id: UUID,
    branch_name: str,
    status_filter: str = "ACTIVE",
) -> dict:
    """Main entry: pull ads from Meta API and import into Creative Library.

    Returns summary dict:
      ads_fetched, copies_created, materials_created, combos_created, skipped
    """
    creds = _get_meta_creds(branch_name)
    if not creds:
        raise ValueError(f"No Meta API credentials for branch '{branch_name}'")

    token, account_id = creds

    # Ensure account_id has act_ prefix
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    # 1. Fetch creatives from Meta
    ads = fetch_ad_creatives(token, account_id, status_filter=status_filter)

    stats = {
        "ads_fetched": len(ads),
        "copies_created": 0,
        "copies_reused": 0,
        "materials_created": 0,
        "materials_reused": 0,
        "combos_created": 0,
        "skipped": 0,
    }

    if not ads:
        logger.info("No ads fetched for branch %s", branch_name)
        return stats

    # Track which copies/materials are new vs reused
    existing_copy_ids = set(
        c.id for c in db.query(CreativeCopy.id).filter(
            CreativeCopy.branch_id == branch_id, CreativeCopy.is_active == True
        ).all()
    )
    existing_mat_ids = set(
        m.id for m in db.query(CreativeMaterial.id).filter(
            CreativeMaterial.branch_id == branch_id, CreativeMaterial.is_active == True
        ).all()
    )

    # 2. Process each ad
    for ad in ads:
        try:
            headline = ad.get("headline", "")
            primary_text = ad.get("primary_text", "")
            ad_name = ad.get("ad_name", "")

            # Must have at least some text to create a copy
            if not headline and not primary_text:
                stats["skipped"] += 1
                continue

            # Find or create copy
            copy = _find_or_create_copy(db, branch_id, headline, primary_text, ad)
            if copy.id in existing_copy_ids:
                stats["copies_reused"] += 1
            else:
                stats["copies_created"] += 1
                existing_copy_ids.add(copy.id)

            # Find or create material
            material = _find_or_create_material(db, branch_id, ad)
            if material is None:
                stats["skipped"] += 1
                continue
            if material.id in existing_mat_ids:
                stats["materials_reused"] += 1
            else:
                stats["materials_created"] += 1
                existing_mat_ids.add(material.id)

            # Create combo
            combo = _find_or_create_combo(db, copy, material, ad_name)
            if combo:
                stats["combos_created"] += 1
            else:
                stats["skipped"] += 1

        except Exception as e:
            db.rollback()
            logger.warning("Error processing ad %s: %s", ad.get("ad_name", "?"), e)
            stats["skipped"] += 1
            continue

    db.commit()
    logger.info(
        "Meta import for %s: %d ads → %d copies, %d materials, %d combos (%d skipped)",
        branch_name, stats["ads_fetched"],
        stats["copies_created"], stats["materials_created"],
        stats["combos_created"], stats["skipped"],
    )
    return stats


def import_all_branches(db: Session, status_filter: str = "ACTIVE") -> dict:
    """Import creatives for all branches that have Meta API credentials."""
    from app.models.branch import Branch

    branches = db.query(Branch).filter(Branch.is_active == True).all()
    all_stats = {}

    for branch in branches:
        creds = _get_meta_creds(branch.name)
        if not creds:
            logger.info("Skipping branch %s — no Meta credentials", branch.name)
            continue

        try:
            stats = import_meta_creatives(db, branch.id, branch.name, status_filter)
            all_stats[branch.name] = stats
        except Exception as e:
            logger.error("Failed import for branch %s: %s", branch.name, e)
            all_stats[branch.name] = {"error": str(e)}

    return all_stats
