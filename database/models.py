from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from flask import current_app

db = SQLAlchemy()

class CryptField(db.TypeDecorator):
    impl = db.String
    cache_ok = True
    
    def __init__(self, max_length=None, raw=False):
        super().__init__(max_length)
        self._crypto = None
        self.raw = raw

    @property
    def crypto(self):
        if self._crypto is None:
            from flask import current_app
            if not hasattr(current_app, 'db_crypto'):
                raise RuntimeError("DatabaseCrypto não inicializado na aplicação")
            self._crypto = current_app.db_crypto
        return self._crypto

    def process_bind_param(self, value, dialect):
        """Criptografa valor antes de salvar no banco"""
        if value is None or self.raw:
            return value
        try:
            if isinstance(value, bytes):
                value = value.decode()
            return self.crypto.encrypt_value(str(value))
        except Exception as e:
            current_app.logger.error(f"Erro ao criptografar: {str(e)}")
            raise

    def process_result_value(self, value, dialect):
        """Descriptografa valor lido do banco"""
        if value is None or self.raw:
            return value
        try:
            decrypted = self.crypto.decrypt_value(value)
            return decrypted
        except Exception as e:
            current_app.logger.error(f"Erro ao descriptografar: {str(e)}")
            return value  # Retorna valor original se falhar

class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(CryptField(80), unique=True, nullable=False)  # Voltou a ser CryptField
    email = db.Column(CryptField(120), unique=True, nullable=False)   # Voltou a ser CryptField
    password_hash = db.Column(db.String(256))  # Mantém sem criptografia por ser já um hash
    role = db.Column(CryptField(20), default='visitante')            # Voltou a ser CryptField
    factory = db.Column(CryptField(20), nullable=False)  # 'latas' ou 'tampas'
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Equipment(db.Model):
    __tablename__ = 'equipments'
    
    id = db.Column(db.String(10), primary_key=True)
    nome = db.Column(CryptField(100), nullable=False)
    tipo = db.Column(CryptField(50), nullable=False)
    linha = db.Column(CryptField(50), nullable=False)
    status = db.Column(CryptField(20), default='operacional')
    plc_tag = db.Column(CryptField(100))
    ultima_atualizacao = db.Column(db.DateTime)
    parent_id = db.Column(db.String(10), db.ForeignKey('equipments.id'), nullable=True)
    
    # Relacionamentos simplificados
    children = db.relationship('Equipment', 
                             backref=db.backref('parent', remote_side=[id]))
    equipment_readings = db.relationship('Reading', 
                                      backref='equipment_parent',
                                      lazy=True)
    sub_equipments = db.relationship('SubEquipment',
                                   backref='main_equipment',
                                   lazy=True)

class SubEquipment(db.Model):
    __tablename__ = 'sub_equipments'
    
    id = db.Column(db.String(10), primary_key=True)
    equipment_id = db.Column(db.String(10), db.ForeignKey('equipments.id'))
    nome = db.Column(CryptField(100), nullable=False)
    tipo = db.Column(CryptField(50), nullable=False)
    status = db.Column(CryptField(20), default='operacional')
    plc_tag = db.Column(CryptField(100))
    linha = db.Column(CryptField(10))
    
    sub_readings = db.relationship('Reading', 
                                 backref='sub_equipment_parent',
                                 lazy=True)

class PLCConfig(db.Model):
    __tablename__ = 'plc_configs'
    
    id = db.Column(db.Integer, primary_key=True)
    ip_address = db.Column(CryptField(15), nullable=False)
    rack = db.Column(CryptField(10))
    slot = db.Column(CryptField(10))
    description = db.Column(CryptField(200))

class Reading(db.Model):
    __tablename__ = 'readings'
    
    id = db.Column(db.Integer, primary_key=True)
    equipment_id = db.Column(db.String(10), db.ForeignKey('equipments.id'))
    sub_equipment_id = db.Column(db.String(10), db.ForeignKey('sub_equipments.id'))
    timestamp = db.Column(db.DateTime, nullable=False)
    value = db.Column(CryptField(50))
    metric = db.Column(CryptField(50))
    unit = db.Column(CryptField(20))
    source = db.Column(CryptField(50))
    encrypted_data = db.Column(CryptField(1000))
