from flask_wtf import FlaskForm
from wtforms import SelectField, DateField, TextAreaField
from wtforms.validators import DataRequired

class AtividadeForm(FlaskForm):
    tipo = SelectField(
        'Tipo de Atividade',
        choices=[
            ('Ligação', 'Ligação'),
            ('E-mail', 'E-mail'),
            ('Visita', 'Visita'),
            ('Outro', 'Outro')
        ],
        validators=[DataRequired()]
    )
    data = DateField('Data', validators=[DataRequired()])
    descricao = TextAreaField('Descrição', validators=[DataRequired()])