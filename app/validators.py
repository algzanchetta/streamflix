"""Validadores e utilitários de dados (CPF, cartão de crédito e formatação)."""


def so_digitos(valor):
    """Remove tudo que não for dígito (pontos, traços, espaços...)."""
    return ''.join(c for c in str(valor or '') if c.isdigit())


def validar_cpf(cpf):
    """Valida um CPF brasileiro (11 dígitos + dígitos verificadores)."""
    c = [int(d) for d in so_digitos(cpf)]
    if len(c) != 11:
        return False
    if len(set(c)) == 1:
        return False

    for i in range(9, 11):
        soma = sum(v * (i + 1 - pos) for pos, v in enumerate(c[:i]))
        resto = (soma * 10) % 11
        digito = 0 if resto == 10 else resto
        if digito != c[i]:
            return False
    return True


def validar_luhn(numero):
    """Valida número de cartão pelo algoritmo de Luhn."""
    n = [int(d) for d in so_digitos(numero)]
    if len(n) < 12 or len(n) > 19:
        return False

    soma = 0
    dobrar = False
    for d in reversed(n):
        if dobrar:
            d *= 2
            if d > 9:
                d -= 9
        soma += d
        dobrar = not dobrar
    return soma % 10 == 0


def detectar_bandeira(numero):
    """Identifica a bandeira a partir do prefixo do número do cartão."""
    n = so_digitos(numero)
    if not n:
        return 'Outro'

    if n.startswith('4'):
        return 'Visa'
    if n[:2] in ('34', '37'):
        return 'Amex'
    if n[:2] in ('51', '52', '53', '54', '55') or (len(n) >= 4 and 2221 <= int(n[:4]) <= 2720):
        return 'Mastercard'
    if n[:6] in ('636368', '438935', '504175', '451416', '636297',
                 '506699', '509048', '509067', '509049', '509069'):
        return 'Elo'
    return 'Outro'


def formatar_cpf(cpf):
    """Formata um CPF como XXX.XXX.XXX-XX."""
    d = so_digitos(cpf)
    if len(d) == 11:
        return f'{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}'
    return cpf or ''


def formatar_cartao(numero):
    """Mascara um cartão exibindo apenas os 4 últimos dígitos."""
    d = so_digitos(numero)
    if len(d) >= 4:
        return f'•••• •••• •••• {d[-4:]}'
    return numero or ''
