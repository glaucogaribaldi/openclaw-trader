import sys
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.enum.shapes import MSO_SHAPE

def create_presentation():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)
    
    # Theme colors
    RED_FELTRINELLI = RGBColor(214, 46, 0)
    DARK_TEXT = RGBColor(33, 37, 41)
    LIGHT_BG = RGBColor(248, 249, 250)
    WHITE = RGBColor(255, 255, 255)
    MUTED_TEXT = RGBColor(108, 117, 125)
    GREEN_SUCCESS = RGBColor(40, 167, 69)
    ORANGE_KPI = RGBColor(253, 126, 20)
    
    blank_layout = prs.slide_layouts[6]
    
    # Helper to add a generic slide with a colored top-bar or clean background
    def add_slide(title_text):
        slide = prs.slides.add_slide(blank_layout)
        
        # Add background color
        background = slide.background
        fill = background.fill
        fill.solid()
        fill.fore_color.rgb = LIGHT_BG
        
        # Add top thin red bar
        top_bar = slide.shapes.add_shape(
            MSO_SHAPE.RECTANGLE,
            Inches(0), Inches(0), Inches(13.33), Inches(0.15)
        )
        top_bar.fill.solid()
        top_bar.fill.fore_color.rgb = RED_FELTRINELLI
        top_bar.line.fill.background()
        
        # Add Title
        title_box = slide.shapes.add_textbox(Inches(0.75), Inches(0.4), Inches(11.83), Inches(0.8))
        tf = title_box.text_frame
        tf.word_wrap = True
        tf.margin_top = Inches(0)
        tf.margin_bottom = Inches(0)
        tf.margin_left = Inches(0)
        tf.margin_right = Inches(0)
        
        p = tf.paragraphs[0]
        p.text = title_text
        p.font.name = 'Arial'
        p.font.size = Pt(28)
        p.font.bold = True
        p.font.color.rgb = DARK_TEXT
        
        return slide

    # SLIDE 1: Title Slide (Dark Theme)
    slide1 = prs.slides.add_slide(blank_layout)
    fill1 = slide1.background.fill
    fill1.solid()
    fill1.fore_color.rgb = DARK_TEXT
    
    # Left accent block
    left_block = slide1.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(0), Inches(0), Inches(0.4), Inches(7.5)
    )
    left_block.fill.solid()
    left_block.fill.fore_color.rgb = RED_FELTRINELLI
    left_block.line.fill.background()
    
    title_box = slide1.shapes.add_textbox(Inches(1.5), Inches(2.2), Inches(10.5), Inches(3.5))
    tf = title_box.text_frame
    tf.word_wrap = True
    
    p1 = tf.paragraphs[0]
    p1.text = "FELTRINELLI EDITORE"
    p1.font.name = 'Arial'
    p1.font.size = Pt(22)
    p1.font.color.rgb = RED_FELTRINELLI
    p1.font.bold = True
    p1.space_after = Pt(20)
    
    p2 = tf.add_paragraph()
    p2.text = "Performance Report Canale YouTube"
    p2.font.name = 'Arial'
    p2.font.size = Pt(44)
    p2.font.color.rgb = WHITE
    p2.font.bold = True
    
    p3 = tf.add_paragraph()
    p3.text = "Analisi biennale di gestione del canale (2024-2026) e strategie di crescita"
    p3.font.name = 'Arial'
    p3.font.size = Pt(18)
    p3.font.color.rgb = RGBColor(200, 200, 200)
    p3.space_after = Pt(40)
    
    p4 = tf.add_paragraph()
    p4.text = "Preparato da: Totally Agency"
    p4.font.name = 'Arial'
    p4.font.size = Pt(14)
    p4.font.color.rgb = MUTED_TEXT

    # SLIDE 2: Executive Summary
    slide2 = add_slide("Executive Summary: I Punti Chiave del Biennio")
    
    # Text container
    summary_box = slide2.shapes.add_textbox(Inches(0.75), Inches(1.5), Inches(11.83), Inches(5.2))
    tf2 = summary_box.text_frame
    tf2.word_wrap = True
    
    p_intro = tf2.paragraphs[0]
    p_intro.text = "Negli ultimi due anni, il canale YouTube di Feltrinelli Editore ha registrato una crescita eccezionale e una maturazione strategica. Il canale si è evoluto da archivio storico a vero e proprio hub di intrattenimento culturale, guidato da nuovi formati podcast e da campagne ADV ad altissima efficienza."
    p_intro.font.name = 'Arial'
    p_intro.font.size = Pt(16)
    p_intro.font.color.rgb = DARK_TEXT
    p_intro.space_after = Pt(24)
    
    # We will draw 3 visually appealing column boxes for highlights
    card_width = Inches(3.6)
    card_height = Inches(3.2)
    card_y = Inches(3.2)
    
    highlights = [
        ("RISULTATI DI CANALE", 
         "• Community a 71.727 iscritti totali.\n• Nel 2025: 1,5 Milioni di views (+29% YoY).\n• Ottimizzazione della monetizzazione con un incremento delle entrate del >999% nel 2025.\n• Accelerazione iscritti nel 2026 (+6.000 YTD)."),
        ("FORMATI EDITORIALI", 
         "• Lancio di format di grandissimo successo.\n• 'Le Stanze del Male' domina il 2026: 6 dei primi 10 video dell'anno appartengono a questa serie.\n• L'episodio 1 (Stefano Nazzi) ha superato 66k views, seguito dall'ep. 3 con 59k views."),
        ("EFFICIENZA DELLE CAMPAGNE", 
         "• 1.690€ totali investiti con risultati incredibili.\n• CPV medio straordinario: 0,01€ su tutte le promozioni video.\n• Campagne PMAX Iscrizioni: acquisiti 3.458 iscritti a soli 0,10€ l'uno.\n• 34% del budget finanziato tramite crediti omaggio.")
    ]
    
    for i, (title, text) in enumerate(highlights):
        x = Inches(0.75) + i * Inches(4.1)
        # Background card
        card = slide2.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, card_y, card_width, card_height)
        card.fill.solid()
        card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = RGBColor(222, 226, 230)
        
        # Text Frame
        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_top = Inches(0.2)
        ctf.margin_left = Inches(0.2)
        ctf.margin_right = Inches(0.2)
        
        cp1 = ctf.paragraphs[0]
        cp1.text = title
        cp1.font.name = 'Arial'
        cp1.font.size = Pt(14)
        cp1.font.bold = True
        cp1.font.color.rgb = RED_FELTRINELLI
        cp1.space_after = Pt(14)
        
        cp2 = ctf.add_paragraph()
        cp2.text = text
        cp2.font.name = 'Arial'
        cp2.font.size = Pt(12)
        cp2.font.color.rgb = DARK_TEXT
        cp2.space_before = Pt(4)

    # SLIDE 3: Channel Performance (2025 vs 2026 YTD)
    slide3 = add_slide("Andamento Canale: 2025 vs 2026 YTD")
    
    # Left column for 2025
    left_x = Inches(0.75)
    col_width = Inches(5.6)
    col_height = Inches(4.8)
    
    card_2025 = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, left_x, Inches(1.6), col_width, col_height)
    card_2025.fill.solid()
    card_2025.fill.fore_color.rgb = WHITE
    card_2025.line.color.rgb = RGBColor(222, 226, 230)
    
    tf_2025 = card_2025.text_frame
    tf_2025.word_wrap = True
    tf_2025.margin_top = Inches(0.3)
    tf_2025.margin_left = Inches(0.3)
    tf_2025.margin_right = Inches(0.3)
    
    p_2025_title = tf_2025.paragraphs[0]
    p_2025_title.text = "ANNO 2025: Consolidamento e Monetizzazione"
    p_2025_title.font.name = 'Arial'
    p_2025_title.font.size = Pt(16)
    p_2025_title.font.bold = True
    p_2025_title.font.color.rgb = DARK_TEXT
    p_2025_title.space_after = Pt(20)
    
    metrics_2025 = (
        "• VISUALIZZAZIONI: 1.494.697 (+29% YoY)\n"
        "  Crescita trainata da formati brevi e viralità.\n\n"
        "• TEMPO DI VISUALIZZAZIONE: 114.014 ore (-19% YoY)\n"
        "  Flessione dovuta allo shift verso Shorts e video brevi.\n\n"
        "• ISCRITTI NETTI: +5.157\n"
        "  Acquisizione organica costante nel corso dell'anno.\n\n"
        "• ENTRATE STIMATE: 2.869,37 USD (+999% YoY)\n"
        "  Attivazione e ottimizzazione radicale della monetizzazione."
    )
    p_2025_body = tf_2025.add_paragraph()
    p_2025_body.text = metrics_2025
    p_2025_body.font.name = 'Arial'
    p_2025_body.font.size = Pt(13)
    p_2025_body.font.color.rgb = DARK_TEXT
    
    # Right column for 2026
    right_x = Inches(6.98)
    card_2026 = slide3.shapes.add_shape(MSO_SHAPE.RECTANGLE, right_x, Inches(1.6), col_width, col_height)
    card_2026.fill.solid()
    card_2026.fill.fore_color.rgb = WHITE
    card_2026.line.color.rgb = RED_FELTRINELLI
    card_2026.line.width = Pt(1.5)
    
    tf_2026 = card_2026.text_frame
    tf_2026.word_wrap = True
    tf_2026.margin_top = Inches(0.3)
    tf_2026.margin_left = Inches(0.3)
    tf_2026.margin_right = Inches(0.3)
    
    p_2026_title = tf_2026.paragraphs[0]
    p_2026_title.text = "ANNO 2026 (YTD): L'Anno dell'Acquisizione Iscritti"
    p_2026_title.font.name = 'Arial'
    p_2026_title.font.size = Pt(16)
    p_2026_title.font.bold = True
    p_2026_title.font.color.rgb = RED_FELTRINELLI
    p_2026_title.space_after = Pt(20)
    
    metrics_2026 = (
        "• VISUALIZZAZIONI: 741.125 (YTD al 17 Settembre)\n"
        "  Format ad alto ingaggio con traffico di ritorno forte.\n\n"
        "• TEMPO DI VISUALIZZAZIONE: 69.418 ore\n"
        "  Tasso di fidelizzazione molto elevato per i nuovi podcast.\n\n"
        "• ISCRITTI NETTI: +6.000 (Superato l'intero 2025!)\n"
        "  Accelerazione eccezionale dell'acquisizione (+71% YoY rispetto\n"
        "  allo stesso periodo del 2025), guidata dalle nostre campagne PMAX.\n\n"
        "• ENTRATE STIMATE: 970,81 USD"
    )
    p_2026_body = tf_2026.add_paragraph()
    p_2026_body.text = metrics_2026
    p_2026_body.font.name = 'Arial'
    p_2026_body.font.size = Pt(13)
    p_2026_body.font.color.rgb = DARK_TEXT

    # SLIDE 4: Format Analysis: The New Pillars
    slide4 = add_slide("Analisi dei Formati: I Nuovi Pilastri del Canale")
    
    # Overview text
    format_intro = slide4.shapes.add_textbox(Inches(0.75), Inches(1.3), Inches(11.83), Inches(0.8))
    ft_tf = format_intro.text_frame
    ft_tf.word_wrap = True
    ft_p = ft_tf.paragraphs[0]
    ft_p.text = "La transizione strategica verso serie originali di alta qualità in formato podcast (video-podcast) ha rivoluzionato il canale. Le campagne ADV hanno funzionato da acceleratore iniziale per creare una solida base di pubblico organico."
    ft_p.font.name = 'Arial'
    ft_p.font.size = Pt(14)
    ft_p.font.color.rgb = DARK_TEXT
    
    # Left column for Le Stanze del Male
    col_y = Inches(2.2)
    col_w = Inches(5.6)
    col_h = Inches(4.3)
    
    card_male = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), col_y, col_w, col_h)
    card_male.fill.solid()
    card_male.fill.fore_color.rgb = WHITE
    card_male.line.color.rgb = RGBColor(222, 226, 230)
    
    tf_male = card_male.text_frame
    tf_male.word_wrap = True
    tf_male.margin_top = Inches(0.25)
    tf_male.margin_left = Inches(0.25)
    tf_male.margin_right = Inches(0.25)
    
    p_male_t = tf_male.paragraphs[0]
    p_male_t.text = "LE STANZE DEL MALE (con Piergiorgio Pulixi)"
    p_male_t.font.name = 'Arial'
    p_male_t.font.size = Pt(15)
    p_male_t.font.bold = True
    p_male_t.font.color.rgb = RED_FELTRINELLI
    p_male_t.space_after = Pt(12)
    
    p_male_b = tf_male.add_paragraph()
    p_male_b.text = (
        "Il format di maggior successo del canale nel 2026.\n\n"
        "• Presenza in Classifica: 6 dei primi 10 video più visti del canale nel 2026 appartengono a questo format!\n\n"
        "• Performance Episodi Top:\n"
        "  - Ep. 01 (con Stefano Nazzi): 66.894 visualizzazioni (#1 del 2026)\n"
        "  - Ep. 03 (con Beniamino Zuncheddu): 59.717 visualizzazioni (#2 del 2026)\n"
        "  - Ep. 06 (con Don Claudio Burgio): 38.485 visualizzazioni (#4 del 2026)\n"
        "  - Ep. 02 (con Cristina Cattaneo): 33.078 visualizzazioni (#5 del 2026)"
    )
    p_male_b.font.name = 'Arial'
    p_male_b.font.size = Pt(12)
    p_male_b.font.color.rgb = DARK_TEXT
    
    # Right column for Kind of Black
    card_black = slide4.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(6.98), col_y, col_w, col_h)
    card_black.fill.solid()
    card_black.fill.fore_color.rgb = WHITE
    card_black.line.color.rgb = RGBColor(222, 226, 230)
    
    tf_black = card_black.text_frame
    tf_black.word_wrap = True
    tf_black.margin_top = Inches(0.25)
    tf_black.margin_left = Inches(0.25)
    tf_black.margin_right = Inches(0.25)
    
    p_black_t = tf_black.paragraphs[0]
    p_black_t.text = "KIND OF BLACK — Podcast"
    p_black_t.font.name = 'Arial'
    p_black_t.font.size = Pt(15)
    p_black_t.font.bold = True
    p_black_t.font.color.rgb = DARK_TEXT
    p_black_t.space_after = Pt(12)
    
    p_black_b = tf_black.add_paragraph()
    p_black_b.text = (
        "Format focalizzato sulla letteratura thriller, noir e mystery, ampiamente apprezzato dalla community.\n\n"
        "• Presenza in Classifica: L'Ep. 2 (con Luca Briasco) è entrato nella Top 10 del 2026 con 14.519 visualizzazioni.\n\n"
        "• Performance Episodi Top in 2026:\n"
        "  - Ep. 5 (con Paolo Roversi) e Ep. 6 (con Luca Briasco) sono risultati essere tra i video a più rapido successo nelle prime ore dalla pubblicazione.\n"
        "• Fidelizzazione: Il pubblico di questo format presenta un tasso di completamento del video superiore alla media di categoria (oltre il 24% di fidelizzazione)."
    )
    p_black_b.font.name = 'Arial'
    p_black_b.font.size = Pt(12)
    p_black_b.font.color.rgb = DARK_TEXT

    # SLIDE 5: Video Ads Campaigns
    slide5 = add_slide("Analisi Campagne ADV: Promozione Video")
    
    adv_intro = slide5.shapes.add_textbox(Inches(0.75), Inches(1.3), Inches(11.83), Inches(0.8))
    adv_p = adv_intro.text_frame.paragraphs[0]
    adv_p.text = "Per supportare il lancio delle nuove serie originali, Totally ha strutturato campagne pubblicitarie video estremamente profilate su Google Ads. I risultati evidenziano un'efficienza economica senza precedenti."
    adv_p.font.name = 'Arial'
    adv_p.font.size = Pt(14)
    adv_p.font.color.rgb = DARK_TEXT
    
    # Cards layout for Le Stanze del Male & Kind of Black Campaign results
    col_h2 = Inches(4.3)
    card_male_adv = slide5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.75), col_y, col_w, col_h2)
    card_male_adv.fill.solid()
    card_male_adv.fill.fore_color.rgb = WHITE
    card_male_adv.line.color.rgb = RGBColor(222, 226, 230)
    
    tf_m_adv = card_male_adv.text_frame
    tf_m_adv.word_wrap = True
    tf_m_adv.margin_top = Inches(0.25)
    tf_m_adv.margin_left = Inches(0.25)
    tf_m_adv.margin_right = Inches(0.25)
    
    pm1 = tf_m_adv.paragraphs[0]
    pm1.text = "PROMOZIONE 'LE STANZE DEL MALE'"
    pm1.font.name = 'Arial'
    pm1.font.size = Pt(15)
    pm1.font.bold = True
    pm1.font.color.rgb = RED_FELTRINELLI
    pm1.space_after = Pt(12)
    
    pm2 = tf_m_adv.add_paragraph()
    pm2.text = (
        "• BUDGET INVESTITO: 980,00 € (7 episodi promossi)\n"
        "• IMPRESSIONS: 159.165\n"
        "• VISUALIZZAZIONI DA CAMPAGNA: 98.107\n"
        "• TASSO DI VISUALIZZAZIONE (View Rate): 61,64%\n"
        "  (Il 61% degli utenti esposti ha visualizzato il video, un valore di enorme pertinenza ed efficacia del target)\n"
        "• COSTO MEDIO PER VIEW (CPV): 0,01 €\n"
        "• IMPATTO SUL TOTALE: La campagna ha generato direttamente il 54,2% delle visualizzazioni totali degli episodi promossi (181.000 views totali), innescando l'algoritmo di raccomandazione organico."
    )
    pm2.font.name = 'Arial'
    pm2.font.size = Pt(12.5)
    pm2.font.color.rgb = DARK_TEXT
    
    # Kind of Black ADV
    card_black_adv = slide5.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(6.98), col_y, col_w, col_h2)
    card_black_adv.fill.solid()
    card_black_adv.fill.fore_color.rgb = WHITE
    card_black_adv.line.color.rgb = RGBColor(222, 226, 230)
    
    tf_b_adv = card_black_adv.text_frame
    tf_b_adv.word_wrap = True
    tf_b_adv.margin_top = Inches(0.25)
    tf_b_adv.margin_left = Inches(0.25)
    tf_b_adv.margin_right = Inches(0.25)
    
    pb1 = tf_b_adv.paragraphs[0]
    pb1.text = "PROMOZIONE 'KIND OF BLACK'"
    pb1.font.name = 'Arial'
    pb1.font.size = Pt(15)
    pb1.font.bold = True
    pb1.font.color.rgb = DARK_TEXT
    pb1.space_after = Pt(12)
    
    pb2 = tf_b_adv.add_paragraph()
    pb2.text = (
        "• BUDGET INVESTITO: 360,00 € (5 episodi promossi)\n"
        "• IMPRESSIONS: 67.669\n"
        "• VISUALIZZAZIONI DA CAMPAGNA: 38.390\n"
        "• TASSO DI VISUALIZZAZIONE (View Rate): 56,73%\n"
        "  (Ottimo interesse riscontrato da un pubblico appassionato di gialli e crime)\n"
        "• COSTO MEDIO PER VIEW (CPV): 0,0094 € (Meno di 1 centesimo)\n"
        "• IMPATTO SUL TOTALE: La campagna ha generato il 65,4% delle visualizzazioni degli episodi (58.700 views totali), garantendo una solida rampa di lancio a formati completamente nuovi."
    )
    pb2.font.name = 'Arial'
    pb2.font.size = Pt(12.5)
    pb2.font.color.rgb = DARK_TEXT

    # SLIDE 6: PMAX Subscriber Campaigns
    slide6 = add_slide("Campagne ADV: Performance Max Iscrizioni")
    
    pmax_box = slide6.shapes.add_textbox(Inches(0.75), Inches(1.4), Inches(11.83), Inches(5.0))
    pmax_tf = pmax_box.text_frame
    pmax_tf.word_wrap = True
    
    pp1 = pmax_tf.paragraphs[0]
    pp1.text = "La crescita degli iscritti nel 2026 ha subito un'accelerazione enorme grazie all'attivazione di campagne Google Ads Performance Max (PMAX) specifiche per le conversioni di iscrizione. Questo strumento ha permesso di acquisire un pubblico profilato ed estremamente fedele a costi minimi."
    pp1.font.name = 'Arial'
    pp1.font.size = Pt(14)
    pp1.font.color.rgb = DARK_TEXT
    pp1.space_after = Pt(20)
    
    # 2 horizontal cards for the two PMAX campaigns
    pmax_cards = [
        ("Campagna PMAX Aprile 2026", "16 - 30 Aprile 2026", "150,00 €", "1.392", "1.180", "84,77%", "0,127 €"),
        ("Campagna PMAX Giugno-Luglio 2026", "25 Giugno - 14 Luglio 2026", "200,00 €", "2.817", "2.278", "80,87%", "0,088 €")
    ]
    
    for idx, (name, period, spend, clicks, subs, conv_rate, cpa) in enumerate(pmax_cards):
        y_pos = Inches(2.6) + idx * Inches(2.1)
        p_card = slide6.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), y_pos, Inches(11.83), Inches(1.8))
        p_card.fill.solid()
        p_card.fill.fore_color.rgb = WHITE
        p_card.line.color.rgb = RED_FELTRINELLI if idx == 1 else RGBColor(222, 226, 230)
        p_card.line.width = Pt(1.5) if idx == 1 else Pt(1.0)
        
        pctf = p_card.text_frame
        pctf.word_wrap = True
        pctf.margin_top = Inches(0.15)
        pctf.margin_left = Inches(0.25)
        
        pc_p1 = pctf.paragraphs[0]
        pc_p1.text = f"{name}  |  Periodo: {period}"
        pc_p1.font.name = 'Arial'
        pc_p1.font.size = Pt(14)
        pc_p1.font.bold = True
        pc_p1.font.color.rgb = RED_FELTRINELLI
        pc_p1.space_after = Pt(8)
        
        # Add values inside
        pc_p2 = pctf.add_paragraph()
        pc_p2.text = (
            f"• Investimento: {spend}  |  • Clic generati: {clicks}  |  "
            f"• Nuovi Iscritti Acquisiti: {subs}  |  • Tasso di Conversione: {conv_rate}  |  "
            f"• Costo per Iscritto (CPA): {cpa}"
        )
        pc_p2.font.name = 'Arial'
        pc_p2.font.size = Pt(13)
        pc_p2.font.color.rgb = DARK_TEXT
        
        # Impact text
        pc_p3 = pctf.add_paragraph()
        pc_p3.text = (
            f"Nota di impatto: Su un totale di circa +6.000 iscritti netti nel 2026, ben {subs} iscritti "
            f"sono derivati direttamente da questa campagna, dimostrando l'efficacia del budget promozionale."
        )
        pc_p3.font.name = 'Arial'
        pc_p3.font.size = Pt(11)
        pc_p3.font.color.rgb = MUTED_TEXT
        pc_p3.font.italic = True
        pc_p3.space_before = Pt(6)

    # SLIDE 7: Budget Optimization and ROI
    slide7 = add_slide("Ottimizzazione Economica: Profitabilità e ROI del Canale")
    
    roi_box = slide7.shapes.add_textbox(Inches(0.75), Inches(1.3), Inches(11.83), Inches(5.2))
    roi_tf = roi_box.text_frame
    roi_tf.word_wrap = True
    
    rp1 = roi_tf.paragraphs[0]
    rp1.text = "L'approccio di Totally combina una straordinaria performance editoriale con un'attenta e intelligente gestione finanziaria del budget pubblicitario, massimizzando il ritorno sugli investimenti (ROI) del cliente."
    rp1.font.name = 'Arial'
    rp1.font.size = Pt(14)
    rp1.font.color.rgb = DARK_TEXT
    rp1.space_after = Pt(20)
    
    # Financial breakdown text
    rp2 = roi_tf.add_paragraph()
    rp2.text = (
        "BILANCIO GENERALE DEL BIENNIO (Canale Feltrinelli):\n"
        "• ENTRATE LORDE GENERATE (Lordo): 3.820,30 €\n"
        "• INVESTIMENTO IN ADV TOTALE (Spesa Ads): 1.690,00 €\n"
        "  - Le Stanze del Male (Promozione Video): 980,00 €\n"
        "  - Kind of Black (Promozione Video): 360,00 €\n"
        "  - PMAX Iscrizioni (Acquisizione Iscritti): 350,00 €\n"
        "• UTILE NETTO DI GESTIONE (Entrate - Adv): 2.130,30 €\n"
        "• FEE AGENZIA TOTALLY: 10% (pari a 382,03 €)"
    )
    rp2.font.name = 'Arial'
    rp2.font.size = Pt(13)
    rp2.font.color.rgb = DARK_TEXT
    rp2.space_after = Pt(24)
    
    # Red background box for Google Ads Credits highlight
    credit_card = slide7.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.75), Inches(4.5), Inches(11.83), Inches(2.1))
    credit_card.fill.solid()
    credit_card.fill.fore_color.rgb = RGBColor(255, 243, 205) # light yellow
    credit_card.line.color.rgb = RGBColor(255, 238, 186)
    
    c_tf = credit_card.text_frame
    c_tf.word_wrap = True
    c_tf.margin_top = Inches(0.2)
    c_tf.margin_left = Inches(0.25)
    c_tf.margin_right = Inches(0.25)
    
    cp_title = c_tf.paragraphs[0]
    cp_title.text = "FOCUS STRATEGICO: Risparmio e Ottimizzazione Tramite Crediti Google Ads"
    cp_title.font.name = 'Arial'
    cp_title.font.size = Pt(14)
    cp_title.font.bold = True
    cp_title.font.color.rgb = RGBColor(133, 100, 4) # dark gold
    cp_title.space_after = Pt(10)
    
    cp_body = c_tf.add_paragraph()
    cp_body.text = (
        "Totally ha riscattato e applicato strategicamente codici promozionali e crediti Google Ads per abbattere i costi out-of-pocket di Feltrinelli:\n"
        "• Credito PMAX riscattato ed utilizzato al 100%: 150,00 €\n"
        "• Credito Generale riscattato ed utilizzato all'85.5%: 427,50 € (su 500€ totali)\n"
        "• RISPARMIO TOTALE OTTENUTO: 577,50 €  -->  Ben il 34,2% dell'investimento ADV è stato finanziato a costo zero tramite crediti promozionali riscattati dall'agenzia, riducendo l'esborso monetario effettivo di Feltrinelli a soli 1.112,50 €!"
    )
    cp_body.font.name = 'Arial'
    cp_body.font.size = Pt(11.5)
    cp_body.font.color.rgb = DARK_TEXT

    # SLIDE 8: Future Strategy and Renewal
    slide8 = add_slide("Strategia di Crescita Futura e Rinnovo")
    
    strat_box = slide8.shapes.add_textbox(Inches(0.75), Inches(1.3), Inches(11.83), Inches(5.2))
    strat_tf = strat_box.text_frame
    strat_tf.word_wrap = True
    
    sp1 = strat_tf.paragraphs[0]
    sp1.text = "Per consolidare il posizionamento del canale come leader nell'editoria italiana su YouTube e massimizzare il valore generato, Totally propone un rinnovo contrattuale focalizzato sulle seguenti direttrici di crescita:"
    sp1.font.name = 'Arial'
    sp1.font.size = Pt(14)
    sp1.font.color.rgb = DARK_TEXT
    sp1.space_after = Pt(20)
    
    # 4 columns of future strategies
    col_w_strat = Inches(2.7)
    col_h_strat = Inches(3.6)
    col_y_strat = Inches(2.8)
    
    strategies = [
        ("1. ESPANSIONE FORMAT", 
         "Sviluppare la Stagione 2 di 'Le Stanze del Male', cavalcando il successo di Nazzi/Pulixi. Integrare ospiti nazionali ed estendere la durata media a 40 minuti per incrementare ulteriormente la fidelizzazione."),
        ("2. SHORTS FUNNEL", 
         "Creare un flusso di lavoro sistematico di Shorts e video brevi (sul modello del Short di Dario Fabbri da 374k views) per intercettare il pubblico giovane ed indirizzarlo verso i video-podcast completi."),
        ("3. RISOLUZIONE TECH", 
         "Risolvere tempestivamente la notifica di blocco sul video 'Spegni tutto #intelligenzaartificiale' per riattivare la visualizzazione ed ottimizzare l'integrità e la monetizzazione complessiva del canale."),
        ("4. AD SPEND BONUS", 
         "Sfruttare immediatamente il secondo credito promozionale di 500€ già attivo sull'account (attualmente allo 0% di utilizzo) per lanciare la nuova campagna iscritti autunnale a costo zero per Feltrinelli.")
    ]
    
    for i, (title, text) in enumerate(strategies):
        x = Inches(0.75) + i * Inches(3.05)
        # Background card
        card = slide8.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, col_y_strat, col_w_strat, col_h_strat)
        card.fill.solid()
        card.fill.fore_color.rgb = WHITE
        card.line.color.rgb = RED_FELTRINELLI if i == 3 else RGBColor(222, 226, 230)
        card.line.width = Pt(1.5) if i == 3 else Pt(1.0)
        
        ctf = card.text_frame
        ctf.word_wrap = True
        ctf.margin_top = Inches(0.15)
        ctf.margin_left = Inches(0.15)
        ctf.margin_right = Inches(0.15)
        
        cp1 = ctf.paragraphs[0]
        cp1.text = title
        cp1.font.name = 'Arial'
        cp1.font.size = Pt(12)
        cp1.font.bold = True
        cp1.font.color.rgb = RED_FELTRINELLI
        cp1.space_after = Pt(10)
        
        cp2 = ctf.add_paragraph()
        cp2.text = text
        cp2.font.name = 'Arial'
        cp2.font.size = Pt(10.5)
        cp2.font.color.rgb = DARK_TEXT
        cp2.space_before = Pt(4)

    # Save presentation
    prs.save('feltrinelli_report.pptx')
    print("Presentation created successfully as 'feltrinelli_report.pptx'.")

if __name__ == '__main__':
    create_presentation()
