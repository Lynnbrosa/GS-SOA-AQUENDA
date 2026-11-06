class RecursoNaoEncontrado(Exception):
    """Vira 404."""


class ParametroInvalido(Exception):
    """Vira 400: o pedido veio com um valor que não faz sentido."""
