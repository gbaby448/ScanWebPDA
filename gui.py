import customtkinter as ctk
import tkinter as tk
import os
import json
import threading
import time
import webbrowser
import math
import io
import requests
from PIL import Image, ImageDraw
import main
import database
import ai_filter
import updater
from version import VERSION

def get_placeholder_image(size=(80, 80)):
    """Génère dynamiquement une icône d'engrenage en mémoire pour servir de placeholder."""
    img = Image.new("RGBA", size, (30, 30, 30, 0)) # transparent background
    draw = ImageDraw.Draw(img)
    # Cog center
    cx, cy = size[0] // 2, size[1] // 2
    r_outer = 22
    r_inner = 14
    r_center = 7
    
    # Outer circle
    draw.ellipse([cx - r_outer, cy - r_outer, cx + r_outer, cy + r_outer], fill="#424242", outline="#2e7d32", width=2)
    # Inner cutout
    draw.ellipse([cx - r_inner, cy - r_inner, cx + r_inner, cy + r_inner], fill="#1e1e1e")
    # Small hub
    draw.ellipse([cx - r_center, cy - r_center, cx + r_center, cy + r_center], fill="#2e7d32")
    
    # Draw teeth
    num_teeth = 8
    for i in range(num_teeth):
        angle = i * (2 * math.pi / num_teeth)
        # Tooth base
        bx1 = cx + (r_outer - 1) * math.cos(angle - 0.15)
        by1 = cy + (r_outer - 1) * math.sin(angle - 0.15)
        bx2 = cx + (r_outer - 1) * math.cos(angle + 0.15)
        by2 = cy + (r_outer - 1) * math.sin(angle + 0.15)
        
        # Tooth tip
        tx1 = cx + (r_outer + 6) * math.cos(angle - 0.1)
        ty1 = cy + (r_outer + 6) * math.sin(angle - 0.1)
        tx2 = cx + (r_outer + 6) * math.cos(angle + 0.1)
        ty2 = cy + (r_outer + 6) * math.sin(angle + 0.1)
        
        draw.polygon([bx1, by1, bx2, by2, tx2, ty2, tx1, ty1], fill="#2e7d32")
        
    return img

