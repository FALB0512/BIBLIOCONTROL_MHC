from datetime import date

from flask import request


def val(name, maxlen=255, required=False):
    text = (request.form.get(name) or '').strip()
    if required and not text:
        raise ValueError(f'El campo «{name}» es obligatorio.')
    if len(text) > maxlen:
        raise ValueError(f'El campo «{name}» supera {maxlen} caracteres.')
    return text


def dateval(name):
    text = val(name, 10, True)
    try:
        date.fromisoformat(text)
    except ValueError:
        raise ValueError(f'Fecha inválida: {name}')
    return text


def as_int(name):
    try:
        return int(request.form.get(name, ''))
    except (ValueError, TypeError):
        raise ValueError(f'Identificador inválido: {name}')
