import re
from datetime import datetime
import pandas as pd
import numpy as np

class DataClassifier:
    """Classifica e processa dados importados"""
    
    REQUIRED_COLUMNS = {
        'timestamp': ['timestamp', 'data', 'date', 'time'],
        'equipment_id': ['equipment_id', 'equipamento_id', 'equip_id', 'id'],
        'value': ['value', 'valor', 'leitura', 'reading'],
        'metric': ['metric', 'metrica', 'medida', 'type'],
        'unit': ['unit', 'unidade', 'medida']
    }
    
    def __init__(self):
        self.column_mapping = {}
        # Dicionário de padrões de equipamentos de latas
        self.can_equipment_patterns = {
            r'(?i)v\d+': {'type': 'Body Maker', 'line': '22'},
            r'(?i)w\d+': {'type': 'Body Maker', 'line': '23'},
            r'(?i)dec\d+|decorator\d+': {'type': 'Decorator', 'line': lambda x: '22' if 'v' in x.lower() else '23'},
            r'(?i)uv\d+|forno\d+': {'type': 'UV Oven', 'line': lambda x: '22' if 'v' in x.lower() else '23'},
            r'(?i)pin\s*chain\d*': {'type': 'Pin Chain', 'line': lambda x: '22' if 'v' in x.lower() else '23'},
            r'(?i)washer\d*': {'type': 'Washer', 'line': lambda x: '22' if 'v' in x.lower() else '23'},
            r'(?i)spray\d*': {'type': 'Spray', 'line': lambda x: '22' if 'v' in x.lower() else '23'}
        }

        # Dicionário de padrões de equipamentos de tampas
        self.end_equipment_patterns = {
            r'(?i)liner\d*': {'type': 'Liner', 'line': '1'},
            r'(?i)shell\s*press|cp\d*': {'type': 'Shell Press', 'line': '1'},
            r'(?i)conv.*press|cvp\d*': {'type': 'Conversion Press', 'line': '1'},
            r'(?i)bagger|rob[ôo]|robot': {'type': 'Bagger', 'line': '1'}
        }
        
        # Dicionário de métricas comuns atualizado
        self.metric_patterns = {
            r'(?i)produ[çc][aã]o|speed|cpm|spm': ('velocidade', 'CPM'),
            r'(?i)temp|température': ('temperatura', '°C'),
            r'(?i)press[ãa]o|press': ('pressão', 'bar'),
            r'(?i)rejei[çc][aã]o|reject|rej': ('rejeitos', 'un'),
            r'(?i)verniz|varnish|flow': ('fluxo_verniz', 'L/min'),
            r'(?i)pot[êe]ncia|power': ('potência', '%'),
            r'(?i)torque|torq': ('torque', 'Nm')
        }

    def identify_equipment_and_line(self, text):
        # Verificar padrões de latas
        for pattern, info in self.can_equipment_patterns.items():
            if re.search(pattern, text):
                line = info['line'] if isinstance(info['line'], str) else info['line'](text)
                return {
                    'type': info['type'],
                    'line': line,
                    'category': 'latas'
                }
        
        # Verificar padrões de tampas
        for pattern, info in self.end_equipment_patterns.items():
            if re.search(pattern, text):
                return {
                    'type': info['type'],
                    'line': info['line'],
                    'category': 'tampas'
                }
        
        return None

    def identify_metric(self, text, value=None):
        for pattern, (metric, unit) in self.metric_patterns.items():
            if re.search(pattern, text):
                return metric, unit
        
        # Tenta inferir pela faixa de valores
        if value is not None:
            if 0 <= value <= 1000:  # Velocidade típica em CPM
                return 'velocidade', 'CPM'
            elif 0 <= value <= 150:  # Temperatura típica em °C
                return 'temperatura', '°C'
            elif 0 <= value <= 10:   # Pressão típica em bar
                return 'pressão', 'bar'
        
        return 'outro', None
    
    def process_dataframe(self, df):
        """Processa o DataFrame e retorna dados estruturados"""
        try:
            # Identifica colunas
            self.column_mapping = self._identify_columns(df)
            
            # Prepara a lista de leituras
            readings = []
            for _, row in df.iterrows():
                reading = {
                    'equipment_id': str(row[self.column_mapping['equipment_id']]),
                    'timestamp': pd.to_datetime(row[self.column_mapping['timestamp']]),
                    'value': float(row[self.column_mapping['value']]),
                    'metric': str(row[self.column_mapping['metric']]),
                    'unit': str(row[self.column_mapping['unit']]),
                    'type': str(row.get('type', 'unknown')),  # opcional
                    'line': str(row.get('line', '1')),  # opcional
                    'sub_equipment_id': str(row.get('sub_equipment_id', None)),  # opcional
                }
                readings.append(reading)
            
            return {
                'status': 'success',
                'readings': readings,
                'message': f"Processados {len(readings)} registros com sucesso"
            }
            
        except Exception as e:
            return {
                'status': 'error',
                'message': f"Erro ao processar dados: {str(e)}"
            }

    def _get_equipment_name(self, parent_type):
        names = {
            'BM_22': 'Body Maker Linha 22',
            'BM_23': 'Body Maker Linha 23',
            'LINER': 'Liner Tampas',
            'SHELLPRESS': 'Shell Press Tampas',
            'CONVPRESS': 'Conversion Press Tampas',
            'BAGGER': 'Bagger Tampas'
        }
        return names.get(parent_type, parent_type)

    def _get_line_number(self, parent_type):
        if '_22' in parent_type:
            return '22'
        elif '_23' in parent_type:
            return '23'
        return '1'  # Linha de tampas

    def _identify_parent_type(self, col):
        if re.search(r'(?i)^V\d+|^DEC_V|^UV_V|^WASHER_V|^SPRAY_V|^PIN_V', col):
            return 'BM_22'
        elif re.search(r'(?i)^W\d+|^DEC_W|^UV_W|^WASHER_W|^SPRAY_W|^PIN_W', col):
            return 'BM_23'
        elif re.search(r'(?i)^LINER\d+', col):
            return 'LINER'
        elif re.search(r'(?i)^CP\d+', col):
            return 'SHELLPRESS'
        elif re.search(r'(?i)^CVP\d+', col):
            return 'CONVPRESS'
        elif re.search(r'(?i)^BAGGER\d+', col):
            return 'BAGGER'
        return None

    def _extract_sub_equipment_id(self, col):
        match = re.search(r'(?i)(V\d+|W\d+|LINER\d+|CP\d+|CVP\d+|BAGGER\d+)', col)
        return match.group(1) if match else None

    def _get_sub_equipment_name(self, col):
        sub_id = self._extract_sub_equipment_id(col)
        if not sub_id:
            return col
        
        metric = re.sub(r'.*?' + sub_id + r'_', '', col).lower()
        return f"{sub_id} - {metric}"

    def _identify_columns(self, df):
        """Identifica as colunas do DataFrame baseado em nomes comuns"""
        found_columns = {}
        df_columns = [col.lower() for col in df.columns]
        
        for required, alternatives in self.REQUIRED_COLUMNS.items():
            for alt in alternatives:
                if alt.lower() in df_columns:
                    found_columns[required] = df.columns[df_columns.index(alt.lower())]
                    break
            
            if required not in found_columns:
                raise ValueError(f"Coluna obrigatória '{required}' não encontrada. "
                               f"Alternativas aceitas: {alternatives}")
        
        return found_columns

    def validate_data(self, reading):
        """Valida os dados de uma leitura"""
        try:
            # Validações básicas
            assert isinstance(reading['equipment_id'], str), "equipment_id deve ser string"
            assert isinstance(reading['value'], (int, float)), "value deve ser numérico"
            assert isinstance(reading['metric'], str), "metric deve ser string"
            assert isinstance(reading['unit'], str), "unit deve ser string"
            
            # Validação de timestamp
            if isinstance(reading['timestamp'], str):
                reading['timestamp'] = pd.to_datetime(reading['timestamp'])
            
            return True
        except Exception as e:
            raise ValueError(f"Erro na validação: {str(e)}")
