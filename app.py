from flask import (
    Flask, render_template, request, redirect, flash,
    abort, url_for, session, Blueprint
)
from flask_login import (
    LoginManager, login_user, logout_user,
    login_required, current_user
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_wtf import CSRFProtect, FlaskForm
from wtforms import StringField, SubmitField, EmailField, TelField
from slugify import slugify
from werkzeug.security import generate_password_hash
from sqlalchemy import and_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload
from collections import Counter
from zoneinfo import ZoneInfo
import datetime
dt = datetime.datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
from datetime import datetime, date, timezone, UTC
import config
import uuid
import re
import copy
import json
from functools import wraps
from flask_wtf import CSRFProtect
from models import LeadForm
from flask_wtf import FlaskForm
from models import ExcluirLeadForm
from models import EmpresaForm
from models import Empresa
from flask import render_template, request, redirect, url_for, flash
import re
from sqlalchemy import and_, or_





# Modelos
from models import (
    db, Lead, Usuario, Cliente, Contato, Empresa,
    ClienteForm, Log, LogAcao, OrigemLead,
    StatusLead, AtividadeLead
)


# App Flask
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data/empresa.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config.from_object(config)
app.secret_key = 'uma-chave-bem-secreta'

# Extensões
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# Criação automática do banco
with app.app_context():
    db.create_all()

# Login
login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(Usuario, int(user_id))

@app.context_processor
def inject_empresa():
    def formatar_doc(doc):
        doc = (doc or '').replace('.', '').replace('/', '').replace('-', '').strip()

        if len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        else:
            return doc

    empresa_id = session.get('empresa_id')
    empresa = Empresa.query.get(empresa_id) if empresa_id else None

    if empresa and hasattr(empresa, 'cpf_cnpj'):
        empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return dict(empresa=empresa)

# Formulário CSRF vazio
class CSRFForm(FlaskForm):
    pass

# Hora local
hora_do_computador = datetime.now()
print(hora_do_computador.strftime('%d/%m/%Y %H:%M:%S'))

# Funções auxiliares
from flask_login import current_user



def horario_brasilia():
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

def registrar_log(usuario_id, acao, detalhes=None):
    log = LogAcao(
        usuario_id=usuario_id,
        acao=acao,
        detalhes=detalhes,
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
    )
    db.session.add(log)
    db.session.commit()

def gerar_codigo_usuario(empresa_id):
    ultimo = Usuario.query.filter_by(empresa_id=empresa_id).order_by(Usuario.codigo.desc()).first()
    return 1 if not ultimo or ultimo.codigo is None else ultimo.codigo + 1

def permissoes_requeridas(*tipos_permitidos):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if current_user.tipo not in tipos_permitidos:
                abort(403)
            return f(*args, **kwargs)
        return wrapper
    return decorator

# PAGINA INICIAL
from flask import session, render_template, redirect, url_for, flash
from flask_login import current_user
from collections import Counter
from datetime import date

@app.route("/")
def dashboard():
    # 🚨 Verifica se o usuário está logado
    if not current_user.is_authenticated:
        flash("Você precisa estar logado para acessar o painel.", "warning")
        return redirect(url_for('login'))

    empresa_id = current_user.empresa_id
    usuario_id = current_user.id
    is_admin = getattr(current_user, 'is_admin', False) or getattr(current_user, 'tipo', '') == 'admin'

    # 📊 CLIENTES da empresa
    clientes_query = Cliente.query.filter_by(empresa_id=empresa_id)
    total_clientes = clientes_query.count()
    clientes_ativos = clientes_query.filter_by(status="ativo").count()
    clientes_inativos = clientes_query.filter_by(status="inativo").count()
    ultimos_clientes = clientes_query.order_by(Cliente.data_cadastro.desc()).limit(5).all()

    # 📋 LEADS da empresa
    leads_query = Lead.query.filter_by(empresa_id=empresa_id)
    total_leads = leads_query.count()

    # 🔍 Últimos leads (admin vê todos, usuário vê os seus)
    ultimos_leads_query = leads_query.options(
        joinedload(Lead.status),
        joinedload(Lead.origem)
    )
    if not is_admin:
        ultimos_leads_query = ultimos_leads_query.filter_by(criado_por_id=usuario_id)

    ultimos_leads = ultimos_leads_query.order_by(Lead.data_cadastro.desc()).limit(5).all()

    # 📈 Leads agrupados por status
    leads_por_status = db.session.query(
        StatusLead.nome,
        StatusLead.cor,
        db.func.count(Lead.id)
    ).join(Lead, Lead.status_id == StatusLead.id)\
     .filter(Lead.empresa_id == empresa_id)\
     .group_by(StatusLead.nome, StatusLead.cor)\
     .all()

    # 📊 Gráfico por origem (admin vê tudo, usuário vê os seus)
    contagem_origem = Counter(
        lead.origem.nome.strip().title()
        for lead in leads_query
        if lead.origem and lead.origem.nome and (is_admin or lead.criado_por_id == usuario_id)
    )
    origens = list(contagem_origem.keys())
    totais = list(contagem_origem.values())

    # 🧾 Leads com retorno marcado para hoje
    alerta_leads_hoje = None
    leads_retorno_hoje = []
    if session.pop('mostrar_alerta_leads', None):
        hoje = date.today()
        retorno_query = Lead.query.options(
            joinedload(Lead.status),
            joinedload(Lead.origem)
        ).filter_by(
            empresa_id=empresa_id,
            data_retorno=hoje
        )
        if not is_admin:
            retorno_query = retorno_query.filter_by(criado_por_id=usuario_id)

        leads_retorno_hoje = retorno_query.all()
        if leads_retorno_hoje:
            alerta_leads_hoje = 'Atenção: Há leads com retorno marcado para hoje! Confira abaixo.'

    empresa = Empresa.query.get(empresa_id)

    return render_template("dashboard.html",
                           total_clientes=total_clientes,
                           clientes_ativos=clientes_ativos,
                           clientes_inativos=clientes_inativos,
                           ultimos_clientes=ultimos_clientes,
                           total_leads=total_leads,
                           ultimos_leads=ultimos_leads,
                           leads_por_status=leads_por_status,
                           origens=origens,
                           totais=totais,
                           empresa=empresa,
                           alerta_leads_hoje=alerta_leads_hoje,
                           leads_retorno_hoje=leads_retorno_hoje)




from decimal import Decimal
from flask import Blueprint, request, jsonify
from app import db
from models import Produto, Lead
from produto.produto import produto_bp
produto_bp = Blueprint('produto', __name__)




# Criar produto
@produto_bp.route('/api/produto', methods=['POST'])
@login_required
def criar_produto():
    print("Content-Type:", request.content_type)
    print("Raw:", request.data)
    print("Parsed JSON:", request.get_json(silent=True))

    dados = request.get_json()

    if not dados:
        return jsonify({'erro': 'Dados JSON ausentes ou inválidos'}), 400

    nome = dados.get('nome')
    valor_bruto = dados.get('valor', '0')

    print("Valor bruto recebido:", valor_bruto)

    # Validação básica
    if not nome:
        return jsonify({'erro': 'Nome do produto é obrigatório'}), 400

    if valor_bruto in [None, '', 'undefined']:
        return jsonify({'erro': 'Valor do produto não informado'}), 400

    try:
        valor = Decimal(str(valor_bruto))
        if valor <= 0:
            return jsonify({'erro': 'O valor deve ser maior que zero'}), 400
    except Exception:
        return jsonify({'erro': 'Valor inválido'}), 400

    empresa = current_user.empresa
    if not empresa:
        return jsonify({'erro': 'Empresa não vinculada ao usuário'}), 403

    produto = Produto(
        nome=nome,
        valor=valor,
        empresa_id=empresa.id
    )

    db.session.add(produto)
    db.session.commit()

    return jsonify({
        'mensagem': 'Produto cadastrado com sucesso!',
        'id': produto.id
    }), 201


# Listar produtos
@produto_bp.route('/api/produto', methods=['GET'])
@login_required
def listar_produtos():
    # 🏢 Recupera empresa vinculada ao usuário
    empresa = current_user.empresa
    if not empresa:
        return jsonify({'erro': 'Empresa não vinculada ao usuário'}), 403

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    cnpj_formatado = formatar_doc(empresa.cpf_cnpj)

    # 🎯 Apenas produtos da empresa logada
    produtos = Produto.query.filter_by(empresa_id=empresa.id).all()

    resultado = []
    for p in produtos:
        resultado.append({
            'id': p.id,
            'nome': p.nome,
            'valor': float(p.valor)
        })

    return jsonify({
        'produtos': resultado,
        'empresa': {
            'id': empresa.id,
            'nome': empresa.nome,
            'cnpj': cnpj_formatado
        }
    })

# Atualizar produto
@produto_bp.route('/api/produto/<int:id>', methods=['PUT'])
def atualizar_produto(id):
    dados = request.get_json()
    produto = Produto.query.get_or_404(id)
    produto.nome = dados.get('nome', produto.nome)
    produto.valor = dados.get('valor', produto.valor)
    db.session.commit()
    
    return jsonify({'mensagem': 'Produto atualizado com sucesso!'})

# Excluir produto
@produto_bp.route('/api/produto/<int:id>', methods=['DELETE'])
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)

    # Verifica se há leads vinculados a este produto via relacionamento muitos-para-muitos
    if produto.leads:  # .leads é uma lista, não uma query
        return jsonify({
            'mensagem': 'Produto vinculado a um lead. Exclusão não permitida.'
        }), 400

    db.session.delete(produto)
    db.session.commit()

    return jsonify({'mensagem': 'Produto excluído com sucesso!'})

@produto_bp.route('/listar')
def listar_produto_html():
    produtos = Produto.query.filter_by(empresa_id=current_user.empresa_id).all()

    # 🏢 Processamento dos dados da empresa logada
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template('listar_produto.html', produtos=produtos, empresa=empresa)

@produto_bp.route('/produto/novo')
def novo_produto_html():
    return render_template('produto.html')

@produto_bp.route('/produto/editar/<int:id>')
def editar_produto_html(id):
    produto = Produto.query.get_or_404(id)
    return render_template('editar_produto.html', produto=produto)

app.register_blueprint(produto_bp, url_prefix='/produto')






