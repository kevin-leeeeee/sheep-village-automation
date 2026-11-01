"""羊村工具共用介面：固定控制與日誌、可捲動的設定分頁。"""
import tkinter as tk
import re
from tkinter import ttk, scrolledtext

BG = '#F3F5F7'
FONT = 'Microsoft JhengHei UI'


def normalize_log_message(message):
    # 移除會觸發彩色 emoji 字型的裝飾符號，保留座標、箭頭與訊息文字。
    plain = re.sub('[\U0001F000-\U0001FAFF\u2300-\u23FF\u2600-\u27BF\uFE0E\uFE0F\u200D\u20E3]',
                   lambda match: match[0] if match[0] in '➔➜➡' else '', str(message))
    plain = re.sub(r'([【（(])[ \t]+', r'\1', plain)
    return re.sub(r'[ \t]{2,}', ' ', plain).strip()


def configure_scroll_area(canvas, scrollbar, content):
    """只有內容超出可視高度時才啟用捲動。"""
    height = canvas.winfo_height()
    overflow = content.winfo_reqheight() > height
    if overflow and not scrollbar.winfo_manager():
        scrollbar.pack(side='right', fill='y', before=canvas)
    elif not overflow and scrollbar.winfo_manager():
        scrollbar.pack_forget()
    canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), max(height, content.winfo_reqheight())))
    if not overflow:
        canvas.yview_moveto(0)
    canvas._content_overflows = overflow


def scroll_settings_canvas(canvas, delta):
    if getattr(canvas, '_content_overflows', False):
        canvas.yview_scroll(int(-delta / 120), 'units')


def secondary(button):
    button.configure(bg='white', fg='#293E52', activebackground='#E9EFF6',
                     activeforeground='#193F6B', disabledforeground='#7A8794',
                     highlightthickness=1, highlightbackground='#A5B1C0', highlightcolor='#245FA8',
                     relief='solid', bd=1, padx=12, pady=7, cursor='hand2', font=(FONT, 9))


def card(parent, title, subtitle=''):
    outer = tk.Frame(parent, bg='white', highlightthickness=1, highlightbackground='#BBC8C5')
    outer.pack(fill='x', pady=(0, 6), padx=(0, 6))
    heading = tk.Frame(outer, bg='white', padx=12, pady=5)
    heading.pack(fill='x')
    label = tk.Label(heading, text=title, bg='white', fg='#283E35', font=(FONT, 11, 'bold'))
    label._ui_font = (FONT, 11, 'bold')
    label.pack(anchor='w')
    return tk.Frame(outer, bg='white', padx=12, pady=2)


def style_settings(widget):
    if isinstance(widget, tk.Frame):
        widget.configure(bg='white')
    elif isinstance(widget, tk.Label):
        widget.configure(bg='white', font=getattr(widget, '_ui_font', (FONT, 10)))
        if widget.cget('fg') not in ('green', '#B71C1C'):
            widget.configure(fg='#475569')
    elif isinstance(widget, (tk.Radiobutton, tk.Checkbutton)):
        tile = isinstance(widget, tk.Radiobutton) and not int(widget.cget('indicatoron'))
        widget.configure(bg='#EEF2F7' if tile else 'white', fg='#263E59',
                         activebackground='#E6EFFA', activeforeground='#174C8C',
                         selectcolor='#AFCDF2', relief='flat', bd=0, highlightthickness=0,
                         padx=8, pady=4, cursor='hand2', font=(FONT, 10))
        if tile:
            widget.configure(relief='solid', offrelief='solid', bd=1)
    elif isinstance(widget, tk.Entry):
        widget.configure(bg='white', fg='#33443D', relief='flat', bd=3,
                         insertbackground='#245FA8', highlightthickness=1,
                         highlightbackground='#A5B1C0', highlightcolor='#245FA8', font=(FONT, 10))
    elif isinstance(widget, tk.Button):
        secondary(widget)
    for child in widget.winfo_children():
        style_settings(child)


def form(parent, fields):
    """fields: (顯示名稱, Tk 變數, 單位或提示)。"""
    for row, (title, variable, unit) in enumerate(fields):
        tk.Label(parent, text=title).grid(row=row, column=0, sticky='w', padx=(0, 18), pady=6)
        tk.Entry(parent, textvariable=variable, width=10).grid(row=row, column=1, sticky='w', pady=6)
        tk.Label(parent, text=unit).grid(row=row, column=2, sticky='w', padx=8, pady=6)


