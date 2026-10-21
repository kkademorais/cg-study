/*
 * MiniPaint - Trabalho 1: Computação grafica
 * Compilar:  gcc minipaint.c -o minipaint $(sdl2-config --cflags --libs)
 * (ou: gcc minipaint.c -o minipaint -lSDL2)
 */
#include <SDL2/SDL.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>


/* Estruturas de dados                                              */
typedef struct { uint8_t r, g, b; } Color;

typedef struct {
    int w, h;
    uint32_t *px;          /* framebuffer 0xAARRGGBB */
} Canvas;

typedef enum {
    T_PENCIL, T_ERASER, T_LINE, T_RECT, T_RECTF,
    T_CIRCLE, T_CIRCLEF, T_BUCKET, T_COUNT
} Tool;

static const char *TOOL_NAMES[T_COUNT] = {
    "Lapis", "Borracha", "Linha", "Retangulo vazado", "Retangulo preenchido",
    "Circulo vazado", "Circulo preenchido", "Balde de tinta"
};

#define CW 800              /* canvas */
#define CH 600
#define TB 64               /* altura da barra de ferramentas */
#define SW CW
#define SH (CH + TB)

static const Color PALETTE[8] = {
    {0,0,0}, {255,255,255}, {255,0,0}, {0,255,0},
    {0,0,255}, {255,255,0}, {0,255,255}, {255,0,255}
};
static const int THICK[3] = {1, 3, 7};      
static const Color BG = {255, 255, 255};


/* Pixels                                                           */

static uint32_t pack(Color c) {
    return 0xFF000000u | ((uint32_t)c.r << 16) | ((uint32_t)c.g << 8) | c.b;
}
static Color unpack(uint32_t v) {
    Color c = { (v >> 16) & 255, (v >> 8) & 255, v & 255 };
    return c;
}

static Canvas canvas_new(int w, int h) {
    Canvas c = { w, h, malloc((size_t)w * h * sizeof(uint32_t)) };
    return c;
}
static void canvas_clear(Canvas *c, Color col) {
    uint32_t v = pack(col);
    for (int i = 0; i < c->w * c->h; i++) c->px[i] = v;
}

void put_pixel(Canvas *c, int x, int y, Color col) {
    if (x < 0 || y < 0 || x >= c->w || y >= c->h) return;
    c->px[y * c->w + x] = pack(col);
}
Color get_pixel(const Canvas *c, int x, int y) {
    if (x < 0 || y < 0 || x >= c->w || y >= c->h) { Color k = {0,0,0}; return k; }
    return unpack(c->px[y * c->w + x]);
}


Color blend(Color src, Color dst, int alpha) {
    Color o = {
        (src.r * alpha + dst.r * (255 - alpha)) / 255,
        (src.g * alpha + dst.g * (255 - alpha)) / 255,
        (src.b * alpha + dst.b * (255 - alpha)) / 255 };
    return o;
}


static void put_brush(Canvas *c, int x, int y, Color col, int t) {
    int h = t / 2;
    for (int dy = -h; dy <= h; dy++)
        for (int dx = -h; dx <= h; dx++)
            put_pixel(c, x + dx, y + dy, col);
}


/* Primitivas                                                       */

/* Linha de Bresenham (todos os octantes) */
void draw_line(Canvas *c, int x0, int y0, int x1, int y1, Color col, int t) {
    int dx = abs(x1 - x0), sx = x0 < x1 ? 1 : -1;
    int dy = -abs(y1 - y0), sy = y0 < y1 ? 1 : -1;
    int err = dx + dy;
    for (;;) {
        put_brush(c, x0, y0, col, t);
        if (x0 == x1 && y0 == y1) break;
        int e2 = 2 * err;
        if (e2 >= dy) { err += dy; x0 += sx; }
        if (e2 <= dx) { err += dx; y0 += sy; }
    }
}

static void hline(Canvas *c, int x0, int x1, int y, Color col) {
    if (x0 > x1) { int t = x0; x0 = x1; x1 = t; }
    for (int x = x0; x <= x1; x++) put_pixel(c, x, y, col);
}