@app.route('/minha_empresa', methods=['GET', 'POST'])
@login_required
def minha_empresa():
    # 🔎 Recupera a empresa vinculada diretamente ou via CNPJ (admin global)
    empresa = current_user.empresa

    if current_user.tipo == 'admin' and current_user.empresa_id is None:
        empresa_id = session.get('empresa_id')
        if empresa_id:
            empresa = Empresa.query.get(empresa_id)

    if not empresa:
        flash('Empresa não encontrada ou não definida.', 'danger')
        return redirect('/login')

    # 📝 Atualização de dados da empresa (somente admin global pode)
    if request.method == 'POST':
        if current_user.tipo != 'admin':
            abort(403)

        nome = request.form.get('nome')
        if not nome or nome.strip() == "":
            flash("⚠️ O campo Nome da Empresa é obrigatório!", "warning")
            return redirect(url_for('minha_empresa'))

        # ⏎ Atualiza os campos da empresa
        empresa.nome = nome
        empresa.cpf_cnpj = request.form.get('cpf_cnpj')
        empresa.telefone = request.form.get('telefone')
        empresa.email = request.form.get('email')
        empresa.endereco = request.form.get('endereco')
        empresa.numero = request.form.get('numero')
        empresa.cidade = request.form.get('cidade')
        empresa.estado = request.form.get('estado')
        empresa.representante = request.form.get('representante')

        db.session.commit()
        flash('✅ Dados da empresa atualizados com sucesso!', 'success')
        return redirect(url_for('listar'))
        empresa = current_user.empresa

    # 🧠 Formatador do campo cpf_cnpj
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)
    # 🎯 Renderiza a página com os dados da empresa
    return render_template('minha_empresa.html', empresa=empresa)


@app.route('/cadastro')
@login_required
def cadastro():
    return render_template('cadastro.html')


# Rota: salvar novo lead
@app.route('/salvar', methods=['POST'])
def salvar():
    nome = request.form.get('nome', '').strip()
    telefone = request.form.get('telefone', '').strip()

    # 👉 Verifica se campos obrigatórios estão preenchidos
    if not nome or not telefone:
        flash('Nome e telefone são obrigatórios para salvar o lead.')
        return redirect('/cadastro')

    # 🧱 Continua o preenchimento dos demais campos
    email = request.form.get('email', '').strip()
    empresa = request.form.get('empresa', '').strip()
    pessoa = request.form.get('pessoa', '').strip()
    origem = request.form.get('origem', '').strip()
    status = request.form.get('status', '').strip()
    interesses = request.form.get('interesses', '').strip()
    observacoes = request.form.get('observacoes', '').strip()

    lead = Lead(
        nome=nome,
        telefone=telefone,
        email=email,
        empresa=empresa,
        pessoa=pessoa,
        origem=origem,
        status=status,
        interesses=interesses,
        observacoes=observacoes
    )

    db.session.add(lead)
    db.session.commit()
    flash('Lead salvo com sucesso!')
    return redirect('/')

