from flask import Flask, render_template, request, redirect, url_for
from pyspark.sql import SparkSession
from datetime import datetime  
from pyspark.sql import functions as F
import pandas as pd
from flask_cors import CORS

app = Flask(__name__)

# Inicializa a sessão do Spark
spark = SparkSession.builder.appName("PastoralSocial").getOrCreate()

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/estoque')
def relatorio():
    # Carregar os dados
    doacoes_df = spark.read.csv("data/doacoes.csv", header=True, inferSchema=True)
    estoque_df = spark.read.csv("data/estoque.csv", header=True, inferSchema=True)
    distribuicoes_df = spark.read.csv("data/distribuicoes.csv", header=True, inferSchema=True)
    
    # Carregar as quantidades necessárias
    quantidades_necessarias_df = spark.read.csv("data/quantidades_necessarias.csv", header=True, inferSchema=True)

    # Contar o número de famílias cadastradas (supondo que você tenha um arquivo de famílias)
    familias_df = spark.read.csv("data/familias.csv", header=True, inferSchema=True)
    numero_familias = familias_df.count()  # Contar o número total de famílias

    # Processamento de dados
    total_doacoes = doacoes_df.groupBy("Tipo_Alimento").agg(F.sum("Quantidade").alias("Total_Doacoes"))
    total_distribuicoes = distribuicoes_df.groupBy("Tipo_Alimento").agg(F.sum("Quantidade").alias("Total_Distribuicoes"))

    estoque_atualizado = estoque_df.join(total_doacoes, "Tipo_Alimento", "left") \
        .join(total_distribuicoes, "Tipo_Alimento", "left").fillna(0)

    # Calcular a quantidade necessária
    quantidade_necessaria = estoque_atualizado.join(quantidades_necessarias_df, "Tipo_Alimento", "left")
    quantidade_necessaria = quantidade_necessaria.withColumn(
        "Quantidade_Necessaria",
        quantidade_necessaria["Quantidade_Por_Familia"] * numero_familias
    )

    # Coletar os dados em uma lista para renderizar no HTML
    relatorio = quantidade_necessaria.select("Tipo_Alimento","Medida", "Quantidade", "Total_Doacoes", "Total_Distribuicoes", "Quantidade_Necessaria").collect()

    return render_template('relatorio.html', relatorio=relatorio)

@app.route('/registro_doacao', methods=['GET', 'POST'])
def registro_doacao():
    # Carregar as famílias cadastradas
    familias_df = pd.read_csv("data/familias.csv")
    familias = familias_df.values.tolist()

    # Carregar o estoque
    estoque_df = pd.read_csv("data/estoque.csv")
    tipos_alimentos = estoque_df[['Tipo_Alimento', 'Quantidade','Medida']].to_dict(orient='records')

    if request.method == 'POST':
        familia = request.form['familia']
        tipo_alimento = request.form['tipo_alimento']
        quantidade = int(request.form['quantidade'])
        data = datetime.now().strftime("%d-%m-%Y")
        # data = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Atualizar o estoque
        if tipo_alimento in estoque_df['Tipo_Alimento'].values:
            estoque_atual = estoque_df.loc[estoque_df['Tipo_Alimento'] == tipo_alimento, 'Quantidade'].values[0]

            if quantidade <= estoque_atual:
                estoque_df.loc[estoque_df['Tipo_Alimento'] == tipo_alimento, 'Quantidade'] -= quantidade

                # Manter o item no estoque com quantidade 0 ao invés de deletar
                estoque_df.to_csv("data/estoque.csv", index=False)

                # Registrar a doação
                nova_doacao = pd.DataFrame({
                    "Data": [data],
                    "Familia": [familia],
                    "Tipo_Alimento": [tipo_alimento],
                    "Quantidade": [quantidade]
                })

                nova_doacao.to_csv("data/distribuicoes.csv", mode='a', header=False, index=False)
                
                return redirect(url_for('historico_doacoes'))
    return render_template('registro_doacao.html', familias=familias, tipos_alimentos=tipos_alimentos)