void draw_rect(Canvas *c, int x0, int y0, int x1, int y1, Color col, int t, int fill) {
    if (fill) {
        if (y0 > y1) { int k = y0; y0 = y1; y1 = k; }
        for (int y = y0; y <= y1; y++) hline(c, x0, x1, y, col);
    } else {
        draw_line(c, x0, y0, x1, y0, col, t);
        draw_line(c, x1, y0, x1, y1, col, t);
        draw_line(c, x1, y1, x0, y1, col, t);
        draw_line(c, x0, y1, x0, y0, col, t);
    }
}

/* Circulo de ponto medio */
void draw_circle(Canvas *c, int cx, int cy, int r, Color col, int t, int fill) {
    int x = 0, y = r, d = 1 - r;
    while (x <= y) {
        if (fill) {
            hline(c, cx - x, cx + x, cy + y, col);
            hline(c, cx - x, cx + x, cy - y, col);
            hline(c, cx - y, cx + y, cy + x, col);
            hline(c, cx - y, cx + y, cy - x, col);
        } else {
            put_brush(c, cx + x, cy + y, col, t); put_brush(c, cx - x, cy + y, col, t);
            put_brush(c, cx + x, cy - y, col, t); put_brush(c, cx - x, cy - y, col, t);
            put_brush(c, cx + y, cy + x, col, t); put_brush(c, cx - y, cy + x, col, t);
            put_brush(c, cx + y, cy - x, col, t); put_brush(c, cx - y, cy - x, col, t);
        }
        if (d < 0) d += 2 * x + 3;
        else { d += 2 * (x - y) + 5; y--; }
        x++;
    }
}

/* Flood fill 4-conectado, iterativo  */
void flood_fill(Canvas *c, int sx, int sy, Color fill) {
    if (sx < 0 || sy < 0 || sx >= c->w || sy >= c->h) return;
    uint32_t target = c->px[sy * c->w + sx], nv = pack(fill);
    if (target == nv) return;
    int *stack = malloc((size_t)c->w * c->h * sizeof(int));
    if (!stack) return;
    int top = 0;
    c->px[sy * c->w + sx] = nv;
    stack[top++] = sy * c->w + sx;
    while (top > 0) {
        int idx = stack[--top];
        int x = idx % c->w, y = idx / c->w;
        const int nx[4] = { x + 1, x - 1, x, x };
        const int ny[4] = { y, y, y + 1, y - 1 };
        for (int k = 0; k < 4; k++) {
            if (nx[k] < 0 || ny[k] < 0 || nx[k] >= c->w || ny[k] >= c->h) continue;
            int j = ny[k] * c->w + nx[k];
            if (c->px[j] == target) { c->px[j] = nv; stack[top++] = j; }
        }
    }
    free(stack);
}


/* Exportar BMP 24 bits                                             */
static void w32(FILE *f, uint32_t v) { for (int i = 0; i < 4; i++) fputc((v >> (8*i)) & 255, f); }
static void w16(FILE *f, uint16_t v) { fputc(v & 255, f); fputc(v >> 8, f); }

int save_bmp(const Canvas *c, const char *name) {
    FILE *f = fopen(name, "wb");
    if (!f) return 0;
    int pad = (4 - (c->w * 3) % 4) % 4;
    uint32_t imgsize = (uint32_t)(c->w * 3 + pad) * c->h;
    fputc('B', f); fputc('M', f);
    w32(f, 54 + imgsize); w32(f, 0); w32(f, 54);
    w32(f, 40); w32(f, c->w); w32(f, c->h);
    w16(f, 1); w16(f, 24); w32(f, 0); w32(f, imgsize);
    w32(f, 2835); w32(f, 2835); w32(f, 0); w32(f, 0);
    for (int y = c->h - 1; y >= 0; y--) {      /* BMP e de baixo para cima */
        for (int x = 0; x < c->w; x++) {
            Color p = get_pixel(c, x, y);
            fputc(p.b, f); fputc(p.g, f); fputc(p.r, f);
        }
        for (int i = 0; i < pad; i++) fputc(0, f);
    }
    fclose(f);
    return 1;
}

/* Interface (barra de ferramentas desenhada com as mesmas primitivas) */