# Rota: carregar dados para editar
from flask import abort
#editar lead
from datetime import datetime
import copy  # caso queira usar deepcopy futuramente

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_lead(id):
    lead = Lead.query.get_or_404(id)
    form = LeadForm(obj=lead)

    # Verifica permissão do usuário
    if lead.criado_por_id != current_user.id and current_user.tipo != 'admin':
        flash("⚠️ Você não tem permissão para editar este lead.", "warning")
        return redirect(url_for('listar'))

    # Busca dados para os selects
    clientes = Cliente.query.order_by(Cliente.nome_fantasia).all()
    status_list = StatusLead.query.order_by(StatusLead.nome).all()
    origens = OrigemLead.query.order_by(OrigemLead.nome).all()
    produtos = Produto.query.order_by(Produto.nome).all()

    clientes_dict = {
        str(cliente.codigo): {
            'email': cliente.email or '',
            'telefone': cliente.telefone or '',
            'empresa': cliente.razao_social or ''
        } for cliente in clientes
    }

    produtos_dict = {
        str(produto.id): float(produto.valor) for produto in produtos
    }

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    if request.method == 'POST':
        valores_antigos = {
            'cliente_id': lead.cliente_id,
            'status_id': lead.status_id,
            'pessoa': lead.pessoa,
            'origem_id': lead.origem_id,
            'interesses': lead.interesses,
            'observacoes': lead.observacoes,
            'data_retorno': lead.data_retorno,
            'valor_personalizado': lead.valor_personalizado,
            'produtos_ids': [p.id for p in lead.produtos]
        }

        try:
            lead.cliente_id = int(request.form.get('cliente_id', lead.cliente_id))
            lead.status_id = int(request.form.get('status_id', lead.status_id))
            lead.origem_id = int(request.form.get('origem_id', lead.origem_id))
            lead.pessoa = request.form.get('pessoa')
            lead.interesses = request.form.get('interesses')
            lead.observacoes = request.form.get('observacoes')
            lead.valor_personalizado = float(request.form.get('valor_personalizado') or 0)

            data_retorno_str = request.form.get('data_retorno')
            lead.data_retorno = datetime.strptime(data_retorno_str, "%Y-%m-%d").date() if data_retorno_str else None

            produtos_ids_novos = request.form.getlist('produtos_ids')
            lead.produtos = Produto.query.filter(Produto.id.in_(produtos_ids_novos)).all()

            db.session.commit()

            # Log de alterações
            alteracoes = []
            for campo, valor_antigo in valores_antigos.items():
                if campo == 'produtos_ids':
                    ids_novos = [p.id for p in lead.produtos]
                    if set(ids_novos) != set(valor_antigo):
                        nomes_antigos = [Produto.query.get(pid).nome for pid in valor_antigo]
                        nomes_novos = [p.nome for p in lead.produtos]
                        alteracoes.append(f"Produtos: {nomes_antigos} → {nomes_novos}")
                    continue

                valor_novo = getattr(lead, campo)
                if valor_novo != valor_antigo:
                    if campo == 'status_id':
                        campo = 'Status'
                        valor_antigo = StatusLead.query.get(valor_antigo).nome if valor_antigo else 'Não definido'
                        valor_novo = lead.status.nome if lead.status else 'Não definido'
                    elif campo == 'origem_id':
                        campo = 'Origem'
                        valor_antigo = OrigemLead.query.get(valor_antigo).nome if valor_antigo else 'Não definida'
                        valor_novo = lead.origem.nome if lead.origem else 'Não definida'
                    elif campo == 'cliente_id':
                        campo = 'Cliente'
                        valor_antigo = Cliente.query.get(valor_antigo).nome_fantasia if valor_antigo else 'Não definido'
                        valor_novo = lead.cliente.nome_fantasia if lead.cliente else 'Não definido'
                    elif campo == 'valor_personalizado':
                        campo = 'Valor Personalizado'
                    elif campo == 'data_retorno':
                        valor_antigo = valor_antigo.strftime('%d/%m/%Y') if valor_antigo else 'Sem data'
                        valor_novo = valor_novo.strftime('%d/%m/%Y') if valor_novo else 'Sem data'
                    alteracoes.append(f"{campo}: '{valor_antigo}' → '{valor_novo}'")

            detalhes_log = " | ".join(alteracoes) if alteracoes else "Nenhuma alteração detectada"
            cliente_nome = lead.cliente.nome_fantasia if lead.cliente else "Cliente não identificado"

            registrar_log(
                usuario_id=current_user.id,
                acao="Editou lead",
                detalhes=f"Lead ID: {lead.id}; Cliente: {cliente_nome} | {detalhes_log}"
            )

            flash('✅ Lead atualizado com sucesso!', 'success')
            return redirect(url_for('listar'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao editar lead: {e}")
            flash("❌ Erro interno ao atualizar lead.", "error")

    return render_template(
        'editar_lead.html',
        form=form,
        lead=lead,
        clientes=clientes,
        clientes_dict=clientes_dict,
        produtos_dict=produtos_dict,
        origens=origens,
        status_list=status_list,
        produtos=produtos,
        empresa=empresa
    )

# Rota: atualizar dados do lead
@app.route('/atualizar/<int:id>', methods=['POST'])
@login_required
def atualizar(id):
    lead = Lead.query.get_or_404(id)

    # 🔍 Registro dos dados antigos para o log
    valores_antigos = {
        'cliente_id': lead.cliente_id,
        'pessoa': lead.pessoa,
        'origem_id': lead.origem_id,
        'status_id': lead.status_id,
        'interesses': lead.interesses,
        'observacoes': lead.observacoes,
        'data_retorno': lead.data_retorno,
        'valor_personalizado': lead.valor_personalizado,
        'produtos_ids': [p.id for p in lead.produtos]
    }

    try:
        # 🔄 Atualiza os campos básicos
        lead.cliente_id = int(request.form.get('cliente_id') or lead.cliente_id)
        lead.pessoa = request.form.get('pessoa') or lead.pessoa
        lead.origem_id = int(request.form.get('origem_id') or lead.origem_id)
        lead.status_id = int(request.form.get('status_id') or lead.status_id)
        lead.interesses = request.form.get('interesses') or lead.interesses
        lead.observacoes = request.form.get('observacoes') or lead.observacoes
        lead.valor_personalizado = float(request.form.get('valor_personalizado') or lead.valor_personalizado)

        data_str = request.form.get('data_retorno')
        lead.data_retorno = datetime.strptime(data_str, '%Y-%m-%d').date() if data_str else lead.data_retorno

        # 🧩 Atualiza produtos relacionados
        novos_ids = request.form.getlist('produtos_ids')
        lead.produtos = Produto.query.filter(Produto.id.in_(novos_ids)).all()

        db.session.commit()

        # 📝 Geração de log detalhado
        alteracoes = []
        for campo, valor_antigo in valores_antigos.items():
            if campo == 'produtos_ids':
                ids_novos = [p.id for p in lead.produtos]
                if set(ids_novos) != set(valor_antigo):
                    nomes_antigos = [Produto.query.get(i).nome for i in valor_antigo]
                    nomes_novos = [p.nome for p in lead.produtos]
                    alteracoes.append(f"Produtos vinculados: {nomes_antigos} → {nomes_novos}")
                continue

            valor_novo = getattr(lead, campo)
            if valor_novo != valor_antigo:
                if campo == 'status_id':
                    campo = 'Status'
                    valor_antigo = StatusLead.query.get(valor_antigo).nome if valor_antigo else 'Não definido'
                    valor_novo = lead.status.nome if lead.status else 'Não definido'
                elif campo == 'origem_id':
                    campo = 'Origem'
                    valor_antigo = OrigemLead.query.get(valor_antigo).nome if valor_antigo else 'Não definida'
                    valor_novo = lead.origem.nome if lead.origem else 'Não definida'
                elif campo == 'cliente_id':
                    campo = 'Cliente'
                    valor_antigo = Cliente.query.get(valor_antigo).nome_fantasia if valor_antigo else 'Não definido'
                    valor_novo = lead.cliente.nome_fantasia if lead.cliente else 'Não definido'
                elif campo == 'valor_personalizado':
                    campo = 'Valor Personalizado'
                elif campo == 'data_retorno':
                    valor_antigo = valor_antigo.strftime('%d/%m/%Y') if valor_antigo else 'Sem data'
                    valor_novo = valor_novo.strftime('%d/%m/%Y') if valor_novo else 'Sem data'

                alteracoes.append(f"{campo}: '{valor_antigo}' → '{valor_novo}'")

        cliente_nome = lead.cliente.nome_fantasia if lead.cliente else "Cliente não identificado"
        detalhes_log = " | ".join(alteracoes) if alteracoes else "Nenhuma alteração detectada"

        registrar_log(
            usuario_id=current_user.id,
            acao="Atualizou lead",
            detalhes=f"Lead ID: {lead.id}; Cliente: {cliente_nome} | {detalhes_log}"
        )

        flash("✅ Lead atualizado com sucesso!", "success")
        return redirect(url_for("listar"))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao atualizar lead: {e}")
        flash("❌ Erro interno ao atualizar lead.", "error")
        return redirect(url_for("listar"))




# Rota: excluir lead
@app.route('/excluir_lead/<int:lead_id>', methods=['POST'])
@login_required
def excluir_lead(lead_id):
    form = ExcluirLeadForm()
    if not form.validate_on_submit():
        flash("❌ Erro de segurança: requisição inválida.", "danger")
        return redirect(url_for('listar'))

    lead = Lead.query.get_or_404(lead_id)

    try:
        cliente_nome = lead.cliente.nome_fantasia if lead.cliente else "Cliente não identificado"
        pessoa = lead.pessoa or "Não especificada"
        status_nome = lead.status.nome if lead.status else "Status não definido"
        origem_nome = lead.origem.nome if lead.origem else "Origem não definida"
        produtos_nomes = [p.nome for p in lead.produtos] if lead.produtos else ["Nenhum produto vinculado"]
        valor = f"R$ {lead.valor_personalizado:,.2f}" if lead.valor_personalizado else "Não definido"
        data_retorno = lead.data_retorno.strftime('%d/%m/%Y') if lead.data_retorno else 'Sem data'
        interesses = lead.interesses or "Não informado"
        observacoes = lead.observacoes or "Sem observações"

        detalhes = (
            f"Lead ID: {lead.id}; Cliente: {cliente_nome}; Pessoa: {pessoa}; "
            f"Status: {status_nome}; Origem: {origem_nome}; Produtos: {', '.join(produtos_nomes)}; "
            f"Valor: {valor}; Interesses: {interesses}; Observações: {observacoes}; "
            f"Data de Retorno: {data_retorno}"
        )

        registrar_log(
            usuario_id=current_user.id,
            acao="Excluiu lead",
            detalhes=detalhes
        )

        db.session.delete(lead)
        db.session.commit()

        flash("✅ Lead excluído com sucesso!", "success")
        return redirect(url_for('listar'))

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao excluir lead ID {lead_id}: {e}")
        flash("❌ Erro interno ao excluir o lead.", "danger")
        return redirect(url_for('listar'))


from flask import flash
from flask_login import UserMixin
from flask import Blueprint, render_template, request
from models import Lead  # Certifique-se que o modelo Lead está bem definido
from sqlalchemy import and_
from datetime import datetime
from flask import Flask





# Blueprint registrado com nome 'relatorio'
relatorios_bp = Blueprint('relatorio', __name__)





@relatorios_bp.route('/relatorio_leads', methods=['GET'])
@login_required
def relatorio_leads():
    # 🔎 Parâmetros de filtro (GET)
    origem = request.args.get('origem')
    status = request.args.get('status')
    inicio = request.args.get('inicio')
    fim = request.args.get('fim')

    # 📦 Filtros dinâmicos
    filtros = [Lead.empresa_id == current_user.empresa_id]  # 🔐 Filtro por empresa

    if origem:
        try:
            filtros.append(Lead.origem_id == int(origem))
        except ValueError:
            pass
    if status:
        try:
            filtros.append(Lead.status_id == int(status))
        except ValueError:
            pass
    if inicio:
        try:
            data_inicio = datetime.strptime(inicio, "%Y-%m-%d")
            filtros.append(Lead.data_cadastro >= data_inicio)
        except ValueError:
            pass
    if fim:
        try:
            data_fim = datetime.strptime(fim, "%Y-%m-%d")
            filtros.append(Lead.data_cadastro <= data_fim)
        except ValueError:
            pass

    # 📋 Consulta principal com filtro por empresa
    leads = Lead.query.filter(and_(*filtros)).order_by(Lead.data_cadastro.desc()).all()

    # 🏢 Dados da empresa logada
    empresa = current_user.empresa

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    # 🔄 Carrega status e origens para os filtros
    status_leads = StatusLead.query.order_by(StatusLead.nome.asc()).all()
    origens = OrigemLead.query.order_by(OrigemLead.nome.asc()).all()

    # 🖼️ Renderiza template com todos os dados
    return render_template(
        'relatorio_leads.html',
        leads=leads,
        status_leads=status_leads,
        origens=origens,
        origem=origem,
        status=status,
        inicio=inicio,
        empresa=empresa,
        fim=fim
    )



#logar no sistema
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        nome_usuario = request.form.get('nome_usuario', '').strip()
        senha = request.form.get('senha', '').strip()
        cpf_cnpj = request.form.get('cpf_cnpj', '').replace('.', '').replace('/', '').replace('-', '').strip()

        usuario = Usuario.query.filter_by(nome_usuario=nome_usuario).first()

        # ⚠️ Validação inicial
        if not usuario:
            flash('Usuário não encontrado.', 'danger')
            return redirect('/login')

        if not usuario.ativo:
            flash('Este usuário está inativo.', 'danger')
            return redirect('/login')

        # ⚡ Verifica admin global
        if usuario.tipo == 'admin' and usuario.empresa_id is None:
            if usuario.verificar_senha(senha):
                login_user(usuario)

                session['empresa_id'] = None
                session['empresa_nome'] = 'Admin Global'

                flash('Login como admin global realizado com sucesso.', 'success')
                return redirect('/')
            else:
                flash('Senha incorreta.', 'danger')
                return redirect('/login')

        # 🧾 Valida CPF/CNPJ para usuários vinculados
        if not cpf_cnpj or not cpf_cnpj.isdigit() or len(cpf_cnpj) not in [11, 14]:
            flash('CPF ou CNPJ inválido.', 'danger')
            return redirect('/login')

        empresa = Empresa.query.filter_by(cpf_cnpj=cpf_cnpj).first()
        if not empresa:
            flash('Empresa com esse CPF/CNPJ não encontrada.', 'danger')
            return redirect('/login')

        # 🔐 Verifica vínculo empresa
        if usuario.empresa_id != empresa.id:
            flash('Este usuário não tem acesso à empresa informada.', 'danger')
            return redirect('/login')

        # 🔑 Verifica senha e finaliza login
        if usuario.verificar_senha(senha):
            login_user(usuario)

            session['empresa_id'] = empresa.id
            session['empresa_nome'] = empresa.nome
            session['mostrar_alerta_leads'] = True

            return redirect('/')
        else:
            flash('Usuário ou senha inválidos.', 'danger')
            return redirect('/login')

    return render_template('login.html')


#lista de funcionarios
@app.route('/listar_funcionarios')
@login_required
def listar_funcionarios():
    termo = request.args.get('busca')

    # 👤 Verifica se o usuário logado é admin global
    if current_user.tipo == 'admin' and current_user.empresa_id is None:
        # Admin global vê todos os funcionários vinculados a empresas
        filtro_base = Usuario.query.filter(
            Usuario.empresa_id.isnot(None),
            Usuario.tipo.in_(['funcionario', 'vendedor', 'admin', 'gerente'])
        )
    else:
        # Admin comum ou gerente vê os da sua própria empresa
        filtro_base = Usuario.query.filter(
            Usuario.empresa_id == current_user.empresa_id,
            Usuario.tipo.in_(['funcionario', 'vendedor', 'admin', 'gerente'])
        )

    # 🔎 Aplica filtro de busca, se houver termo
    if termo:
        filtro_base = filtro_base.filter(
            (Usuario.nome.ilike(f"%{termo}%")) |
            (Usuario.email.ilike(f"%{termo}%"))
        )

    # 📋 Lista ordenada por ID decrescente
    funcionarios = filtro_base.order_by(Usuario.id.desc()).all()
    empresa = current_user.empresa

    # 🧠 Formatador do campo cpf_cnpj
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)
    
    return render_template('listar_funcionarios.html', funcionarios=funcionarios)

from flask import redirect, flash, url_for
from flask_login import logout_user

@app.route('/logout')
def logout():
    logout_user()
    return redirect('/login')
@app.route('/entrada')
def entrada():
    return render_template('entrada.html')

from flask_login import current_user, login_required

@app.route('/inicio')
@login_required
def inicio():
    if current_user.is_authenticated:
        return redirect('/')  # vai para painel principal (lista de leads)
    else:
        return redirect('/entrada')  # volta para página pública
    
    
from datetime import datetime

from models import Cliente, Lead, StatusLead, OrigemLead  # certifique-se de importar tudo corretamente

@app.route('/criar_lead', methods=['GET', 'POST'])
@login_required
def criar_lead():
    form = LeadForm()
    lead = None
    cliente_selecionado = None
    cliente_codigo = request.args.get('cliente_codigo')

    if cliente_codigo:
        try:
            cliente_codigo_int = int(cliente_codigo)
            cliente_selecionado = Cliente.query.filter_by(codigo=cliente_codigo_int).first()
            if not cliente_selecionado:
                flash('❌ Cliente não encontrado na criação de lead.', 'danger')
        except ValueError:
            flash('❌ Parâmetro de cliente inválido.', 'danger')

    clientes = Cliente.query.order_by(Cliente.nome_fantasia).all()
    status_list = StatusLead.query.order_by(StatusLead.nome).all()
    origens = OrigemLead.query.order_by(OrigemLead.nome).all()
    produtos = Produto.query.order_by(Produto.nome).all()

    # ✅ Dicionário seguro para uso com |tojson
    clientes_dict = {
        str(cliente.codigo): {
            'email': cliente.email or '',
            'telefone': cliente.telefone or ''
        } for cliente in clientes
    }

    produtos_dict = {
        str(produto.id): float(produto.valor) for produto in produtos
    }

    # 🔁 Se método POST: criar lead
    if request.method == 'POST':
        db.session.rollback()
        try:
            nome = request.form.get('nome')
            email = request.form.get('email')
            telefone = request.form.get('telefone')
            cliente_codigo = int(request.form.get('cliente_id'))
            status_id = int(request.form.get('status_id'))
            origem_id = int(request.form.get('origem_id'))
            pessoa = request.form.get('pessoa')
            interesses = request.form.get('interesses')
            observacoes = request.form.get('observacoes')
            valor_personalizado = float(request.form.get('valor_personalizado') or 0)

            produtos_ids = request.form.getlist('produtos_ids')
            produtos_associados = Produto.query.filter(Produto.id.in_(produtos_ids)).all()

            data_retorno_str = request.form.get('data_retorno')
            data_retorno = datetime.strptime(data_retorno_str, '%Y-%m-%d').date() if data_retorno_str else None
            empresa_id = session.get('empresa_id')

            if not empresa_id:
                flash('⚠️ Sessão inválida: nenhuma empresa ativa.', 'danger')
                return redirect(url_for('login'))

            cliente = Cliente.query.filter_by(codigo=cliente_codigo).first()
            status = StatusLead.query.get(status_id)
            origem = OrigemLead.query.get(origem_id)

            if not cliente or not status or not origem:
                flash('❌ Dados inválidos para criação de lead.', 'danger')
                return redirect(url_for('criar_lead'))

            novo_lead = Lead(
                nome=nome,
                email=email,
                telefone=telefone,
                cliente_id=cliente.id,
                pessoa=pessoa,
                status_id=status.id,
                origem_id=origem.id,
                valor_personalizado=valor_personalizado,
                interesses=interesses,
                observacoes=observacoes,
                data_retorno=data_retorno,
                criado_por_id=current_user.id,
                empresa_id=empresa_id
            )

            novo_lead.produtos = produtos_associados
            db.session.add(novo_lead)
            db.session.commit()

            registrar_log(
                usuario_id=current_user.id,
                acao="Criou lead",
                detalhes=(
                    f"Lead ID: {novo_lead.id}, Cliente: {cliente.nome_fantasia}, "
                    f"Produtos: {[p.nome for p in produtos_associados]}, Valor: R$ {valor_personalizado:,.2f}, "
                    f"Status: {status.nome}, Origem: {origem.nome}"
                )
            )

            flash('✅ Lead criado com sucesso!', 'success')
            return redirect(url_for('listar'))

        except Exception as e:
            db.session.rollback()
            flash(f'❌ Ocorreu um erro ao criar o lead: {str(e)}', 'danger')

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = current_user.empresa
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template(
        'criar_lead.html',
        lead=lead,
        form=form,
        clientes=clientes,
        clientes_dict=clientes_dict,
        produtos_dict=produtos_dict,
        cliente_selecionado=cliente_selecionado,
        status_list=status_list,
        origens=origens,
        produtos=produtos,
        empresa=empresa
    )

    




 #listar leads  
@app.route('/listar')
@login_required
def listar():
    form = ExcluirLeadForm()
    busca = request.args.get('busca', '')
    status = request.args.get('status', '')
    sort_by = request.args.get('sort_by', 'data_cadastro')
    order = request.args.get('order', 'desc')
    arquivados = request.args.get('arquivados', type=int)
    hoje = date.today()

    query = Lead.query.options(
        joinedload(Lead.cliente),
        joinedload(Lead.origem),
        joinedload(Lead.status),
        joinedload(Lead.criado_por),
        joinedload(Lead.produtos)
    ).filter(Lead.empresa_id == current_user.empresa_id)

    if arquivados:
        query = query.filter(Lead.arquivado.is_(True))
    else:
        query = query.filter(Lead.arquivado.is_(False))

    if busca:
        query = query.join(Lead.cliente).join(Lead.origem).join(Lead.status).join(Lead.produtos).filter(
            (Cliente.nome_fantasia.ilike(f'%{busca}%')) |
            (OrigemLead.nome.ilike(f'%{busca}%')) |
            (StatusLead.nome.ilike(f'%{busca}%')) |
            (Produto.nome.ilike(f'%{busca}%'))
        )

    if status:
        query = query.join(Lead.status).filter(StatusLead.nome == status)

    if sort_by == 'cliente':
        query = query.join(Lead.cliente)
        coluna = Cliente.nome_fantasia
    elif sort_by == 'origem':
        query = query.join(Lead.origem)
        coluna = OrigemLead.nome
    elif sort_by == 'status':
        query = query.join(Lead.status)
        coluna = StatusLead.nome
    elif sort_by == 'valor_personalizado':
        coluna = Lead.valor_personalizado
    elif sort_by == 'responsavel':
        query = query.join(Lead.criado_por)
        coluna = Usuario.nome_usuario
    elif sort_by == 'produto':
        query = query.join(Lead.produtos)
        coluna = Produto.nome
    elif sort_by in ['data_cadastro', 'data_retorno']:
        coluna = getattr(Lead, sort_by)
    else:
        coluna = Lead.data_cadastro

    if current_user.tipo != 'admin':
        query = query.filter(Lead.criado_por_id == current_user.id)

    leads = query.order_by(coluna.desc() if order == 'desc' else coluna.asc()).all()

    if 'lead_atualizado' in request.args:
        flash('Lead atualizado com sucesso!', 'success')

    empresa = current_user.empresa

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)
    todos_status = StatusLead.query.order_by(StatusLead.nome).all()

    return render_template(
        'listar.html',
        leads=leads,
        todos_status=todos_status,
        status=status,
        arquivados=bool(arquivados),
        form=form,
        hoje=hoje,
        empresa=empresa,
        busca=busca,
        sort_by=sort_by,
        order=order
    )