# Configuration initiale de l'apparence
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class ScanWebApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Paramètres généraux de la fenêtre
        self.title("ScanWebPDA - Surveillance Pièces Auto")
        self.geometry("980x740")
        self.minsize(900, 680)

        # Liaison de la fermeture de fenêtre pour arrêter la surveillance
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Liaison du redimensionnement de la fenêtre pour le mode responsive
        self.bind("<Configure>", self.on_window_resize)

        # Variables d'état
        self.ollama_online = False
        self.check_thread_running = True

        # Génération du placeholder d'engrenage par défaut pour les images
        self.placeholder_pil = get_placeholder_image()
        self.placeholder_image = ctk.CTkImage(
            light_image=self.placeholder_pil, 
            dark_image=self.placeholder_pil, 
            size=(80, 80)
        )

        # Initialisation de l'interface
        self.create_widgets()
        self.load_config_ui()
        self.load_monitored_pieces()
        self.load_valid_items_ui()

        # Démarrage du thread de surveillance d'Ollama
        self.start_ollama_check_thread()

        # Vérification silencieuse des mises à jour au démarrage
        self.after(3000, lambda: self.check_updates_silent(silent=True))

    def create_widgets(self):
        # Configuration de la grille principale
        self.grid_rowconfigure(1, weight=1)  # La zone de contenu s'étire
        self.grid_columnconfigure(0, weight=1)

        # ==========================================
        # 1. HEADER FRAME
        # ==========================================
        self.header_frame = ctk.CTkFrame(self, height=70, corner_radius=0)
        self.header_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        
        self.title_label = ctk.CTkLabel(
            self.header_frame, 
            text="ScanWebPDA - Panneau de Contrôle", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        self.title_label.pack(side="left", padx=20, pady=10)

        self.subtitle_label = ctk.CTkLabel(
            self.header_frame, 
            text="Surveillance intelligente de pièces auto par IA", 
            font=ctk.CTkFont(size=13, slant="italic")
        )
        self.subtitle_label.pack(side="left", padx=10, pady=15)

        # Bouton mise à jour dans le header
        self.btn_check_update = ctk.CTkButton(
            self.header_frame,
            text="🔄 Mise à jour",
            fg_color="#1a237e",
            hover_color="#283593",
            font=ctk.CTkFont(size=13),
            height=36,
            width=140,
            command=lambda: self.check_updates_silent(silent=False)
        )
        self.btn_check_update.pack(side="right", padx=(0, 8), pady=10)

        # Bouton principal dans le header (toujours visible)
        self.header_btn_toggle = ctk.CTkButton(
            self.header_frame,
            text="▶  Démarrer la Surveillance",
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            width=230,
            command=self.toggle_surveillance
        )
        self.header_btn_toggle.pack(side="right", padx=20, pady=10)

        # ==========================================
        # TABVIEW PRINCIPALE
        # ==========================================
        self.tabview = ctk.CTkTabview(self)
        self.tabview.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        # Ajout des onglets
        self.tab_surveillance = self.tabview.add("Surveillance & Contrôle")
        self.tab_trouvees = self.tabview.add("Pièces Trouvées (AI)")

        # --- ONGLET 1 : SURVEILLANCE & CONTRÔLE ---
        self.tab_surveillance.grid_columnconfigure(0, weight=1)
        self.tab_surveillance.grid_rowconfigure(0, weight=3)  # content_frame s'étire
        self.tab_surveillance.grid_rowconfigure(1, weight=2)  # log_frame s'étire

        # ==========================================
        # 2. MAIN CONTENT FRAME (2 colonnes) dans tab_surveillance
        # ==========================================
        self.content_frame = ctk.CTkFrame(self.tab_surveillance, fg_color="transparent")
        self.content_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        
        self.content_frame.grid_columnconfigure(0, weight=4)  # Colonne gauche (Saisie & Contrôle)
        self.content_frame.grid_columnconfigure(1, weight=5)  # Colonne droite (Tableau de bord)
        self.content_frame.grid_rowconfigure(0, weight=1)

        # --- PANNEAU GAUCHE ---
        self.left_panel = ctk.CTkFrame(self.content_frame, fg_color="transparent")
        self.left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self.left_panel.grid_rowconfigure(5, weight=1)  # Spacer à la fin
        self.left_panel.grid_columnconfigure(0, weight=1)

        # Zone Saisie Référence
        self.input_frame = ctk.CTkFrame(self.left_panel)
        self.input_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=(0, 15))
        self.input_frame.grid_columnconfigure(0, weight=1)

        self.input_label = ctk.CTkLabel(
            self.input_frame, 
            text="Ajouter une pièce à surveiller", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.input_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 0), sticky="w")
        
        self.ref_entry = ctk.CTkEntry(
            self.input_frame, 
            placeholder_text="Ex: Injecteur Bosch 0445110311"
        )
        self.ref_entry.grid(row=1, column=0, padx=15, pady=15, sticky="ew")
        
        # Liaison de la touche Entrée pour ajouter rapidement
        self.ref_entry.bind("<Return>", lambda e: self.add_reference())

        self.btn_add = ctk.CTkButton(
            self.input_frame, 
            text="Ajouter la pièce", 
            command=self.add_reference
        )
        self.btn_add.grid(row=1, column=1, padx=(0, 15), pady=15)

        # Zone Configuration ntfy
        self.ntfy_frame = ctk.CTkFrame(self.left_panel)
        self.ntfy_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=(0, 15))
        self.ntfy_frame.grid_columnconfigure(0, weight=1)
        self.ntfy_frame.grid_columnconfigure(1, weight=0)
        self.ntfy_frame.grid_columnconfigure(2, weight=0)

        self.ntfy_label = ctk.CTkLabel(
            self.ntfy_frame, 
            text="Configuration des alertes ntfy", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.ntfy_label.grid(row=0, column=0, columnspan=2, padx=15, pady=(10, 0), sticky="w")

        self.ntfy_entry = ctk.CTkEntry(
            self.ntfy_frame, 
            placeholder_text="https://ntfy.sh/mon_topic_pda"
        )
        self.ntfy_entry.grid(row=1, column=0, padx=15, pady=15, sticky="ew")

        self.btn_save_ntfy = ctk.CTkButton(
            self.ntfy_frame, 
            text="Enregistrer", 
            command=self.save_ntfy_url,
            width=100
        )
        self.btn_save_ntfy.grid(row=1, column=1, padx=(0, 8), pady=15)

        self.btn_test_ntfy = ctk.CTkButton(
            self.ntfy_frame,
            text="🔔 Tester",
            fg_color="#1565c0",
            hover_color="#0d47a1",
            width=90,
            command=self.test_ntfy
        )
        self.btn_test_ntfy.grid(row=1, column=2, padx=(0, 15), pady=15)

        # Zone Cibles de Recherche (Filtres Précis)
        self.targets_frame = ctk.CTkFrame(self.left_panel)
        self.targets_frame.grid(row=2, column=0, sticky="nsew", padx=0, pady=(0, 15))
        self.targets_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.targets_label = ctk.CTkLabel(
            self.targets_frame, 
            text="Filtrer et cibler les sites de recherche", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.targets_label.grid(row=0, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")

        # Variables Checkbox
        self.check_lbc = tk.BooleanVar(value=True)
        self.check_ebay = tk.BooleanVar(value=True)
        self.check_oscaro = tk.BooleanVar(value=True)
        self.check_mister = tk.BooleanVar(value=False)
        self.check_autodoc = tk.BooleanVar(value=False)
        self.check_ovoko = tk.BooleanVar(value=True)
        self.check_opisto = tk.BooleanVar(value=True)
        self.check_bparts = tk.BooleanVar(value=False)
        self.check_allegro = tk.BooleanVar(value=False)
        self.check_all = tk.BooleanVar(value=False)

        # Checkboxes (Grille 3x4)
        # Ligne 1 : LeBonCoin, eBay, Ovoko (Casses Europe)
        self.cb_lbc = ctk.CTkCheckBox(self.targets_frame, text="LeBonCoin", variable=self.check_lbc, command=self.on_target_checked)
        self.cb_lbc.grid(row=1, column=0, padx=10, pady=6, sticky="w")

        self.cb_ebay = ctk.CTkCheckBox(self.targets_frame, text="eBay", variable=self.check_ebay, command=self.on_target_checked)
        self.cb_ebay.grid(row=1, column=1, padx=10, pady=6, sticky="w")

        self.cb_ovoko = ctk.CTkCheckBox(self.targets_frame, text="Ovoko 🇪🇺", variable=self.check_ovoko, command=self.on_target_checked)
        self.cb_ovoko.grid(row=1, column=2, padx=10, pady=6, sticky="w")

        # Ligne 2 : Oscaro, Mister-Auto, Auto-Doc
        self.cb_oscaro = ctk.CTkCheckBox(self.targets_frame, text="Oscaro", variable=self.check_oscaro, command=self.on_target_checked)
        self.cb_oscaro.grid(row=2, column=0, padx=10, pady=6, sticky="w")

        self.cb_mister = ctk.CTkCheckBox(self.targets_frame, text="Mister-Auto", variable=self.check_mister, command=self.on_target_checked)
        self.cb_mister.grid(row=2, column=1, padx=10, pady=6, sticky="w")

        self.cb_autodoc = ctk.CTkCheckBox(self.targets_frame, text="Auto-Doc", variable=self.check_autodoc, command=self.on_target_checked)
        self.cb_autodoc.grid(row=2, column=2, padx=10, pady=6, sticky="w")

        # Ligne 3 : Opisto (Casses France), B-Parts (Europe), Allegro (Pologne)
        self.cb_opisto = ctk.CTkCheckBox(self.targets_frame, text="Opisto 🇫🇷", variable=self.check_opisto, command=self.on_target_checked)
        self.cb_opisto.grid(row=3, column=0, padx=10, pady=6, sticky="w")

        self.cb_bparts = ctk.CTkCheckBox(self.targets_frame, text="B-Parts 🇪🇺", variable=self.check_bparts, command=self.on_target_checked)
        self.cb_bparts.grid(row=3, column=1, padx=10, pady=6, sticky="w")

        self.cb_allegro = ctk.CTkCheckBox(self.targets_frame, text="Allegro 🇵🇱", variable=self.check_allegro, command=self.on_target_checked)
        self.cb_allegro.grid(row=3, column=2, padx=10, pady=6, sticky="w")

        # Ligne 4 : Tout le Web (sur 3 colonnes)
        self.cb_all = ctk.CTkCheckBox(self.targets_frame, text="Tout le Web 🌐", variable=self.check_all, command=self.on_all_web_checked)
        self.cb_all.grid(row=4, column=0, columnspan=3, padx=10, pady=(10, 6), sticky="w")

        # Zone Filtres de résultats
        self.filters_frame = ctk.CTkFrame(self.left_panel)
        self.filters_frame.grid(row=3, column=0, sticky="nsew", padx=0, pady=(0, 15))
        self.filters_frame.grid_columnconfigure(0, weight=1)
        self.filters_frame.grid_columnconfigure(1, weight=1)
        self.filters_frame.grid_columnconfigure(2, weight=1)

        self.filters_label = ctk.CTkLabel(
            self.filters_frame,
            text="Filtres de résultats",
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.filters_label.grid(row=0, column=0, columnspan=3, padx=15, pady=(10, 5), sticky="w")

        # Prix min / max
        price_lbl = ctk.CTkLabel(self.filters_frame, text="Prix :", font=ctk.CTkFont(size=12))
        price_lbl.grid(row=1, column=0, padx=(15, 5), pady=6, sticky="w")

        self.price_min_entry = ctk.CTkEntry(self.filters_frame, placeholder_text="Min €", width=80)
        self.price_min_entry.grid(row=1, column=1, padx=5, pady=6, sticky="ew")
        self.price_min_entry.bind("<FocusOut>", lambda e: self.save_filters_ui())
        self.price_min_entry.bind("<Return>", lambda e: self.save_filters_ui())

        self.price_max_entry = ctk.CTkEntry(self.filters_frame, placeholder_text="Max €", width=80)
        self.price_max_entry.grid(row=1, column=2, padx=(5, 15), pady=6, sticky="ew")
        self.price_max_entry.bind("<FocusOut>", lambda e: self.save_filters_ui())
        self.price_max_entry.bind("<Return>", lambda e: self.save_filters_ui())

        # Filtre stock
        self.check_stock_only = tk.BooleanVar(value=False)
        self.cb_stock_only = ctk.CTkCheckBox(
            self.filters_frame,
            text="Exclure articles hors stock",
            variable=self.check_stock_only,
            command=self.save_filters_ui
        )
        self.cb_stock_only.grid(row=2, column=0, columnspan=3, padx=15, pady=(4, 6), sticky="w")

        # Filtres par pays (aucun coché = tous acceptés)
        country_note = ctk.CTkLabel(
            self.filters_frame,
            text="Pays acceptés (aucun coché = tous) :",
            font=ctk.CTkFont(size=11)
        )
        country_note.grid(row=3, column=0, columnspan=3, padx=15, pady=(6, 2), sticky="w")

        self.check_cf_france    = tk.BooleanVar(value=False)
        self.check_cf_allemagne = tk.BooleanVar(value=False)
        self.check_cf_pologne   = tk.BooleanVar(value=False)
        self.check_cf_lituanie  = tk.BooleanVar(value=False)
        self.check_cf_uk        = tk.BooleanVar(value=False)
        self.check_cf_italie    = tk.BooleanVar(value=False)
        self.check_cf_espagne   = tk.BooleanVar(value=False)
        self.check_cf_belgique  = tk.BooleanVar(value=False)
        self.check_cf_intl      = tk.BooleanVar(value=False)

        country_filters = [
            ("🇫🇷 France",     self.check_cf_france,    4, 0),
            ("🇩🇪 Allemagne",  self.check_cf_allemagne, 4, 1),
            ("🇵🇱 Pologne",    self.check_cf_pologne,   4, 2),
            ("🇱🇹 Lituanie",   self.check_cf_lituanie,  5, 0),
            ("🇬🇧 Royaume-Uni",self.check_cf_uk,        5, 1),
            ("🇮🇹 Italie",     self.check_cf_italie,    5, 2),
            ("🇪🇸 Espagne",    self.check_cf_espagne,   6, 0),
            ("🇧🇪 Belgique",   self.check_cf_belgique,  6, 1),
            ("🌐 Intl",        self.check_cf_intl,      6, 2),
        ]
        for text, var, r, c in country_filters:
            cb = ctk.CTkCheckBox(
                self.filters_frame, text=text, variable=var,
                command=self.save_filters_ui, font=ctk.CTkFont(size=11)
            )
            cb.grid(row=r, column=c, padx=10, pady=3, sticky="w")

        # Zone de Contrôle de Surveillance
        self.control_frame = ctk.CTkFrame(self.left_panel)
        self.control_frame.grid(row=4, column=0, sticky="nsew", padx=0, pady=0)
        self.control_frame.grid_columnconfigure(0, weight=1)

        self.control_label = ctk.CTkLabel(
            self.control_frame, 
            text="Contrôle général", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.control_label.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        self.btn_toggle = ctk.CTkButton(
            self.control_frame, 
            text="▶  Démarrer la Surveillance", 
            fg_color="#2e7d32", 
            hover_color="#1b5e20",
            font=ctk.CTkFont(size=16, weight="bold"),
            height=44,
            command=self.toggle_surveillance
        )
        self.btn_toggle.grid(row=1, column=0, padx=20, pady=(15, 20), sticky="ew")

        # --- PANNEAU DROITE (TABLEAU DE BORD) ---
        self.right_panel = ctk.CTkFrame(self.content_frame)
        self.right_panel.grid(row=0, column=1, sticky="nsew", padx=0)
        
        self.right_panel.grid_rowconfigure(1, weight=1)
        self.right_panel.grid_columnconfigure(0, weight=1)

        self.right_label = ctk.CTkLabel(
            self.right_panel, 
            text="Pièces actuellement surveillées", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.right_label.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        # Scrollable frame pour la liste des pièces
        self.scroll_frame = ctk.CTkScrollableFrame(self.right_panel, fg_color="transparent")
        self.scroll_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)

        # ==========================================
        # 3. LOG CONSOLE FRAME dans tab_surveillance
        # ==========================================
        self.log_frame = ctk.CTkFrame(self.tab_surveillance)
        self.log_frame.grid(row=1, column=0, sticky="nsew", padx=0, pady=(10, 0))
        self.log_frame.grid_rowconfigure(1, weight=1)
        self.log_frame.grid_columnconfigure(0, weight=1)

        self.log_label = ctk.CTkLabel(
            self.log_frame, 
            text="Console de logs (IA Ollama & Scanner)", 
            font=ctk.CTkFont(size=13, weight="bold")
        )
        self.log_label.grid(row=0, column=0, padx=15, pady=(10, 0), sticky="w")

        self.console = ctk.CTkTextbox(
            self.log_frame, 
            height=180, 
            font=ctk.CTkFont(family="Courier", size=12)
        )
        self.console.grid(row=1, column=0, sticky="nsew", padx=10, pady=10)
        self.console.configure(state="disabled")

        # Message de bienvenue
        self.log_to_console("--- Initialisation de ScanWebPDA complétée ---")
        self.log_to_console("Ajoutez des références de pièces et lancez la surveillance pour commencer.")


        # --- ONGLET 2 : PIÈCES TROUVÉES ---
        self.tab_trouvees.grid_columnconfigure(0, weight=1)
        self.tab_trouvees.grid_rowconfigure(1, weight=1)  # La liste s'étire

        self.trouvees_header = ctk.CTkFrame(self.tab_trouvees, fg_color="transparent")
        self.trouvees_header.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        
        self.trouvees_title = ctk.CTkLabel(
            self.trouvees_header, 
            text="Articles validés comme pièces mécaniques réelles par l'IA", 
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.trouvees_title.pack(side="left", padx=5)

        self.btn_refresh_trouvees = ctk.CTkButton(
            self.trouvees_header, 
            text="Actualiser la liste", 
            command=self.load_valid_items_ui,
            fg_color="#3a3a3a",
            hover_color="#5a5a5a",
            width=140
        )
        self.btn_refresh_trouvees.pack(side="right", padx=5)

        # Scrollable frame pour les fiches articles
        self.scroll_trouvees = ctk.CTkScrollableFrame(self.tab_trouvees, fg_color="transparent")
        self.scroll_trouvees.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)


        # ==========================================
        # 4. STATUS BAR FRAME (Placée en bas de la fenêtre)
        # ==========================================
        self.footer_frame = ctk.CTkFrame(self, height=35, corner_radius=0)
        self.footer_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.status_info_label = ctk.CTkLabel(
            self.footer_frame, 
            text="Statut système : Prêt",
            font=ctk.CTkFont(size=11)
        )
        self.status_info_label.pack(side="left", padx=15, pady=5)

        # Pastille et label pour Ollama
        self.status_frame = ctk.CTkFrame(self.footer_frame, fg_color="transparent")
        self.status_frame.pack(side="right", padx=15, pady=5)

        # Déterminer la couleur de fond dynamique pour le canvas
        self.bg_color_hex = "#2b2b2b"
        try:
            bg_color = self.status_frame.cget("fg_color")
            if isinstance(bg_color, (list, tuple)):
                self.bg_color_hex = bg_color[1] if ctk.get_appearance_mode() == "Dark" else bg_color[0]
            elif isinstance(bg_color, str) and bg_color != "transparent":
                self.bg_color_hex = bg_color
        except Exception:
            pass

        self.status_canvas = tk.Canvas(
            self.status_frame, 
            width=16, 
            height=16, 
            bg=self.bg_color_hex, 
            highlightthickness=0
        )
        self.status_canvas.pack(side="left", padx=(0, 5))
        # Pastille initialement rouge (déconnectée)
        self.status_circle = self.status_canvas.create_oval(2, 2, 14, 14, fill="red", outline="")

        self.ollama_status_label = ctk.CTkLabel(
            self.status_frame, 
            text="Ollama hors-ligne", 
            font=ctk.CTkFont(size=11, weight="bold")
        )
        self.ollama_status_label.pack(side="left")

    # ==========================================
    # LOGIQUE DE L'APPLICATION
    # ==========================================

    def log_to_console(self, message):
        """Ajoute un message dans la console de logs (thread-safe).
        Tronque automatiquement à 500 lignes pour éviter une croissance infinie en mémoire.
        """
        self.console.configure(state="normal")
        self.console.insert("end", message + "\n")
        # Rotation : on garde seulement les 500 dernières lignes
        line_count = int(self.console.index("end-1c").split(".")[0])
        if line_count > 500:
            self.console.delete("1.0", f"{line_count - 500}.0")
        self.console.see("end")
        self.console.configure(state="disabled")

    def log_from_thread(self, message):
        """Callback utilisé par le thread d'arrière-plan pour loguer de façon sécurisée."""
        self.after(0, lambda: self.log_to_console(message))

    def _bind_mousewheel_to_children(self, widget, scroll_frame):
        """Associe récursivement le défilement de la molette de la souris d'un widget et de ses enfants au cadre de défilement."""
        # Windows & macOS
        widget.bind("<MouseWheel>", lambda event: scroll_frame._on_mousewheel(event), add="+")
        # Linux
        widget.bind("<Button-4>", lambda event: scroll_frame._on_mousewheel(event), add="+")
        widget.bind("<Button-5>", lambda event: scroll_frame._on_mousewheel(event), add="+")
        
        for child in widget.winfo_children():
            self._bind_mousewheel_to_children(child, scroll_frame)

    def on_window_resize(self, event):
        """Ajuste dynamiquement l'interface lorsque la fenêtre est redimensionnée (mode responsive)."""
        if event.widget == self:
            width = event.width
            if width < 960:
                # Masquer le sous-titre pour gagner de la place
                self.subtitle_label.pack_forget()
                # Raccourcir le texte du bouton du header
                if main.engine.running:
                    self.header_btn_toggle.configure(text="⏹  Arrêter", width=100)
                else:
                    self.header_btn_toggle.configure(text="▶  Démarrer", width=100)
                self.btn_check_update.configure(text="🔄 MAJ", width=80)
            else:
                # Réafficher le sous-titre
                self.subtitle_label.pack_forget()
                self.subtitle_label.pack(side="left", padx=10, pady=15)
                # Restaurer les textes complets
                if main.engine.running:
                    self.header_btn_toggle.configure(text="⏹  Arrêter la Surveillance", width=230)
                else:
                    self.header_btn_toggle.configure(text="▶  Démarrer la Surveillance", width=230)
                self.btn_check_update.configure(text="🔄 Mise à jour", width=140)

    def load_config_ui(self):
        """Charge la configuration initiale de ntfy et des cibles de recherche."""
        try:
            if os.path.exists(main.CONFIG_PATH):
                with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)
                    # Chargement ntfy
                    self.ntfy_entry.delete(0, "end")
                    self.ntfy_entry.insert(0, config.get("ntfy_url", ""))
                    
                    # Chargement des cibles de recherche
                    targets = config.get("search_targets", {})
                    if targets:
                        self.check_lbc.set(targets.get("leboncoin.fr", True))
                        self.check_ebay.set(targets.get("ebay.fr", True))
                        self.check_oscaro.set(targets.get("oscaro.com", True))
                        self.check_mister.set(targets.get("mister-auto.com", False))
                        self.check_autodoc.set(targets.get("auto-doc.fr", False))
                        self.check_ovoko.set(targets.get("ovoko.fr", True))
                        self.check_opisto.set(targets.get("opisto.fr", True))
                        self.check_bparts.set(targets.get("b-parts.com", False))
                        self.check_allegro.set(targets.get("allegro.pl", False))
                        self.check_all.set(targets.get("all_web", False))
                        
                        # Met à jour l'état visuel (activé/désactivé)
                        self.on_all_web_checked()

            # Chargement des filtres de résultats
            self.load_filters_ui()
        except Exception as e:
            self.log_to_console(f"Erreur de chargement de la config: {e}")

    def on_all_web_checked(self):
        """Gère l'activation globale de 'Tout le Web' en désactivant les filtres individuels."""
        state = self.check_all.get()
        if state:
            self.cb_lbc.configure(state="disabled")
            self.cb_ebay.configure(state="disabled")
            self.cb_ovoko.configure(state="disabled")
            self.cb_oscaro.configure(state="disabled")
            self.cb_mister.configure(state="disabled")
            self.cb_autodoc.configure(state="disabled")
            self.cb_opisto.configure(state="disabled")
            self.cb_bparts.configure(state="disabled")
            self.cb_allegro.configure(state="disabled")
        else:
            self.cb_lbc.configure(state="normal")
            self.cb_ebay.configure(state="normal")
            self.cb_ovoko.configure(state="normal")
            self.cb_oscaro.configure(state="normal")
            self.cb_mister.configure(state="normal")
            self.cb_autodoc.configure(state="normal")
            self.cb_opisto.configure(state="normal")
            self.cb_bparts.configure(state="normal")
            self.cb_allegro.configure(state="normal")
        self.save_targets_ui()

    def on_target_checked(self):
        """Gère le changement d'état d'un site de recherche individuel."""
        self.save_targets_ui()

    def save_targets_ui(self):
        """Enregistre l'ensemble des cases cochées dans config.json."""
        try:
            config = {"references": [], "ntfy_url": "", "search_targets": {}}
            if os.path.exists(main.CONFIG_PATH):
                with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

            config["search_targets"] = {
                "leboncoin.fr": self.check_lbc.get(),
                "ebay.fr": self.check_ebay.get(),
                "oscaro.com": self.check_oscaro.get(),
                "mister-auto.com": self.check_mister.get(),
                "auto-doc.fr": self.check_autodoc.get(),
                "ovoko.fr": self.check_ovoko.get(),
                "opisto.fr": self.check_opisto.get(),
                "b-parts.com": self.check_bparts.get(),
                "allegro.pl": self.check_allegro.get(),
                "all_web": self.check_all.get()
            }

            with open(main.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            self.log_to_console(f"Erreur de sauvegarde des cibles: {e}")

    def load_monitored_pieces(self):
        """Lit config.json et met à jour l'affichage de la CTkScrollableFrame."""
        # On vide la frame d'abord
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        try:
            if not os.path.exists(main.CONFIG_PATH):
                return
                
            with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                references = config.get("references", [])

            if not references:
                no_ref_label = ctk.CTkLabel(
                    self.scroll_frame, 
                    text="Aucune pièce sous surveillance active.", 
                    font=ctk.CTkFont(slant="italic")
                )
                no_ref_label.pack(pady=20)
                return

            for i, ref in enumerate(references):
                # Cadre ligne
                row_frame = ctk.CTkFrame(self.scroll_frame)
                row_frame.pack(fill="x", padx=5, pady=4)
                
                # Label texte
                lbl = ctk.CTkLabel(
                    row_frame, 
                    text=ref, 
                    font=ctk.CTkFont(size=13, weight="normal"), 
                    anchor="w"
                )
                lbl.pack(side="left", padx=15, pady=8, fill="x", expand=True)

                # Bouton Supprimer
                btn_del = ctk.CTkButton(
                    row_frame, 
                    text="Supprimer", 
                    fg_color="#d32f2f", 
                    hover_color="#b71c1c",
                    width=80,
                    height=26,
                    command=lambda r=ref: self.delete_reference(r)
                )
                btn_del.pack(side="right", padx=10, pady=5)
                
            # Liaison de la molette souris sur tous les éléments chargés
            self._bind_mousewheel_to_children(self.scroll_frame, self.scroll_frame)
            
        except Exception as e:
            self.log_to_console(f"Erreur de lecture de la liste des pièces: {e}")

    def add_reference(self, event=None):
        """Ajoute une nouvelle référence dans config.json."""
        ref = self.ref_entry.get().strip()
        if not ref:
            return

        try:
            config = {"references": [], "ntfy_url": ""}
            if os.path.exists(main.CONFIG_PATH):
                with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

            if ref in config["references"]:
                self.log_to_console(f"Info: '{ref}' est déjà sous surveillance.")
                self.ref_entry.delete(0, "end")
                return

            config["references"].append(ref)
            
            with open(main.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.ref_entry.delete(0, "end")
            self.load_monitored_pieces()
            self.log_to_console(f"Référence ajoutée : '{ref}'")

        except Exception as e:
            self.log_to_console(f"Erreur lors de l'ajout de la pièce: {e}")

    def delete_reference(self, ref):
        """Supprime une référence existante dans config.json."""
        try:
            if not os.path.exists(main.CONFIG_PATH):
                return

            with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)

            if ref in config["references"]:
                config["references"].remove(ref)

                with open(main.CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)

                self.load_monitored_pieces()
                self.log_to_console(f"Référence supprimée : '{ref}'")

        except Exception as e:
            self.log_to_console(f"Erreur lors de la suppression de la pièce: {e}")

    def save_ntfy_url(self):
        """Enregistre le lien ntfy dans la configuration."""
        url = self.ntfy_entry.get().strip()
        try:
            config = {"references": [], "ntfy_url": ""}
            if os.path.exists(main.CONFIG_PATH):
                with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

            config["ntfy_url"] = url
            
            with open(main.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.log_to_console(f"Lien ntfy configuré avec succès : {url}")
            
        except Exception as e:
            self.log_to_console(f"Erreur d'enregistrement ntfy: {e}")

    def load_filters_ui(self):
        """Charge les filtres de résultats depuis config.json."""
        try:
            if not os.path.exists(main.CONFIG_PATH):
                return
            with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
            f = config.get("result_filters", {})
            if not f:
                return
            # Prix
            price_min = f.get("price_min") or ""
            price_max = f.get("price_max") or ""
            self.price_min_entry.delete(0, "end")
            if price_min:
                self.price_min_entry.insert(0, str(int(price_min)))
            self.price_max_entry.delete(0, "end")
            if price_max:
                self.price_max_entry.insert(0, str(int(price_max)))
            # Stock
            self.check_stock_only.set(f.get("stock_only", False))
            # Pays
            ac = f.get("allowed_countries", [])
            self.check_cf_france.set("France" in " ".join(ac))
            self.check_cf_allemagne.set("Allemagne" in " ".join(ac))
            self.check_cf_pologne.set("Pologne" in " ".join(ac))
            self.check_cf_lituanie.set("Lituanie" in " ".join(ac))
            self.check_cf_uk.set("Royaume" in " ".join(ac))
            self.check_cf_italie.set("Italie" in " ".join(ac))
            self.check_cf_espagne.set("Espagne" in " ".join(ac))
            self.check_cf_belgique.set("Belgique" in " ".join(ac))
            self.check_cf_intl.set("Intl" in " ".join(ac) or "International" in " ".join(ac))
        except Exception as e:
            self.log_to_console(f"Erreur chargement filtres: {e}")

    def save_filters_ui(self):
        """Sauvegarde les filtres de résultats dans config.json."""
        try:
            # Lecture prix
            def parse_price(val):
                try:
                    return float(val.strip()) if val.strip() else 0
                except ValueError:
                    return 0

            price_min = parse_price(self.price_min_entry.get())
            price_max = parse_price(self.price_max_entry.get())

            # Pays autorisés
            allowed = []
            if self.check_cf_france.get():    allowed.append("France")
            if self.check_cf_allemagne.get(): allowed.append("Allemagne")
            if self.check_cf_pologne.get():   allowed.append("Pologne")
            if self.check_cf_lituanie.get():  allowed.append("Lituanie")
            if self.check_cf_uk.get():        allowed.append("Royaume-Uni")
            if self.check_cf_italie.get():    allowed.append("Italie")
            if self.check_cf_espagne.get():   allowed.append("Espagne")
            if self.check_cf_belgique.get():  allowed.append("Belgique")
            if self.check_cf_intl.get():      allowed.append("International")

            config = {"references": [], "ntfy_url": ""}
            if os.path.exists(main.CONFIG_PATH):
                with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                    config = json.load(f)

            config["result_filters"] = {
                "price_min": price_min,
                "price_max": price_max,
                "stock_only": self.check_stock_only.get(),
                "allowed_countries": allowed
            }

            with open(main.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=4, ensure_ascii=False)

            self.log_to_console("Filtres de résultats sauvegardés.")
        except Exception as e:
            self.log_to_console(f"Erreur sauvegarde filtres: {e}")

    def test_ntfy(self):
        """Lance le diagnostic ntfy dans un thread de fond et affiche les résultats dans la console."""
        url = self.ntfy_entry.get().strip()
        if not url:
            self.log_to_console("⚠️ Veuillez saisir une URL ntfy avant de tester.")
            self.log_to_console("   Exemple : https://ntfy.sh/ScanWebPDA")
            return

        # Désactiver le bouton pendant le test
        self.btn_test_ntfy.configure(state="disabled", text="Test en cours...")

        def _run_test():
            import notifier
            notifier.test_ntfy_diagnostic(url, self.log_from_thread)
            # Réactiver le bouton une fois terminé
            self.after(0, lambda: self.btn_test_ntfy.configure(state="normal", text="🔔 Tester"))

        threading.Thread(target=_run_test, daemon=True).start()

    def toggle_surveillance(self):
        """Bouton pour lancer/arrêter la surveillance en tâche de fond."""
        if not main.engine.running:
            # Lancer
            main.engine.start(self.log_from_thread)
            # Mise à jour du bouton dans le panneau de gauche
            self.btn_toggle.configure(
                text="⏹  Arrêter la Surveillance", 
                fg_color="#d32f2f", 
                hover_color="#b71c1c"
            )
            # Mise à jour du bouton dans le header (s'adapte à la largeur de l'écran)
            text_toggle = "⏹  Arrêter" if self.winfo_width() < 960 else "⏹  Arrêter la Surveillance"
            width_toggle = 100 if self.winfo_width() < 960 else 230
            self.header_btn_toggle.configure(
                text=text_toggle,
                width=width_toggle,
                fg_color="#d32f2f",
                hover_color="#b71c1c"
            )
            self.status_info_label.configure(text="Statut système : Surveillance en cours...")
        else:
            # Arrêter
            main.engine.stop()
            # Mise à jour du bouton dans le panneau de gauche
            self.btn_toggle.configure(
                text="▶  Démarrer la Surveillance", 
                fg_color="#2e7d32", 
                hover_color="#1b5e20"
            )
            # Mise à jour du bouton dans le header (s'adapte à la largeur de l'écran)
            text_toggle = "▶  Démarrer" if self.winfo_width() < 960 else "▶  Démarrer la Surveillance"
            width_toggle = 100 if self.winfo_width() < 960 else 230
            self.header_btn_toggle.configure(
                text=text_toggle,
                width=width_toggle,
                fg_color="#2e7d32",
                hover_color="#1b5e20"
            )
            self.status_info_label.configure(text="Statut système : Arrêté")

    # ==========================================
    # MULTI-THREADING STATUT OLLAMA
    # ==========================================

    def start_ollama_check_thread(self):
        """Lance le thread de vérification régulier de l'API Ollama."""
        t = threading.Thread(target=self._ollama_check_loop, daemon=True)
        t.start()

    def _ollama_check_loop(self):
        """Boucle s'exécutant dans un thread secondaire."""
        while self.check_thread_running:
            online = ai_filter.check_ollama_status()

            # Mise à jour graphique sécurisée (la fenêtre peut avoir été fermée)
            try:
                if self.winfo_exists():
                    self.after(0, self.update_ollama_ui_status, online)
            except RuntimeError:
                break  # Fenêtre détruite, on arrête proprement

            # On vérifie toutes les 6 secondes
            for _ in range(6):
                if not self.check_thread_running:
                    break
                time.sleep(1)

    def update_ollama_ui_status(self, online):
        """Met à jour les couleurs de l'indicateur graphique d'Ollama."""
        self.ollama_online = online
        if online:
            self.status_canvas.itemconfig(self.status_circle, fill="green")
            self.ollama_status_label.configure(text="Ollama opérationnel", text_color="#4caf50")
        else:
            self.status_canvas.itemconfig(self.status_circle, fill="red")
            self.ollama_status_label.configure(text="Ollama hors-ligne", text_color="#f44336")

    def download_and_set_image(self, url, label_widget):
        """Télécharge de façon asynchrone l'image d'un article et l'applique au widget.
        Limite la lecture à 5 Mo pour se protéger contre des images anormalement grandes.
        """
        MAX_IMAGE_BYTES = 5_000_000  # 5 Mo
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            response = requests.get(url, headers=headers, timeout=5, stream=True)
            if response.status_code == 200:
                image_data = response.raw.read(MAX_IMAGE_BYTES, decode_content=True)
                response.close()
                pil_image = Image.open(io.BytesIO(image_data))

                # Formatage en carré 80x80 propre (crop central)
                pil_image = pil_image.convert("RGBA")
                pil_image.thumbnail((120, 120))

                w, h = pil_image.size
                left = (w - 80) / 2
                top = (h - 80) / 2
                right = (w + 80) / 2
                bottom = (h + 80) / 2
                cropped = pil_image.crop((max(0, left), max(0, top), min(w, right), min(h, bottom)))
                cropped = cropped.resize((80, 80), Image.Resampling.LANCZOS)

                # Créer le CTkImage
                ctk_img = ctk.CTkImage(light_image=cropped, dark_image=cropped, size=(80, 80))

                # Mise à jour thread-safe : vérifier que le widget existe encore
                def _apply_image(widget=label_widget, img=ctk_img):
                    try:
                        if widget.winfo_exists():
                            widget.configure(image=img)
                    except Exception:
                        pass  # Widget détruit entre-temps (refresh liste)

                try:
                    if self.winfo_exists():
                        self.after(0, _apply_image)
                except RuntimeError:
                    pass  # Fenêtre fermée
        except Exception:
            pass  # Timeout ou image invalide, on garde l'engrenage par défaut

    def load_valid_items_ui(self):
        """Récupère et dessine sous forme de fiches élégantes toutes les pièces validées par l'IA."""
        # On vide d'abord la zone de défilement
        for widget in self.scroll_trouvees.winfo_children():
            widget.destroy()

        items = database.get_valid_items()
        
        if not items:
            no_items_label = ctk.CTkLabel(
                self.scroll_trouvees, 
                text="Aucune pièce validée n'a encore été trouvée.\nLancez la surveillance en arrière-plan et laissez l'IA classer !", 
                font=ctk.CTkFont(size=13, slant="italic")
            )
            no_items_label.pack(pady=40)
            self.trouvees_title.configure(text="Articles validés comme pièces mécaniques réelles par l'IA")
            return

        self.trouvees_title.configure(text=f"Articles validés comme pièces mécaniques réelles par l'IA ({len(items)})")

        for item in items:
            # Card/Conteneur principal pour chaque article
            card = ctk.CTkFrame(self.scroll_trouvees, height=110)
            card.pack(fill="x", padx=5, pady=8)
            card.grid_columnconfigure(1, weight=1)  # Zone texte extensible
            
            # 1. Vignette Image (Gauche) - Place l'engrenage par défaut
            img_label = ctk.CTkLabel(card, image=self.placeholder_image, text="")
            img_label.grid(row=0, column=0, padx=10, pady=10, rowspan=3)
            
            # Lancement asynchrone du chargement d'image
            img_url = item.get("image_url")
            if img_url:
                threading.Thread(
                    target=lambda u=img_url, lbl=img_label: self.download_and_set_image(u, lbl),
                    daemon=True
                ).start()
                
            # 2. Texte de l'annonce (Milieu)
            title = item.get("title", "N/D")
            display_title = title[:80] + "..." if len(title) > 83 else title
            
            # Provenance du pays et drapeau
            country = item.get("country") or "🌐 International"
            country_flag = country.split(" ")[0] if " " in country else "🌐"
            
            title_lbl = ctk.CTkLabel(
                card, 
                text=f"{country_flag}  {display_title}", 
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
                justify="left",
                wraplength=520
            )
            title_lbl.grid(row=0, column=1, padx=(10, 15), pady=(8, 2), sticky="w")
            
            # Si le traducteur local a produit une traduction en français
            translated = item.get("translated_title")
            row_idx = 1
            if translated:
                trans_lbl = ctk.CTkLabel(
                    card, 
                    text=f"📝 Traduction : {translated}", 
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color="#ffb74d", # Belle couleur or/orange en mode sombre
                    anchor="w",
                    justify="left",
                    wraplength=520
                )
                trans_lbl.grid(row=row_idx, column=1, padx=(10, 15), pady=(0, 2), sticky="w")
                row_idx += 1
            
            ref = item.get("reference", "N/D")
            price = item.get("price", "N/D")
            site = item.get("source_domain") or "Web"
            date_found = item.get("found_date", "")
            
            # Formatage propre de la date et heure
            date_str = date_found
            try:
                parts = date_found.split(" ")
                date_parts = parts[0].split("-")
                time_parts = parts[1].split(":")
                date_str = f"le {date_parts[2]}/{date_parts[1]} à {time_parts[0]}:{time_parts[1]}"
            except Exception:
                pass

            meta_text = f"Recherche : {ref}   |   Prix : {price}   |   Pays : {country}   |   Site : {site}   |   Trouvé {date_str}"
            meta_lbl = ctk.CTkLabel(
                card, 
                text=meta_text, 
                font=ctk.CTkFont(size=11, slant="italic"),
                text_color="#aaaaaa",
                anchor="w",
                justify="left"
            )
            meta_lbl.grid(row=row_idx, column=1, padx=(10, 15), pady=(0, 8), sticky="w")

            # 3. Actions (Droite)
            btn_frame = ctk.CTkFrame(card, fg_color="transparent")
            btn_frame.grid(row=0, column=2, rowspan=3, padx=15, pady=10, sticky="e")
            
            url = item.get("url", "")
            btn_open = ctk.CTkButton(
                btn_frame, 
                text="Voir l'annonce", 
                fg_color="#1b5e20" if url else "#424242", 
                hover_color="#2e7d32",
                width=110,
                height=26,
                command=lambda u=url: webbrowser.open(u) if u else None
            )
            btn_open.pack(side="top", pady=4)
            
            item_id = item.get("id")
            btn_del = ctk.CTkButton(
                btn_frame, 
                text="Supprimer", 
                fg_color="#b71c1c", 
                hover_color="#d32f2f",
                width=110,
                height=26,
                command=lambda i_id=item_id: self.delete_valid_item(i_id)
            )
            btn_del.pack(side="top", pady=4)

        # Liaison de la molette souris sur tous les éléments chargés
        self._bind_mousewheel_to_children(self.scroll_trouvees, self.scroll_trouvees)

    def delete_valid_item(self, item_id):
        """Supprime une pièce validée de la BDD et rafraîchit l'onglet."""
        if database.delete_item(item_id):
            self.log_to_console(f"Article [ID {item_id}] retiré des pièces trouvées.")
            self.load_valid_items_ui()

    # ==========================================
    # SYSTÈME DE MISE À JOUR GITHUB
    # ==========================================

    def check_updates_silent(self, silent: bool = True):
        """Vérifie les mises à jour en arrière-plan.
        Si silent=True, n'affiche rien si l'app est à jour.
        Si silent=False (bouton manuel), affiche un message dans tous les cas.
        """
        self.btn_check_update.configure(state="disabled", text="⏳ Vérification...")

        def _on_result(release):
            self.btn_check_update.configure(state="normal", text="🔄 Mise à jour")
            if release:
                # Une mise à jour est disponible → afficher la popup
                self.after(0, lambda: self.show_update_dialog(release))
            elif not silent:
                # Pas de mise à jour, mais l'utilisateur a cliqué manuellement
                self.after(0, lambda: self._show_up_to_date_popup())

        # Lire le token optionnel depuis config.json
        token = ""
        try:
            with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            token = cfg.get("github", {}).get("github_token", "")
        except Exception:
            pass

        updater.check_for_updates_async(_on_result, token=token)

    def _show_up_to_date_popup(self):
        """Popup simple indiquant que l'application est à jour."""
        popup = ctk.CTkToplevel(self)
        popup.title("Mises à jour")
        popup.geometry("380x160")
        popup.resizable(False, False)
        popup.grab_set()
        popup.focus_force()

        ctk.CTkLabel(
            popup,
            text="✅  ScanWebPDA est à jour",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(28, 6))
        ctk.CTkLabel(
            popup,
            text=f"Version actuelle : {VERSION}",
            font=ctk.CTkFont(size=13)
        ).pack(pady=4)
        ctk.CTkButton(
            popup, text="OK", width=100, command=popup.destroy
        ).pack(pady=14)

    def show_update_dialog(self, release: dict):
        """Affiche la popup modale de mise à jour avec changelog et barre de progression."""
        popup = ctk.CTkToplevel(self)
        popup.title("Mise à jour disponible")
        popup.geometry("520x460")
        popup.resizable(False, False)
        popup.grab_set()
        popup.focus_force()

        # ── En-tête ───────────────────────────────────────────────────────
        ctk.CTkLabel(
            popup,
            text="🚀  Nouvelle version disponible !",
            font=ctk.CTkFont(size=17, weight="bold")
        ).pack(pady=(22, 4))

        ctk.CTkLabel(
            popup,
            text=f"v{VERSION}  →  v{release['version']}",
            font=ctk.CTkFont(size=14),
            text_color="#64b5f6"
        ).pack(pady=(0, 10))

        # ── Changelog ────────────────────────────────────────────────────
        changelog_box = ctk.CTkTextbox(popup, height=160, wrap="word")
        changelog_box.pack(fill="x", padx=20, pady=(0, 12))
        body = release.get("body") or "Aucune note de version disponible."
        changelog_box.insert("end", body)
        changelog_box.configure(state="disabled")

        # ── Barre de progression (cachée au départ) ───────────────────────
        self._update_progress_var = tk.DoubleVar(value=0.0)
        self._update_status_var   = tk.StringVar(value="")

        progress_bar = ctk.CTkProgressBar(popup, variable=self._update_progress_var, width=460)
        status_lbl   = ctk.CTkLabel(popup, textvariable=self._update_status_var,
                                    font=ctk.CTkFont(size=11), text_color="#aaaaaa")

        # ── Boutons ───────────────────────────────────────────────────────
        btn_frame = ctk.CTkFrame(popup, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=8)

        btn_later = ctk.CTkButton(
            btn_frame, text="Plus tard",
            fg_color="#424242", hover_color="#616161",
            width=120, command=popup.destroy
        )
        btn_later.pack(side="left")

        def _start_update():
            btn_install.configure(state="disabled", text="Installation...")
            btn_later.configure(state="disabled")
            progress_bar.pack(fill="x", padx=20, pady=(4, 0))
            status_lbl.pack(pady=(2, 6))

            def _progress_cb(val, msg):
                self._update_progress_var.set(val)
                self._update_status_var.set(msg)

            def _worker():
                install_dir = os.path.dirname(os.path.abspath(__file__))
                token = ""
                try:
                    with open(main.CONFIG_PATH, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    token = cfg.get("github", {}).get("github_token", "")
                except Exception:
                    pass

                ok, err = updater.download_and_install(
                    release["zip_url"], install_dir, _progress_cb, token
                )
                if ok:
                    self.after(0, lambda: self._on_update_success(popup))
                else:
                    self.after(0, lambda: self._on_update_error(popup, err))

            threading.Thread(target=_worker, daemon=True).start()

        btn_install = ctk.CTkButton(
            btn_frame,
            text="⬇  Installer la mise à jour",
            fg_color="#1565c0", hover_color="#0d47a1",
            width=220, command=_start_update
        )
        btn_install.pack(side="right")

    def _on_update_success(self, popup):
        """Affiche un message de succès et propose de redémarrer."""
        popup.destroy()
        success = ctk.CTkToplevel(self)
        success.title("Mise à jour réussie")
        success.geometry("400x190")
        success.resizable(False, False)
        success.grab_set()
        success.focus_force()

        ctk.CTkLabel(
            success,
            text="✅  Mise à jour installée !",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=(28, 8))
        ctk.CTkLabel(
            success,
            text="Redémarrez l'application pour appliquer les changements.",
            font=ctk.CTkFont(size=12), wraplength=340
        ).pack(pady=4)

        btn_row = ctk.CTkFrame(success, fg_color="transparent")
        btn_row.pack(pady=16)
        ctk.CTkButton(
            btn_row, text="Redémarrer", fg_color="#1b5e20", hover_color="#2e7d32",
            command=lambda: self._restart_app(success)
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            btn_row, text="Plus tard", fg_color="#424242", hover_color="#616161",
            command=success.destroy
        ).pack(side="left", padx=8)

    def _on_update_error(self, popup, error_msg: str):
        """Affiche une popup d'erreur."""
        popup.destroy()
        err_win = ctk.CTkToplevel(self)
        err_win.title("Erreur de mise à jour")
        err_win.geometry("420x200")
        err_win.resizable(False, False)
        err_win.grab_set()
        err_win.focus_force()

        ctk.CTkLabel(
            err_win,
            text="❌  Échec de la mise à jour",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#ef5350"
        ).pack(pady=(24, 8))
        ctk.CTkLabel(
            err_win,
            text=str(error_msg)[:200],
            font=ctk.CTkFont(size=11),
            wraplength=380, text_color="#aaaaaa"
        ).pack(pady=4)
        ctk.CTkButton(
            err_win, text="OK", width=100, command=err_win.destroy
        ).pack(pady=14)

    def _restart_app(self, popup):
        """Redémarre l'application."""
        popup.destroy()
        self.on_closing()
        
        import subprocess
        try:
            if getattr(sys, 'frozen', False):
                # Version compilee PyInstaller (.exe)
                subprocess.Popen([sys.executable])
            else:
                # Script Python de developpement
                subprocess.Popen([sys.executable] + sys.argv)
        except Exception as e:
            # Au cas ou Popen echouerait exceptionnellement
            pass
        sys.exit(0)

    # ==========================================
    # FERMETURE PROPRE
    # ==========================================

    def on_closing(self):
        """Ferme proprement les threads lors de la fermeture de la fenêtre."""
        self.check_thread_running = False
        if main.engine.running:
            main.engine.stop()
        self.destroy()

if __name__ == "__main__":
    app = ScanWebApp()
    app.mainloop()