def coordinate_table(parent, rows):
    """回傳每列的值標籤，供既有座標更新流程直接更新。"""
    parent.columnconfigure(1, weight=1)
    for column, title in enumerate(('項目', '目前設定', '操作')):
        label = tk.Label(parent, text=title, anchor='w')
        label._ui_font = (FONT, 9, 'bold')
        label.grid(row=0, column=column, sticky='ew', padx=(0, 10), pady=(0, 4))
    labels = {}
    for row, (key, title, value, action, command) in enumerate(rows, start=1):
        tk.Label(parent, text=title, anchor='w').grid(row=row, column=0, sticky='w', padx=(0, 12), pady=3)
        label = tk.Label(parent, text=value, anchor='w', fg='#B71C1C' if value == '未設定' else '#475569')
        label.grid(row=row, column=1, sticky='w', padx=(0, 8), pady=3)
        labels[key] = label
        tk.Button(parent, text=action, width=8, command=command).grid(row=row, column=2, sticky='ew', pady=3)
    return labels


def workspace(app, title, subtitle, start, stop, save, is_admin, compact=False):
    root = app.root
    root.configure(bg=BG)
    root.minsize(560, 650)
    root.option_add('*Font', (FONT, 10))
    # Windows 上 flat 按鈕不會可靠地畫出 highlight 邊界；使用實線外框。
    # 選項預設也套用到之後建立的設定、預覽與截圖對話框。
    root.option_add('*Button.relief', 'solid')
    root.option_add('*Button.borderWidth', 1)
    style = ttk.Style(root)
    style.theme_use('clam')
    style.configure('Village.TNotebook', background=BG, borderwidth=0, tabmargins=(0, 0, 0, 8))
    style.configure('Village.TNotebook.Tab', padding=(18, 9), borderwidth=0,
                    font=(FONT, 10), background=BG, foreground='#3E4F60')
    style.map('Village.TNotebook.Tab', background=[('selected', '#245FA8'), ('active', '#E6EFFA')],
              foreground=[('selected', 'white')],
              padding=[('selected', (24, 13)), ('!selected', (18, 9))],
              font=[('selected', (FONT, 11, 'bold')), ('!selected', (FONT, 10))])
    style.configure('Village.Vertical.TScrollbar', gripcount=0, background='#7F8D9E',
                    troughcolor=BG, borderwidth=0, arrowsize=10, width=10)

    header = tk.Frame(root, bg=BG, padx=16, pady=12)
    header.pack(fill='x')
    top = tk.Frame(header, bg=BG)
    top.pack(fill='x', pady=(0, 8) if compact else 0)
    tk.Label(top, text=title if compact else '羊村助手  /  ' + title,
             bg=BG, fg='#203B32' if compact else '#425B4C',
             font=(FONT, 21, 'bold') if compact else (FONT, 9)).pack(side='left')
    app.topmost_btn = tk.Button(top, text='視窗置頂', command=app.toggle_topmost)
    secondary(app.topmost_btn)
    app.topmost_btn.pack(side='right')
    if not is_admin and hasattr(app, 'request_admin'):
        app.admin_btn = tk.Button(top, text='以管理員執行', command=app.request_admin)
        secondary(app.admin_btn)
        app.admin_btn.pack(side='right', padx=(8, 8))
    if not compact:
        tk.Label(header, text=title, bg=BG, fg='#203B32', font=(FONT, 21, 'bold')).pack(anchor='w', pady=(8, 2))
        tk.Label(header, text=subtitle, bg=BG, fg='#465968', font=(FONT, 9)).pack(anchor='w', pady=(0, 12))
    controls = tk.Frame(header, bg=BG)
    controls.pack(fill='x')
    app.start_btn = tk.Button(controls, text='▶  開始執行', command=start, bg='#277653', fg='white',
                             activebackground='#1F6144', activeforeground='white', relief='solid', bd=1,
                             pady=4 if compact else 10, cursor='hand2', disabledforeground='#A6BEB2', font=(FONT, 11, 'bold'))
    app.start_btn.pack(side='left', fill='both' if compact else 'x', expand=True, padx=(0, 8))
    app.stop_btn = tk.Button(controls, text='停止  F10', command=stop, state='disabled', bg='#FBE9E7',
                            fg='#B33A32', activebackground='#F6D4D0', relief='solid', bd=1,
                            pady=4 if compact else 10, disabledforeground='#BAA29F', cursor='hand2', font=(FONT, 10))
    app.stop_btn.pack(side='left', fill='both' if compact else 'x', expand=True)

    if not compact:
        app.status_var = tk.StringVar(value='待命中 · 可先調整下方設定')
        app.status_message_limit = 65
        tk.Label(header, textvariable=app.status_var, bg=BG, fg='#385547', font=(FONT, 9),
                 wraplength=520, justify='left', anchor='w', height=2).pack(fill='x', pady=(12, 0))
    log = tk.Frame(root, bg='white', padx=14, pady=10, highlightbackground='#BBC8C5', highlightthickness=1)
    log.pack(fill='x', padx=16, pady=(0, 12))
    log_heading = tk.Frame(log, bg='white')
    log_heading.pack(fill='x', pady=(0, 6))
    tk.Label(log_heading, text='執行動態', bg='white', fg='#334155', font=(FONT, 10, 'bold')).pack(side='left')
    clear = tk.Button(log_heading, text='清空日誌', command=lambda: app.log_text.delete('1.0', 'end'))
    secondary(clear)
    clear.pack(side='right')
    app.log_text = scrolledtext.ScrolledText(log, height=6, wrap='word', font=(FONT, 9),
                    bg='#FAFBFC', fg='#293E4C', relief='flat', bd=0, padx=10, pady=10, spacing1=2, spacing3=3)
    app.log_text.pack(fill='x')
    app.log_text.tag_configure('timestamp', foreground='#526575')
    app.log_text.tag_configure('error', foreground='#B74A43')
    app.log_text.tag_configure('success', foreground='#267655')

    footer = tk.Frame(root, bg=BG, padx=16, pady=10)
    footer.pack(side='bottom', fill='x')
    app.shortcut_label = tk.Label(footer, text='F10 停止執行', bg=BG, fg='#465968', font=(FONT, 9))
    app.shortcut_label.pack(side='left')
    app.save_btn = tk.Button(footer, text='儲存設定', command=save)
    secondary(app.save_btn)
    app.save_btn.pack(side='right')
    app.settings_tabs = ttk.Notebook(root, style='Village.TNotebook')
    app.settings_tabs.pack(fill='both', expand=True, padx=16)
    app._settings_scrolls = {}
    pages = []
    for title in ('任務設定', '座標設定', '時間與辨識'):
        page = tk.Frame(app.settings_tabs, bg=BG)
        app.settings_tabs.add(page, text=title)
        scrollbar = ttk.Scrollbar(page, orient='vertical', style='Village.Vertical.TScrollbar')
        scrollbar.pack(side='right', fill='y')
        canvas = tk.Canvas(page, bg=BG, highlightthickness=0, yscrollcommand=scrollbar.set)
        canvas.pack(side='left', fill='both', expand=True)
        scrollbar.configure(command=canvas.yview)
        content = tk.Frame(canvas, bg=BG)
        item = canvas.create_window((0, 0), window=content, anchor='nw')
        content.bind('<Configure>', lambda event, c=canvas, s=scrollbar, f=content:
                     configure_scroll_area(c, s, f))
        def resize(event, c=canvas, i=item, s=scrollbar, f=content):
            c.itemconfigure(i, width=event.width)
            configure_scroll_area(c, s, f)
        canvas.bind('<Configure>', resize)
        app._settings_scrolls[str(page)] = canvas
        pages.append(content)

    def scroll(event):
        widget = root.winfo_containing(event.x_root, event.y_root)
        while widget is not None:
            if widget is app.settings_tabs:
                scroll_settings_canvas(app._settings_scrolls[app.settings_tabs.select()], event.delta)
                break
            widget = getattr(widget, 'master', None)
    root.bind_all('<MouseWheel>', scroll)
    return pages


def finish(app, pages):
    for page in pages:
        for child in page.winfo_children():
            style_settings(child)
    app.topmost_btn.configure(text='置頂：開' if app.topmost else '置頂：關',
                              bg='#E6EFFA' if app.topmost else 'white')


def update_status(app, message):
    if hasattr(app, 'status_var'):
        limit = getattr(app, 'status_message_limit', 65)
        app.root.after(0, lambda: app.status_var.set(str(message).split('\n')[0][:limit]))
