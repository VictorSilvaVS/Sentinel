import os
import sys
import json
import base64
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet, InvalidToken  # Adicionar import

# Configuração do path para importações
root_path = Path(__file__).parent.parent.parent
sys.path.append(str(root_path))

# Configuração de logging
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Carrega a chave mestra globalmente
try:
    key_file = root_path / 'instance' / '.master.key'
    with open(key_file, 'r') as f:
        data = json.load(f)
        master_key = data['key']
        logger.info(f"Chave mestra carregada: {master_key[:20]}...")
except FileNotFoundError:
    logger.error(f"Arquivo de chave não encontrado em: {key_file}")
    sys.exit(1)
except json.JSONDecodeError:
    logger.error(f"Arquivo de chave inválido em: {key_file}")
    sys.exit(1)
except Exception as e:
    logger.error(f"Erro ao carregar chave mestra: {str(e)}")
    sys.exit(1)

# Flask e SQLAlchemy
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

# Importações do projeto
from src.api.app import app, db
from src.database.models import User, Equipment, SubEquipment
from src.security.crypto import CryptoManager
from src.security.db_crypto import DatabaseCrypto

def test_crypto_performance():
    """Testa a performance das operações de criptografia"""
    logger.info("\n=== Teste de Performance de Criptografia ===")
    import time
    
    with app.app_context():
        crypto_manager = CryptoManager(master_key)
        db_crypto = DatabaseCrypto(app)
        
        # Dados de teste com diferentes tamanhos
        test_sizes = [100, 1000, 10000]
        results = {}
        
        for size in test_sizes:
            test_data = {
                'texto': 'A' * size,
                'números': list(range(size)),
                'data': datetime.now().isoformat()
            }
            
            start_time = time.time()
            encrypted = crypto_manager.encrypt(test_data)
            encrypt_time = time.time() - start_time
            
            start_time = time.time()
            decrypted = crypto_manager.decrypt(encrypted)
            decrypt_time = time.time() - start_time
            
            results[size] = {
                'encrypt': encrypt_time,
                'decrypt': decrypt_time
            }
            
        try:
            logger.info("\nResultados de Performance:")
            for size, times in results.items():
                logger.info(f"Tamanho {size}: Encrypt={times['encrypt']:.4f}s, Decrypt={times['decrypt']:.4f}s")
            return True
        except Exception as e:
            logger.error(f"Erro no teste de performance: {str(e)}")
            return False

def test_edge_cases():
    """Testa casos extremos e especiais"""
    logger.info("\n=== Teste de Casos Extremos ===")
    success = True
    
    with app.app_context():
        crypto_manager = CryptoManager(master_key)
        
        test_cases = [
            {},  # Dicionário vazio
            {'null': None},  # Valores None
            {'special': '@#$%¨&*()'},  # Caracteres especiais
            {'unicode': 'áéíóúàâêîôûãõ'},  # Unicode
            {'nested': {'a': {'b': {'c': 1}}}},  # Estruturas aninhadas
            {'binary': base64.b64encode(os.urandom(32)).decode()},  # Dados binários aleatórios
            {'large': 'x' * 1000000},  # Teste com dados grandes
            {'timestamp': datetime.now().isoformat()},  # Timestamp
            [1, 2, 3],  # Lista
            {'array': list(range(1000))}  # Array grande
        ]
        
        for i, case in enumerate(test_cases):
            try:
                encrypted = crypto_manager.encrypt(case)
                decrypted = crypto_manager.decrypt(encrypted)
                
                # Normaliza os dados antes da comparação
                case_str = json.dumps(case, sort_keys=True, default=str)
                decrypted_str = json.dumps(decrypted, sort_keys=True, default=str)
                
                assert case_str == decrypted_str, f"Falha na consistência para caso {i}"
                logger.info(f"Caso especial {i} testado com sucesso: {type(case)}")
            except Exception as e:
                logger.error(f"Falha no caso {i}: {str(e)}")
                success = False
        
        return success

