"""Versão opcional independente: leitura, validação e groupby com pandas."""
import math
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

import pandas as pd

LIMITE_SUSPEITO = 10000.00
COLUNAS = ['id', 'data', 'cliente_id', 'tipo', 'valor', 'descricao', 'categoria']


def converter_valor(texto):
    try:
        numero = float(texto)
        if not math.isfinite(numero) or numero <= 0:
            return None
        return Decimal(texto)
    except (ValueError, OverflowError, InvalidOperation):
        return None


def moeda(numero):
    return float(numero.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def registro(linha):
    return {'id': int(linha['id']), 'data': linha['data'].strftime('%Y-%m-%d'),
            'cliente_id': linha['cliente_id'], 'tipo': linha['tipo'],
            'valor': moeda(linha['valor']), 'descricao': linha['descricao'],
            'categoria': linha['categoria']}


def agrupar_mensal(df):
    """Calcula somas e média em Decimal via agregações do groupby."""
    if df.empty:
        return {}
    df = df.copy()
    df['mes'] = df['data'].dt.strftime('%Y-%m')
    df['credito'] = df.apply(lambda r: r['valor'] if r['tipo'] == 'credito' else Decimal('0'), axis=1)
    df['debito'] = df.apply(lambda r: r['valor'] if r['tipo'] == 'debito' else Decimal('0'), axis=1)
    grupos = df.groupby('mes', sort=True)
    metricas = grupos.agg(quantidade=('id', 'size'), total_credito=('credito', 'sum'),
                          total_debito=('debito', 'sum'), soma=('valor', 'sum'))
    resumo = {}
    for mes, dados in metricas.iterrows():
        grupo = grupos.get_group(mes)
        maior = grupo.loc[grupo['valor'].idxmax()]
        menor = grupo.loc[grupo['valor'].idxmin()]
        resumo[mes] = {'quantidade': int(dados['quantidade']),
                       'total_credito': moeda(dados['total_credito']),
                       'total_debito': moeda(dados['total_debito']),
                       'saldo': moeda(dados['total_credito'] - dados['total_debito']),
                       'media': moeda(dados['soma'] / int(dados['quantidade'])),
                       'maior_transacao': registro(maior), 'menor_transacao': registro(menor)}
    return resumo


def analisar_pandas(caminho='transacoes.csv'):
    df = pd.read_csv(caminho, dtype=str, keep_default_na=False, encoding='utf-8-sig')
    if list(df.columns) != COLUNAS:
        raise ValueError('Cabeçalho inválido.')
    total = len(df)
    for coluna in COLUNAS:
        df[coluna] = df[coluna].str.strip()
    ids_ok = df['id'].str.fullmatch(r'[+-]?[0-9]+')
    datas_ok = df['data'].str.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
    datas = pd.to_datetime(df['data'].where(datas_ok), format='%Y-%m-%d', errors='coerce')
    valores = df['valor'].map(converter_valor)
    mascara = (ids_ok & df['cliente_id'].ne('') & df['tipo'].isin(['credito', 'debito'])
               & datas.notna() & valores.notna())
    df = df.loc[mascara].copy()
    df['id'] = df['id'].map(int)
    df['data'] = datas.loc[mascara]
    df['valor'] = valores.loc[mascara]
    duplicadas = int(df.duplicated(subset='id', keep='first').sum())
    df = df.drop_duplicates(subset='id', keep='first')
    suspeitas = df.loc[df['valor'] > Decimal(str(LIMITE_SUSPEITO))]
    return {'total_linhas_lidas': total, 'total_transacoes_validas': len(df),
            'total_transacoes_invalidas': total - len(df),
            'duplicadas_descartadas': duplicadas, 'resumo_mensal': agrupar_mensal(df),
            'transacoes_suspeitas': [registro(linha) for _, linha in suspeitas.iterrows()]}


if __name__ == '__main__':
    import json
    try:
        print(json.dumps(analisar_pandas(), ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, pd.errors.ParserError) as erro:
        print(f'Não foi possível analisar o CSV com pandas: {erro}')
