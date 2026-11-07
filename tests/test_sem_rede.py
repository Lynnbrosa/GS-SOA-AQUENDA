"""A trava de rede do conftest: internet bloqueada, localhost liberado (o asyncio do Windows precisa dele)."""

import socket

import pytest


def test_internet_fica_bloqueada():
    with pytest.raises(RuntimeError, match="rede"):
        socket.create_connection(("api.adzuna.com", 443), timeout=1)
    with pytest.raises(RuntimeError, match="rede"):
        socket.socket().connect(("93.184.215.14", 80))


def test_localhost_continua_liberado():
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    cliente = socket.create_connection(servidor.getsockname(), timeout=2)
    conexao, _ = servidor.accept()
    cliente.close(); conexao.close(); servidor.close()
