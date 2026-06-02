"""
data/check_qdrant.py  —  Qdrant baglanti tanisi

Kullanim:
    python data/check_qdrant.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

qdrant_url     = os.getenv("QDRANT_URL", "TANIMLANMAMIS")
qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
collection     = os.getenv("QDRANT_COLLECTION", "SAP-AI")

print("=" * 55)
print("  QDRANT BAGLANTI TANISI")
print("=" * 55)
print(f"  QDRANT_URL        : {qdrant_url}")
print(f"  QDRANT_API_KEY    : {'SET (' + qdrant_api_key[:6] + '...)' if qdrant_api_key else 'YOK'}")
print(f"  QDRANT_COLLECTION : {collection}")
print("=" * 55)

# 1. URL formatini kontrol et
if qdrant_url == "TANIMLANMAMIS":
    print("\n[HATA] .env dosyasinda QDRANT_URL tanimlanmamis!")
    print("  Ekleyin: QDRANT_URL=https://xxxx.qdrant.io:6333")
    sys.exit(1)

if qdrant_api_key and qdrant_url.startswith("http://"):
    print("\n[UYARI] API key var ama URL http:// ile basliyor!")
    print("  Qdrant Cloud icin https:// kullanin.")
    print(f"  Duzeltme: QDRANT_URL={qdrant_url.replace('http://', 'https://')}")

# 2. HTTP erisilebilirlik testi (requests ile)
try:
    import requests
    health_url = qdrant_url.rstrip("/") + "/healthz"
    print(f"\n[TEST] {health_url} adresine istek atiliyor...")
    r = requests.get(health_url, timeout=5,
                     headers={"api-key": qdrant_api_key} if qdrant_api_key else {})
    print(f"  HTTP {r.status_code}")
    if r.status_code == 200:
        print("  [OK] Qdrant erisilebilir!")
    else:
        print(f"  [UYARI] Beklenmedik status: {r.text[:200]}")
except requests.exceptions.ConnectionError as e:
    print(f"  [HATA] Baglanti reddedildi: {e}")
    print("\n  Olasiliklar:")
    print("  1. Qdrant Cloud kullaniyorsaniz URL'yi kontrol edin (https://)")
    print("  2. Lokal Qdrant icin Docker calistigin kontrol edin:")
    print("     docker run -p 6333:6333 qdrant/qdrant")
except requests.exceptions.Timeout:
    print("  [HATA] Zaman asimi! Sunucu erisilemedile.")
    print("\n  Olasiliklar:")
    print("  1. URL yanlis — Qdrant Cloud URL'si genellikle su formatta:")
    print("     https://xxxx-xxxx-xxxx.us-east4-0.gcp.cloud.qdrant.io:6333")
    print("  2. Guvenlik duvari portu (6333) engelliyor olabilir")
except Exception as e:
    print(f"  [HATA] {type(e).__name__}: {e}")

# 3. Qdrant client testi
print("\n[TEST] qdrant_client ile baglanti deneniyor...")
try:
    from qdrant_client import QdrantClient
    client = QdrantClient(
        url=qdrant_url,
        api_key=qdrant_api_key or None,
        timeout=8,
    )
    cols = client.get_collections().collections
    print(f"  [OK] Baglanti basarili! Mevcut koleksiyonlar:")
    if cols:
        for c in cols:
            print(f"       - {c.name}")
    else:
        print("       (henuz koleksiyon yok)")
except Exception as e:
    print(f"  [HATA] {type(e).__name__}: {e}")

print("\n" + "=" * 55)