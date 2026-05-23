import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import os
from PIL import Image, ImageTk, ImageDraw, ImageFont
import numpy as np
from sklearn.cluster import KMeans

# ── Temas ──────────────────────────────────────────────────────────────────────
TEMAS = {
    "escuro": {
        "bg":        "#1e1e2e",
        "surface":   "#313244",
        "fg":        "#cdd6f4",
        "fg2":       "#6c7086",
        "btn":       "#89b4fa",
        "btn_fg":    "#1e1e2e",
        "slider_tr": "#313244",
    },
    "claro": {
        "bg":        "#eff1f5",
        "surface":   "#dce0e8",
        "fg":        "#4c4f69",
        "fg2":       "#8c8fa1",
        "btn":       "#1e66f5",
        "btn_fg":    "#ffffff",
        "slider_tr": "#bcc0cc",
    },
}

def extrair_paleta(caminho, n):
    img = Image.open(caminho).convert("RGB")
    img_pequena = img.resize((200, 200))
    pixels = np.array(img_pequena).reshape(-1, 3)
    kmeans = KMeans(n_clusters=n, random_state=42, n_init="auto")
    kmeans.fit(pixels)
    cores = kmeans.cluster_centers_.astype(int)
    contagens = np.bincount(kmeans.labels_)
    ordem = np.argsort(-contagens)
    return [tuple(cores[i]) for i in ordem]

def rgb_para_hex(r, g, b):
    return f"#{r:02X}{g:02X}{b:02X}"

