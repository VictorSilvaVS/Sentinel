import os
import json
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from pathlib import Path
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_master_key(app_root):
    """Lê a chave mestra do arquivo"""
    key_file = Path(app_root) / 'instance' / '.master.key'
    
    try:
        if not key_file.exists():
            raise FileNotFoundError(f"Chave mestra não encontrada em: {key_file}")
            
        with open(key_file, 'r') as f:
            data = json.load(f)
            if 'key' not in data:
                raise ValueError("Arquivo de chave inválido")
                
            key = data['key']
            # Garante padding correto
            if not key.endswith('='):
                key += '=' * (-len(key) % 4)
            return key
            
    except Exception as e:
        logger.error(f"Erro ao ler chave mestra: {str(e)}")
        raise
