from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_cors import CORS
from datetime import datetime, timedelta
import random
from pylogix import PLC
import pandas as pd
import json
from functools import wraps
import os
import sys
from urllib.parse import urlparse  # Substituir werkzeug.urls import
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from src.database.models import db, User, Equipment, PLCConfig, SubEquipment
from src.ai.data_classifier import DataClassifier
from src.database.models import Reading
from src.security.crypto import CryptoManager, CryptographyError
from src.security.db_crypto import DatabaseCrypto

template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates'))
static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'static'))

app = Flask(__name__, 
           template_folder=template_dir,
           static_folder=static_dir)

app.secret_key = '324253453453442342132342342543545'
CORS(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'  # Adicionar esta linha

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///sentinel.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(__file__), 'temp')

ROLE = {
    'admin': 3,
    'colaborador': 2,
    'visitante': 1
}

def init_database():
    with app.app_context():
        try:
            app.logger.info("Criando tabelas do banco de dados...")
            db.create_all()            
            app.logger.info("Banco de dados inicializado com sucesso!")
        except Exception as e:
            app.logger.error(f"Erro na inicialização do banco de dados: {str(e)}")
            raise

# Substituir o bloco with app.app_context() por:
init_database()

@login_manager.user_loader
def load_user(user_id):
    try:
        return db.session.get(User, int(user_id))  # Usa session.get ao invés de query.get
    except Exception:
        return None

def role_required(min_role):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('login'))
            if ROLE[current_user.role] < ROLE[min_role]:
                return jsonify({'error': 'Permissão negada'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def init_app():
    # Configuração de logs
    if not os.path.exists('logs'):
        os.makedirs('logs')
    
    # Configuração do logger
    import logging
    from logging.handlers import RotatingFileHandler
    import atexit
    
    # Remover handlers existentes
    for handler in app.logger.handlers[:]:
        app.logger.removeHandler(handler)
    
    # Formatador personalizado
    formatter = logging.Formatter(
        '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
    )
    
    # Handler para arquivo com tratamento de erros
    try:
        file_handler = RotatingFileHandler(
            'logs/sentinel.log', 
            maxBytes=10240, 
            backupCount=10,
            delay=True  # Atrasa a abertura do arquivo
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        
        # Handler para console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        console_handler.setLevel(logging.INFO)
        
        # Adiciona os handlers
        app.logger.addHandler(file_handler)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)
        
        # Função para fechar handlers no shutdown
        def cleanup():
            for handler in app.logger.handlers[:]:
                handler.close()
                app.logger.removeHandler(handler)
        
        # Registra função de cleanup
        atexit.register(cleanup)
        
    except Exception as e:
        print(f"Erro ao configurar log: {str(e)}")
        # Fallback para logging apenas no console
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        app.logger.addHandler(console_handler)
        app.logger.setLevel(logging.INFO)

    try:
        from pathlib import Path
        from src.security.crypto_utils import get_master_key
        
        root_path = Path(__file__).parent.parent.parent
        master_key = get_master_key(root_path)
        
        # Inicializa primeiro o CryptoManager
        app.crypto = CryptoManager(master_key)
        app.logger.info("CryptoManager inicializado com sucesso")
        
        # Depois inicializa o DatabaseCrypto
        app.db_crypto = DatabaseCrypto(app)
        app.logger.info("Sistemas de criptografia inicializados com sucesso")
        
    except Exception as e:
        app.logger.error(f"Erro ao inicializar criptografia: {str(e)}")
        raise

# Inicializa app e criptografia
init_app()

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        email = request.form['email']
        
        if User.query.filter_by(username=username).first():
            return render_template('register.html', error='Usuário já existe')
            
        if User.query.filter_by(email=email).first():
            return render_template('register.html', error='Email já cadastrado')
            
        user = User(username=username, email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        app.logger.info("Usuário já autenticado, redirecionando para dashboard")
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            form_username = request.form.get('username', '').strip()
            form_password = request.form.get('password', '')
            
            app.logger.info("=== Iniciando processo de login ===")
            app.logger.info(f"Tentativa de login com username: {form_username}")
            
            app.logger.debug("Buscando usuário no banco de dados...")
            # Busca todos os usuários para comparação
            users = User.query.all()
            app.logger.info(f"Total de usuários encontrados: {len(users)}")
            
            user_found = None
            for u in users:
                try:
                    app.logger.debug(f"Verificando usuário ID: {u.id}")
                    # Tenta descriptografar o username
                    decrypted_username = u.username  # CryptField faz a descriptografia automaticamente
                    app.logger.debug(f"Username descriptografado: {decrypted_username}")
                    
                    if decrypted_username.lower() == form_username.lower():
                        app.logger.info(f"Usuário encontrado com ID: {u.id}")
                        user_found = u
                        break
                except Exception as e:
                    app.logger.error(f"Erro ao processar usuário ID {u.id}: {str(e)}")
                    continue
            
            if user_found:
                app.logger.info(f"Verificando credenciais para usuário ID: {user_found.id}")
                app.logger.debug(f"Role do usuário: {user_found.role}")
                
                if user_found.check_password(form_password):
                    app.logger.info("Senha validada com sucesso")
                    login_user(user_found, remember=True)
                    
                    app.logger.info("Usuário autenticado com sucesso")
                    app.logger.debug(f"Detalhes do login: ID={user_found.id}, Role={user_found.role}")
                    
                    next_page = request.args.get('next')
                    if not next_page or urlparse(next_page).netloc != '':
                        next_page = url_for('dashboard')
                    
                    app.logger.info(f"Redirecionando para: {next_page}")
                    return redirect(next_page)
                else:
                    app.logger.warning(f"Senha incorreta para usuário ID: {user_found.id}")
                    return render_template('login.html', error='Senha incorreta')
            else:
                app.logger.warning(f"Nenhum usuário encontrado com username: {form_username}")
                return render_template('login.html', error='Usuário não encontrado')
                    
        except Exception as e:
            app.logger.error("=== Erro no processo de login ===")
            app.logger.error(f"Detalhes do erro: {str(e)}", exc_info=True)
            return render_template('login.html', error='Erro ao fazer login')
            
    return render_template('login.html')

@app.route('/api/config', methods=['GET'])
@login_required
def get_config():
    """Endpoint para buscar configurações do usuário"""
    try:
        # Garante que os dados sejam descriptografados
        user_config = {
            'username': current_user.username,
            'role': current_user.role,
                            }
        return jsonify(user_config)
    except Exception as e:
        app.logger.error(f"Erro ao buscar configurações: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao carregar configurações'}), 500

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html', user=current_user)

@app.route('/api/health')
def health_check():
    return jsonify({'status': 'ok'})

@app.route('/api/equipamentos')
@login_required
def listar_equipamentos():
    try:
        app.logger.debug("Buscando equipamentos principais...")
        
        # Se for admin, mostra todos os equipamentos
        if current_user.role == 'admin':
            equipamentos = Equipment.query.filter(Equipment.parent_id.is_(None)).all()
        # Se não for admin, filtra pela fábrica do usuário
        else:
            if current_user.factory == 'latas':
                # Filtra equipamentos que contém '22' ou '23' no ID
                equipamentos = Equipment.query.filter(
                    Equipment.parent_id.is_(None),
                    db.or_(
                        Equipment.id.like('%22%'),
                        Equipment.id.like('%23%')
                    )
                ).all()
            else:  # tampas - todos os outros que não têm 22 ou 23
                equipamentos = Equipment.query.filter(
                    Equipment.parent_id.is_(None),
                    ~Equipment.id.like('%22%'),
                    ~Equipment.id.like('%23%')
                ).all()
            
        app.logger.debug(f"Encontrados {len(equipamentos)} equipamentos")
        
        if not equipamentos:
            return jsonify({}), 200  # Retorna objeto vazio com status 200
            
        response_data = {
            str(eq.id): {
                "id": eq.id,
                "nome": eq.nome,
                "tipo": eq.tipo,
                "linha": eq.linha,
                "status": eq.status,
                "plc_tag": eq.plc_tag,
                "display_name": f"{eq.tipo} {eq.nome}",
                "linha_display": f"Linha {eq.linha} - {eq.tipo}"
            } for eq in equipamentos
        }
        
        return jsonify(response_data)
        
    except Exception as e:
        app.logger.error(f"Erro ao listar equipamentos: {str(e)}", exc_info=True)
        return jsonify({'error': 'Erro ao buscar equipamentos'}), 500

@app.route('/api/predictions/<equipment_id>')
def get_predictions(equipment_id):
    # Usando Session.get() ao invés de Query.get()
    equipment = db.session.get(Equipment, equipment_id)
    
    # Se não encontrar, tenta buscar como sub-equipamento
    if not equipment:
        equipment = db.session.get(SubEquipment, equipment_id)
        if not equipment:
            return jsonify({'error': 'Equipamento não encontrado'}), 404
    
    # Gera previsões simuladas
    previsoes = []
    data_atual = datetime.now()
    
    # Ajusta as probabilidades baseado no tipo de equipamento
    base_prob = 0.1  # Probabilidade base
    if hasattr(equipment, 'tipo'):
        if equipment.tipo == 'SubBM':  # Para sub-equipamentos do BodyMaker
            base_prob = 0.15
    
    for i in range(5):
        prob_falha = min(1.0, base_prob + (i * 0.05) + random.uniform(-0.05, 0.05))
        
        if prob_falha < 0.3:
            severidade = "baixa"
        elif prob_falha < 0.7:
            severidade = "média"
        else:
            severidade = "alta"
            
        previsao = {
            "data": (data_atual + timedelta(days=i)).isoformat(),
            "probabilidade_falha": round(prob_falha, 3),
            "severidade": severidade
        }
        previsoes.append(previsao)
    
    return jsonify({
        'equipment_id': equipment.id,
        'equipment_name': equipment.nome,
        'status': equipment.status,
        'predictions': previsoes,
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/alert/<equipment_id>', methods=['POST'])
def criar_alerta(equipment_id):
    equipment = Equipment.query.get_or_404(equipment_id)
    
    return jsonify({
        "message": f"Alerta criado para {equipment.nome}",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/plc/read')
@role_required('colaborador')
def read_plc():
    """Simula leitura do PLC usando dados do banco"""
    try:
        tag = request.args.get('tag', '')
        if not tag:
            return jsonify({'error': 'Tag não especificada'}), 400
            
        # Busca últimas leituras do equipamento
        readings = Reading.query.join(Equipment).filter(
            Equipment.id == tag
        ).order_by(
            Reading.timestamp.desc()
        ).limit(100).all()
        
        if not readings:
            return jsonify({'error': 'Nenhuma leitura encontrada'}), 404
        
        # Agrupa leituras por métrica
        metrics = {}
        for reading in readings:
            if reading.metric not in metrics:
                metrics[reading.metric] = []
            metrics[reading.metric].append(float(reading.value))
        
        # Calcula médias e valores atuais
        response = {
            'status': 'Online',
            'timestamp': datetime.now().isoformat()
        }
        
        for metric, values in metrics.items():
            response[metric] = values[0]  # Valor mais recente
            response[f'avg_{metric}'] = sum(values) / len(values)
            response[f'min_{metric}'] = min(values)
            response[f'max_{metric}'] = max(values)
            
            if len(values) > 1:
                trend = ((values[0] - values[-1]) / values[-1] * 100)
                response[f'{metric}_trend'] = round(trend, 2)
        
        return jsonify(response)
        
    except Exception as e:
        app.logger.error(f"Erro ao ler PLC: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/api/config/settings', methods=['GET', 'POST'])
@login_required
def config_api():
    if not current_user.is_authenticated or current_user.role != 'admin':
        return jsonify({'error': 'Permissão negada'}), 403
        
    if request.method == 'POST':
        config = request.json
        with open('config.json', 'w') as f:
            json.dump(config, f)
        return jsonify({'status': 'success'})
    else:
        try:
            with open('config.json', 'r') as f:
                return jsonify(json.load(f))
        except:
            return jsonify({})

@app.route('/api/config/import', methods=['POST'])
@login_required
def import_data():
    if not current_user.role == 'admin':
        return jsonify({'error': 'Permissão negada'}), 403
        
    if 'file' not in request.files:
        return jsonify({'error': 'Nenhum arquivo enviado'}), 400
        
    file = request.files['file']
    if not file.filename:
        return jsonify({'error': 'Arquivo inválido'}), 400
        
    file_type = request.form.get('type', '')
    if not file_type:
        return jsonify({'error': 'Tipo de arquivo não especificado'}), 400
    
    try:
        # Lista de encodings para tentar
        encodings = ['utf-8', 'latin1', 'utf-16', 'utf-16le', 'utf-16be', 'cp1252']
        
        # Verifica extensão do arquivo
        allowed_extensions = {
            'csv': ['.csv'],
            'json': ['.json'],
            'excel': ['.xlsx', '.xls'],
        }
        
        if not any(file.filename.lower().endswith(ext) 
                  for ext in allowed_extensions.get(file_type, [])):
            return jsonify({
                'error': f'Extensão de arquivo inválida para o tipo {file_type}'
            }), 400
        
        # Salva o arquivo temporariamente
        temp_path = os.path.join(app.config['UPLOAD_FOLDER'], 'temp_' + file.filename)
        os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
        file.save(temp_path)
        
        try:
            if file_type == 'csv':
                # Tenta diferentes encodings
                df = None
                last_error = None
                
                for encoding in encodings:
                    try:
                        df = pd.read_csv(
                            temp_path,
                            sep=request.form.get('separator', ','),
                            encoding=encoding
                        )
                        app.logger.info(f"Arquivo CSV lido com sucesso usando encoding: {encoding}")
                        break
                    except UnicodeError as e:
                        last_error = e
                        continue
                    except Exception as e:
                        last_error = e
                        continue
                
                if df is None:
                    raise ValueError(f"Não foi possível ler o arquivo com nenhum encoding. Último erro: {last_error}")
                    
            elif file_type == 'json':
                df = pd.read_json(temp_path)
            elif file_type == 'excel':
                df = pd.read_excel(temp_path, sheet_name=request.form.get('sheet', 0))
            else:
                return jsonify({'error': f'Tipo de arquivo não suportado: {file_type}'}), 400
                
        finally:
            # Limpa o arquivo temporário
            try:
                os.remove(temp_path)
            except:
                pass
                
        # Validação básica dos dados
        if df.empty:
            return jsonify({'error': 'O arquivo não contém dados'}), 400
            
        # Processa os dados
        result = process_imported_data(df)
        if result.get('status') == 'error':
            return jsonify({'error': result['message']}), 400
        
        # Criptografa e salva os dados
        try:
            encrypted_data = app.crypto.encrypt(str(result['data']))
            
            for eq_id, eq_data in result['data'].items():
                for metric, readings in eq_data['leituras'].items():
                    for reading in readings:
                        reading_obj = Reading(
                            equipment_id=eq_id,
                            timestamp=pd.to_datetime(reading['timestamp']),
                            value=reading['valor'],
                            metric=metric,
                            unit=reading['unidade'],
                            source='import',
                            encrypted_data=encrypted_data
                        )
                        db.session.add(reading_obj)
                        
            db.session.commit()
            return jsonify({
                'status': 'success',
                'message': 'Dados importados e criptografados com sucesso',
                'details': result.get('message', '')
            })
            
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao salvar dados: {str(e)}", exc_info=True)
            return jsonify({'error': f'Erro ao salvar dados: {str(e)}'}), 500
            
    except Exception as e:
        app.logger.error(f"Erro na importação: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

def process_imported_data(df):
    """Processa e classifica os dados importados usando a IA"""
    try:
        # Inicializa o classificador
        classifier = DataClassifier()
        
        # Processa o DataFrame
        result = classifier.process_dataframe(df)
        if result['status'] == 'error':
            return result
            
        readings = result['readings']
        equipment_summary = {}
        
        # Agrupa as leituras por equipamento
        for reading in readings:
            eq_id = reading['equipment_id']
            if eq_id not in equipment_summary:
                equipment_summary[eq_id] = {
                    'tipo': reading.get('type', 'unknown'),
                    'linha': reading.get('line', '1'),
                    'leituras': {}
                }
            
            metric = reading['metric']
            if metric not in equipment_summary[eq_id]['leituras']:
                equipment_summary[eq_id]['leituras'][metric] = []
            
            equipment_summary[eq_id]['leituras'][metric].append({
                'valor': reading['value'],
                'unidade': reading['unit'],
                'timestamp': reading['timestamp'].isoformat()
            })
        
        # Formata o relatório
        report = []
        for eq_id, eq_data in equipment_summary.items():
            report.append(f"\nEquipamento: {eq_id}")
            report.append(f"Tipo: {eq_data['tipo']}")
            report.append(f"Linha: {eq_data['linha']}")
            
            for metric, readings in eq_data['leituras'].items():
                values = [r['valor'] for r in readings]
                avg = sum(values) / len(values)
                min_val = min(values)
                max_val = max(values)
                unit = readings[0]['unidade']
                
                report.append(f"\n{metric.capitalize()}:")
                report.append(f"- Média: {avg:.2f} {unit}")
                report.append(f"- Mínimo: {min_val:.2f} {unit}")
                report.append(f"- Máximo: {max_val:.2f} {unit}")
        
        return {
            'status': 'success',
            'message': '\n'.join(report),
            'data': equipment_summary,
            'readings': readings
        }
        
    except Exception as e:
        app.logger.error(f"Erro ao processar dados: {str(e)}", exc_info=True)
        return {
            'status': 'error',
            'message': f'Erro ao processar dados: {str(e)}'
        }

@app.route('/config')
@login_required
def config_page():
    if current_user.role != 'admin':
        return redirect(url_for('dashboard'))
    return render_template('config.html')

@app.route('/api/readings/latest')
@login_required
def get_latest_readings():
    # Consulta as últimas leituras de cada equipamento
    subquery = db.session.query(
        Reading.equipment_id,
        db.func.max(Reading.timestamp).label('max_timestamp')
    ).group_by(Reading.equipment_id).subquery()
    
    latest_readings = db.session.query(Reading, Equipment).join(
        subquery, 
        db.and_(
            Reading.equipment_id == subquery.c.equipment_id,
            Reading.timestamp == subquery.c.max_timestamp
        )
    ).join(Equipment).all()
    
    return jsonify([{
        'equipment_id': reading.equipment_id,
        'equipment_name': equipment.nome,
        'status': equipment.status,
        'value': reading.value,
        'unit': reading.unit,
        'timestamp': reading.timestamp.isoformat()
    } for reading, equipment in latest_readings])

@app.route('/api/readings/latest/<equipment_id>')
@login_required
def get_latest_readings_by_equipment(equipment_id):
    try:
        # Primeiro verifica se é um equipamento principal
        equipment = db.session.get(Equipment, equipment_id)
        if equipment:
            query_filter = Reading.equipment_id == equipment_id
        else:
            # Se não for equipamento principal, tenta sub-equipamento
            sub_equipment = db.session.get(SubEquipment, equipment_id)
            if not sub_equipment:
                return jsonify({'error': 'Equipamento não encontrado'}), 404
            equipment = sub_equipment
            query_filter = Reading.sub_equipment_id == equipment_id

        # Consulta as últimas leituras para cada métrica
        latest_by_metric = db.session.query(
            Reading.metric,
            Reading.equipment_id,
            Reading.sub_equipment_id,
            db.func.max(Reading.timestamp).label('max_timestamp')
        ).filter(query_filter).group_by(
            Reading.metric,
            Reading.equipment_id,
            Reading.sub_equipment_id
        ).subquery()
        
        # Join para buscar as leituras completas
        latest_readings = db.session.query(Reading).join(
            latest_by_metric,
            db.and_(
                db.or_(
                    Reading.equipment_id == latest_by_metric.c.equipment_id,
                    Reading.sub_equipment_id == latest_by_metric.c.sub_equipment_id
                ),
                Reading.timestamp == latest_by_metric.c.max_timestamp,
                Reading.metric == latest_by_metric.c.metric
            )
        ).all()
        
        readings_data = [{
            'equipment_id': reading.equipment_id or reading.sub_equipment_id,
            'equipment_name': equipment.nome,
            'status': equipment.status,
            'metric': reading.metric,
            'value': reading.value,
            'unit': reading.unit,
            'timestamp': reading.timestamp.isoformat()
        } for reading in latest_readings]
        
        return jsonify(readings_data)
        
    except Exception as e:
        app.logger.error(f"Erro ao buscar leituras: {str(e)}")
        return jsonify({'error': 'Erro ao buscar leituras'}), 500

@app.route('/api/equipamentos/<parent_id>/sub')
def listar_sub_equipamentos(parent_id):
    parent = db.session.get(Equipment, parent_id)
    if not parent:
        return jsonify({'error': 'Equipamento não encontrado'}), 404
    
    sub_equipments = []
    
    # Definição dos tipos de equipamentos com sub-equipamentos e suas configurações
    SUB_EQUIPMENT_CONFIG = {
        'BM': {
            'prefix': lambda linha: 'V' if linha == '22' else 'W',
            'range': range(1, 8)
        },
        'ISP': {
            'prefix': lambda linha: 'IS',
            'range': range(1, 9)
        },
        'BAG': {
            'prefix': lambda linha: 'BAG',
            'range': range(1, 3)
        },
        'BAL': {
            'prefix': lambda linha: 'BAL',
            'range': range(1, 3)
        },
        'CVP': {
            'prefix': lambda linha: 'CP',
            'range': range(1, 5)
        },
        'LNR': {
            'prefix': lambda linha: 'LN',
            'range': range(1, 15)
        }
    }
    
    if parent.tipo in SUB_EQUIPMENT_CONFIG:
        config = SUB_EQUIPMENT_CONFIG[parent.tipo]
        prefix = config['prefix'](parent.linha)  # Agora prefix é uma função
        range_num = config['range']
        
        for i in range_num:
            sub_id = f"{prefix}{i}"
            sub_eq = SubEquipment(
                id=f"{parent.id}_{sub_id}",
                nome=sub_id,
                tipo=f"Sub{parent.tipo}",
                linha=parent.linha,
                status='operacional',
                plc_tag=f"{parent.linha}.{sub_id}_TAG",
                equipment_id=parent.id
            )
            db.session.add(sub_eq)
            
            sub_equipments.append({
                "id": sub_eq.id,
                "nome": sub_id,
                "tipo": f"Sub{parent.tipo}",
                "status": "operacional",
                "linha": parent.linha,
                "plc_tag": f"{parent.linha}.{sub_id}_TAG"
            })
    
    try:
        db.session.commit()
    except:
        db.session.rollback()
        
    return jsonify(sub_equipments)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/api/readings/metrics/<equipment_id>')
@login_required
def get_equipment_metrics(equipment_id):
    try:
        # Buscar últimas leituras do equipamento
        readings = Reading.query.filter(
            (Reading.equipment_id == equipment_id) |
            (Reading.sub_equipment_id == equipment_id)
        ).order_by(Reading.timestamp.desc()).limit(100).all()
        
        # Processar métricas
        metrics = {
            'producao': calculate_metric(readings, 'producao'),
            'temperatura': calculate_metric(readings, 'temperatura'),
            'rejeitos': calculate_metric(readings, 'rejeitos', True),
            'plc_status': 'Online'
        }
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/readings/general')
@login_required
def get_general_metrics():
    try:
        # Filtrar equipamentos pela fábrica do usuário
        if current_user.factory == 'latas':
            equipment_filter = Equipment.linha.in_(['22', '23'])
        elif current_user.factory == 'tampas':
            equipment_filter = Equipment.linha == '1'
        else:  # admin
            equipment_filter = True
        
        # Buscar últimas leituras de todos os equipamentos
        readings = Reading.query.join(Equipment).filter(
            equipment_filter
        ).order_by(Reading.timestamp.desc()).limit(1000).all()
        
        # Calcular métricas gerais
        metrics = {
            'total_producao': calculate_total_metric(readings, 'producao'),
            'avg_temperatura': calculate_avg_metric(readings, 'temperatura'),
            'total_rejeitos': calculate_total_metric(readings, 'rejeitos'),
            'system_status': 'Sistema Operacional',
            'production_history': get_production_history(readings)
        }
        
        return jsonify(metrics)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def calculate_metric(readings, metric_name, is_cumulative=False):
    metric_readings = [r for r in readings if r.metric == metric_name]
    if not metric_readings:
        return {'current': 0, 'average': 0, 'trend': 0}
    
    current = float(metric_readings[0].value)
    values = [float(r.value) for r in metric_readings]
    average = sum(values) / len(values)
    
    if is_cumulative:
        total = sum(values)
        trend = ((current - average) / average * 100) if average != 0 else 0
        return {'current': current, 'total': total, 'trend': round(trend, 2)}
    else:
        trend = ((current - average) / average * 100) if average != 0 else 0
        return {'current': current, 'average': round(average, 2), 'trend': round(trend, 2)}

def calculate_total_metric(readings, metric_name):
    """Calcula métricas totais"""
    metric_readings = [r for r in readings if r.metric == metric_name]
    if not metric_readings:
        return {'current': 0, 'average': 0, 'trend': 0, 'total': 0}
    
    current = float(metric_readings[0].value)
    values = [float(r.value) for r in metric_readings]
    average = sum(values) / len(values)
    total = sum(values)
    
    trend = ((current - average) / average * 100) if average != 0 else 0
    return {
        'current': current,
        'average': round(average, 2),
        'trend': round(trend, 2),
        'total': round(total, 2)
    }

def calculate_avg_metric(readings, metric_name):
    """Calcula métricas médias"""
    metric_readings = [r for r in readings if r.metric == metric_name]
    if not metric_readings:
        return {'current': 0, 'average': 0, 'trend': 0}
    
    current = float(metric_readings[0].value)
    values = [float(r.value) for r in metric_readings]
    average = sum(values) / len(values)
    
    trend = ((current - average) / average * 100) if average != 0 else 0
    return {
        'current': current,
        'average': round(average, 2),
        'trend': round(trend, 2)
    }

def get_production_history(readings, hours=24):
    """Retorna histórico de produção das últimas 24 horas"""
    now = datetime.now()
    start_time = now - timedelta(hours=hours)
    
    prod_readings = [r for r in readings 
                    if r.metric == 'producao' and r.timestamp >= start_time]
    
    history = []
    for reading in prod_readings:
        history.append({
            'timestamp': reading.timestamp.isoformat(),
            'total_producao': float(reading.value)
        })
    
    return sorted(history, key=lambda x: x['timestamp'])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
