"""
app/services/tenant.py — çok-kiracılık (firma) yardımcıları.

Token formatı: demo-token-{id}-{role}-{company}
  - [2] = user_id, [3] = role, [4] = company  (geriye uyumlu)
company yoksa/ALL ise kısıt uygulanmaz (global admin).
"""

from __future__ import annotations


def _parts(req) -> list[str]:
    token = req.headers.get("Authorization", "").replace("Bearer ", "")
    if token.startswith("demo-token-"):
        return token.split("-")
    return []


# Firma adı kanonikleştirme — "Beyçelik"/"beycelik"/"BEYCELIK" hepsi → "Beycelik".
# Türkçe ç/c, ş/s gibi farklı yazımlar tek değere indirgenir; aksi halde firma filtreleri
# (entegrasyon listesi, şema, metrik) yanlışlıkla eşleşmez ve kayıtlar "kaybolur".
_TR_FOLD = str.maketrans("ıİşŞğĞüÜöÖçÇ", "iissgguuoocc")
_CANON   = {"beycelik": "Beycelik", "warmhaus": "Warmhaus", "all": "ALL"}


def canonical_company(c: str | None) -> str:
    if not c:
        return "ALL"
    key = c.strip().lower().translate(_TR_FOLD)
    return _CANON.get(key, c.strip())


def user_id_from_request(req) -> str | None:
    p = _parts(req)
    return p[2] if len(p) > 2 else None


def role_from_request(req) -> str | None:
    p = _parts(req)
    return p[3] if len(p) > 3 else None


def company_from_request(req) -> str:
    """Token'dan firma (kanonikleştirilmiş); yoksa kullanıcı id'sinden USERS'a bakar; yine yoksa 'ALL'."""
    p = _parts(req)
    if len(p) > 4 and p[4]:
        return canonical_company(p[4])
    # Eski token (company'siz) → id'den çöz
    uid = p[2] if len(p) > 2 else None
    if uid is not None:
        try:
            from app.models.store import company_of
            return canonical_company(company_of(uid))
        except Exception:
            pass
    return "ALL"


def is_global(company: str | None) -> bool:
    """ALL / None → tüm firmalara erişim (filtre uygulanmaz)."""
    return company in (None, "", "ALL")


def is_admin(req) -> bool:
    return (role_from_request(req) or "").upper() == "ADMIN"