#define BTN 40
#define TOOL_X0 8
#define TOOL_STEP 48
#define THICK_X0 410
#define THICK_STEP 40
#define PAL_X0 540
#define PAL_SZ 24
#define NEW_X 668
#define SAVE_X 716
#define BTN_Y 12

static int in_rect(int mx, int my, int x, int y, int w, int h) {
    return mx >= x && mx < x + w && my >= y && my < y + h;
}

static void draw_icon(Canvas *s, int tool, int x, int y) {
    Color k = {0,0,0}, pink = {240,150,170};
    switch (tool) {
    case T_PENCIL:
        draw_line(s, x+8, y+32, x+30, y+8, k, 1);
        draw_line(s, x+10, y+34, x+32, y+10, k, 1);
        draw_line(s, x+8, y+32, x+10, y+34, k, 1); break;
    case T_ERASER:
        draw_rect(s, x+8, y+14, x+32, y+28, pink, 1, 1);
        draw_rect(s, x+8, y+14, x+32, y+28, k, 1, 0); break;
    case T_LINE: draw_line(s, x+7, y+33, x+33, y+7, k, 1); break;
    case T_RECT: draw_rect(s, x+7, y+10, x+33, y+30, k, 1, 0); break;
    case T_RECTF: draw_rect(s, x+7, y+10, x+33, y+30, k, 1, 1); break;
    case T_CIRCLE: draw_circle(s, x+20, y+20, 13, k, 1, 0); break;
    case T_CIRCLEF: draw_circle(s, x+20, y+20, 13, k, 1, 1); break;
    case T_BUCKET:
        draw_rect(s, x+9, y+14, x+27, y+32, k, 1, 0);
        draw_rect(s, x+10, y+22, x+26, y+31, (Color){60,120,220}, 1, 1);
        draw_line(s, x+27, y+14, x+33, y+8, k, 1);
        draw_circle(s, x+34, y+22, 3, (Color){60,120,220}, 1, 1); break;
    }
}

static void render_ui(Canvas *s, Tool tool, int thick, int color) {
    Color bar = {205,205,210}, k = {0,0,0}, sel = {80,140,255}, w = {255,255,255};
    for (int y = 0; y < TB; y++) hline(s, 0, SW - 1, y, bar);
    hline(s, 0, SW - 1, TB - 1, (Color){90,90,90});

    for (int i = 0; i < T_COUNT; i++) {
        int x = TOOL_X0 + i * TOOL_STEP;
        draw_rect(s, x, BTN_Y, x + BTN - 1, BTN_Y + BTN - 1, i == (int)tool ? blend(sel, bar, 90) : w, 1, 1);
        draw_rect(s, x, BTN_Y, x + BTN - 1, BTN_Y + BTN - 1, i == (int)tool ? sel : k, i == (int)tool ? 3 : 1, 0);
        draw_icon(s, i, x, BTN_Y);
    }
    for (int i = 0; i < 3; i++) {                       /* espessuras */
        int x = THICK_X0 + i * THICK_STEP;
        draw_rect(s, x, BTN_Y, x + 35, BTN_Y + BTN - 1, i == thick ? blend(sel, bar, 90) : w, 1, 1);
        draw_rect(s, x, BTN_Y, x + 35, BTN_Y + BTN - 1, i == thick ? sel : k, i == thick ? 3 : 1, 0);
        draw_line(s, x + 6, BTN_Y + 20, x + 29, BTN_Y + 20, k, THICK[i]);
    }
    for (int i = 0; i < 8; i++) {                       /* paleta 4x2 */
        int x = PAL_X0 + (i % 4) * (PAL_SZ + 2), y = 8 + (i / 4) * (PAL_SZ + 2);
        draw_rect(s, x, y, x + PAL_SZ - 1, y + PAL_SZ - 1, PALETTE[i], 1, 1);
        draw_rect(s, x, y, x + PAL_SZ - 1, y + PAL_SZ - 1, i == color ? sel : k, i == color ? 3 : 1, 0);
    }
    /* Novo: folha em branco */
    draw_rect(s, NEW_X, BTN_Y, NEW_X + 39, BTN_Y + 39, w, 1, 1);
    draw_rect(s, NEW_X, BTN_Y, NEW_X + 39, BTN_Y + 39, k, 1, 0);
    draw_rect(s, NEW_X + 11, BTN_Y + 7, NEW_X + 29, BTN_Y + 33, k, 1, 0);
    draw_line(s, NEW_X + 20, BTN_Y + 14, NEW_X + 20, BTN_Y + 26, k, 1);
    draw_line(s, NEW_X + 14, BTN_Y + 20, NEW_X + 26, BTN_Y + 20, k, 1);
    /* Salvar: disquete */
    int sx = SAVE_X;
    draw_rect(s, sx, BTN_Y, sx + 39, BTN_Y + 39, w, 1, 1);
    draw_rect(s, sx, BTN_Y, sx + 39, BTN_Y + 39, k, 1, 0);
    draw_rect(s, sx + 9, BTN_Y + 8, sx + 31, BTN_Y + 32, (Color){60,60,160}, 1, 1);
    draw_rect(s, sx + 14, BTN_Y + 8, sx + 26, BTN_Y + 16, w, 1, 1);
    draw_rect(s, sx + 14, BTN_Y + 22, sx + 26, BTN_Y + 32, (Color){200,200,200}, 1, 1);
}