lead_bp = Blueprint('lead', __name__, url_prefix='/lead')
#ARQUIVAR LEAD
from datetime import datetime

@app.route('/lead/<int:id>/arquivar', methods=['PUT'])
def arquivar_lead(id):
    lead = Lead.query.get_or_404(id)
    lead.arquivado = True
    lead.data_arquivamento = datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    lead.data_desaquivamento = None
    lead.arquivado_por_id = current_user.id  # se estiver usando login
    lead.motivo_arquivamento = request.json.get('motivo')
    db.session.commit()
    return jsonify({"message": "Lead arquivado com sucesso!"})

#DESARQUIVAR LEAD
@app.route('/lead/api/desarquivar/<int:id>', methods=['PUT'])
def desarquivar_lead(id):
    lead = Lead.query.get_or_404(id)
    lead.arquivado = False
    lead.data_desaquivamento = datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
    lead.data_arquivamento = None
    db.session.commit()
    return jsonify({"message": "Lead desarquivado com sucesso!"})

#ARQUIVAR MULTIPLOS
@lead_bp.route('/api/arquivar-multiplos', methods=['PUT'])
@login_required
def arquivar_leads_em_lote():
    data = request.get_json()
    ids = data.get('ids', [])
    motivo = data.get('motivo', '').strip()

    if not ids:
        return jsonify({'mensagem': 'Nenhum ID recebido.'}), 400
    if not motivo:
        return jsonify({'mensagem': 'Motivo do arquivamento é obrigatório.'}), 400

    leads = Lead.query.filter(
        Lead.id.in_(ids),
        Lead.empresa_id == current_user.empresa_id
    ).all()

    for lead in leads:
        lead.arquivado = True
        lead.motivo_arquivamento = motivo
        lead.data_arquivamento = datetime.now(tz=ZoneInfo("America/Sao_Paulo"))
        lead.data_desaquivamento = None
        lead.arquivado_por_id = current_user.id  # 🔒 salvar quem arquivou

    db.session.commit()
    return jsonify({'mensagem': f'{len(leads)} leads arquivados com sucesso.'})

app.register_blueprint(lead_bp)


from forms import AtividadeForm
from models import AtividadeLeadForm
#NOVA ATIVIDADE
@app.route('/lead/<int:lead_id>/nova_atividade', methods=['GET', 'POST'])
@login_required
def nova_atividade(lead_id):
    form = AtividadeLeadForm()
    lead = Lead.query.get_or_404(lead_id)

    # 🏢 Processamento dos dados da empresa logada
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    if form.validate_on_submit():
        # ✅ Criação da nova atividade
        nova = AtividadeLead(
            tipo=form.tipo.data,
            data=form.data.data,
            descricao=form.descricao.data,
            lead_id=lead.id,
            usuario_id=current_user.id
        )
        db.session.add(nova)
        db.session.commit()

        # 🗂 Registro da ação no log
        log = LogAcao(
            usuario_id=current_user.id,
            acao='nova_atividade',
            detalhes=f"Atividade '{form.tipo.data}' registrada para lead #{lead.id} ({lead.cliente.nome_fantasia})",
            ip=request.remote_addr,
            user_agent=request.headers.get('User-Agent')
        )
        db.session.add(log)
        db.session.commit()

        flash('atividade_registrada', 'success')
        return redirect(url_for('detalhes_lead', lead_id=lead.id))

    # 👀 Renderiza o template com os dados da empresa
    return render_template('nova_atividade.html', form=form, lead=lead, empresa=empresa)

