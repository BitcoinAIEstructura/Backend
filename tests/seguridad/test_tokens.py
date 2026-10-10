from bitcoinai.seguridad.tokens import generar_token, hash_token, mismo_hash


def test_tokens_largos_y_distintos() -> None:
    tokens = {generar_token() for _ in range(100)}
    assert len(tokens) == 100
    assert all(len(t) == 43 for t in tokens)


def test_hash_determinista_sin_el_token_adentro() -> None:
    token = generar_token()
    assert hash_token(token) == hash_token(token)
    assert len(hash_token(token)) == 32
    assert token.encode() not in hash_token(token)
    assert mismo_hash(hash_token(token), hash_token(token))
    assert not mismo_hash(hash_token(token), hash_token(generar_token()))
