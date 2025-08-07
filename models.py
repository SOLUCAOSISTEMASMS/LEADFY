from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
db = SQLAlchemy()
import uuid
from flask_wtf import FlaskForm
from wtforms import StringField
from wtforms.validators import DataRequired, Email
from wtforms import SubmitField
from wtforms import IntegerField

leads_produtos = db.Table('leads_produtos',
    db.Column('lead_id', db.Integer, db.ForeignKey('lead.id'), primary_key=True),
    db.Column('produto_id', db.Integer, db.ForeignKey('produto.id'), primary_key=True)
)



class Empresa(db.Model):
    __tablename__ = 'empresas'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), nullable=False, unique=True)
    plano = db.Column(db.String(50), default='gratuito')
    criada_em = db.Column(db.DateTime, default=datetime.utcnow)
    cpf_cnpj = db.Column(db.String(20), unique=True, nullable=False)
    telefone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    numero = db.Column(db.String(10))
    cidade = db.Column(db.String(50), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    representante = db.Column(db.String(100), nullable=True)
    codigo = db.Column(db.String(20), unique=True, nullable=False, default=lambda: str(uuid.uuid4())[:8])

    # Relacionamento com usuários vinculados a esta empresa
    usuarios = db.relationship('Usuario', back_populates='empresa')  # ✅ conexão bidirecional
    produtos = db.relationship('Produto', back_populates='empresa')

from werkzeug.security import generate_password_hash, check_password_hash

class Usuario(db.Model, UserMixin):
    __tablename__ = 'usuario'

    codigo = db.Column(db.Integer, nullable=False)
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), unique=True, nullable=False)
    nome_usuario = db.Column(db.String(50), unique=True)
    ativo = db.Column(db.Boolean, default=True)
    email = db.Column(db.String(120), nullable=True)
    senha_hash = db.Column(db.String(128), nullable=False)
    tipo = db.Column(db.String(20), nullable=False, default='vendedor')

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=True)
    empresa = db.relationship('Empresa', back_populates='usuarios')

    # ✅ Novos campos adicionados com base no cadastro
    telefone = db.Column(db.String(20), nullable=True)
    documento = db.Column(db.String(20), nullable=True)
    nascimento = db.Column(db.Date, nullable=True)
    rua = db.Column(db.String(100), nullable=True)
    numero = db.Column(db.String(10), nullable=True)
    bairro = db.Column(db.String(50), nullable=True)
    cep = db.Column(db.String(10), nullable=True)
    cidade = db.Column(db.String(50), nullable=True)
    estado = db.Column(db.String(2), nullable=True)  # Exemplo: 'MS'

    __table_args__ = (
        db.UniqueConstraint('codigo', 'empresa_id'),
    )

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)

from zoneinfo import ZoneInfo

def horario_brasilia():
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

