from flask import Blueprint, render_template, request, jsonify
from app import db
from models import Produto, Lead
from flask_login import login_required, current_user
from decimal import Decimal


produto_bp = Blueprint('produto', __name__)

# ------------------------------
# ROTAS DE API (JSON)
# ------------------------------

@produto_bp.route('/api/produto', methods=['POST'])
@login_required
def criar_produto():
    dados = request.get_json()

    if not dados:
        return jsonify({'erro': 'Dados inválidos ou ausentes'}), 400

    nome = dados.get('nome')
    valor_bruto = dados.get('valor')

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

    if not current_user.empresa:
        return jsonify({'erro': 'Empresa não vinculada ao usuário'}), 403

    produto = Produto(
        nome=nome,
        valor=valor,
        empresa_id=current_user.empresa.id
    )

    db.session.add(produto)
    db.session.commit()

    return jsonify({'mensagem': 'Produto cadastrado com sucesso!', 'id': produto.id}), 201



@produto_bp.route('/api/produto', methods=['GET'])
def listar_produtos():
    produtos = Produto.query.all()
    resultado = [
        {
            'id': p.id,
            'nome': p.nome,
            'valor': float(p.valor),
        }
        for p in produtos
    ]
    return jsonify(resultado)


@produto_bp.route('/api/produto/<int:id>', methods=['PUT'])
def atualizar_produto(id):
    produto = Produto.query.get_or_404(id)
    dados = request.get_json()
    produto.nome = dados.get('nome', produto.nome)
    produto.valor = dados.get('valor', produto.valor)
    db.session.commit()

    return jsonify({'mensagem': 'Produto atualizado com sucesso!'})


@produto_bp.route('/api/produto/<int:id>', methods=['DELETE'])
def excluir_produto(id):
    produto = Produto.query.get_or_404(id)
    db.session.delete(produto)
    db.session.commit()

    return jsonify({'mensagem': 'Produto excluído com sucesso!'})


# ------------------------------
# ROTAS DE INTERFACE HTML
# ------------------------------

@produto_bp.route('/novo')
def novo_produto_html():
    return render_template('produto.html')


@produto_bp.route('/listar')
def listar_produto_html():
    produtos = Produto.query.all()
    return render_template('listar_produto.html', produtos=produtos)


@produto_bp.route('/editar/<int:id>')
def editar_produto_html(id):
    produto = Produto.query.get_or_404(id)
    return render_template('editar_produto.html', produto=produto)