@app.route('/historico_doacoes', methods=['GET', 'POST'])
def historico_doacoes():
    # Carregar as doações
    doacoes_df = pd.read_csv("data/distribuicoes.csv")

    # Filtrar por família se o formulário for enviado
    familias_df = pd.read_csv("data/familias.csv")
    familias = familias_df.values.tolist()

    if request.method == 'POST':
        familia_selecionada = request.form['familia']
        doacoes_df = doacoes_df[doacoes_df['Familia'] == familia_selecionada]

    return render_template('historico_doacoes.html', doacoes=doacoes_df.values.tolist(), familias=familias)

@app.route('/cadastro_familia', methods=['GET', 'POST'])
def cadastro_familia():
    if request.method == 'POST':
        # Capturar os dados do formulário
        nome = request.form['nome']
        responsavel = request.form['responsavel']
        telefone = request.form['telefone']
        endereco = request.form['endereco']

        # Criar um DataFrame com a nova família
        nova_familia = pd.DataFrame({
            "Nome": [nome],
            "Responsavel": [responsavel],
            "Telefone": [telefone],
            "Endereco": [endereco]
        })

        # Salvar a nova família no arquivo CSV
        nova_familia.to_csv("data/familias.csv", mode='a', header=False, index=False)

        return redirect(url_for('home'))

    return render_template('cadastro_familia.html')

@app.route('/lista_familia')
def lista_familias():
    # Carregar os dados
    familias_df = pd.read_csv("data/familias.csv")
    familias = familias_df.values.tolist()

    return render_template('lista_familias.html', familias=familias)

@app.route('/cadastro_doacao', methods=['GET', 'POST'])
def cadastro_doacao():
    # Carregar os tipos de alimentos disponíveis no estoque
    estoque_df = pd.read_csv("data/estoque.csv")
    tipos_alimentos = estoque_df['Tipo_Alimento'].values.tolist()

    if request.method == 'POST':
        # Capturar os dados do formulário
        data = request.form['data']
        tipo_alimento = request.form['tipo_alimento']
        quantidade = int(request.form['quantidade'])
        origem = request.form['origem']

        # Criar um DataFrame com a nova doação
        nova_doacao = pd.DataFrame({
            "Data": [data],
            "Tipo_Alimento": [tipo_alimento],
            "Quantidade": [quantidade],
            "Origem": [origem]
        })

        # Salvar a nova doação no arquivo CSV
        nova_doacao.to_csv("data/doacoes.csv", mode='a', header=False, index=False)

        # Atualizar o estoque
        estoque_df = pd.read_csv("data/estoque.csv")

        # Verificar se o tipo de alimento já existe no estoque
        if tipo_alimento in estoque_df['Tipo_Alimento'].values:
            # Atualizar a quantidade existente
            estoque_df.loc[estoque_df['Tipo_Alimento'] == tipo_alimento, 'Quantidade'] += quantidade
        else:
            # Adicionar novo item ao estoque
            novo_item = pd.DataFrame({
                "Tipo_Alimento": [tipo_alimento],
                "Quantidade": [quantidade]
            })
            estoque_df = pd.concat([estoque_df, novo_item], ignore_index=True)

        # Salvar o estoque atualizado
        estoque_df.to_csv("data/estoque.csv", index=False)

        return redirect(url_for('relatorio'))

    # Renderizar a página e passar os tipos de alimentos para o template
    return render_template('cadastro_doacao.html', tipos_alimentos=tipos_alimentos)

@app.route('/historico_entrada')
def historico_entrada():
    # Ler o CSV de doações
    doacoes_df = pd.read_csv('data/doacoes.csv')

    # Ordenar por data para mostrar as entradas mais recentes primeiro
    doacoes_df['Data'] = pd.to_datetime(doacoes_df['Data'])  # Converter a coluna 'Data' para formato datetime
    doacoes_df = doacoes_df.sort_values(by='Data', ascending=False)

    # Converter o DataFrame em uma lista para passar para o template
    historico = doacoes_df.to_dict(orient='records')

    return render_template('historico_entrada.html', historico=historico)

if __name__ == '__main__':
    CORS(app) 
    app.run(host='0.0.0.0', port=5000, debug=True)
    