class Log(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, nullable=False)
    acao = db.Column(db.String(100), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    data_hora = db.Column(db.DateTime, default=horario_brasilia)




# Valores possíveis: 'admin', 'gerente', 'vendedor'

    def set_senha(self, senha):
        self.senha_hash = generate_password_hash(senha)

    def verificar_senha(self, senha):
        return check_password_hash(self.senha_hash, senha)
    



class EmpresaPersonalizada(db.Model):
    __tablename__ = 'empresa_personalizada'
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    cnpj = db.Column(db.String(20), nullable=True)
    telefone = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    endereco = db.Column(db.String(200), nullable=True)
    cidade = db.Column(db.String(50), nullable=True)
    estado = db.Column(db.String(2), nullable=True)
    representante = db.Column(db.String(100), nullable=True)

    # Empresa pode ter vários usuários
from wtforms.validators import DataRequired, Length, Email

class EmpresaForm(FlaskForm):
    nome = StringField('Nome da empresa', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    telefone = StringField('Telefone', validators=[DataRequired(), Length(max=50)])
    endereco = StringField('Endereço', validators=[DataRequired(), Length(max=200)])
    numero = StringField('Número', validators=[DataRequired(), Length(max=10)])
    cidade = StringField('Cidade', validators=[DataRequired(), Length(max=50)])
    estado = StringField('Estado', validators=[DataRequired(), Length(max=2)])
    representante = StringField('Representante', validators=[DataRequired(), Length(max=100)])
    cpf_cnpj = StringField('CPF ou CNPJ', validators=[DataRequired(), Length(min=11, max=20)])
    submit = SubmitField('Cadastrar')

class Contato(db.Model):
    codigo = db.Column(db.Integer, primary_key=True)
    data = db.Column(db.DateTime, nullable=False)
    assunto = db.Column(db.String(100), nullable=False)
    descricao = db.Column(db.Text)
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.codigo'))
    cliente = db.relationship('Cliente', backref='contatos')

# 🔹 Modelo de Cliente



class Cliente(db.Model):
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)  # Novo campo para identificação interna
    codigo = db.Column(db.Integer, unique=True, nullable=False)  # Código visível, controlado manualmente
    status = db.Column(db.String(10), nullable=False, default="ativo")  # valores: 'ativo', 'inativo'
    nome_fantasia = db.Column(db.String(255))  # Ajuste o tamanho conforme necessário
    razao_social = db.Column(db.String(120))  # Ajuste o tamanho conforme necessário
    email = db.Column(db.String(120), nullable=True)
    telefone = db.Column(db.String(50))
    data_cadastro = db.Column(db.DateTime, server_default=db.func.now())
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)
    endereco_rua = db.Column(db.String(100))
    endereco_numero = db.Column(db.String(10))
    endereco_complemento = db.Column(db.String(50))
    bairro = db.Column(db.String(50))
    cidade = db.Column(db.String(50))
    estado = db.Column(db.String(2))      # Ex: 'SP', 'RJ'
    cep = db.Column(db.String(9))         # Formato: 00000-000
    cpf_cnpj = db.Column(db.String(20), unique=True, nullable=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    empresa = db.relationship('Empresa', backref='clientes')


    
from wtforms import SelectField
from wtforms.validators import DataRequired, Length, Regexp

from wtforms import StringField
from wtforms.validators import Optional, Email


class ClienteForm(FlaskForm):
    email = StringField('Email', validators=[Optional(), Email()])
    telefone = StringField('Telefone')
    nome_fantasia = StringField("Nome Fantasia", validators=[Length(max=255)])
    razao_social = StringField("Razão Social")
    endereco_rua = StringField('Rua')
    endereco_numero = StringField('Número')
    endereco_complemento = StringField('Complemento')
    bairro = StringField('Bairro')
    cidade = StringField('Cidade')
    estado = StringField('Estado')
    cep = StringField('CEP')
    status = SelectField('Status', choices=[('ativo', 'Ativo'), ('inativo', 'Inativo')], default='ativo')

    cpf_cnpj = StringField('CPF/CNPJ', validators=[
        Optional(),  # ✅ Torna o campo não obrigatório
        Length(min=11, max=20, message="Digite um CPF ou CNPJ válido."),
        Regexp(
            r'^(\d{11}|\d{14}|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})$',
            message="CPF ou CNPJ em formato inválido."
        )
    ])





    



# 🔹 Modelo de Lead
from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

class LogAcao(db.Model):
    __tablename__ = 'log_acao'

    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=False)
    acao = db.Column(db.String(100), nullable=False)
    detalhes = db.Column(db.Text, nullable=True)
    ip = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    data_hora = db.Column(db.DateTime, default=horario_brasilia)
    usuario = db.relationship('Usuario', backref='logs')