/* Programa principal                                               */

static Canvas canvas, snapshot, screen;
static Tool tool = T_PENCIL;
static int thick = 0, color = 0;
static int save_count = 0;

static void update_title(SDL_Window *win) {
    char t[160];
    snprintf(t, sizeof t, "MiniPaint - %s | espessura %dpx | teclas: P E L R T C O B N S",
             TOOL_NAMES[tool], THICK[thick]);
    SDL_SetWindowTitle(win, t);
}

static void do_save(void) {
    char name[64];
    snprintf(name, sizeof name, "desenho_%d.bmp", ++save_count);
    if (save_bmp(&canvas, name)) printf("Salvo: %s\n", name);
    else fprintf(stderr, "Erro ao salvar %s\n", name);
}

static void draw_shape(int x0, int y0, int x1, int y1) {
    Color col = PALETTE[color];
    int t = THICK[thick];
    switch (tool) {
    case T_LINE:  draw_line(&canvas, x0, y0, x1, y1, col, t); break;
    case T_RECT:  draw_rect(&canvas, x0, y0, x1, y1, col, t, 0); break;
    case T_RECTF: draw_rect(&canvas, x0, y0, x1, y1, col, t, 1); break;
    case T_CIRCLE: case T_CIRCLEF: {
        int dx = x1 - x0, dy = y1 - y0, r2 = dx*dx + dy*dy, r = 0;
        while ((r + 1) * (r + 1) <= r2) r++;            /* raiz inteira */
        draw_circle(&canvas, x0, y0, r, col, t, tool == T_CIRCLEF);
        break; }
    default: break;
    }
}

