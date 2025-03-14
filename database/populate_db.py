import os
import sys
from datetime import datetime
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.app import app, db
from src.database.models import User, Equipment, PLCConfig, SubEquipment

# Atualizar configurações de usuários para incluir factory
DEFAULT_USERS = {
    'admin': {
        'password': 'admin123', 
        'role': 'admin', 
        'email': 'admin@sentinel.com',
        'factory': 'admin'  # Mudado de 'latas' para 'admin'
    },
    'colab_latas': {
        'password': 'colab123', 
        'role': 'colaborador', 
        'email': 'colab.latas@sentinel.com',
        'factory': 'latas'
    },
    'colab_tampas': {
        'password': 'colab123', 
        'role': 'colaborador', 
        'email': 'colab.tampas@sentinel.com',
        'factory': 'tampas'
    },
    'visitante': {
        'password': 'visit123', 
        'role': 'visitante', 
        'email': 'visit@sentinel.com',
        'factory': 'latas'  # Mantido como 'latas' para visitantes
    }
}

# Configuração dos equipamentos principais
MAIN_EQUIPMENT = {
    '22': [
        {'id': 'CUP22', 'nome': 'Cupper', 'tipo': 'CUP', 'plc_tag': 'CUP_L22'},
        {'id': 'BM22', 'nome': 'BodyMaker', 'tipo': 'BM', 'plc_tag': 'BM_L22'},
        {'id': 'WSH22', 'nome': 'Washer', 'tipo': 'WSH', 'plc_tag': 'WSH_L22'},
        {'id': 'PRT22', 'nome': 'Printer', 'tipo': 'PRT', 'plc_tag': 'PRT_L22'},
        {'id': 'IS22', 'nome': 'Inside Spray', 'tipo': 'ISP', 'plc_tag': 'IS_L22'},
        {'id': 'NCK22', 'nome': 'Necker', 'tipo': 'NCK', 'plc_tag': 'NCK_L22'},
        {'id': 'PAL22', 'nome': 'Paletizadora', 'tipo': 'PAL', 'plc_tag': 'PAL_L22'}
    ],
    '23': [
        {'id': 'CUP23', 'nome': 'Cupper', 'tipo': 'CUP', 'plc_tag': 'CUP_L23'},
        {'id': 'BM23', 'nome': 'BodyMaker', 'tipo': 'BM', 'plc_tag': 'BM_L23'},
        {'id': 'WSH23', 'nome': 'Washer', 'tipo': 'WSH', 'plc_tag': 'WSH_L23'},
        {'id': 'PRT23', 'nome': 'Printer', 'tipo': 'PRT', 'plc_tag': 'PRT_L23'},
        {'id': 'IS23', 'nome': 'Inside Spray', 'tipo': 'ISP', 'plc_tag': 'IS_L23'},
        {'id': 'NCK23', 'nome': 'Necker', 'tipo': 'NCK', 'plc_tag': 'NCK_L23'},
        {'id': 'PAL23', 'nome': 'Paletizadora', 'tipo': 'PAL', 'plc_tag': 'PAL_L23'}
    ],
    '1': [
        {'id': 'CVP', 'nome': 'ConversionPress', 'tipo': 'CVP', 'plc_tag': 'CVP_L1'},
        {'id': 'LNR', 'nome': 'Liner', 'tipo': 'LNR', 'plc_tag': 'LNR_L1'},
        {'id': 'BAL', 'nome': 'Balancer', 'tipo': 'BAL', 'plc_tag': 'BAL_L1'},
        {'id': 'BAG', 'nome': 'Bagger', 'tipo': 'BAG', 'plc_tag': 'BAG_L1'},
        {'id': 'SP', 'nome': 'ShellPress', 'tipo': 'Shell', 'plc_tag': 'SP_L1'}
    ]
}

# Configuração dos sub-equipamentos
SUB_EQUIPMENT_CONFIG = {
    'BM': {'prefix': {'22': 'V', '23': 'W'}, 'range': range(1, 8)},  # V1-V7 ou W1-W7
    'ISP': {'prefix': {'22': 'IS', '23': 'IS'}, 'range': range(1, 9)},  # IS1-IS8
    'CVP': {'prefix': {'1': 'CP'}, 'range': range(1, 5)},  # CP1-CP4
    'LNR': {'prefix': {'1': 'LN'}, 'range': range(1, 15)},  # LN1-LN14
    'BAL': {'prefix': {'1': 'BAL'}, 'range': range(1, 3)},  # BAL1-BAL2
    'BAG': {'prefix': {'1': 'BAG'}, 'range': range(1, 3)}   # BAG1-BAG2
}

def create_users():
    """Cria usuários padrão"""
    try:
        for username, data in DEFAULT_USERS.items():
            if not User.query.filter(User.username.ilike(username)).first():
                user = User(
                    username=username,
                    email=data['email'],
                    role=data['role'],
                    factory=data['factory']  # Adiciona factory
                )
                user.set_password(data['password'])
                db.session.add(user)
        db.session.commit()
        print("Usuários criados com sucesso")
    except Exception as e:
        print(f"Erro ao criar usuários: {e}")
        db.session.rollback()

def create_equipment(linha):
    for eq_data in MAIN_EQUIPMENT[linha]:
        # Cria equipamento principal
        equipment = Equipment(
            id=eq_data['id'],
            nome=eq_data['nome'],
            tipo=eq_data['tipo'],
            linha=linha,
            status='operacional',
            plc_tag=eq_data['plc_tag']
        )
        db.session.add(equipment)
        db.session.flush()
        
        # Se o tipo do equipamento está na configuração de sub-equipamentos
        if eq_data['tipo'] in SUB_EQUIPMENT_CONFIG:
            config = SUB_EQUIPMENT_CONFIG[eq_data['tipo']]
            prefix = config['prefix'].get(linha, '')
            range_num = config['range']
            
            # Cria sub-equipamentos
            for i in range_num:
                sub_id = f"{prefix}{i}"
                sub_eq = SubEquipment(
                    id=f"{equipment.id}_{sub_id}",
                    nome=sub_id,
                    tipo=f"Sub{equipment.tipo}",
                    linha=linha,
                    status='operacional',
                    plc_tag=f"{linha}.{sub_id}_TAG",
                    equipment_id=equipment.id
                )
                db.session.add(sub_eq)

def populate_database():
    with app.app_context():
        try:
            # Limpa o banco de dados
            print("Limpando banco de dados...")
            db.drop_all()
            db.create_all()

            # Cria usuários
            print("Criando usuários...")
            create_users()

            # Cria equipamentos para cada linha
            print("Criando equipamentos...")
            for linha in MAIN_EQUIPMENT.keys():
                create_equipment(linha)

            # Configuração do PLC
            plc_config = PLCConfig(
                ip_address='192.168.1.100',
                rack='0',
                slot='1',
                description='PLC Principal'
            )
            db.session.add(plc_config)

            # Commit final
            db.session.commit()
            print("Banco de dados populado com sucesso!")

        except Exception as e:
            print(f"Erro ao popular banco de dados: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    populate_database()
