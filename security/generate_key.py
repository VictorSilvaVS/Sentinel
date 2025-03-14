import os
import json
import base64
from datetime import datetime
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print("Erro: Bibliotecas de criptografia não encontradas.")
    print("Execute: pip install cryptography")
    exit(1)

def generate_master_key():
    """Gera uma chave mestra forte para o sistema"""
    try:
        # Define o caminho do arquivo de chave
        root_path = Path(__file__).parent.parent.parent
        instance_path = root_path / 'instance'
        key_file = instance_path / '.master.key'

        # Remove chave antiga se existir
        if key_file.exists():
            os.remove(key_file)
            print("Chave antiga removida.")

        # Gera salt aleatório
        salt = os.urandom(16)
        
        # Configura PBKDF2HMAC para derivação de chave
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=480000,
            backend=default_backend()
        )
        
        # Gera chave base aleatória
        base_key = os.urandom(32)
        
        # Deriva a chave final
        key = base64.urlsafe_b64encode(kdf.derive(base_key))
        
        # Testa se a chave é válida para Fernet
        try:
            Fernet(key)
        except Exception as e:
            raise ValueError(f"Chave gerada inválida: {str(e)}")
            
        # Cria diretório se não existir
        instance_path.mkdir(exist_ok=True)
        
        # Salva a chave com metadados
        config = {
            'key': key.decode('utf-8'),
            'created_at': datetime.now().isoformat(),
            'key_type': 'AES-256-GCM',
            'version': '2.0'
        }
        
        # Salva com permissões restritas
        with open(key_file, 'w') as f:
            os.chmod(key_file.as_posix(), 0o600)
            json.dump(config, f, indent=2)
        
        print(f"Nova chave mestra gerada em: {key_file}")
        print("ATENÇÃO: Mantenha este arquivo seguro e faça backup!")
        print(f"Chave gerada (primeiros 20 caracteres): {key.decode('utf-8')[:20]}...")
        
        return key
        
    except Exception as e:
        print(f"Erro ao gerar chave mestra: {str(e)}")
        raise

if __name__ == '__main__':
    print("Iniciando geração de nova chave mestra...")
    generate_master_key()
