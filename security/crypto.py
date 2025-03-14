from cryptography.fernet import Fernet, InvalidToken
import base64
import json
from typing import Union, Optional
from .exceptions import CryptographyError, SecurityValidationError

class SecurityConfig:
    KEY_ENCODING = 'utf-8'
    DATA_ENCODING = 'utf-8'
    JSON_ENSURE_ASCII = False

class CryptoManager:
    def __init__(self, master_key: Union[str, bytes]):
        """Inicializa com uma chave mestra existente"""
        if not master_key:
            raise ValueError("Uma chave mestra válida é obrigatória")
        self.master_key = self._validate_master_key(master_key)
        self.fernet = Fernet(self.master_key)

    def _validate_master_key(self, key: Union[str, bytes]) -> bytes:
        """Valida e formata a chave mestra"""
        try:
            if isinstance(key, str):
                # Garante padding correto para base64
                if not key.endswith('='):
                    key += '=' * (-len(key) % 4)
                key_bytes = key.encode(SecurityConfig.KEY_ENCODING)
            elif isinstance(key, bytes):
                key_bytes = key
            else:
                raise ValueError("Chave mestra deve ser string ou bytes")
            
            # Testa se é uma chave Fernet válida
            Fernet(key_bytes)
            return key_bytes
            
        except Exception as e:
            raise ValueError(f"Chave mestra inválida: {str(e)}")

    def encrypt(self, data: Union[dict, list, str, bytes, int, float]) -> bytes:
        """
        Criptografa dados com validação de tipo e formato
        Retorna: bytes criptografados em base64
        """
        if data is None:
            raise CryptographyError("Dados vazios não podem ser criptografados")
            
        try:
            # Converte números para string
            if isinstance(data, (int, float)):
                data = str(data)
            
            # Serializa dados complexos
            if isinstance(data, (dict, list)):
                data = json.dumps(
                    data,
                    ensure_ascii=SecurityConfig.JSON_ENSURE_ASCII
                )
            
            # Garante que os dados são bytes
            if isinstance(data, str):
                data = data.encode(SecurityConfig.DATA_ENCODING)
            elif not isinstance(data, bytes):
                raise TypeError(f"Tipo de dado não suportado: {type(data)}")
            
            # Criptografa e retorna em bytes
            return self.fernet.encrypt(data)
            
        except TypeError as e:
            raise CryptographyError(f"Tipo de dado inválido: {str(e)}")
        except Exception as e:
            raise CryptographyError(f"Erro na criptografia: {str(e)}")

    def decrypt(self, encrypted_data: Union[bytes, str]) -> Union[dict, list, str, int, float]:
        """
        Descriptografa dados com validação de integridade
        Retorna: dados originais no formato apropriado
        """
        if not encrypted_data:
            raise CryptographyError("Dados criptografados vazios")
            
        try:
            # Converte para bytes se necessário
            if isinstance(encrypted_data, str):
                try:
                    encrypted_data = encrypted_data.encode(SecurityConfig.DATA_ENCODING)
                except UnicodeEncodeError as e:
                    raise CryptographyError(f"Dados criptografados inválidos: {str(e)}")
            
            # Descriptografa com validação de integridade
            try:
                decrypted = self.fernet.decrypt(encrypted_data)
            except InvalidToken:
                raise SecurityValidationError("Dados adulterados ou chave inválida")
            
            # Tenta converter de volta para o formato original
            try:
                decrypted_str = decrypted.decode(SecurityConfig.DATA_ENCODING)
                try:
                    return int(decrypted_str)
                except ValueError:
                    try:
                        return float(decrypted_str)
                    except ValueError:
                        try:
                            return json.loads(decrypted_str)
                        except json.JSONDecodeError:
                            return decrypted_str
            except Exception:
                return decrypted.decode(SecurityConfig.DATA_ENCODING)
                
        except SecurityValidationError:
            raise  # Re-lança erros de segurança
        except UnicodeDecodeError as e:
            raise CryptographyError(f"Erro ao decodificar dados: {str(e)}")
        except Exception as e:
            raise CryptographyError(f"Erro na descriptografia: {str(e)}")

    def encrypt_bytes(self, data: bytes) -> bytes:
        """Método específico para criptografar bytes puros"""
        if not isinstance(data, bytes):
            raise TypeError("Dados devem ser bytes")
        return self.fernet.encrypt(data)

    def decrypt_bytes(self, encrypted_data: bytes) -> bytes:
        """Método específico para descriptografar para bytes"""
        if not isinstance(encrypted_data, bytes):
            raise TypeError("Dados criptografados devem ser bytes")
        return self.fernet.decrypt(encrypted_data)