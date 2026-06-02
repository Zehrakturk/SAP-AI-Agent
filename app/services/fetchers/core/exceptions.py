"""Custom exception sınıfları — fetcher hata hiyerarşisi."""


class FetcherError(Exception):
    """Tüm fetcher hatalarının kök sınıfı."""


class AuthError(FetcherError):
    """Authentication başarısız (kullanıcı adı/şifre/token hatalı)."""


class ResponseError(FetcherError):
    """Servis cevabı beklenen formatta değil ya da hata döndü."""


class ParamMappingError(FetcherError):
    """Zorunlu parametre eksik veya eşleştirilemedi."""


class IntegrationNotFoundError(FetcherError):
    """integrations tablosunda kayıt bulunamadı / pasif."""