int main(int argc, char **argv) {
    (void)argc; (void)argv;
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        fprintf(stderr, "SDL_Init: %s\n", SDL_GetError());
        return 1;
    }
    SDL_Window *win = SDL_CreateWindow("MiniPaint", SDL_WINDOWPOS_CENTERED,
                        SDL_WINDOWPOS_CENTERED, SW, SH, 0);
    SDL_Renderer *ren = SDL_CreateRenderer(win, -1, 0);
    SDL_Texture *tex = SDL_CreateTexture(ren, SDL_PIXELFORMAT_ARGB8888,
                        SDL_TEXTUREACCESS_STREAMING, SW, SH);
    if (!win || !ren || !tex) { fprintf(stderr, "SDL: %s\n", SDL_GetError()); return 1; }

    canvas = canvas_new(CW, CH);
    snapshot = canvas_new(CW, CH);
    screen = canvas_new(SW, SH);
    canvas_clear(&canvas, BG);
    update_title(win);

    int running = 1, drawing = 0, sx = 0, sy = 0, lx = 0, ly = 0;
    SDL_Event e;
    while (running) {
        while (SDL_PollEvent(&e)) {
            if (e.type == SDL_QUIT) running = 0;

            else if (e.type == SDL_KEYDOWN) {
                switch (e.key.keysym.sym) {
                case SDLK_p: tool = T_PENCIL; break;
                case SDLK_e: tool = T_ERASER; break;
                case SDLK_l: tool = T_LINE; break;
                case SDLK_r: tool = T_RECT; break;
                case SDLK_t: tool = T_RECTF; break;
                case SDLK_c: tool = T_CIRCLE; break;
                case SDLK_o: tool = T_CIRCLEF; break;
                case SDLK_b: tool = T_BUCKET; break;
                case SDLK_1: thick = 0; break;
                case SDLK_2: thick = 1; break;
                case SDLK_3: thick = 2; break;
                case SDLK_n: canvas_clear(&canvas, BG); break;
                case SDLK_s: do_save(); break;
                case SDLK_ESCAPE: running = 0; break;
                default: break;
                }
                update_title(win);
            }

            else if (e.type == SDL_MOUSEBUTTONDOWN && e.button.button == SDL_BUTTON_LEFT) {
                int mx = e.button.x, my = e.button.y;
                if (my < TB) {                                   /* clique na barra */
                    for (int i = 0; i < T_COUNT; i++)
                        if (in_rect(mx, my, TOOL_X0 + i*TOOL_STEP, BTN_Y, BTN, BTN)) tool = i;
                    for (int i = 0; i < 3; i++)
                        if (in_rect(mx, my, THICK_X0 + i*THICK_STEP, BTN_Y, 36, BTN)) thick = i;
                    for (int i = 0; i < 8; i++)
                        if (in_rect(mx, my, PAL_X0 + (i%4)*(PAL_SZ+2), 8 + (i/4)*(PAL_SZ+2), PAL_SZ, PAL_SZ)) color = i;
                    if (in_rect(mx, my, NEW_X, BTN_Y, BTN, BTN)) canvas_clear(&canvas, BG);
                    if (in_rect(mx, my, SAVE_X, BTN_Y, BTN, BTN)) do_save();
                    update_title(win);
                } else {                                         /* clique no canvas */
                    int cx = mx, cy = my - TB;
                    if (tool == T_BUCKET) flood_fill(&canvas, cx, cy, PALETTE[color]);
                    else {
                        drawing = 1; sx = lx = cx; sy = ly = cy;
                        memcpy(snapshot.px, canvas.px, (size_t)CW * CH * 4);
                        if (tool == T_PENCIL) put_brush(&canvas, cx, cy, PALETTE[color], THICK[thick]);
                        if (tool == T_ERASER) put_brush(&canvas, cx, cy, BG, THICK[thick]);
                    }
                }
            }

            else if (e.type == SDL_MOUSEMOTION && drawing) {      /* arrasto */
                int cx = e.motion.x, cy = e.motion.y - TB;
                if (tool == T_PENCIL) draw_line(&canvas, lx, ly, cx, cy, PALETTE[color], THICK[thick]);
                else if (tool == T_ERASER) draw_line(&canvas, lx, ly, cx, cy, BG, THICK[thick]);
                else {                                            /* preview da forma */
                    memcpy(canvas.px, snapshot.px, (size_t)CW * CH * 4);
                    draw_shape(sx, sy, cx, cy);
                }
                lx = cx; ly = cy;
            }

            else if (e.type == SDL_MOUSEBUTTONUP && e.button.button == SDL_BUTTON_LEFT && drawing) {
                drawing = 0;                                      /* soltar */
                if (tool != T_PENCIL && tool != T_ERASER) {
                    memcpy(canvas.px, snapshot.px, (size_t)CW * CH * 4);
                    draw_shape(sx, sy, e.button.x, e.button.y - TB);
                }
            }
        }

        /* Composicao do frame: barra + canvas */
        render_ui(&screen, tool, thick, color);
        memcpy(screen.px + TB * SW, canvas.px, (size_t)CW * CH * 4);
        SDL_UpdateTexture(tex, NULL, screen.px, SW * 4);
        SDL_RenderClear(ren);
        SDL_RenderCopy(ren, tex, NULL, NULL);
        SDL_RenderPresent(ren);
        SDL_Delay(8);
    }

    free(canvas.px); free(snapshot.px); free(screen.px);
    SDL_DestroyTexture(tex); SDL_DestroyRenderer(ren); SDL_DestroyWindow(win);
    SDL_Quit();
    return 0;
}
