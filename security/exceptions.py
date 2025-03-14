"""
Exceções personalizadas para o módulo de segurança.
"""

class SecurityError(Exception):
    """Classe base para erros de segurança"""
    pass

class CryptographyError(SecurityError):
    """Erro genérico relacionado à criptografia"""
    pass

class SecurityValidationError(CryptographyError):
    """Erro específico para validações de segurança falhas"""
    pass

class KeyError(SecurityError):
    """Erro relacionado a chaves criptográficas"""
    pass

class DataError(SecurityError):
    """Erro relacionado aos dados sendo processados"""
    pass

class IntegrityError(SecurityValidationError):
    """Erro específico para falhas de integridade"""
    pass

class AuthenticationError(SecurityValidationError):
    """Erro específico para falhas de autenticação"""
    pass
