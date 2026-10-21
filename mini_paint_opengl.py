"""
Trabalho 1 - Sistema Gráfico de Desenho 2D Iterativo (Mini Paint)
===================================================================
Bibliotecas usadas APENAS para:
  - GLFW      -> criar a janela e capturar eventos de mouse/teclado
  - OpenGL    -> glDrawPixels, que envia o framebuffer (matriz de pixels) para a tela

Tudo o mais é implementado neste arquivo, sem nenhuma função gráfica pronta:
  put_pixel, get_pixel, Bresenham (linha), ponto médio (círculo), retângulo,
  flood fill com pilha, exportação BMP/PPM, e até os botões e textos da interface
  (fonte bitmap 5x7 embutida, desenhada pixel a pixel).

Instalação:   pip install glfw PyOpenGL
Execução:     python mini_paint_opengl.py
Atalhos:      N = Novo | S = Salvar (desenho.bmp e desenho.ppm)
"""
import glfw
from OpenGL.GL import (
    glViewport, glMatrixMode, glLoadIdentity, glOrtho, glRasterPos2i,
    glPixelZoom, glPixelStorei, glDrawPixels, glClearColor, glClear,
    GL_PROJECTION, GL_MODELVIEW, GL_UNPACK_ALIGNMENT, GL_RGB,
    GL_UNSIGNED_BYTE, GL_COLOR_BUFFER_BIT,
)

# ============================================================================
# 1) FRAMEBUFFER (estrutura de dados central)
# ============================================================================
# O framebuffer da janela é uma matriz de pixels RGB (1 byte por canal) guardada
# linearmente em um bytearray, linha 0 = topo da tela.
#   - Linhas 0..599   : CANVAS de desenho (800x600)
#   - Linhas 600..719 : barra de ferramentas
LARGURA = 800
ALTURA_CANVAS = 600
ALTURA_BARRA = 120
ALTURA_JANELA = ALTURA_CANVAS + ALTURA_BARRA

COR_FUNDO = (255, 255, 255)

frame = bytearray(LARGURA * ALTURA_JANELA * 3)


def put_pixel(x, y, cor):
    """Escreve um pixel no CANVAS. Ignora coordenadas fora dele (clipping)."""
    if 0 <= x < LARGURA and 0 <= y < ALTURA_CANVAS:
        i = (y * LARGURA + x) * 3
        frame[i] = cor[0]
        frame[i + 1] = cor[1]
        frame[i + 2] = cor[2]


def get_pixel(x, y):
    """Lê um pixel do CANVAS. Retorna None fora dele."""
    if 0 <= x < LARGURA and 0 <= y < ALTURA_CANVAS:
        i = (y * LARGURA + x) * 3
        return (frame[i], frame[i + 1], frame[i + 2])
    return None


def put_pixel_ui(x, y, cor):
    """Escreve um pixel na região da barra de ferramentas (somente interface)."""
    if 0 <= x < LARGURA and ALTURA_CANVAS <= y < ALTURA_JANELA:
        i = (y * LARGURA + x) * 3
        frame[i] = cor[0]
        frame[i + 1] = cor[1]
        frame[i + 2] = cor[2]


def limpar_canvas():
    """Botão 'Novo': preenche o canvas com a cor de fundo."""
    n = LARGURA * ALTURA_CANVAS
    frame[0:n * 3] = bytes(COR_FUNDO) * n


# ============================================================================
# 2) ALGORITMOS DE RASTERIZAÇÃO
# ============================================================================
def pincel(x, y, cor, esp):
    """Carimba um quadrado esp x esp centrado em (x, y). esp=1 -> 1 pixel."""
    r = esp // 2
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            put_pixel(x + dx, y + dy, cor)


def linha_bresenham(x0, y0, x1, y1, cor, esp=1):
    """Algoritmo de Bresenham (todos os octantes, apenas aritmética inteira)."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    erro = dx - dy
    while True:
        pincel(x0, y0, cor, esp)
        if x0 == x1 and y0 == y1:
            break
        e2 = 2 * erro
        if e2 > -dy:
            erro -= dy
            x0 += sx
        if e2 < dx:
            erro += dx
            y0 += sy


def retangulo_vazado(x0, y0, x1, y1, cor, esp):
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    linha_bresenham(xa, ya, xb, ya, cor, esp)
    linha_bresenham(xb, ya, xb, yb, cor, esp)
    linha_bresenham(xb, yb, xa, yb, cor, esp)
    linha_bresenham(xa, yb, xa, ya, cor, esp)


def retangulo_preenchido(x0, y0, x1, y1, cor):
    xa, xb = min(x0, x1), max(x0, x1)
    ya, yb = min(y0, y1), max(y0, y1)
    for y in range(max(ya, 0), min(yb, ALTURA_CANVAS - 1) + 1):
        for x in range(max(xa, 0), min(xb, LARGURA - 1) + 1):
            put_pixel(x, y, cor)


def circulo_ponto_medio(cx, cy, r, cor, esp=1):
    """Círculo vazado - algoritmo do ponto médio (8 simetrias)."""
    x, y = 0, r
    d = 1 - r
    while x <= y:
        for px, py in ((x, y), (-x, y), (x, -y), (-x, -y),
                       (y, x), (-y, x), (y, -x), (-y, -x)):
            pincel(cx + px, cy + py, cor, esp)
        x += 1
        if d < 0:
            d += 2 * x + 1
        else:
            y -= 1
            d += 2 * (x - y) + 1


def circulo_preenchido(cx, cy, r, cor):
    """Círculo preenchido - ponto médio + segmentos horizontais (spans)."""
    x, y = 0, r
    d = 1 - r
    while x <= y:
        for yy, meia in ((y, x), (-y, x), (x, y), (-x, y)):
            for px in range(cx - meia, cx + meia + 1):
                put_pixel(px, cy + yy, cor)
        x += 1
        if d < 0:
            d += 2 * x + 1
        else:
            y -= 1
            d += 2 * (x - y) + 1


def flood_fill(x, y, nova):
    """
    Flood fill 4-conectado, iterativo, com pilha explícita e varredura de linhas
    (scanline). Não é recursivo, então não estoura o limite de recursão do Python.
    """
    alvo = get_pixel(x, y)
    if alvo is None or alvo == nova:
        return
    pilha = [(x, y)]
    while pilha:
        sx, sy = pilha.pop()
        if get_pixel(sx, sy) != alvo:
            continue
        xe = sx                                   # expande para a esquerda
        while get_pixel(xe - 1, sy) == alvo:
            xe -= 1
        xd = sx                                   # expande para a direita
        while get_pixel(xd + 1, sy) == alvo:
            xd += 1
        for px in range(xe, xd + 1):              # pinta o trecho
            put_pixel(px, sy, nova)
        for ny in (sy - 1, sy + 1):               # sementes das linhas vizinhas
            dentro = False
            for px in range(xe, xd + 1):
                if get_pixel(px, ny) == alvo:
                    if not dentro:
                        pilha.append((px, ny))
                        dentro = True
                else:
                    dentro = False


# ============================================================================
# 3) EXPORTAÇÃO (BMP 24 bits e PPM P6, escritos manualmente)
# ============================================================================
def salvar_ppm(caminho):
    with open(caminho, "wb") as f:
        f.write(b"P6\n%d %d\n255\n" % (LARGURA, ALTURA_CANVAS))
        f.write(bytes(frame[0:LARGURA * ALTURA_CANVAS * 3]))


def salvar_bmp(caminho):
    linha_bytes = LARGURA * 3
    pad = (4 - linha_bytes % 4) % 4
    tam_img = (linha_bytes + pad) * ALTURA_CANVAS
    cabecalho = (b"BM" + (54 + tam_img).to_bytes(4, "little") + bytes(4)
                 + (54).to_bytes(4, "little"))
    info = ((40).to_bytes(4, "little") + LARGURA.to_bytes(4, "little")
            + ALTURA_CANVAS.to_bytes(4, "little") + (1).to_bytes(2, "little")
            + (24).to_bytes(2, "little") + bytes(4) + tam_img.to_bytes(4, "little")
            + bytes(16))
    with open(caminho, "wb") as f:
        f.write(cabecalho + info)
        for y in range(ALTURA_CANVAS - 1, -1, -1):        # BMP: de baixo para cima
            linha = frame[y * linha_bytes:(y + 1) * linha_bytes]
            bgr = bytearray(linha_bytes)                  # RGB -> BGR
            bgr[0::3] = linha[2::3]
            bgr[1::3] = linha[1::3]
            bgr[2::3] = linha[0::3]
            f.write(bgr)
            f.write(bytes(pad))


# ============================================================================
# 4) INTERFACE (desenhada no próprio framebuffer, sem widgets)
# ============================================================================
# Fonte bitmap 5x7 (cada glifo = 7 linhas de 5 bits)
FONTE = {
    "A": (0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "B": (0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E),
    "C": (0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E),
    "D": (0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E),
    "E": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F),
    "F": (0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10),
    "G": (0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F),
    "H": (0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11),
    "I": (0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E),
    "J": (0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C),
    "K": (0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11),
    "L": (0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F),
    "M": (0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11),
    "N": (0x11, 0x11, 0x19, 0x15, 0x13, 0x11, 0x11),
    "O": (0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "P": (0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10),
    "Q": (0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D),
    "R": (0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11),
    "S": (0x0F, 0x10, 0x10, 0x0E, 0x01, 0x01, 0x1E),
    "T": (0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04),
    "U": (0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E),
    "V": (0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04),
    "W": (0x11, 0x11, 0x11, 0x15, 0x15, 0x1B, 0x11),
    "X": (0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11),
    "Y": (0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04),
    "Z": (0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F),
    ".": (0, 0, 0, 0, 0, 0x0C, 0x0C),
    "-": (0, 0, 0, 0x1F, 0, 0, 0),
    " ": (0, 0, 0, 0, 0, 0, 0),
}


def ui_retangulo(x, y, w, h, cor):
    for yy in range(y, y + h):
        for xx in range(x, x + w):
            put_pixel_ui(xx, yy, cor)


def ui_borda(x, y, w, h, cor, e=1):
    ui_retangulo(x, y, w, e, cor)
    ui_retangulo(x, y + h - e, w, e, cor)
    ui_retangulo(x, y, e, h, cor)
    ui_retangulo(x + w - e, y, e, h, cor)


def ui_texto(x, y, texto, escala, cor):
    for ch in texto.upper():
        glifo = FONTE.get(ch, FONTE[" "])
        for linha, bits in enumerate(glifo):
            for col in range(5):
                if bits & (0x10 >> col):
                    ui_retangulo(x + col * escala, y + linha * escala, escala, escala, cor)
        x += 6 * escala


PALETA = [
    (0, 0, 0), (255, 255, 255), (255, 0, 0), (0, 255, 0),
    (0, 0, 255), (255, 255, 0), (0, 255, 255), (255, 0, 255),
]
# (rótulo, ferramenta)
FERRAMENTAS = [
    ("LAPIS", "lapis"), ("BORRACHA", "borracha"), ("LINHA", "linha"), ("BALDE", "balde"),
    ("RET VAZ", "ret_vaz"), ("RET CHEIO", "ret_cheio"),
    ("CIR VAZ", "cir_vaz"), ("CIR CHEIO", "cir_cheio"),
]
ESPESSURAS = [("FINO", 1), ("MEDIO", 3), ("GROSSO", 7)]

# Botões: (tipo, valor, (x, y, w, h), rótulo)
BOTOES = []
for i, (rotulo, ferr) in enumerate(FERRAMENTAS):
    BOTOES.append(("ferr", ferr,
                   (5 + (i % 4) * 122, ALTURA_CANVAS + 5 + (i // 4) * 32, 118, 28), rotulo))
for i, (rotulo, valor) in enumerate(ESPESSURAS):
    BOTOES.append(("esp", valor, (500 + i * 98, ALTURA_CANVAS + 5, 94, 28), rotulo))
BOTOES.append(("acao", "novo", (500, ALTURA_CANVAS + 37, 94, 28), "NOVO"))
BOTOES.append(("acao", "salvar", (598, ALTURA_CANVAS + 37, 94, 28), "SALVAR"))
AMOSTRAS = [(PALETA[i], (5 + i * 46, ALTURA_CANVAS + 74, 42, 40)) for i in range(8)]


# ============================================================================
# 5) ESTADO DA APLICAÇÃO
# ============================================================================
estado = {
    "ferramenta": "lapis",
    "cor": PALETA[0],
    "esp": 1,
    "arrastando": False,
    "inicio": (0, 0),
    "ultimo": (0, 0),
    "snapshot": None,         # cópia do canvas para pré-visualizar formas
    "msg": "",
    "sujo": True,             # precisa redesenhar a tela?
}


def desenhar_interface():
    ui_retangulo(0, ALTURA_CANVAS, LARGURA, ALTURA_BARRA, (200, 200, 200))
    for tipo, valor, (x, y, w, h), rotulo in BOTOES:
        ativo = ((tipo == "ferr" and valor == estado["ferramenta"])
                 or (tipo == "esp" and valor == estado["esp"]))
        ui_retangulo(x, y, w, h, (120, 180, 255) if ativo else (240, 240, 240))
        ui_borda(x, y, w, h, (0, 0, 0))
        largura_txt = len(rotulo) * 12 - 2
        ui_texto(x + (w - largura_txt) // 2, y + 7, rotulo, 2, (0, 0, 0))
    for cor, (x, y, w, h) in AMOSTRAS:
        ui_retangulo(x, y, w, h, cor)
        if cor == estado["cor"]:
            ui_borda(x - 2, y - 2, w + 4, h + 4, (255, 140, 0), 3)
        else:
            ui_borda(x, y, w, h, (60, 60, 60))
    ui_texto(500, ALTURA_CANVAS + 80, estado["msg"], 2, (0, 90, 0))


def desenhar_forma(a, b):
    """Desenha a forma da ferramenta atual entre os pontos a (início) e b (atual)."""
    (x0, y0), (x1, y1) = a, b
    f, cor, esp = estado["ferramenta"], estado["cor"], estado["esp"]
    if f == "linha":
        linha_bresenham(x0, y0, x1, y1, cor, esp)
    elif f == "ret_vaz":
        retangulo_vazado(x0, y0, x1, y1, cor, esp)
    elif f == "ret_cheio":
        retangulo_preenchido(x0, y0, x1, y1, cor)
    elif f in ("cir_vaz", "cir_cheio"):
        r = int(((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5)
        if f == "cir_vaz":
            circulo_ponto_medio(x0, y0, r, cor, esp)
        else:
            circulo_preenchido(x0, y0, r, cor)


def salvar():
    salvar_bmp("desenho.bmp")
    salvar_ppm("desenho.ppm")
    estado["msg"] = "SALVO"
    print("Arquivos gerados: desenho.bmp e desenho.ppm")


def clamp_canvas(x, y):
    return max(0, min(LARGURA - 1, x)), max(0, min(ALTURA_CANVAS - 1, y))


# ============================================================================
# 6) TRATAMENTO DE EVENTOS (clique, arrasto, soltar)
# ============================================================================
def clique_na_barra(x, y):
    for tipo, valor, (bx, by, bw, bh), _ in BOTOES:
        if bx <= x < bx + bw and by <= y < by + bh:
            if tipo == "ferr":
                estado["ferramenta"] = valor
            elif tipo == "esp":
                estado["esp"] = valor
            elif valor == "novo":
                limpar_canvas()
            elif valor == "salvar":
                salvar()
            estado["msg"] = estado["msg"] if valor == "salvar" else ""
    for cor, (bx, by, bw, bh) in AMOSTRAS:
        if bx <= x < bx + bw and by <= y < by + bh:
            estado["cor"] = cor
    estado["sujo"] = True


def ao_pressionar(x, y):
    if y >= ALTURA_CANVAS:
        clique_na_barra(x, y)
        return
    f = estado["ferramenta"]
    if f == "balde":
        flood_fill(x, y, estado["cor"])
    else:
        estado["arrastando"] = True
        estado["inicio"] = estado["ultimo"] = (x, y)
        estado["snapshot"] = bytes(frame[0:LARGURA * ALTURA_CANVAS * 3])
        if f in ("lapis", "borracha"):
            cor = COR_FUNDO if f == "borracha" else estado["cor"]
            pincel(x, y, cor, estado["esp"])
    estado["msg"] = ""
    estado["sujo"] = True


def ao_arrastar(x, y):
    if not estado["arrastando"]:
        return
    x, y = clamp_canvas(x, y)
    f = estado["ferramenta"]
    if f in ("lapis", "borracha"):
        cor = COR_FUNDO if f == "borracha" else estado["cor"]
        ux, uy = estado["ultimo"]
        linha_bresenham(ux, uy, x, y, cor, estado["esp"])   # liga pontos amostrados
        estado["ultimo"] = (x, y)
    else:                                                   # pré-visualização elástica
        frame[0:LARGURA * ALTURA_CANVAS * 3] = estado["snapshot"]
        desenhar_forma(estado["inicio"], (x, y))
    estado["sujo"] = True


def ao_soltar(x, y):
    if not estado["arrastando"]:
        return
    ao_arrastar(x, y)
    estado["arrastando"] = False
    estado["snapshot"] = None


def cb_botao_mouse(janela, botao, acao, mods):
    if botao != glfw.MOUSE_BUTTON_LEFT:
        return
    x, y = glfw.get_cursor_pos(janela)
    x, y = int(x), int(y)
    if acao == glfw.PRESS:
        ao_pressionar(x, y)
    elif acao == glfw.RELEASE:
        ao_soltar(x, y)


def cb_cursor(janela, x, y):
    ao_arrastar(int(x), int(y))


def cb_teclado(janela, tecla, scancode, acao, mods):
    if acao != glfw.PRESS:
        return
    if tecla == glfw.KEY_N:
        limpar_canvas()
        estado["msg"] = ""
    elif tecla == glfw.KEY_S:
        salvar()
    estado["sujo"] = True


def cb_refresh(janela):
    estado["sujo"] = True


# ============================================================================
# 7) EXIBIÇÃO: framebuffer -> tela via glDrawPixels
# ============================================================================
def renderizar(janela):
    desenhar_interface()
    fbw, fbh = glfw.get_framebuffer_size(janela)
    zoom = fbw / LARGURA                       # 1.0 normal, 2.0 em telas HiDPI/Retina
    glViewport(0, 0, fbw, fbh)
    glMatrixMode(GL_PROJECTION)
    glLoadIdentity()
    glOrtho(0, LARGURA, ALTURA_JANELA, 0, -1, 1)   # origem no canto superior esquerdo
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glClear(GL_COLOR_BUFFER_BIT)
    glRasterPos2i(0, 0)                        # canto superior esquerdo
    glPixelZoom(zoom, -zoom)                   # -zoom: linhas descem (linha 0 = topo)
    glPixelStorei(GL_UNPACK_ALIGNMENT, 1)
    glDrawPixels(LARGURA, ALTURA_JANELA, GL_RGB, GL_UNSIGNED_BYTE, bytes(frame))
    glfw.swap_buffers(janela)


def main():
    if not glfw.init():
        raise RuntimeError("Falha ao inicializar o GLFW")
    glfw.window_hint(glfw.RESIZABLE, glfw.FALSE)
    janela = glfw.create_window(LARGURA, ALTURA_JANELA, "Mini Paint - OpenGL", None, None)
    if not janela:
        glfw.terminate()
        raise RuntimeError("Falha ao criar a janela")
    glfw.make_context_current(janela)
    glfw.swap_interval(1)
    glfw.set_mouse_button_callback(janela, cb_botao_mouse)
    glfw.set_cursor_pos_callback(janela, cb_cursor)
    glfw.set_key_callback(janela, cb_teclado)
    glfw.set_window_refresh_callback(janela, cb_refresh)
    glClearColor(0.8, 0.8, 0.8, 1.0)

    limpar_canvas()
    while not glfw.window_should_close(janela):
        glfw.wait_events_timeout(0.02)
        if estado["sujo"]:
            estado["sujo"] = False
            renderizar(janela)
    glfw.terminate()


if __name__ == "__main__":
    main()
