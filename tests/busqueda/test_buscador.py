from bitcoinai.busqueda import Buscador, Entrada, normalizar, palabras

BUSCADOR = Buscador()


def ids(consulta: str, limite: int = 8) -> tuple[str, ...]:
    return tuple(e.id for e in BUSCADOR.buscar(consulta, limite))


def test_normalizar_quita_tildes_y_mayusculas() -> None:
    assert normalizar("Órdenes ÁRBOL Comisión") == "ordenes arbol comision"
    assert tuple(palabras("Stop-loss, 2FA!")) == ("stop", "loss", "2fa")


def test_busca_por_prefijo_sin_importar_tildes() -> None:
    assert ids("ord")[0] == "ordenes"
    assert ids("ÓRDE")[0] == "ordenes"
    assert "avl" in ids("arbol")


def test_todas_las_palabras_deben_coincidir() -> None:
    assert set(ids("media exp")) == {"ema", "macd"}  # el MACD es la resta de dos medias exponenciales
    assert "sma" in ids("media")
    assert ids("vender btc") == ("vender",)


def test_primero_las_que_coinciden_en_el_titulo() -> None:
    resultado = ids("pila")
    assert resultado[0] == "pila"
    assert "deshacer" in resultado  # "pila" está en su descripción


def test_sinonimos_en_las_claves() -> None:
    assert ids("2fa") == ("dos-pasos",)
    assert ids("heap") == ("monticulo",)


def test_consultas_vacias_sin_resultados_y_limite() -> None:
    assert ids("") == ()
    assert ids("  ,, ") == ()
    assert ids("zzzz") == ()
    assert len(ids("estructura", limite=3)) == 3
    assert ids("bot", limite=0) == ()


def test_los_prefijos_comparten_nodos() -> None:
    assert BUSCADOR.palabras_indexadas() > 50
    total_letras = sum(len(p) for p, _ in BUSCADOR._trie.con_prefijo("", limite=10_000))
    assert BUSCADOR.nodos_del_trie() < total_letras


def test_catalogo_propio() -> None:
    buscador = Buscador((Entrada("a", "Alfa", "x", "/a", "pagina"), Entrada("b", "Alfabeto", "y", "/b", "pagina")))
    assert tuple(e.id for e in buscador.buscar("alfa")) == ("a", "b")