def test_security_validations():
    """Testa validações de segurança"""
    logger.info("\n=== Teste de Validações de Segurança ===")
    
    try:
        with app.app_context():
            crypto_manager = CryptoManager(master_key)
            
            # Teste de integridade
            test_data = {'sensitive': 'data'}
            encrypted = crypto_manager.encrypt(test_data)
            
            # Adulteração mais efetiva dos dados
            if isinstance(encrypted, bytes):
                # Modifica bytes aleatórios no meio do conteúdo
                pos = len(encrypted) // 2
                tampered = encrypted[:pos] + os.urandom(16) + encrypted[pos+16:]
            else:
                # Converte para bytes, adultera e converte de volta
                try:
                    encrypted_bytes = base64.b64decode(encrypted)
                    pos = len(encrypted_bytes) // 2
                    tampered_bytes = encrypted_bytes[:pos] + os.urandom(16) + encrypted_bytes[pos+16:]
                    tampered = base64.b64encode(tampered_bytes).decode()
                except:
                    # Se falhar a decodificação, adultera a string diretamente
                    pos = len(encrypted) // 2
                    tampered = encrypted[:pos] + base64.b64encode(os.urandom(8)).decode() + encrypted[pos+12:]
            
            integrity_test_passed = False
            try:
                decrypted = crypto_manager.decrypt(tampered)
                logger.error("FALHA: Detecção de adulteração falhou!")
            except (InvalidToken, Exception) as e:
                logger.info(f"Sucesso: Detectou dados adulterados - {str(e)}")
                integrity_test_passed = True
            
            # Teste de chaves diferentes mais robusto
            try:
                another_key = base64.urlsafe_b64encode(os.urandom(32)).decode()
                another_crypto = CryptoManager(another_key)
                encrypted_1 = crypto_manager.encrypt(test_data)
                
                key_test_passed = False
                try:
                    decrypted = another_crypto.decrypt(encrypted_1)
                    logger.error("FALHA: Permitiu decriptação com chave errada!")
                except (InvalidToken, Exception) as e:
                    logger.info(f"Sucesso: Bloqueou decriptação com chave errada - {str(e)}")
                    key_test_passed = True
                
                return integrity_test_passed and key_test_passed
                
            except Exception as e:
                logger.error(f"Erro no teste de chaves: {str(e)}")
                return False
            
    except Exception as e:
        logger.error(f"Erro no teste de segurança: {str(e)}")
        return False

def test_crypto_consistency():
    """Testa se todas as partes do sistema estão usando a mesma chave"""
    logger.info("\n=== Teste de Consistência de Criptografia ===")
    
    try:
        with app.app_context():
            crypto_manager = CryptoManager(master_key)
            db_crypto = DatabaseCrypto(app)

            # Dados de teste em diferentes formatos
            test_cases = [
                # String simples
                "Teste de criptografia",
                
                # Dicionário
                {
                    'texto': 'Teste de criptografia',
                    'número': 42,
                    'data': datetime.now().isoformat()
                },
                
                # Lista
                [1, 2, 3, "teste"]
            ]

            for test_data in test_cases:
                logger.info(f"\nTestando: {test_data}")
                
                # Teste CryptoManager
                encrypted_cm = crypto_manager.encrypt(test_data)
                decrypted_cm = crypto_manager.decrypt(encrypted_cm)
                
                # Teste DatabaseCrypto
                db_data = json.dumps(test_data) if isinstance(test_data, (dict, list)) else str(test_data)
                encrypted_db = db_crypto.encrypt_value(db_data)
                decrypted_db = db_crypto.decrypt_value(encrypted_db)
                
                # Converte resultado do DatabaseCrypto para objeto se necessário
                try:
                    decrypted_db = json.loads(decrypted_db)
                except json.JSONDecodeError:
                    pass  # Mantém como string
                
                # Compara resultados
                if isinstance(test_data, (dict, list)):
                    test_str = json.dumps(test_data, sort_keys=True)
                    cm_str = json.dumps(decrypted_cm, sort_keys=True)
                    db_str = json.dumps(decrypted_db, sort_keys=True)
                else:
                    test_str = str(test_data)
                    cm_str = str(decrypted_cm)
                    db_str = str(decrypted_db)
                
                if test_str != cm_str or test_str != db_str:
                    logger.error("Falha na consistência")
                    logger.error(f"Original: {test_str}")
                    logger.error(f"CryptoManager: {cm_str}")
                    logger.error(f"DatabaseCrypto: {db_str}")
                    return False
                    
                logger.info("✓ Teste passou")
            
            logger.info("\nTodos os testes de consistência passaram!")
            return True
            
    except Exception as e:
        logger.error(f"Erro no teste de consistência: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Iniciando testes de criptografia...")
    logger.info(f"Usando arquivo de chave em: {root_path / 'instance' / '.master.key'}")
    
    results = {
        'consistency': False,
        'performance': False,
        'edge_cases': False,
        'security': False
    }
    
    try:
        results['consistency'] = test_crypto_consistency() or False
        results['performance'] = test_crypto_performance() or False
        results['edge_cases'] = test_edge_cases() or False
        results['security'] = test_security_validations() or False
        
        success = all(results.values())
        
        logger.info("\n=== Resumo dos Testes ===")
        for test, result in results.items():
            status = 'SUCESSO' if result else 'FALHA'
            logger.info(f"{test.title()}: {status}")
        logger.info(f"\nResultado Final: {'SUCESSO' if success else 'FALHA'}")
        
        sys.exit(0 if success else 1)
        
    except Exception as e:
        logger.error(f"Erro fatal durante os testes: {str(e)}", exc_info=True)
        sys.exit(1)