def fonte(tamanho, negrito=False):
    tentativas = [
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans{'-Bold' if negrito else ''}.ttf",
        f"/usr/share/fonts/truetype/liberation/LiberationSans{'-Bold' if negrito else '-Regular'}.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in tentativas:
        if os.path.exists(path):
            return ImageFont.truetype(path, tamanho)
    return ImageFont.load_default()

def gerar_imagem_exportacao(caminho_original, cores):
    LARGURA = 800
    PAD = 32
    QUAD = 80
    GAP = 12
    RODAPE = 24

    img_orig = Image.open(caminho_original).convert("RGB")
    ratio = img_orig.width / img_orig.height
    altura_preview = int(LARGURA / ratio)
    img_orig = img_orig.resize((LARGURA, altura_preview), Image.LANCZOS)

    n = len(cores)
    total_quads = n * QUAD + (n - 1) * GAP
    offset_x = (LARGURA - total_quads) // 2

    altura_total = altura_preview + PAD + QUAD + 52 + PAD + RODAPE
    canvas = Image.new("RGB", (LARGURA, altura_total), (18, 18, 28))
    draw = ImageDraw.Draw(canvas)
    canvas.paste(img_orig, (0, 0))

    fn_hex = fonte(13, negrito=True)
    fn_rgb = fonte(11)
    fn_nome = fonte(11)

    nome_arquivo = os.path.basename(caminho_original)
    draw.text((PAD, altura_preview + 10), nome_arquivo, font=fn_nome, fill=(100, 100, 120))

    y_quad = altura_preview + PAD
    for i, (r, g, b) in enumerate(cores):
        x = offset_x + i * (QUAD + GAP)
        draw.rectangle([x, y_quad, x + QUAD, y_quad + QUAD], fill=(r, g, b))
        hex_str = rgb_para_hex(r, g, b)
        rgb_str = f"rgb({r},{g},{b})"
        bx1, _, bx2, _ = draw.textbbox((0, 0), hex_str, font=fn_hex)
        draw.text((x + (QUAD - (bx2 - bx1)) // 2, y_quad + QUAD + 6), hex_str, font=fn_hex, fill=(220, 220, 235))
        bx1, _, bx2, _ = draw.textbbox((0, 0), rgb_str, font=fn_rgb)
        draw.text((x + (QUAD - (bx2 - bx1)) // 2, y_quad + QUAD + 24), rgb_str, font=fn_rgb, fill=(130, 130, 150))

    return canvas


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Paleta de Cores")
        self.root.geometry("740x680")
        self.root.resizable(False, False)

        self.tema_atual = "escuro"
        self.caminho_atual = None
        self.cores_atuais = []
        self._reanalise_timer = None
        self._popup = None

        self._construir_ui()
        self._aplicar_tema()

    def t(self):
        return TEMAS[self.tema_atual]

    def _construir_ui(self):
        # ── Barra superior ────────────────────────────────────────────────────
        self.frame_topo = tk.Frame(self.root)
        self.frame_topo.pack(fill="x", padx=20, pady=(14, 0))

        self.btn_tema = tk.Button(self.frame_topo, text="☀ Tema claro",
                                  font=("Sans", 9), relief="flat",
                                  padx=10, pady=4, cursor="hand2",
                                  command=self.alternar_tema)
        self.btn_tema.pack(side="right")

        # ── Título ────────────────────────────────────────────────────────────
        self.frame_titulo = tk.Frame(self.root)
        self.frame_titulo.pack(pady=(8, 0))
        self.lbl_titulo = tk.Label(self.frame_titulo, text="🎨 Extrator de Paleta",
                                   font=("Sans", 18, "bold"))
        self.lbl_titulo.pack()
        self.lbl_sub = tk.Label(self.frame_titulo,
                                text="Carregue uma imagem e veja as cores dominantes",
                                font=("Sans", 10))
        self.lbl_sub.pack(pady=(2, 0))

        # ── Botão escolher ────────────────────────────────────────────────────
        self.btn = tk.Button(self.root, text="Escolher Imagem", font=("Sans", 11),
                             relief="flat", padx=16, pady=8, cursor="hand2",
                             command=self.escolher_imagem)
        self.btn.pack(pady=10)

        # ── Slider ────────────────────────────────────────────────────────────
        self.frame_slider = tk.Frame(self.root)
        self.frame_slider.pack(pady=(0, 8))
        self.lbl_slider = tk.Label(self.frame_slider, text="Quantidade de cores:",
                                   font=("Sans", 10))
        self.lbl_slider.pack(side="left", padx=(0, 10))
        self.num_cores = tk.IntVar(value=8)
        self.slider = tk.Scale(self.frame_slider, from_=4, to=10, orient="horizontal",
                               variable=self.num_cores, length=180,
                               highlightthickness=0, command=self.slider_alterado)
        self.slider.pack(side="left")
        self.lbl_num = tk.Label(self.frame_slider, text="8 cores",
                                font=("Sans", 10, "bold"), width=7)
        self.lbl_num.pack(side="left", padx=(8, 0))

        # ── Preview ───────────────────────────────────────────────────────────
        self.label_img = tk.Label(self.root)
        self.label_img.pack()

        # ── Paleta ────────────────────────────────────────────────────────────
        self.frame_paleta = tk.Frame(self.root)
        self.frame_paleta.pack(pady=10)

        # ── Exportação ────────────────────────────────────────────────────────
        self.frame_export = tk.Frame(self.root)
        self.frame_export.pack(pady=4)

        # ── Status ────────────────────────────────────────────────────────────
        self.status = tk.Label(self.root, text="", font=("Sans", 10))
        self.status.pack()

    def _aplicar_tema(self):
        t = self.t()
        widgets_bg = [
            self.root, self.frame_topo, self.frame_titulo,
            self.frame_slider, self.frame_paleta, self.frame_export,
        ]
        for w in widgets_bg:
            w.configure(bg=t["bg"])

        self.lbl_titulo.configure(bg=t["bg"], fg=t["fg"])
        self.lbl_sub.configure(bg=t["bg"], fg=t["fg2"])
        self.label_img.configure(bg=t["bg"])
        self.status.configure(bg=t["bg"], fg=t["fg2"])
        self.lbl_slider.configure(bg=t["bg"], fg=t["fg2"])
        self.lbl_num.configure(bg=t["bg"], fg=t["fg"])
        self.slider.configure(bg=t["bg"], fg=t["fg"],
                              troughcolor=t["slider_tr"], activebackground=t["btn"])
        self.btn.configure(bg=t["btn"], fg=t["btn_fg"])
        self.btn_tema.configure(
            bg=t["bg"], fg=t["fg2"],
            text="☀ Tema claro" if self.tema_atual == "escuro" else "🌙 Tema escuro"
        )
        self._recolorir_paleta()

    def alternar_tema(self):
        self.tema_atual = "claro" if self.tema_atual == "escuro" else "escuro"
        self._aplicar_tema()

    def _recolorir_paleta(self):
        if not self.cores_atuais:
            return
        t = self.t()
        for frame in self.frame_paleta.winfo_children():
            frame.configure(bg=t["surface"])
            for w in frame.winfo_children():
                if isinstance(w, tk.Label):
                    txt = w.cget("text")
                    if txt.startswith("#") and len(txt) == 7:
                        # label de texto HEX
                        w.configure(bg=t["surface"], fg=t["fg"])
                    elif txt.startswith("rgb"):
                        w.configure(bg=t["surface"], fg=t["fg2"])
                    else:
                        # quadradinho — não mexe no bg (é a cor da paleta)
                        pass

    # ── Slider ────────────────────────────────────────────────────────────────
    def slider_alterado(self, valor):
        self.lbl_num.config(text=f"{valor} cores")
        if self.caminho_atual:
            if self._reanalise_timer:
                self.root.after_cancel(self._reanalise_timer)
            self._reanalise_timer = self.root.after(400, self.reanalisar)

    def reanalisar(self):
        if self.caminho_atual:
            self.status.config(text="Reanalisando...")
            self.btn.config(state="disabled")
            threading.Thread(target=self.processar, args=(self.caminho_atual,), daemon=True).start()

    # ── Imagem ────────────────────────────────────────────────────────────────
    def escolher_imagem(self):
        caminho = filedialog.askopenfilename(
            title="Escolher imagem",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.bmp *.webp")]
        )
        if not caminho:
            return
        self.caminho_atual = caminho
        self.status.config(text="Analisando imagem...")
        self.btn.config(state="disabled")
        threading.Thread(target=self.processar, args=(caminho,), daemon=True).start()

    def processar(self, caminho):
        try:
            n = self.num_cores.get()
            cores = extrair_paleta(caminho, n)
            img = Image.open(caminho)
            img.thumbnail((700, 220))
            foto = ImageTk.PhotoImage(img)
            self.root.after(0, lambda: self.mostrar_resultado(foto, cores))
        except Exception as e:
            self.root.after(0, lambda: messagebox.showerror("Erro", str(e)))
            self.root.after(0, lambda: self.btn.config(state="normal"))

    def mostrar_resultado(self, foto, cores):
        t = self.t()
        self.cores_atuais = cores
        self.label_img.config(image=foto)
        self.label_img.image = foto

        for w in self.frame_paleta.winfo_children():
            w.destroy()
        for w in self.frame_export.winfo_children():
            w.destroy()

        for r, g, b in cores:
            hex_cor = rgb_para_hex(r, g, b)
            rgb_str = f"rgb({r},{g},{b})"

            frame = tk.Frame(self.frame_paleta, bg=t["surface"], padx=6, pady=6)
            frame.pack(side="left", padx=4)

            quadrado = tk.Label(frame, bg=hex_cor, width=6, height=3, cursor="hand2")
            quadrado.pack()
            quadrado.bind("<Button-1>", lambda e, h=hex_cor, rs=rgb_str: self.abrir_popup(e, h, rs))

            tk.Label(frame, text=hex_cor, font=("Mono", 9),
                     bg=t["surface"], fg=t["fg"]).pack(pady=(4, 0))
            tk.Label(frame, text=rgb_str, font=("Mono", 8),
                     bg=t["surface"], fg=t["fg2"]).pack()

        estilos = [
            ("Exportar PNG",  "#a6e3a1", self.exportar_png),
            ("Exportar JPEG", "#89dceb", self.exportar_jpeg),
            ("Exportar PDF",  "#cba6f7", self.exportar_pdf),
        ]
        for texto, cor, cmd in estilos:
            tk.Button(self.frame_export, text=texto, font=("Sans", 10),
                      bg=cor, fg="#1e1e2e", relief="flat",
                      padx=12, pady=6, cursor="hand2",
                      command=cmd).pack(side="left", padx=6)

        self.btn.config(state="normal", text="Escolher outra imagem")
        self.status.config(text="✓ Clique em uma cor para copiar HEX ou RGB")

    # ── Popup copiar ──────────────────────────────────────────────────────────
    def abrir_popup(self, event, hex_cor, rgb_str):
        if self._popup:
            self._popup.destroy()
        t = self.t()
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.configure(bg=t["surface"])
        self._popup = popup

        x = event.widget.winfo_rootx()
        y = event.widget.winfo_rooty() + event.widget.winfo_height() + 4
        popup.geometry(f"+{x}+{y}")

        def copiar_e_fechar(valor, label):
            self.root.clipboard_clear()
            self.root.clipboard_append(valor)
            self.status.config(text=f"✓ {label} copiado!")
            popup.destroy()
            self._popup = None

        tk.Button(popup, text=f"Copiar HEX  {hex_cor}",
                  font=("Mono", 9), relief="flat", cursor="hand2",
                  bg=t["surface"], fg=t["fg"], padx=12, pady=6,
                  command=lambda: copiar_e_fechar(hex_cor, hex_cor)).pack(fill="x")

        sep = tk.Frame(popup, bg=t["fg2"], height=1)
        sep.pack(fill="x")

        tk.Button(popup, text=f"Copiar RGB  {rgb_str}",
                  font=("Mono", 9), relief="flat", cursor="hand2",
                  bg=t["surface"], fg=t["fg"], padx=12, pady=6,
                  command=lambda: copiar_e_fechar(rgb_str, rgb_str)).pack(fill="x")

        self.root.bind("<Button-1>", lambda e: self._fechar_popup_externo(e, popup), add="+")

    def _fechar_popup_externo(self, event, popup):
        try:
            if not popup.winfo_containing(event.x_root, event.y_root):
                popup.destroy()
                self._popup = None
        except Exception:
            pass

    # ── Exportação ────────────────────────────────────────────────────────────
    def _gerar_e_salvar(self, destino, salvar_fn):
        if not self.caminho_atual or not self.cores_atuais:
            return
        self.status.config(text="Gerando arquivo...")
        def task():
            try:
                img = gerar_imagem_exportacao(self.caminho_atual, self.cores_atuais)
                salvar_fn(img, destino)
                self.root.after(0, lambda: self.status.config(
                    text=f"✓ Salvo em: {os.path.basename(destino)}"))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Erro ao exportar", str(e)))
        threading.Thread(target=task, daemon=True).start()

    def exportar_png(self):
        destino = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG", "*.png")], initialfile="paleta.png")
        if destino:
            self._gerar_e_salvar(destino, lambda img, p: img.save(p, "PNG"))

    def exportar_jpeg(self):
        destino = filedialog.asksaveasfilename(
            defaultextension=".jpg", filetypes=[("JPEG", "*.jpg")], initialfile="paleta.jpg")
        if destino:
            self._gerar_e_salvar(destino, lambda img, p: img.save(p, "JPEG", quality=95))

    def exportar_pdf(self):
        destino = filedialog.asksaveasfilename(
            defaultextension=".pdf", filetypes=[("PDF", "*.pdf")], initialfile="paleta.pdf")
        if destino:
            self._gerar_e_salvar(destino, lambda img, p: img.save(p, "PDF", resolution=150))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
