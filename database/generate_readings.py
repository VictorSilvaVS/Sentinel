import os
import sys
from datetime import datetime, timedelta
import random
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from src.api.app import app, db
from src.database.models import Equipment, Reading, SubEquipment

# Configurações de leituras por tipo de equipamento
EQUIPMENT_METRICS = {
    'CUP': {
        'producao': {'base': 3000, 'var': 200, 'unit': 'CPM'},
        'temperatura': {'base': 45, 'var': 5, 'unit': '°C'},
        'pressao': {'base': 6, 'var': 0.5, 'unit': 'bar'}
    },
    'BM': {
        'producao': {'base': 2800, 'var': 150, 'unit': 'CPM'},
        'temperatura': {'base': 42, 'var': 3, 'unit': '°C'},
        'rejeitos': {'base': 25, 'var': 10, 'unit': 'un'}
    },
    'WSH': {
        'temperatura': {'base': 65, 'var': 5, 'unit': '°C'},
        'concentracao': {'base': 1.8, 'var': 0.2, 'unit': '%'},
        'fluxo': {'base': 2.5, 'var': 0.3, 'unit': 'L/min'}
    },
    'PRT': {
        'producao': {'base': 2600, 'var': 100, 'unit': 'CPM'},
        'temperatura': {'base': 38, 'var': 2, 'unit': '°C'},
        'pressao': {'base': 4.5, 'var': 0.3, 'unit': 'bar'}
    },
    'ISP': {
        'pressao': {'base': 4.2, 'var': 0.4, 'unit': 'bar'},
        'fluxo': {'base': 1.5, 'var': 0.2, 'unit': 'L/min'},
        'temperatura': {'base': 35, 'var': 3, 'unit': '°C'}
    },
    'NCK': {
        'producao': {'base': 2500, 'var': 120, 'unit': 'CPM'},
        'torque': {'base': 25, 'var': 2, 'unit': 'Nm'},
        'rejeitos': {'base': 20, 'var': 8, 'unit': 'un'}
    },
    'LNR': {
        'producao': {'base': 3200, 'var': 150, 'unit': 'CPM'},
        'temperatura': {'base': 42, 'var': 3, 'unit': '°C'},
        'verniz': {'base': 0.8, 'var': 0.1, 'unit': 'L/min'},
        'rejeitos': {'base': 15, 'var': 5, 'unit': 'un'}
    }
}

# Adicionar métricas para sub-equipamentos do BodyMaker
EQUIPMENT_METRICS['SubBM'] = {
    'producao': {'base': 2800, 'var': 150, 'unit': 'CPM'},
    'temperatura': {'base': 42, 'var': 3, 'unit': '°C'},
    'rejeitos': {'base': 25, 'var': 10, 'unit': 'un'}
}

# Adicionar métricas para sub-equipamentos do Inside Spray
EQUIPMENT_METRICS['SubISP'] = {
    'pressao': {'base': 4.2, 'var': 0.4, 'unit': 'bar'},
    'fluxo': {'base': 1.5, 'var': 0.2, 'unit': 'L/min'},
    'temperatura': {'base': 35, 'var': 3, 'unit': '°C'}
}

def generate_value(base, var):
    """Gera valor com variação aleatória e tendência"""
    trend = np.sin(datetime.now().timestamp() / 3600) * var * 0.3  # Tendência senoidal
    noise = random.uniform(-var, var)
    return max(0, base + trend + noise)

def generate_readings(days=1, interval_minutes=60):
    with app.app_context():
        try:
            # Limpa leituras antigas
            Reading.query.delete()
            db.session.commit()
            
            end_time = datetime.now()
            start_time = end_time - timedelta(days=days)
            current_time = start_time
            
            print(f"Gerando leituras de {start_time} até {end_time}...")
            
            # Para cada intervalo de tempo
            while current_time <= end_time:
                # Para equipamentos principais
                equipments = Equipment.query.all()
                for eq in equipments:
                    if eq.tipo not in EQUIPMENT_METRICS:
                        continue
                        
                    # Gera leituras para cada métrica do equipamento
                    for metric, config in EQUIPMENT_METRICS[eq.tipo].items():
                        value = generate_value(config['base'], config['var'])
                        
                        reading = Reading(
                            equipment_id=eq.id,
                            timestamp=current_time,
                            value=str(round(value, 2)),
                            metric=metric,
                            unit=config['unit'],
                            source='historic'
                        )
                        db.session.add(reading)
                        
                    # Se for BodyMaker ou Inside Spray, gera leituras para sub-equipamentos
                    if eq.tipo in ['BM', 'ISP']:
                        sub_equipments = SubEquipment.query.filter_by(equipment_id=eq.id).all()
                        metrics_key = 'Sub' + eq.tipo  # SubBM ou SubISP
                        for sub_eq in sub_equipments:
                            for metric, config in EQUIPMENT_METRICS[metrics_key].items():
                                # Ajusta valores base para cada sub-equipamento
                                base_mod = random.uniform(0.9, 1.1)  # ±10% variação entre sub-equipamentos
                                value = generate_value(config['base'] * base_mod, config['var'])
                                
                                reading = Reading(
                                    equipment_id=eq.id,
                                    sub_equipment_id=sub_eq.id,
                                    timestamp=current_time,
                                    value=str(round(value, 2)),
                                    metric=metric,
                                    unit=config['unit'],
                                    source='historic'
                                )
                                db.session.add(reading)
                
                # Avança para o próximo intervalo
                current_time += timedelta(minutes=interval_minutes)
                
                # Commit a cada 100 registros para não sobrecarregar a memória
                if current_time.minute % 100 == 0:
                    db.session.commit()
                    print(f"Processando... {current_time}")
            
            # Commit final
            db.session.commit()
            print("Dados históricos gerados com sucesso!")
            
        except Exception as e:
            print(f"Erro ao gerar dados históricos: {e}")
            db.session.rollback()
            raise

if __name__ == "__main__":
    # Gera 7 dias de dados com leituras a cada 15 minutos
    generate_readings(days=7, interval_minutes=15)