from datetime import date
class Lead(db.Model):
    __tablename__ = 'lead'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100))
    email = db.Column(db.String(100))
    telefone = db.Column(db.String(20))
    empresa = db.Column(db.String(100))
    pessoa = db.Column(db.String(100))
    interesses = db.Column(db.Text)
    observacoes = db.Column(db.Text)
    data_cadastro = db.Column(db.DateTime, default=datetime.utcnow)
    data_retorno = db.Column(db.Date)
    arquivado = db.Column(db.Boolean, default=False)
    data_arquivamento = db.Column(db.DateTime, default=None)
    data_desaquivamento = db.Column(db.DateTime, default=None)


    # 📁 Motivo e autor do arquivamento
    motivo_arquivamento = db.Column(db.Text)
    arquivado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    arquivado_por = db.relationship('Usuario', foreign_keys=[arquivado_por_id])

    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.codigo'))
    cliente = db.relationship('Cliente')

    criado_por_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    criado_por = db.relationship('Usuario', backref='leads_lancados', foreign_keys=[criado_por_id])

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    valor_personalizado = db.Column(db.Float, nullable=True)

    origem_id = db.Column(db.Integer, db.ForeignKey('origem_lead.id'))
    origem = db.relationship('OrigemLead')

    status_id = db.Column(db.Integer, db.ForeignKey('status_lead.id'))
    status = db.relationship('StatusLead')

    # 🔗 Relacionamento muitos-para-muitos com produtos
    produtos = db.relationship('Produto', secondary=leads_produtos, backref='leads')






class AtividadeLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tipo = db.Column(db.String(50), nullable=False)
    data = db.Column(db.Date, nullable=False, default=date.today)
    descricao = db.Column(db.Text, nullable=False)

    # Relacionamento com o lead
    lead_id = db.Column(db.Integer, db.ForeignKey('lead.id'), nullable=False)
    lead = db.relationship('Lead', backref=db.backref('atividades', lazy=True))
    usuario = db.relationship('Usuario')


    # Opcional: rastrear quem registrou a atividade
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'), nullable=True)

from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, TextAreaField, SelectField, DateField
from wtforms.validators import DataRequired

class AtividadeLeadForm(FlaskForm):
    tipo = SelectField('Tipo de Atividade', choices=[
        ('ligacao', 'Ligação'),
        ('whatsapp', 'Whatsapp'),
        ('email', 'E-mail'),
        ('visita', 'Visita'),
        ('followup', 'Follow-Up'),
        ('outro', 'Outro')
    ], validators=[DataRequired()])

    data = DateField('Data', format='%Y-%m-%d', validators=[DataRequired()])
    descricao = TextAreaField('Descrição', validators=[DataRequired()])

    submit = SubmitField('Salvar')


class OrigemLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    empresa = db.relationship('Empresa', backref='origens')

class StatusLead(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False, unique=True)
    cor = db.Column(db.String(20))  # opcional, pra personalizar cor do status

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    empresa = db.relationship('Empresa', backref='status_leads')

    
    
class Produto(db.Model):
    __tablename__ = 'produto'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    valor = db.Column(db.Numeric(10, 2), nullable=False)

    empresa_id = db.Column(db.Integer, db.ForeignKey('empresas.id'), nullable=False)
    empresa = db.relationship('Empresa', back_populates='produtos')



from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SelectMultipleField, SubmitField, FloatField, DateField
from wtforms.validators import DataRequired, Email
from wtforms.widgets import ListWidget, CheckboxInput

class LeadForm(FlaskForm):
    nome = StringField('Nome', validators=[DataRequired()])
    email = StringField('Email', validators=[Email()])
    telefone = StringField('Telefone')
    empresa = StringField('Empresa')
    pessoa = StringField('Pessoa de contato')
    interesses = TextAreaField('Interesses')
    observacoes = TextAreaField('Observações')
    data_retorno = DateField('Data de retorno', format='%Y-%m-%d')

    cliente_id = SelectField('Cliente', coerce=int)
    criado_por_id = SelectField('Criado por', coerce=int)
    empresa_id = SelectField('Empresa vinculada', coerce=int, validators=[DataRequired()])
    origem_id = SelectField('Origem do lead', coerce=int)
    status_id = SelectField('Status do lead', coerce=int)
    valor_personalizado = FloatField('Valor personalizado')

    produtos = SelectMultipleField('Produtos',
        coerce=int,
        option_widget=CheckboxInput(),
        widget=ListWidget(prefix_label=False)
    )

    submit = SubmitField('Salvar')



class ExcluirLeadForm(FlaskForm):
    pass  # Só serve para gerar o csrf_token




# 🔹 Modelo de Usuário (login)
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin





