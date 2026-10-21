# MiniPaint — Trabalho 1 de Computação Gráfica

Sistema gráfico de desenho 2D interativo em C, com SDL2 usada **apenas** para
criar a janela, exibir o framebuffer e receber eventos de mouse/teclado.
Todo o desenho (pixels, linhas, círculos, preenchimento, exportação) é
implementado manualmente sobre uma matriz de pixels.

## Como compilar / executar

**Linux:**


sudo apt install libsdl2-dev
gcc minipaint.c -o minipaint $(sdl2-config --cflags --libs)

apos isso basta escrever e confirmar no terminal 

./minipaint



## Controles

| Ação | Mouse (barra superior) | Teclado |
|---|---|---|
| Lápis | ícone do lápis | `P` |
| Borracha | ícone da borracha | `E` |
| Linha | ícone de linha | `L` |
| Retângulo vazado | ícone | `R` |
| Retângulo preenchido | ícone | `T` |
| Círculo vazado | ícone | `C` |
| Círculo preenchido | ícone | `O` |
| Balde de tinta | ícone | `B` |
| Espessura fina / média / grossa (1, 3, 7 px) | três botões | `1` `2` `3` |
| Cor | paleta com 8 cores | — |
| Novo (limpa o canvas) | botão com "+" | `N` |
| Salvar (gera `desenho_N.bmp`) | botão de disquete | `S` |
| Sair | — | `Esc` |

Formas (linha, retângulo, círculo) mostram uma **prévia em tempo real** enquanto
o botão do mouse está pressionado e são fixadas ao soltar. No círculo, o clique
inicial é o centro e a distância até o ponto atual é o raio.

## Requisitos do trabalho × onde estão no código

| Requisito | Implementação (`minipaint.c`) |
|---|---|
| Canvas de tamanho fixo | `CW x CH` = 800 x 600 |
| `put_pixel(x, y, cor)` | função `put_pixel` |
| `get_pixel(x, y)` | função `get_pixel` |
| Linha (Bresenham) | `draw_line`, todos os octantes, com espessura |
| Círculo (ponto médio) | `draw_circle`, vazado e preenchido |
| Retângulo vazado / preenchido | `draw_rect` |
| Flood fill sem função pronta | `flood_fill`, 4-conectado, iterativo com pilha explícita |
| Eventos de mouse (clique, arrasto, soltar) | laço principal: `SDL_MOUSEBUTTONDOWN`, `SDL_MOUSEMOTION`, `SDL_MOUSEBUTTONUP` |
| Estrutura de dados | `Color` (RGB), `Canvas` (largura, altura, vetor de pixels), `enum Tool` |
| Paleta com 8 cores | preto, branco, vermelho, verde, azul, amarelo, ciano, magenta |
| 3 espessuras | fino (1), médio (3), grosso (7) |
| Botão Novo | `canvas_clear` |
| Botão Salvar | `save_bmp`, BMP 24 bits escrito byte a byte |
| Cores RGB e blend | struct `Color` e função `blend` (mistura por alfa, usada no destaque da UI) |

## Detalhes dos algoritmos

**Framebuffer.** O canvas é um vetor de `uint32_t` (formato ARGB). `put_pixel`
ignora coordenadas fora dos limites. A barra de ferramentas é desenhada com as
mesmas primitivas e composta acima do canvas a cada quadro.

**Bresenham (linha).** Versão com aritmética inteira e termo de erro
`err = dx + dy`, que funciona em todos os octantes sem tratar casos
separadamente. A espessura é obtida estampando um quadrado `t x t` em cada
ponto da linha.

**Ponto médio (círculo).** Calcula um octante usando a variável de decisão
`d`, iniciada em `1 - r`, e espelha cada ponto nos 8 octantes. No círculo
preenchido, cada par de pontos simétricos vira uma linha horizontal.

**Flood fill.** Lê a cor do pixel clicado (alvo) e a troca pela cor escolhida,
espalhando para os 4 vizinhos. Usa uma pilha explícita em vez de recursão para
não estourar a pilha de chamadas em áreas grandes. O pixel é pintado ao ser
empilhado, então cada pixel entra na pilha no máximo uma vez.

**Borracha.** Funciona como o lápis, mas pinta com a cor de fundo (branco).

**Prévia das formas.** Ao pressionar o mouse, o canvas é copiado para um
`snapshot`. A cada movimento o canvas é restaurado do snapshot e a forma é
redesenhada até a posição atual; assim não ficam rastros.

**BMP.** Cabeçalho de 54 bytes (arquivo + DIB), pixels em BGR, linhas de baixo
para cima e preenchimento (padding) para múltiplo de 4 bytes por linha.

## Estrutura do pacote

```
MiniPaint/
├── SDL2.dll        biblioteca necessária para o .exe
├── minipaint.c     código-fonte completo
└── README.md       este arquivo
```
