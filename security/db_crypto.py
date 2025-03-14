import os
from pathlib import Path
import json
from cryptography.fernet import Fernet
from .crypto import CryptoManager
from flask import current_app
import logging

logger = logging.getLogger(__name__)

class DatabaseCrypto:
    def __init__(self, app=None):
        self.app = app
        self._crypto = None
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        """Inicializa a criptografia do banco de dados"""
        try:
            if not hasattr(app, 'crypto'):
                raise RuntimeError("CryptoManager não inicializado")
            self._crypto = app.crypto
            logger.info("DatabaseCrypto inicializado com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar DatabaseCrypto: {str(e)}")
            raise

    def encrypt_value(self, value):
        """Criptografa um valor usando o CryptoManager"""
        if self._crypto is None:
            raise RuntimeError("DatabaseCrypto não inicializado")
        try:
            if isinstance(value, (int, float)):
                value = str(value)
            if not isinstance(value, (str, bytes)):
                value = str(value)
            return self._crypto.encrypt(value)
        except Exception as e:
            logger.error(f"Erro ao criptografar valor: {str(e)}")
            raise

    def decrypt_value(self, encrypted_value):
        """Descriptografa um valor usando o CryptoManager"""
        if self._crypto is None:
            raise RuntimeError("DatabaseCrypto não inicializado")
        try:
            return self._crypto.decrypt(encrypted_value)
        except Exception as e:
            logger.error(f"Erro ao descriptografar valor: {str(e)}")
            raise

    # Aliases para compatibilidade
    encrypt = encrypt_value
    decrypt = decrypt_value