#SALVAR ATIVIDADE
@app.route('/lead/<int:lead_id>/salvar_atividade', methods=['POST'])
@login_required
def salvar_atividade(lead_id):
    lead = Lead.query.get_or_404(lead_id)

    tipo = request.form.get('tipo')
    data_str = request.form.get('data')
    descricao = request.form.get('descricao')

    # 🚦 Validação básica
    if not all([tipo, data_str, descricao]):
        flash('Preencha todos os campos da atividade.', 'warning')
        return redirect(url_for('nova_atividade', lead_id=lead.id))

    try:
        data = datetime.strptime(data_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Data inválida. Use o formato correto.', 'danger')
        return redirect(url_for('nova_atividade', lead_id=lead.id))

    # ✅ Criação da atividade
    nova_atividade = AtividadeLead(
        tipo=tipo,
        data=data,
        descricao=descricao,
        lead_id=lead.id,
        usuario_id=current_user.id
    )
    db.session.add(nova_atividade)
    db.session.commit()

    # 🧾 Registro no log_acao
    log = LogAcao(
        usuario_id=current_user.id,
        acao='salvar_atividade',
        detalhes=f"Atividade '{tipo}' registrada para lead #{lead.id} ({lead.cliente.nome_fantasia})",
        ip=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    db.session.add(log)
    db.session.commit()

    flash('atividade_registrada', 'success')
    return redirect(url_for('detalhes_lead', lead_id=lead.id))






    

@app.route('/salvar_cliente', methods=['POST'])
@login_required
@permissoes_requeridas('admin', 'gerente')
def salvar_cliente():
    cliente = Cliente(
        nome=request.form['nome'],
        email=request.form['email'],
        telefone=request.form['telefone'],
        empresa=request.form['empresa']
    )
    db.session.add(cliente)
    db.session.commit()
    flash('Cliente cadastrado com sucesso!' 'success')
    return redirect('/listar_clientes')
def gerar_codigo_cliente():
    ultimo = Cliente.query.order_by(Cliente.id.desc()).first()
    sequencia = (ultimo.id + 1) if ultimo else 1
    return str(sequencia).zfill(6)



def validar_cpf_cnpj(valor):
    valor = re.sub(r'\D', '', valor)
    if len(valor) == 11:
        return validar_cpf(valor)
    elif len(valor) == 14:
        return validar_cnpj(valor)
    return False
def validar_cpf(cpf):
    cpf = ''.join(filter(str.isdigit, cpf))
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    soma1 = sum(int(cpf[i]) * (10 - i) for i in range(9))
    digito1 = (soma1 * 10 % 11) % 10
    soma2 = sum(int(cpf[i]) * (11 - i) for i in range(10))
    digito2 = (soma2 * 10 % 11) % 10
    return cpf[-2:] == f"{digito1}{digito2}"
def validar_cnpj(cnpj):
    cnpj = ''.join(filter(str.isdigit, cnpj))
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    soma1 = sum(int(cnpj[i]) * pesos1[i] for i in range(12))
    digito1 = 11 - (soma1 % 11)
    digito1 = digito1 if digito1 < 10 else 0

    pesos2 = [6] + pesos1
    soma2 = sum(int(cnpj[i]) * pesos2[i] for i in range(13))
    digito2 = 11 - (soma2 % 11)
    digito2 = digito2 if digito2 < 10 else 0

    return cnpj[-2:] == f"{digito1}{digito2}"

@app.route('/criar_cliente', methods=['GET', 'POST'])
@login_required
def criar_cliente():
    form = ClienteForm()

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    if form.validate_on_submit():
        cpf_cnpj = form.cpf_cnpj.data.strip()
        cpf_cnpj_limpo = None

        if cpf_cnpj:
            # Remove pontuação
            cpf_cnpj_limpo = re.sub(r'\D', '', cpf_cnpj)

            if not validar_cpf_cnpj(cpf_cnpj_limpo):
                flash("CPF ou CNPJ inválido.", "erro")
                return render_template("criar_cliente.html", form=form, empresa=empresa)

            if Cliente.query.filter(
                Cliente.cpf_cnpj.isnot(None),
                Cliente.cpf_cnpj == cpf_cnpj_limpo
            ).first():
                flash("CPF/CNPJ já cadastrado.", "erro")
                return render_template("criar_cliente.html", form=form, empresa=empresa)

        try:
            ultimo_cliente = Cliente.query.order_by(Cliente.codigo.desc()).first()
            ultimo_numero = ultimo_cliente.codigo if ultimo_cliente else 0
            numero = ultimo_numero + 1

            while Cliente.query.filter_by(codigo=numero).first():
                numero += 1

            codigo_valor = numero
        except Exception as e:
            app.logger.error(f"Erro ao gerar código do cliente: {e}")
            codigo_valor = int(datetime.utcnow().strftime("%H%M%S"))

        cliente = Cliente(
            codigo=codigo_valor,
            razao_social=form.razao_social.data,
            nome_fantasia=form.nome_fantasia.data,
            email=form.email.data,
            telefone=form.telefone.data,
            cpf_cnpj=cpf_cnpj_limpo,  # ✅ Salva limpo ou None
            endereco_rua=form.endereco_rua.data,
            endereco_numero=form.endereco_numero.data,
            endereco_complemento=form.endereco_complemento.data,
            bairro=form.bairro.data,
            cidade=form.cidade.data,
            estado=form.estado.data,
            cep=form.cep.data,
            status=form.status.data,
            data_criacao=datetime.utcnow(),
            empresa_id=empresa.id
        )

        try:
            db.session.add(cliente)
            db.session.commit()

            cliente_documento = formatar_doc(cliente.cpf_cnpj)
            registrar_log(
                usuario_id=current_user.id,
                acao="Criou cliente",
                detalhes=f"Código: {cliente.codigo}, Nome Fantasia: {cliente.nome_fantasia}, CPF/CNPJ: {cliente_documento}"
            )

            flash("Registro salvo com sucesso!", "success")
            return redirect(url_for("listar_clientes"))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao salvar cliente: {e}")
            flash("Erro interno ao salvar cliente.", "erro")

    return render_template("criar_cliente.html", form=form, empresa=empresa)










from flask import flash

@app.route("/novo_contato/<int:cliente_codigo>", methods=["GET", "POST"])
@login_required
def novo_contato(cliente_codigo):
    cliente = Cliente.query.get_or_404(cliente_codigo)

    if request.method == "POST":
        try:
            data = datetime.strptime(request.form["data"], "%Y-%m-%dT%H:%M")
            assunto = request.form["assunto"]
            descricao = request.form["descricao"]

            novo = Contato(data=data, assunto=assunto, descricao=descricao, cliente=cliente)
            db.session.add(novo)
            db.session.commit()

            # 📝 Log de criação de contato
            registrar_log(
                usuario_id=current_user.id,
                acao="Criou contato",
                detalhes=f"Cliente Código: {cliente.nome_fantasia}, Assunto: {assunto}, Data: {data.strftime('%Y-%m-%d %H:%M')}"
            )

            flash('contato_salvo', 'success')
            return redirect(url_for("detalhes_cliente", cliente_codigo=cliente.codigo))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao salvar contato: {e}")
            flash("Erro ao salvar contato.", "erro")
            return redirect(url_for("detalhes_cliente", cliente_codigo=cliente.codigo))
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template("novo_contato.html", cliente=cliente)

@app.route('/detalhes_cliente/<int:cliente_codigo>')
@login_required
def detalhes_cliente(cliente_codigo):
    cliente = Cliente.query.get_or_404(cliente_codigo)

    # 🔄 Ordena os contatos do cliente por data decrescente
    contatos_ordenados = sorted(cliente.contatos, key=lambda c: c.data, reverse=True)
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template('detalhes_cliente.html', cliente=cliente, contatos=contatos_ordenados)

@app.route("/relatorio_clientes")
@login_required
def relatorio_clientes():
    inicio = request.args.get("inicio")
    fim = request.args.get("fim")
    status = request.args.get("status")

    # 🔐 Filtro por empresa
    filtros = [Cliente.empresa_id == current_user.empresa_id]

    if status:
        filtros.append(Cliente.status == status)
    if inicio:
        try:
            dt_inicio = datetime.strptime(inicio, "%Y-%m-%d")
            filtros.append(Cliente.data_cadastro >= dt_inicio)
        except ValueError:
            pass
    if fim:
        try:
            dt_fim = datetime.strptime(fim, "%Y-%m-%d")
            filtros.append(Cliente.data_cadastro <= dt_fim)
        except ValueError:
            pass

    # 📋 Consulta com todos os filtros aplicados
    clientes = Cliente.query.filter(and_(*filtros)).order_by(Cliente.data_cadastro.desc()).all()

    empresa = current_user.empresa

    # 🧠 Formatador do campo cpf_cnpj
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template("relatorio_clientes.html", clientes=clientes)


#cadastro origens
@app.route('/origens', methods=['GET', 'POST'])
@login_required
def gerenciar_origens():
    form = CSRFForm()

    # 🔎 Buscar termo de pesquisa (GET)
    termo = request.args.get('busca', '').strip()

    # 🏢 Recupera empresa vinculada ao usuário logado
    empresa = current_user.empresa

    # 📋 Filtro por empresa
    base_query = OrigemLead.query.filter_by(empresa_id=empresa.id)

    # 🎯 Filtra origens pelo nome, se tiver termo
    if termo:
        origens = base_query.filter(OrigemLead.nome.ilike(f'%{termo}%')).order_by(OrigemLead.nome.asc()).all()
    else:
        origens = base_query.order_by(OrigemLead.nome.asc()).all()

    # ➕ Criação de nova origem (POST)
    if request.method == 'POST' and form.validate_on_submit():
        nome = request.form['nome'].strip()
        if nome:
            nova = OrigemLead(nome=nome, empresa_id=empresa.id)  # 🔐 Vincula à empresa
            db.session.add(nova)
            db.session.commit()
            return redirect(url_for('gerenciar_origens'))

    # 🧠 Formatador do campo cpf_cnpj
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    # 🧪 Instancia CSRFForm para cada item da lista de exclusão
    formularios_exclusao = {o.id: CSRFForm() for o in origens}

    # ✅ Envia tudo pro template
    return render_template(
        'gerenciar_origens.html',
        origens=origens,
        busca=termo,
        form=form,
        formularios_exclusao=formularios_exclusao
    )
@app.route('/excluir_origem/<int:id>', methods=['POST'])
@login_required
def excluir_origem(id):
    if current_user.tipo != 'admin':
        return jsonify(status='error', message='⛔ Você não tem permissão para excluir origem.'), 403

    origem = OrigemLead.query.get_or_404(id)

    # Verifica se há leads usando essa origem
    leads_vinculados = Lead.query.filter_by(origem_id=origem.id).count()
    if leads_vinculados > 0:
        return jsonify(status='error', message='❌ Esta origem está vinculada a um ou mais leads e não pode ser excluída.'), 400

    db.session.delete(origem)
    db.session.commit()
    return jsonify(status='success', message='✅ Origem excluída com sucesso.'), 200

#status lead
@app.route('/status', methods=['GET', 'POST'])
@login_required
def gerenciar_status():
    form = CSRFForm()
    busca = request.args.get('busca', '').strip()

    empresa = current_user.empresa

    # 🎯 Filtra registros conforme a busca e empresa
    base_query = StatusLead.query.filter_by(empresa_id=empresa.id)

    if busca:
        status_list = base_query.filter(StatusLead.nome.ilike(f'%{busca}%')).order_by(StatusLead.nome.asc()).all()
    else:
        status_list = base_query.order_by(StatusLead.nome.asc()).all()

    # ✅ Instanciar formulários de exclusão só depois de obter a lista
    formularios_exclusao = {s.id: CSRFForm() for s in status_list}

    # ➕ Criação de novo status com proteção CSRF
    if request.method == 'POST' and form.validate_on_submit():
        nome = request.form.get('nome', '').strip()
        cor = request.form.get('cor', '#0d6efd').strip()  # cor padrão azul

        if nome:
            novo_status = StatusLead(nome=nome, cor=cor, empresa_id=empresa.id)  # 🔐 Vincula à empresa
            db.session.add(novo_status)
            db.session.commit()
            return redirect(url_for('gerenciar_status'))

    # 🧠 Formatador do documento da empresa
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    # 🧾 Envia dados pro template
    return render_template(
        'gerenciar_status.html',
        status_list=status_list,
        busca=busca,
        form=form,
        formularios_exclusao=formularios_exclusao
    )

from flask import jsonify

@app.route('/excluir_status/<int:id>', methods=['POST'])
@login_required
def excluir_status(id):
    if current_user.tipo != 'admin':
        return jsonify(status='error', message='⛔ Você não tem permissão para excluir status.'), 403

    status = StatusLead.query.get_or_404(id)

    # 🚨 Verifica se há leads vinculados ao status
    leads_vinculados = Lead.query.filter_by(status_id=status.id).count()
    if leads_vinculados > 0:
        return jsonify(status='error', message='❌ Este status está vinculado a um ou mais leads e não pode ser excluído.'), 400

    db.session.delete(status)
    db.session.commit()
    return jsonify(status='success', message='✅ Status excluído com sucesso.'), 200




#detalhes lead
@app.route('/detalhes_lead/<int:lead_id>')
@login_required
def detalhes_lead(lead_id):
    lead = Lead.query.get_or_404(lead_id)
    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)
    return render_template('detalhes_lead.html', lead=lead, empresa=empresa)

@app.route('/ver_contato/<int:contato_id>')
def ver_contato(contato_id):
    contato = Contato.query.get_or_404(contato_id)
    return render_template('ver_contato.html', contato=contato)

from sqlalchemy.exc import IntegrityError

from sqlalchemy.exc import IntegrityError

from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_

def gerar_codigo_por_empresa(empresa_id):
    ultimo = Usuario.query.filter_by(empresa_id=empresa_id).order_by(
        cast(Usuario.codigo, Integer).desc()
    ).first()
    try:
        return str(int(ultimo.codigo) + 1)
    except (AttributeError, ValueError):
        return '1'
    
from sqlalchemy.exc import IntegrityError


from datetime import datetime

@app.route('/criar_usuario', methods=['GET', 'POST'])
@login_required
@permissoes_requeridas('admin')
def criar_usuario():
    empresas = []
    empresa_id = current_user.empresa_id

    # 🔄 Se admin global, carrega lista de empresas
    admin_global = empresa_id is None and current_user.tipo == 'admin'
    if admin_global:
        empresas = Empresa.query.order_by(Empresa.nome.asc()).all()

    if request.method == 'POST':
        nome = request.form.get('nome', '').strip()
        nome_usuario = request.form.get('nome_usuario', '').strip()
        email = request.form.get('email', '').strip()
        senha = request.form.get('senha', '').strip()
        tipo = request.form.get('tipo') or 'vendedor'

        # 🆕 Novos campos
        telefone = request.form.get('telefone', '').strip()
        documento = request.form.get('documento', '').strip()
        nascimento_str = request.form.get('nascimento')
        rua = request.form.get('rua', '').strip()
        numero = request.form.get('numero', '').strip()
        bairro = request.form.get('bairro', '').strip()
        cep = request.form.get('cep', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()

        # 🗓️ Conversão para objeto date
        nascimento = None
        if nascimento_str:
            try:
                nascimento = datetime.strptime(nascimento_str, '%Y-%m-%d').date()
            except ValueError:
                flash("⚠️ Data de nascimento inválida. Use o formato YYYY-MM-DD.", "warning")
                return render_template('criar_usuario.html', empresas=empresas)

        # 🏢 Se admin global, pega empresa selecionada via slug
        if admin_global:
            slug = request.form.get('empresa_slug')
            empresa_selecionada = Empresa.query.filter_by(slug=slug).first()
            if not empresa_selecionada:
                flash("Empresa selecionada é inválida.", "danger")
                return render_template('criar_usuario.html', empresas=empresas)
            empresa_id = empresa_selecionada.id

        # 🛡️ Validações de unicidade
        alerta = None
        if Usuario.query.filter_by(nome=nome).first():
            alerta = 'nome'
        elif Usuario.query.filter_by(nome_usuario=nome_usuario).first():
            alerta = 'nome_usuario'
        elif Usuario.query.filter_by(email=email).first():
            alerta = 'email'

        if alerta:
            return render_template('criar_usuario.html',
                                   alerta=alerta,
                                   nome=nome,
                                   nome_usuario=nome_usuario,
                                   email=email,
                                   tipo=tipo,
                                   empresas=empresas)

        # 🔐 Geração de código único
        admin_existente = Usuario.query.filter_by(tipo='admin').first()

        if tipo == 'admin' and not admin_existente:
            codigo = 1
        else:
            ultimo = Usuario.query.filter_by(empresa_id=empresa_id).order_by(Usuario.codigo.desc()).first()
            codigo = (ultimo.codigo + 1) if ultimo and isinstance(ultimo.codigo, int) else 1

        try:
            novo_usuario = Usuario(
                nome=nome,
                nome_usuario=nome_usuario,
                email=email,
                tipo=tipo,
                empresa_id=empresa_id,
                codigo=codigo,
                telefone=telefone,
                documento=documento,
                nascimento=nascimento,
                rua=rua,
                numero=numero,
                bairro=bairro,
                cep=cep,
                cidade=cidade,
                estado=estado
            )
            novo_usuario.set_senha(senha)
            db.session.add(novo_usuario)
            db.session.commit()

            registrar_log(
                usuario_id=current_user.id,
                acao="Criou usuário",
                detalhes=f"Código: {codigo}, Nome: {nome}, Nome de usuário: {nome_usuario}, Email: {email}, Tipo: {tipo}"
            )

            return render_template('criar_usuario.html', alerta='salvo', empresas=empresas)

        except IntegrityError as e:
            db.session.rollback()
            print("Erro ao salvar usuário:", str(e))
            flash("Erro inesperado ao salvar. Verifique os dados e tente novamente.", "danger")

            return render_template('criar_usuario.html',
                                   alerta='erro_interno',
                                   nome=nome,
                                   nome_usuario=nome_usuario,
                                   email=email,
                                   tipo=tipo,
                                   empresas=empresas)

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa = current_user.empresa
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template('criar_usuario.html', empresas=empresas)


from datetime import datetime

@app.route('/salvar_usuarios', methods=['POST'])
@login_required
@permissoes_requeridas('admin')
def salvar_usuarios():
    nome = request.form['nome']
    nome_usuario = request.form['nome_usuario']
    email = request.form['email']
    senha = request.form['senha']
    tipo = request.form['tipo']

    # 🆕 Novos campos
    telefone = request.form.get('telefone', '').strip()
    documento = request.form.get('documento', '').strip()
    nascimento_str = request.form.get('nascimento')
    rua = request.form.get('rua', '').strip()
    numero = request.form.get('numero', '').strip()
    bairro = request.form.get('bairro', '').strip()
    cep = request.form.get('cep', '').strip()
    cidade = request.form.get('cidade', '').strip()
    estado = request.form.get('estado', '').strip()

    # 🗓️ Converte nascimento para objeto date
    nascimento = None
    if nascimento_str:
        try:
            nascimento = datetime.strptime(nascimento_str, '%Y-%m-%d').date()
        except ValueError:
            flash("⚠️ Data de nascimento inválida. Use o formato YYYY-MM-DD.", "warning")
            return redirect('/cadastro_usuarios')

    # 🔍 Verifica se já existe usuário com mesmo nome_usuario ou email
    existente = Usuario.query.filter(
        (Usuario.nome_usuario == nome_usuario) | (Usuario.email == email)
    ).first()

    if existente:
        flash('Já existe um usuário com este nome de usuário ou email.')
        return redirect('/cadastro_usuarios')

    try:
        novo_usuario = Usuario(
            nome=nome,
            nome_usuario=nome_usuario,
            email=email,
            tipo=tipo,
            telefone=telefone,
            documento=documento,
            nascimento=nascimento,
            rua=rua,
            numero=numero,
            bairro=bairro,
            cep=cep,
            cidade=cidade,
            estado=estado
        )
        novo_usuario.set_senha(senha)
        db.session.add(novo_usuario)
        db.session.commit()

        # 📝 Log de criação de funcionário
        registrar_log(
            usuario_id=current_user.id,
            acao="Criou funcionário",
            detalhes=f"👤 Nome: {nome} | 🆔 Usuário: {nome_usuario} | 📧 {email} | 🔐 Tipo: {tipo}"
        )

        flash('Funcionário cadastrado com sucesso!')
        return redirect('/listar_funcionarios')

    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao cadastrar funcionário: {e}")
        flash("Erro interno ao cadastrar funcionário.")
        return redirect('/cadastro_usuarios')
    


@app.route('/editar_cliente/<int:cliente_codigo>', methods=['GET', 'POST'])
@login_required
def editar_cliente(cliente_codigo):
    def gerar_detalhes_alteracao(cliente_antigo, cliente_novo):
        campos = [
            'nome_fantasia', 'razao_social', 'email', 'telefone',
            'cpf_cnpj', 'endereco_rua', 'endereco_numero', 'endereco_complemento',
            'bairro', 'cidade', 'estado', 'cep', 'status'
        ]
        detalhes = []
        for campo in campos:
            antigo = getattr(cliente_antigo, campo)
            novo = getattr(cliente_novo, campo)
            if antigo != novo:
                detalhes.append(f"{campo}: '{antigo}' → '{novo}'")
        return "; ".join(detalhes)

    cliente = Cliente.query.get_or_404(cliente_codigo)
    cliente_original = copy.deepcopy(cliente)

    form = ClienteForm(obj=cliente)  # <-- Instancia o formulário com dados do cliente

    if request.method == 'POST':
        form = ClienteForm(request.form, obj=cliente)  # Repopula o cliente com dados enviados
        if form.validate():
            form.populate_obj(cliente)  # Atualiza cliente com os dados do form

            try:
                alteracoes = gerar_detalhes_alteracao(cliente_original, cliente)
                db.session.commit()

                registrar_log(
                    usuario_id=current_user.id,
                    acao="Editou cliente",
                    detalhes=f"Cliente: {cliente.nome_fantasia}; {alteracoes}"
                )

                flash('✅ Cliente atualizado com sucesso!', 'success')
                return redirect(url_for('listar_clientes'))
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Erro ao editar cliente: {e}")
                flash("❌ Erro interno ao atualizar cliente.", "erro")
        else:
            flash("❌ Formulário inválido. Verifique os dados preenchidos.", "erro")

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)
    
    return render_template('editar_cliente.html', cliente=cliente, form=form)



@app.route('/atualizar_cliente/<int:id>', methods=['POST'])
@login_required
def atualizar_cliente(id):
    cliente = Cliente.query.get_or_404(id)

    cliente.nome_fantasia = request.form['nome_fantasia']
    cliente.razao_social = request.form.get('razao_social')  # opcional se estiver no formulário
    cliente.email = request.form['email']
    cliente.telefone = request.form['telefone']
    cliente.cpf_cnpj = request.form.get('cpf_cnpj')  # se estiver no form
    cliente.endereco_rua = request.form.get('endereco_rua')
    cliente.endereco_numero = request.form.get('endereco_numero')
    cliente.endereco_complemento = request.form.get('endereco_complemento')
    cliente.bairro = request.form.get('bairro')
    cliente.cidade = request.form.get('cidade')
    cliente.estado = request.form.get('estado')
    cliente.cep = request.form.get('cep')
    try:
        db.session.commit()

        # 📝 Log de atualização de cliente
        registrar_log(
            usuario_id=current_user.id,
            acao="Atualizou cliente",
            detalhes=f"ID: {cliente.id}, Código: {cliente.codigo}, Nome Fantasia: {cliente.nome_fantasia}, CPF/CNPJ: {cliente.cpf_cnpj}"
        )

        flash('✅ Cliente atualizado com sucesso!', 'success')
        return redirect('/listar_clientes')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao atualizar cliente: {e}")
        flash("❌ Erro interno ao atualizar cliente.", "danger")
        return redirect('/listar_clientes')


@app.route('/excluir_cliente/<int:cliente_id>', methods=['POST'])
@login_required
def excluir_cliente(cliente_id):
    if current_user.tipo not in ['admin', 'gerente']:
        flash('Você não tem permissão para excluir clientes.', 'danger')
        return redirect(url_for('listar_clientes'))

    cliente = Cliente.query.get_or_404(cliente_id)

    # 🔍 Verifica se há leads vinculados
    leads_vinculados = Lead.query.filter_by(cliente_id=cliente_id).count()
    if leads_vinculados > 0:
        flash("❌ Este cliente possui leads vinculados e não pode ser excluído.", "warning")
        return redirect(url_for('listar_clientes'))

    try:
        # 📝 Log antes da exclusão
        registrar_log(
            usuario_id=current_user.id,
            acao="Excluiu cliente",
            detalhes=f"Código: {cliente.codigo}; Nome Fantasia: {cliente.nome_fantasia}; CPF/CNPJ: {cliente.cpf_cnpj}"
        )

        db.session.delete(cliente)
        db.session.commit()

        flash("✅ Cliente excluído com sucesso!", "success")
        return redirect(url_for('listar_clientes'))
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Erro ao excluir cliente: {e}")
        flash("❌ Erro interno ao excluir cliente.", "danger")
        return redirect(url_for('listar_clientes'))



@app.route('/editar_usuario/<int:id>', methods=['GET', 'POST'])
@login_required
def editar_usuario(id):

    def gerar_detalhes_alteracao(usuario_antigo, usuario_novo):
        campos = ['nome', 'nome_usuario', 'email', 'tipo', 'telefone', 'documento',
                  'nascimento', 'rua', 'numero', 'bairro', 'cep', 'cidade', 'estado']
        detalhes = []
        for campo in campos:
            antigo = getattr(usuario_antigo, campo)
            novo = getattr(usuario_novo, campo)
            if antigo != novo:
                detalhes.append(f"{campo}: '{antigo}' → '{novo}'")
        return "; ".join(detalhes)

    usuario = Usuario.query.get_or_404(id)
    usuario_original = copy.deepcopy(usuario)

    if current_user.tipo not in ['admin', 'gerente']:
        flash("⚠️ Você não tem permissão para editar usuários.", "warning")
        return redirect(url_for('listar_funcionarios'))

    if request.method == 'POST':
        nome = request.form['nome']
        nome_usuario = request.form['nome_usuario']
        email = request.form['email']
        senha = request.form['senha']
        tipo = request.form['tipo']

        telefone = request.form.get('telefone', '').strip()
        documento = request.form.get('documento', '').strip()
        nascimento_str = request.form.get('nascimento')
        rua = request.form.get('rua', '').strip()
        numero = request.form.get('numero', '').strip()
        bairro = request.form.get('bairro', '').strip()
        cep = request.form.get('cep', '').strip()
        cidade = request.form.get('cidade', '').strip()
        estado = request.form.get('estado', '').strip()

        # 🗓️ Converte nascimento para tipo date
        nascimento = None
        if nascimento_str:
            try:
                nascimento = datetime.strptime(nascimento_str, '%Y-%m-%d').date()
            except ValueError:
                flash("⚠️ Data de nascimento inválida. Use o formato YYYY-MM-DD.", "warning")
                return redirect(url_for('editar_usuario', id=usuario.id))

        # 🔎 Verifica se o nome de login já existe
        login_existente = Usuario.query.filter_by(nome_usuario=nome_usuario).first()
        if login_existente and login_existente.id != usuario.id:
            flash("❌ Este login já está sendo usado por outro usuário.", "warning")
            return redirect(url_for('editar_usuario', id=usuario.id))

        # 🔧 Atualiza campos
        usuario.nome = nome
        usuario.nome_usuario = nome_usuario
        usuario.email = email
        usuario.tipo = tipo
        usuario.telefone = telefone
        usuario.documento = documento
        usuario.nascimento = nascimento
        usuario.rua = rua
        usuario.numero = numero
        usuario.bairro = bairro
        usuario.cep = cep
        usuario.cidade = cidade
        usuario.estado = estado

        if senha:
            usuario.set_senha(senha)

        try:
            alteracoes = gerar_detalhes_alteracao(usuario_original, usuario)
            db.session.commit()

            registrar_log(
                usuario_id=current_user.id,
                acao="Editou usuário",
                detalhes=f"Funcionário: {usuario.nome}; {alteracoes}"
            )

            flash("✅ Usuário atualizado com sucesso!", "success")
            return redirect(url_for('listar_funcionarios'))

        except Exception as e:
            db.session.rollback()
            app.logger.error(f"Erro ao editar usuário: {e}")
            flash("Erro interno ao atualizar usuário.", "erro")
            return render_template('editar_usuario.html', usuario=usuario)

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"  # CPF
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"  # CNPJ
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template('editar_usuario.html', usuario=usuario)


@app.route('/excluir_usuario/<int:id>')
@login_required
@permissoes_requeridas ('admin' , 'gerente')
def excluir_usuario(id):
    usuario = Usuario.query.get_or_404(id)
    db.session.delete(usuario)
    db.session.commit()
    flash('Funcionário excluído com sucesso!')
    return redirect('/listar_funcionarios')



    
    
#listagem clientes
@app.route('/listar_clientes')
@login_required
def listar_clientes():
    termo = request.args.get('busca')
    
    # 🔐 Filtro por empresa + busca
    if termo:
        clientes = Cliente.query.filter(
            and_(
                Cliente.empresa_id == current_user.empresa_id,
                or_(
                    Cliente.nome_fantasia.ilike(f"%{termo}%"),
                    Cliente.email.ilike(f"%{termo}%")
                )
            )
        ).all()
    else:
        clientes = Cliente.query.filter_by(empresa_id=current_user.empresa_id).all()

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa = Empresa.query.get(current_user.empresa_id)
    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    form = CSRFForm()

    return render_template('listar_clientes.html', clientes=clientes, form=form)


    


import csv
from flask import Response
@app.route('/editar_permissao/<int:id>', methods=['GET', 'POST'])
@login_required
@permissoes_requeridas('admin')  # só admins podem editar permissões
def editar_permissao(id):
    usuario = Usuario.query.get_or_404(id)

    if request.method == 'POST':
        novo_tipo = request.form.get('tipo')
        if novo_tipo in ['admin', 'gerente', 'funcionario']:
            tipo_antigo = usuario.tipo
            usuario.tipo = novo_tipo

            try:
                db.session.commit()

                # 📝 Log de alteração de permissão
                registrar_log(
                    usuario_id=current_user.id,
                    acao="Alterou permissão",
                    detalhes=f"Usuário ID: {usuario.id}, Nome: {usuario.nome}, Tipo antigo: {tipo_antigo}, Tipo novo: {novo_tipo}"
                )

                flash('Permissão atualizada com sucesso!')
            except Exception as e:
                db.session.rollback()
                app.logger.error(f"Erro ao atualizar permissão: {e}")
                flash("Erro interno ao atualizar permissão.")

        else:
            flash('Tipo inválido.')

        return redirect('/listar_funcionarios')
    
    

    return render_template('editar_permissao.html', usuario=usuario)

@app.route('/painel_logs')
@login_required
@permissoes_requeridas('admin')
def painel_logs():
    acoes_raw = db.session.query(LogAcao.acao).distinct().all()
    acoes_lista = sorted({acao[0] for acao in acoes_raw if acao[0]})

    pagina = request.args.get('pagina', 1, type=int)
    termo = request.args.get('termo', '')
    acao = request.args.get('acao', '')

    # 🔎 Consulta com join e filtro por empresa
    query = db.session.query(LogAcao)\
        .join(LogAcao.usuario)\
        .filter(Usuario.empresa_id == current_user.empresa_id)\
        .order_by(LogAcao.data_hora.desc())

    if termo:
        query = query.filter(LogAcao.detalhes.ilike(f"%{termo}%"))
    if acao:
        query = query.filter(LogAcao.acao == acao)

    logs = query.paginate(page=pagina, per_page=15)

    empresa = current_user.empresa

    def formatar_doc(doc):
        if doc and len(doc) == 11:
            return f"{doc[:3]}.{doc[3:6]}.{doc[6:9]}-{doc[9:]}"
        elif doc and len(doc) == 14:
            return f"{doc[:2]}.{doc[2:5]}.{doc[5:8]}/{doc[8:12]}-{doc[12:]}"
        return doc or "Não informado"

    empresa.documento = formatar_doc(empresa.cpf_cnpj)

    return render_template(
        'painel_logs.html',
        logs=logs,
        acoes=acoes_lista,
        termo=termo,
        acao=acao
    )


@app.route('/alternar_status/<int:id>')
@login_required
def alternar_status(id):
    usuario = Usuario.query.get_or_404(id)

    usuario.ativo = not usuario.ativo  # alterna entre True e False
    db.session.commit()

    if usuario.ativo:
        flash(f"O usuário {usuario.nome} foi reativado com sucesso.")
    else:
        flash(f"O usuário {usuario.nome} foi inativado com sucesso.")

    return redirect('/listar_funcionarios')

@app.route('/exportar_clientes')
@login_required
def exportar_clientes():
    clientes = Cliente.query.all()
    si = csv.StringIO()
    writer = csv.writer(si)
    writer.writerow(['ID', 'Nome', 'Email', 'Telefone', 'Empresa', 'Data'])
    for c in clientes:
        writer.writerow([c.id, c.nome, c.email, c.telefone, c.empresa, c.data_criacao.strftime('%d/%m/%Y')])
    output = Response(si.getvalue(), mimetype='text/csv')
    output.headers["Content-Disposition"] = "attachment; filename=clientes.csv"
    return output

from sqlalchemy import cast, Integer

@app.route('/cadastro_empresa', methods=['GET', 'POST'])
def cadastro_empresa():
    form = EmpresaForm()

    print("Método:", request.method)
    print("Formulário validado:", form.validate_on_submit())
    print("Erros do formulário:", form.errors)

    # Funções auxiliares
    def limpar_doc(doc):
        return re.sub(r'\D', '', doc or '')

    def validar_cpf(cpf):
        cpf = limpar_doc(cpf)
        if not cpf.isdigit() or len(cpf) != 11 or cpf in (c * 11 for c in "0123456789"):
            return False

        def calc_digito(cpf, pesos):
            soma = sum(int(n) * p for n, p in zip(cpf, pesos))
            resto = soma % 11
            return '0' if resto < 2 else str(11 - resto)

        d1 = calc_digito(cpf[:9], range(10, 1, -1))
        d2 = calc_digito(cpf[:10], range(11, 2, -1))
        return cpf[-2:] == d1 + d2

    def validar_cnpj(cnpj):
        cnpj = limpar_doc(cnpj)
        if not cnpj.isdigit() or len(cnpj) != 14 or cnpj in (c * 14 for c in "0123456789"):
            return False

        def calc_digito(cnpj, pesos):
            soma = sum(int(n) * p for n, p in zip(cnpj, pesos))
            resto = soma % 11
            return '0' if resto < 2 else str(11 - resto)

        d1 = calc_digito(cnpj[:12], [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        d2 = calc_digito(cnpj[:13], [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
        return cnpj[-2:] == d1 + d2

    def proximo_codigo_para_empresa(empresa_id):
        ultimo = Usuario.query.filter_by(empresa_id=empresa_id).order_by(Usuario.codigo.desc()).first()
        return 1 if not ultimo else ultimo.codigo + 1

    if form.validate_on_submit():
        # Dados da empresa
        nome_empresa  = (form.nome.data or '').strip()
        email_empresa = (form.email.data or '').strip()
        telefone      = (form.telefone.data or '').strip()
        endereco      = (form.endereco.data or '').strip()
        numero        = (form.numero.data or '').strip()
        cidade        = (form.cidade.data or '').strip()
        estado        = (form.estado.data or '').strip()
        representante = (form.representante.data or '').strip()
        doc_raw       = (form.cpf_cnpj.data or '').strip()
        doc           = limpar_doc(doc_raw)

        # Dados do usuário administrador
        admin_nome  = request.form.get('admin_nome', '').strip()
        admin_login = request.form.get('admin_login', '').strip()
        admin_email = request.form.get('admin_email', '').strip()
        admin_senha = request.form.get('admin_senha', '').strip()

        # Validação do documento
        if not doc:
            flash("CPF ou CNPJ é obrigatório!", "danger")
            return render_template('cadastro_empresa.html', form=form)

        if len(doc) == 11:
            if not validar_cpf(doc):
                flash("CPF inválido!", "danger")
                return render_template('cadastro_empresa.html', form=form)
        elif len(doc) == 14:
            if not validar_cnpj(doc):
                flash("CNPJ inválido!", "danger")
                return render_template('cadastro_empresa.html', form=form)
        else:
            flash("Documento inválido! Informe um CPF ou CNPJ válido.", "danger")
            return render_template('cadastro_empresa.html', form=form)

        # Verifica duplicidade de empresa
        if Empresa.query.filter_by(cpf_cnpj=doc).first():
            flash("Já existe uma empresa cadastrada com esse CPF/CNPJ.", "warning")
            return render_template('cadastro_empresa.html', form=form)

        # Verifica duplicidade de login/email do usuário
        if Usuario.query.filter_by(nome_usuario=admin_login).first():
            flash("Login já está em uso!", "warning")
            return render_template('cadastro_empresa.html', form=form)

        if Usuario.query.filter_by(email=admin_email).first():
            flash("Email já está em uso!", "warning")
            return render_template('cadastro_empresa.html', form=form)

        try:
            print("✅ Entrou no bloco try")

            # Geração de slug único
            base_slug = slugify(nome_empresa)
            slug_final = base_slug
            contador = 1
            while Empresa.query.filter_by(slug=slug_final).first():
                slug_final = f"{base_slug}-{contador}"
                contador += 1

            nova_empresa = Empresa(
                nome=nome_empresa,
                slug=slug_final,
                plano='gratuito',
                criada_em=datetime.utcnow(),
                cpf_cnpj=doc,
                telefone=telefone,
                email=email_empresa,
                endereco=f"{endereco}, Nº {numero}",
                cidade=cidade,
                estado=estado,
                representante=representante,
                codigo=str(uuid.uuid4())[:8]
            )

            db.session.add(nova_empresa)
            db.session.flush()  # Garante que nova_empresa.id esteja disponível

            # Geração do código sequencial do usuário
            codigo_gerado = proximo_codigo_para_empresa(nova_empresa.id)

            novo_usuario = Usuario(
                codigo=codigo_gerado,
                nome=admin_nome,
                nome_usuario=admin_login,
                email=admin_email,
                tipo='admin',
                empresa_id=nova_empresa.id,
                ativo=True
            )
            novo_usuario.set_senha(admin_senha)

            db.session.add(novo_usuario)
            db.session.commit()

            flash("Empresa e usuário administrador cadastrados com sucesso!", "success")
            return redirect(url_for('login'))

        except Exception as e:
            import traceback
            traceback.print_exc()
            db.session.rollback()
            flash("Erro ao cadastrar empresa e usuário.", "danger")
            return render_template('cadastro_empresa.html', form=form)

    return render_template('cadastro_empresa.html', form=form)















def gerar_codigo():
    ultimo_usuario = Usuario.query.order_by(
        Usuario.codigo.cast(db.Integer).desc()
    ).first()

    try:
        ultimo_codigo = int(ultimo_usuario.codigo)
        return str(ultimo_codigo + 1)
    except (AttributeError, ValueError):
        return '1'  # Primeiro usuário
app.register_blueprint(relatorios_bp)

# Inicialização do servidor/# Criação automática do banco de dados na primeira execução
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

        # 🏢 Verifica se a empresa existe
        empresa = Empresa.query.filter_by(slug='empresateste').first()
        if not empresa:
            empresa = Empresa(
                nome='Empresa Teste',
                slug='empresateste',
                plano='gratuito',
                cpf_cnpj='00000000000000'
            )
            db.session.add(empresa)
            db.session.commit()
            print(f'✅ Empresa "{empresa.nome}" criada com sucesso.')

        # 🔐 Verifica se o admin já existe
        admin_existente = Usuario.query.filter_by(email='admin@email.com').first()
        print("Admin existente?", bool(admin_existente))
        if not admin_existente:
            codigo = gerar_codigo()  # 👈 garantindo que o admin tenha código
            admin = Usuario(
                codigo='ADM',
                nome='admin',
                nome_usuario='admin',
                email='admin@email.com',
                tipo='admin',
                empresa_id=None  # 👈 admin global sem vínculo
            )
            admin.set_senha('123')
            db.session.add(admin)
            db.session.commit()
            print('✅ Usuário admin global criado com sucesso.')
        else:
            print('ℹ️ Usuário admin já existe.')
            

    # 🔥 Aqui inicia o servidor Flask
    app.run(debug=True)
    



    
