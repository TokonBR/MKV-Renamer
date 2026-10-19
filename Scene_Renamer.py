import json, re, subprocess, shutil, threading, queue, os, datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

APP='MKV Renamer v1.0.0 By Tokon'
VIDEO={ 'HEVC':'H.265','H265':'H.265','V_MPEGH/ISO/HEVC':'H.265','H264':'H.264','V_MPEG4/ISO/AVC':'H.264','AVC':'H.264','MPEG-4 VISUAL':'XviD','AV1':'AV1'}

def mediainfo(path):
    """Usa mkvmerge, ffprobe ou MediaInfo CLI sem abrir interface externa."""
    import os
    # A versão gráfica MediaInfo.exe abre uma janela por arquivo.
    # Usar somente a versão CLI; priorizar mkvmerge, que já acompanha MKVToolNix.
    candidates = []
    for name in ('mediainfo', 'mediainfo.exe'):
        found = shutil.which(name)
        if found and 'MediaInfo CLI' in str(found): candidates.append(found)
    for root in (os.environ.get('ProgramFiles', r'C:\Program Files'),
                 os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')):
        candidates.append(str(Path(root) / 'MediaInfo CLI' / 'MediaInfo.exe'))
    errors = []
    mkv_tracks=None
    for exe in filter(None, (shutil.which('mkvmerge'), r'C:\\Program Files\\MKVToolNix\\mkvmerge.exe')):
        if not Path(exe).is_file(): continue
        try:
            proc = subprocess.run([exe, '-J', str(path)], capture_output=True,
                text=True, encoding='utf-8', errors='replace', timeout=40,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if proc.returncode: raise ValueError(proc.stderr.strip())
            tracks = []
            for track in json.loads(proc.stdout).get('tracks', []):
                kind = track.get('type', '')
                if kind not in ('video', 'audio'): continue
                props = track.get('properties', {})
                codec = track.get('codec', '')
                dims = props.get('pixel_dimensions', '0x0').split('x')
                tracks.append({'@type': kind.title(), 'Format': codec,
                    'Width': dims[0], 'Height': dims[-1],
                    'Channels': props.get('audio_channels', ''),
                    'Language': props.get('language_ietf',props.get('language','')), 
                    'hdr_info': str(props.get('hdr_type','')) + ' ' + str(props.get('colour_transfer_characteristics',''))})
            if any(t['@type'] == 'Video' for t in tracks):
                mkv_tracks=tracks
                break
        except Exception as exc: errors.append(f'mkvmerge: {exc}')
    probes = [shutil.which('ffprobe'), r'C:\\Program Files\\ffmpeg\\bin\\ffprobe.exe']
    for exe in filter(None, probes):
        if not Path(exe).is_file(): continue
        try:
            proc = subprocess.run([exe, '-v', 'error', '-show_streams', '-of', 'json', str(path)],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=40, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if proc.returncode: raise ValueError(proc.stderr.strip())
            tracks = []
            probe_data=json.loads(proc.stdout)
            for stream in probe_data.get('streams', []):
                kind = stream.get('codec_type', '').lower()
                if kind not in ('video', 'audio'): continue
                codec = stream.get('codec_name', '').upper()
                if codec == 'HEVC': codec = 'HEVC'
                if codec == 'H264': codec = 'AVC'
                if codec == 'EAC3': codec = 'E-AC-3'
                if codec == 'AC3': codec = 'AC-3'
                tracks.append({'@type': kind.title(), 'Format': codec,
                    'Width': stream.get('width', 0), 'Height': stream.get('height', 0),
                    'Channels': stream.get('channels', ''),
                    'Language':stream.get('tags',{}).get('language',''),
                    'color_transfer': stream.get('color_transfer',''),
                    'colour_primaries': stream.get('color_primaries',''),
                    'side_data_list': stream.get('side_data_list',[]),
                    'tags':stream.get('tags',{}), 'codec_tag_string':stream.get('codec_tag_string','')})
            if any(t['@type'] == 'Video' for t in tracks):
                if mkv_tracks:
                    v=next(t for t in mkv_tracks if t['@type']=='Video')
                    extra=next(t for t in tracks if t['@type']=='Video')
                    v.update({k:val for k,val in extra.items() if k not in ('@type','Format','Width','Height')})
                    other_audio=[t for t in tracks if t['@type']=='Audio']
                    for i,old in enumerate(t for t in mkv_tracks if t['@type']=='Audio'):
                        if i<len(other_audio):old.update({k:val for k,val in other_audio[i].items() if k not in ('@type','Format')})
                    # Continua até MediaInfo CLI, que expõe HDR_Format e Dolby Vision.
                    break
                return tracks
        except Exception as exc: errors.append(f'ffprobe: {exc}')
    for exe in dict.fromkeys(candidates):
        if not Path(exe).is_file(): continue
        try:
            proc = subprocess.run([exe, '--Output=JSON', str(path)],
                capture_output=True, text=True, encoding='utf-8', errors='replace',
                timeout=40, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if proc.returncode: raise ValueError(proc.stderr.strip() or 'erro no MediaInfo')
            tracks = json.loads(proc.stdout)['media']['track']
            if any(t.get('@type') == 'Video' for t in tracks):
                if mkv_tracks:
                    v=next(t for t in mkv_tracks if t['@type']=='Video')
                    extra=next(t for t in tracks if t.get('@type')=='Video')
                    v.update({k:val for k,val in extra.items() if k not in ('@type','Format','Width','Height')})
                    for i,extra_audio in enumerate(t for t in tracks if t.get('@type')=='Audio'):
                        audios=[t for t in mkv_tracks if t['@type']=='Audio']
                        if i<len(audios):audios[i].update({k:val for k,val in extra_audio.items() if k not in ('@type','Format')})
                    return mkv_tracks
                return tracks
            raise ValueError('Nenhuma faixa de vídeo identificada')
        except Exception as exc: errors.append(f'MediaInfo: {exc}')
    if mkv_tracks:return mkv_tracks
    raise RuntimeError('Não foi possível detectar as faixas. Instale MediaInfo CLI, '
        'FFmpeg (ffprobe) ou MKVToolNix. Detalhes: ' + '; '.join(errors))

def parse_episode(stem):
    m=re.search(r'(?i)(?<!\w)S(\d{1,2})[ ._-]*E(\d{1,3})(?:[ ._-]*E(\d{1,3}))?',stem)
    if not m: m=re.search(r'(?i)(?<!\w)(\d{1,2})x(\d{1,3})',stem)
    if not m: raise ValueError('SxxExx não encontrado no nome')
    name=stem[:m.start()].strip(' ._-')
    if not name: raise ValueError('Nome da série não encontrado')
    episode=f'S{int(m.group(1)):02d}E{int(m.group(2)):02d}'
    if m.lastindex and m.lastindex>=3 and m.group(3): episode+=f'E{int(m.group(3)):02d}'
    return name,episode

def codec_audio(track):
    fmt=str(track.get('Format','')).upper(); profile=str(track.get('Format_Profile','')).upper()
    if 'TRUEHD' in fmt or 'MLP FBA' in fmt: codec='TrueHD'
    elif 'E-AC-3' in fmt or 'EAC3' in fmt or 'A_EAC3' in fmt: codec='DDP'
    elif 'AC-3' in fmt or fmt=='AC3' or 'A_AC3' in fmt: codec='DD'
    elif 'DTS' in fmt: codec='DTS-HD.MA' if any(x in profile for x in ('MA','MASTER')) or 'DTS-HD MASTER' in fmt else 'DTS-HD' if 'DTS-HD' in fmt or 'HRA' in profile else 'DTS'
    elif 'AAC' in fmt: codec='AAC'
    elif 'FLAC' in fmt: codec='FLAC'
    elif 'OPUS' in fmt: codec='Opus'
    elif 'PCM' in fmt: codec='PCM'
    else: codec=re.sub(r'[^A-Za-z0-9]','',fmt) or 'Audio'
    ch=track.get('Channels','')
    try:
        n=int(float(str(ch).split(' ')[0])); layout={1:'1.0',2:'2.0',6:'5.1',8:'7.1'}.get(n,f'{n}.0')
    except (ValueError,TypeError): layout=''
    atmos='Atmos' if 'ATMOS' in str(track.get('Format_AdditionalFeatures','')).upper() or 'ATMOS' in str(track.get('CommercialName','')).upper() else ''
    return codec + (layout if layout else '') + ('.'+atmos if atmos else '')

def audio_rank(track):
    # Priorização por qualidade de formato; em empate, maior número de canais.
    fmt=(str(track.get('Format',''))+' '+str(track.get('Format_Profile',''))).upper()
    if 'TRUEHD' in fmt or 'MLP FBA' in fmt: score=100
    elif 'DTS-HD' in fmt and ('MA' in fmt or 'MASTER' in fmt):score=95
    elif 'FLAC' in fmt or 'PCM' in fmt:score=90
    elif 'DTS-HD' in fmt:score=85
    elif 'DTS' in fmt:score=70
    elif 'E-AC-3' in fmt or 'EAC3' in fmt:score=60
    elif 'AC-3' in fmt or 'AC3' in fmt:score=50
    elif 'AAC' in fmt:score=40
    else:score=10
    try:channels=int(float(str(track.get('Channels','0')).split(' ')[0]))
    except (TypeError,ValueError):channels=0
    return score,channels

def detect_hdr(video):
    """DV precede HDR, quando ambos estão presentes."""
    fields=('HDR_Format','HDR_Format_String','HDR_Format_Commercial','HDR_Format_Compatibility',
            'HDR_Format_Profile','HDR_Format_Version','colour_primaries',
            'transfer_characteristics','color_transfer','hdr_info','side_data_list')
    values=' '.join(str(video.get(k,'')) for k in fields).upper()
    values+=' '+str(video.get('tags',{})).upper()+' '+str(video.get('codec_tag_string','')).upper()
    # Evita falso positivo de PQ como trecho de outras palavras.
    values=re.sub(r'\bPQ\b','SMPTE ST 2084',values)
    if any(token in values for token in ('DOLBY VISION','DOLBY_VISION','DOVI','DVHE','DVH1','DOVI CONFIGURATION RECORD','DOVI_CONFIGURATION_RECORD')):
        return '.DV.HDR' if any(token in values for token in ('HDR10','HDR10+','SMPTE ST 2084','SMPTE2084','ARIB-STD-B67','PQ','HLG','BT2020','BT.2020')) else '.DV'
    if any(token in values for token in ('HDR10','HDR10+','SMPTE ST 2084','SMPTE2084','ARIB-STD-B67','PQ','HLG','BT2020','BT.2020')):
        return '.HDR'
    return ''

def has_dual(tracks):
    """Detecta dois ou mais idiomas distintos nas faixas de áudio.

    Regiões (pt-BR/pt-PT) não contam como idiomas distintos; códigos
    ISO-639 de duas/três letras e nomes frequentes são normalizados.
    Faixas sem idioma definido não contam como um idioma adicional.
    """
    aliases = {
        'por':'pt', 'portuguese':'pt', 'portugues':'pt', 'português':'pt',
        'eng':'en', 'english':'en', 'ingles':'en', 'inglês':'en',
        'jpn':'ja', 'japanese':'ja', 'japones':'ja', 'japonês':'ja',
        'spa':'es', 'esp':'es', 'spanish':'es', 'espanol':'es', 'español':'es',
        'fra':'fr', 'fre':'fr', 'french':'fr',
        'deu':'de', 'ger':'de', 'german':'de',
        'ita':'it', 'italian':'it',
        'kor':'ko', 'korean':'ko',
        'zho':'zh', 'chi':'zh', 'chinese':'zh',
        'rus':'ru', 'russian':'ru',
        'ara':'ar', 'arabic':'ar',
        'hin':'hi', 'hindi':'hi',
        'nld':'nl', 'dut':'nl', 'dutch':'nl',
        'swe':'sv', 'swedish':'sv',
        'pol':'pl', 'polish':'pl',
        'tur':'tr', 'turkish':'tr',
        'ces':'cs', 'cze':'cs', 'czech':'cs',
        'dan':'da', 'danish':'da',
        'fin':'fi', 'finnish':'fi',
        'nor':'no', 'norwegian':'no',
        'heb':'he', 'hebrew':'he',
        'ell':'el', 'gre':'el', 'greek':'el',
        'tha':'th', 'thai':'th',
        'vie':'vi', 'vietnamese':'vi',
        'ind':'id', 'indonesian':'id',
        'ukr':'uk', 'ukrainian':'uk',
    }
    unknown={'', 'und', 'undefined', 'unknown', 'unk', 'mul', 'zxx', 'mis', 'none', 'null'}
    langs=set()
    for track in tracks:
        if track.get('@type')!='Audio':
            continue
        raw=str(track.get('Language') or track.get('Language_String3') or track.get('Language_String') or '').strip().lower()
        # pt-BR e pt-PT são ambos português; en-US e en-GB são inglês.
        base=raw.replace('_','-').split('-',1)[0]
        lang=aliases.get(base,base)
        if lang in unknown:
            continue
        langs.add(lang)
        if len(langs)>=2:
            return True
    return False

def analyze(path):
    tracks=mediainfo(path)
    video=next((x for x in tracks if x.get('@type')=='Video'),None)
    audios=[x for x in tracks if x.get('@type')=='Audio']
    if not video:raise ValueError('Faixa de vídeo não encontrada')
    return tracks,video,max(audios,key=audio_rank,default=None)

def get_name(path,source,group,title,episode,dual,template='Scene/P2P'):

    tracks,video,audio=analyze(path)
    height=int(float(str(video.get('Height','0')).split(' ')[0] or 0))
    width=int(float(str(video.get('Width','0')).split(' ')[0] or 0))
    resolution='2160p' if height>=2000 else '1080p' if height>=1000 else '720p' if height>=700 else '576p' if height>=550 else '480p' if height else f'{width}w'
    vf=str(video.get('Format','')).upper()
    vc=next((v for k,v in VIDEO.items() if k in vf),'Video')
    ac=codec_audio(audio) if audio else 'NoAudio'
    hdr=detect_hdr(video)
    title=re.sub(r'[ ._-]+','.',title).strip('.')
    if template=='Simples':return f'{title}{"."+episode if episode else ""}{path.suffix}'
    return f'{title}{"." + episode if episode else ""}.{resolution}.{source}.{ac}{hdr}.{vc}{".DUAL" if dual else ""}{"-" + group if group else ""}{path.suffix}'

class App:
    def __init__(self,root):
        self.root=root;root.title(APP);root.geometry('1120x720');root.minsize(900,600);root.configure(bg='#080808')
        style=ttk.Style();style.theme_use('clam')
        style.configure('.',background='#080808',foreground='#edf2fa',fieldbackground='#171717',font=('Segoe UI',10))
        style.configure('TButton',padding=8,background='#252525',foreground='white');style.map('TButton',background=[('active','#383838')])
        style.configure('TEntry',fieldbackground='#171717',foreground='white')
        style.configure('TCombobox',fieldbackground='#171717',background='#252525',foreground='#ffffff',arrowcolor='#ffffff',selectbackground='#171717',selectforeground='#ffffff')
        style.map('TCombobox',fieldbackground=[('readonly','#171717'),('disabled','#222222')],foreground=[('readonly','#ffffff'),('disabled','#999999')],selectbackground=[('readonly','#171717')],selectforeground=[('readonly','#ffffff')],background=[('readonly','#252525')],arrowcolor=[('readonly','#ffffff')])
        root.option_add('*TCombobox*Listbox.background','#171717')
        root.option_add('*TCombobox*Listbox.foreground','#ffffff')
        root.option_add('*TCombobox*Listbox.selectBackground','#333d50')
        root.option_add('*TCombobox*Listbox.selectForeground','#ffffff')
        style.configure('Treeview',background='#111111',fieldbackground='#111111',foreground='#edf2fa',rowheight=27)
        style.configure('Treeview.Heading',background='#252525',foreground='white',font=('Segoe UI',10,'bold'))
        header=tk.Frame(root,bg='#080808')
        header.pack(fill='x',padx=18,pady=(15,4))
        tk.Label(header,text='MKV Renamer',bg='#080808',fg='#f2f6fc',font=('Segoe UI',19,'bold')).pack(side='left')
        ttk.Button(header,text='Sobre',command=self.show_about).pack(side='right')
        tk.Label(root,text='Selecione uma pasta de série ou use Arquivo; resolução e codecs automáticos',bg='#080808',fg='#aab8c9').pack(anchor='w',padx=18)
        bar=ttk.Frame(root);bar.pack(fill='x',padx=18,pady=14)
        ttk.Button(bar,text='Selecionar pasta',command=self.pick).pack(side='left')
        ttk.Button(bar,text='Selecionar arquivo',command=self.pick_file).pack(side='left',padx=(8,0))
        self.file_path=None;self.txt_names=None;self.folder=tk.StringVar();ttk.Entry(bar,textvariable=self.folder).pack(side='left',fill='x',expand=True,padx=8)
        opts=ttk.Frame(root);opts.pack(fill='x',padx=18,pady=(0,8))
        ttk.Label(opts,text='Nome da série:').pack(side='left')
        self.title=tk.StringVar();ttk.Entry(opts,textvariable=self.title,width=37).pack(side='left',padx=(7,18))
        ttk.Label(opts,text='Fonte:').pack(side='left')
        self.settings_path=Path(os.environ.get('APPDATA', str(Path.home()))) / 'MKV_Renamer' / 'settings.json'
        try:
            saved=json.loads(self.settings_path.read_text(encoding='utf-8'))
            if not isinstance(saved,dict):saved={}
        except (OSError,ValueError):saved={}
        self.default_sources=['WEB-DL','WEB-DL.NF','WEB-DL.AMZN','WEB-DL.DSNP','WEB-DL.ATVP','WEB-DL.MAX','WEB-DL.HMAX','WEB-DL.HULU','WEB-DL.PMTP','WEB-DL.PCOK','WEB-DL.CR','WEBRip','BluRay','BluRay.REMUX','UHD.BluRay','UHD.BluRay.REMUX','BDRip','BRRip','DVDRip','TVRip','VHSRip','DVD','DVD.REMUX','HDTV']
        custom=saved.get('custom_sources',[])
        self.custom_sources=[x for x in custom if isinstance(x,str) and re.fullmatch(r'[A-Za-z0-9.-]+',x) and x.casefold() not in {v.casefold() for v in self.default_sources}] if isinstance(custom,list) else []
        self.custom_sources=list(dict.fromkeys(self.custom_sources))
        self.source=tk.StringVar(value=saved.get('source','WEB-DL'))
        self.source_combo=ttk.Combobox(opts,textvariable=self.source,values=self.default_sources+self.custom_sources+['+ Adicionar nova fonte...'],width=16,state='readonly')
        if self.source.get() not in self.default_sources+self.custom_sources:self.source.set('WEB-DL')
        self.source_combo.pack(side='left',padx=(7,5))
        self.source_combo.bind('<<ComboboxSelected>>',self.on_source_selected)
        self.previous_source=self.source.get()
        ttk.Button(opts,text='Gerenciar fontes',command=self.manage_sources).pack(side='left',padx=(0,12))
        self.auto_dual=tk.BooleanVar(value=True)
        ttk.Checkbutton(opts,text='DUAL automático',variable=self.auto_dual).pack(side='left',padx=(0,12))
        ttk.Label(opts,text='Grupo:').pack(side='left')
        self.group=tk.StringVar(value=saved.get('group',''));ttk.Entry(opts,textvariable=self.group,width=17).pack(side='left',padx=7)
        seasonbar=ttk.Frame(root);seasonbar.pack(fill='x',padx=18,pady=(0,12))
        ttk.Label(seasonbar,text='Temporada:').pack(side='left')
        self.season=tk.StringVar(value='S01');ttk.Combobox(seasonbar,textvariable=self.season,values=[f'S{i:02d}' for i in range(1,101)],width=6).pack(side='left',padx=(7,18))
        ttk.Label(seasonbar,text='Episódio inicial:').pack(side='left')
        self.start_ep=tk.StringVar(value='EP01');ttk.Combobox(seasonbar,textvariable=self.start_ep,values=[f'EP{i:02d}' for i in range(1,201)],width=7).pack(side='left',padx=(7,18))
        ttk.Label(seasonbar,text='Quantidade de episódios:').pack(side='left')
        self.count=tk.StringVar(value='');ttk.Entry(seasonbar,textvariable=self.count,width=7).pack(side='left',padx=(7,18))
        ttk.Button(seasonbar,text='Analisar / Pré-visualizar',command=self.preview).pack(side='left',padx=8)
        ttk.Button(seasonbar,text='Renomear arquivos',command=self.rename).pack(side='left')
        ttk.Button(seasonbar,text='Renomear por TXT',command=self.pick_txt).pack(side='left',padx=8)
        ttk.Button(seasonbar,text='Detectar automaticamente',command=self.clear_txt).pack(side='left',padx=4)
        extras=ttk.Frame(root);extras.pack(fill='x',padx=18,pady=(0,8))
        self.recursive=tk.BooleanVar(value=False)
        ttk.Checkbutton(extras,text='Incluir subpastas',variable=self.recursive).pack(side='left')
        ttk.Label(extras,text='Padrão:').pack(side='left',padx=(15,5))
        self.template=tk.StringVar(value='Scene/P2P')
        ttk.Combobox(extras,textvariable=self.template,values=['Scene/P2P','Simples'],width=15,state='readonly').pack(side='left')
        ttk.Button(extras,text='Editar nome',command=self.edit_name).pack(side='left',padx=6)
        ttk.Button(extras,text='Desfazer',command=self.undo).pack(side='left',padx=6)

        outputbar=ttk.Frame(root);outputbar.pack(fill='x',padx=18,pady=(0,9))
        self.copy_mode=tk.BooleanVar(value=saved.get('copy_mode',True))
        ttk.Radiobutton(outputbar,text='Copiar e renomear (preserva originais)',variable=self.copy_mode,value=True).pack(side='left')
        ttk.Radiobutton(outputbar,text='Renomear arquivos originais',variable=self.copy_mode,value=False).pack(side='left',padx=12)
        outrow=ttk.Frame(root);outrow.pack(fill='x',padx=18,pady=(0,8))
        ttk.Label(outrow,text='Pasta de saída:').pack(side='left')
        self.output_dir=tk.StringVar(value=saved.get('output_dir',''))
        ttk.Entry(outrow,textvariable=self.output_dir).pack(side='left',fill='x',expand=True,padx=8)
        ttk.Button(outrow,text='Escolher pasta de saída',command=self.pick_output).pack(side='left')
        self.progress=tk.DoubleVar(value=0)
        style.configure('Green.Horizontal.TProgressbar', troughcolor='#242424', background='#22c55e', lightcolor='#22c55e', darkcolor='#22c55e', bordercolor='#242424', thickness=15)
        self.progressbar=ttk.Progressbar(root,variable=self.progress,maximum=100,style='Green.Horizontal.TProgressbar')
        self.progressbar.pack(fill='x',padx=18,pady=(0,3))
        self.progress_label=tk.StringVar(value='0%')
        self.progress_text=tk.Label(root,textvariable=self.progress_label,anchor='center',bg='#080808',fg='#edf2fa',font=('Segoe UI',10,'bold'))
        self.progress_text.pack(fill='x',padx=18,pady=(0,7))
        frame=ttk.Frame(root);frame.pack(fill='both',expand=True,padx=18)
        self.tree=ttk.Treeview(frame,columns=('old','new','status'),show='headings',selectmode='extended')
        for key,label,w in [('old','Nome atual',310),('new','Novo nome',490),('status','Status',160)]:self.tree.heading(key,text=label);self.tree.column(key,width=w,stretch=key!='status')
        sy=ttk.Scrollbar(frame,orient='vertical',command=self.tree.yview);self.tree.configure(yscrollcommand=sy.set);self.tree.pack(side='left',fill='both',expand=True);sy.pack(side='right',fill='y')
        self.tree.tag_configure('success',foreground='#4ade80')
        self.tree.tag_configure('error',foreground='#ff5a5f')
        self.tree.bind('<Double-1>',self.edit_name)
        try:
            from tkinterdnd2 import DND_FILES
            root.drop_target_register(DND_FILES)
            root.dnd_bind('<<Drop>>',self.on_drop)
        except (ImportError,AttributeError):pass
        self.status=tk.StringVar(value='0% — Selecione uma pasta para começar.')
        self.status_label=tk.Label(root,textvariable=self.status,bg='#080808',fg='#edf2fa',anchor='w',font=('Segoe UI',10,'bold'))
        self.status_label.pack(anchor='w',padx=18,pady=13)
        self.auto_dual.trace_add('write',self.save_preferences)
        self.source.trace_add('write',self.save_preferences)
        self.group.trace_add('write',self.save_preferences)
        self.output_dir.trace_add('write',self.save_preferences)
        self.copy_mode.trace_add('write',self.save_preferences)
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.items=[];self.busy=False;self.q=queue.Queue();root.after(100,self.poll)
        self.history_path=self.settings_path.with_name('historico.json')
    def refresh_sources(self):
        self.source_combo.configure(values=self.default_sources+self.custom_sources+['+ Adicionar nova fonte...'])

    def on_source_selected(self,event=None):
        if self.source.get()=='+ Adicionar nova fonte...':
            self.source.set(getattr(self,'previous_source','WEB-DL'))
            self.manage_sources(add_now=True)
        else:
            self.previous_source=self.source.get()

    def manage_sources(self,add_now=False):
        dialog=tk.Toplevel(self.root)
        dialog.title('Gerenciar fontes personalizadas')
        dialog.configure(bg='#101010')
        dialog.geometry('440x390')
        dialog.resizable(False,False)
        dialog.transient(self.root)
        dialog.grab_set()
        frame=tk.Frame(dialog,bg='#101010',padx=22,pady=20)
        frame.pack(fill='both',expand=True)
        tk.Label(frame,text='Fontes personalizadas',bg='#101010',fg='white',font=('Segoe UI',16,'bold')).pack(anchor='w',pady=(0,12))
        tk.Label(frame,text='Digite uma fonte (letras, números, ponto ou hífen):',bg='#101010',fg='#dddddd').pack(anchor='w')
        field=tk.StringVar()
        entry=ttk.Entry(frame,textvariable=field)
        entry.pack(fill='x',pady=(6,9))
        listbox=tk.Listbox(frame,bg='#1a1a1a',fg='white',selectbackground='#38533e',selectforeground='white',relief='flat',height=8,exportselection=False)
        listbox.pack(fill='both',expand=True,pady=(8,10))
        def update_list():
            listbox.delete(0,'end')
            for item in self.custom_sources:listbox.insert('end',item)
        def add():
            name=field.get().strip()
            if not re.fullmatch(r'[A-Za-z0-9.-]+',name):
                return messagebox.showerror('Fonte inválida','Use apenas letras, números, pontos e hífens.',parent=dialog)
            if name.casefold() in {x.casefold() for x in self.default_sources+self.custom_sources}:
                return messagebox.showwarning('Fonte duplicada','Essa fonte já está cadastrada.',parent=dialog)
            self.custom_sources.append(name)
            self.refresh_sources()
            self.source.set(name)
            self.previous_source=name
            self.save_preferences()
            update_list()
            field.set('')
        def remove():
            selection=listbox.curselection()
            if not selection:return
            name=self.custom_sources[selection[0]]
            self.custom_sources.remove(name)
            if self.source.get()==name:self.source.set('WEB-DL')
            self.previous_source=self.source.get()
            self.refresh_sources()
            self.save_preferences()
            update_list()
        controls=ttk.Frame(frame)
        controls.pack(fill='x')
        ttk.Button(controls,text='Adicionar',command=add).pack(side='left')
        ttk.Button(controls,text='Excluir selecionada',command=remove).pack(side='left',padx=8)
        ttk.Button(controls,text='Fechar',command=dialog.destroy).pack(side='right')
        entry.bind('<Return>',lambda event:add())
        update_list()
        dialog.update_idletasks()
        x=self.root.winfo_rootx()+max(0,(self.root.winfo_width()-dialog.winfo_width())//2)
        y=self.root.winfo_rooty()+max(0,(self.root.winfo_height()-dialog.winfo_height())//2)
        dialog.geometry(f'+{x}+{y}')
        entry.focus_set()

    def show_about(self):
        """Janela Sobre com tema escuro e sem alterar o processamento."""
        dialog=tk.Toplevel(self.root)
        dialog.title('Sobre — MKV Renamer')
        dialog.configure(bg='#101010')
        dialog.geometry('460x395')
        dialog.resizable(False,False)
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.protocol('WM_DELETE_WINDOW',dialog.destroy)
        content=tk.Frame(dialog,bg='#101010',padx=28,pady=22)
        content.pack(fill='both',expand=True)
        tk.Label(content,text='MKV Renamer',bg='#101010',fg='#ffffff',font=('Segoe UI',21,'bold')).pack(anchor='center',pady=(4,2))
        tk.Label(content,text='Versão 1.0.0  •  By Tokon',bg='#101010',fg='#70d990',font=('Segoe UI',11,'bold')).pack(anchor='center',pady=(0,18))
        tk.Frame(content,bg='#343434',height=1).pack(fill='x',pady=(0,16))
        description=('Renomeador de filmes e séries para Windows.\n'
                     'Detecta características de áudio e vídeo,\n'
                     'permite renomear por lista TXT e copiar para\n'
                     'uma pasta de saída sem alterar os originais.')
        tk.Label(content,text=description,bg='#101010',fg='#d9d9d9',font=('Segoe UI',10),justify='center').pack(pady=(0,15))
        tk.Label(content,text='Desenvolvido por Tokon',bg='#101010',fg='#a6a6a6',font=('Segoe UI',9)).pack(pady=(0,6))
        tk.Label(content,text='Licença: MIT',bg='#101010',fg='#d9d9d9',font=('Segoe UI',9)).pack(pady=(0,4))
        tk.Label(content,text='Ano: 2026',bg='#101010',fg='#d9d9d9',font=('Segoe UI',9)).pack(pady=(0,4))
        ttk.Button(content,text='Fechar',command=dialog.destroy).pack()
        dialog.update_idletasks()
        x=self.root.winfo_rootx()+max(0,(self.root.winfo_width()-dialog.winfo_width())//2)
        y=self.root.winfo_rooty()+max(0,(self.root.winfo_height()-dialog.winfo_height())//2)
        dialog.geometry(f'+{x}+{y}')
        dialog.focus_set()

    def save_preferences(self,*_):
        try:
            self.settings_path.parent.mkdir(parents=True,exist_ok=True)
            data={'source':self.source.get(),'custom_sources':self.custom_sources,'group':self.group.get(),'auto_dual':self.auto_dual.get(),'output_dir':self.output_dir.get(),'copy_mode':self.copy_mode.get()}
            self.settings_path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        except OSError:
            pass

    def pick_output(self):
        folder=filedialog.askdirectory(title='Selecionar pasta de saída',initialdir=self.output_dir.get() if Path(self.output_dir.get()).is_dir() else None)
        if folder:self.output_dir.set(folder)

    def close(self):
        self.save_preferences()
        self.root.destroy()

    def on_drop(self,event):
        try:paths=self.root.tk.splitlist(event.data)
        except tk.TclError:return
        if not paths:return
        p=Path(paths[0])
        if p.is_dir():
            self.file_path=None;self.txt_names=None;self.folder.set(str(p));self.autofill_series(p)
        elif p.is_file() and p.suffix.lower() in ('.mkv','.mp4','.avi','.m4v','.ts'):
            self.file_path=p;self.txt_names=None;self.folder.set(str(p));self.title.set(re.sub(r'[._]+',' ',p.stem))
        self.status.set('Arquivo ou pasta recebido. Confira os campos e analise.')

    def pick(self):
        p=filedialog.askdirectory();
        if p:
            self.file_path=None;self.folder.set(p)
            self.autofill_series(Path(p))
    def autofill_series(self, folder):
        videos=sorted((p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ('.mkv','.mp4','.avi','.m4v','.ts')),key=lambda p:p.name.casefold())
        if not videos:return
        try:
            name,_=parse_episode(videos[0].stem)
        except ValueError:
            return
        name=re.sub(r'[._]+',' ',name).strip()
        if name:self.title.set(name)

    def pick_file(self):
        selected=filedialog.askopenfilename(title='Selecionar filme',filetypes=[('Vídeos','*.mkv *.mp4 *.avi *.m4v *.ts'),('Todos os arquivos','*.*')])
        if not selected:return
        self.file_path=Path(selected);self.txt_names=None
        self.folder.set(str(self.file_path))
        stem=self.file_path.stem
        # Conserva ano de lançamento quando identificado e elimina tags técnicas comuns.
        match=re.search(r'(?i)(?:^|[ ._-])(?:19|20)\\d{2}(?=$|[ ._-])',stem)
        if match:
            name=stem[:match.end()].strip(' ._-')
        else:
            match=re.search(r'(?i)[ ._-](?:2160p|1080p|720p|480p|WEB[-.]DL|BluRay|DVD|HDR|HEVC|x264|x265)(?=$|[ ._-])',stem)
            name=stem[:match.start()] if match else stem
        self.title.set(re.sub(r'[._]+',' ',name).strip())
        self.status.set('Modo filme: selecione a fonte, confira o título e clique em Analisar / Pré-visualizar.')

    def clear_txt(self):
        self.txt_names=None
        self.items=[]
        self.tree.delete(*self.tree.get_children())
        self.status.set('Detecção automática ativada. Clique em Analisar / Pré-visualizar.')

    def pick_txt(self):
        selected=filedialog.askopenfilename(title='Selecionar lista de nomes',filetypes=[('Bloco de notas','*.txt')])
        if not selected:return
        try:
            lines=Path(selected).read_text(encoding='utf-8-sig').splitlines()
        except UnicodeDecodeError:
            lines=Path(selected).read_text(encoding='cp1252').splitlines()
        names=[line.strip() for line in lines if line.strip()]
        if not names:return messagebox.showerror('Lista TXT','O arquivo TXT está vazio.')
        self.txt_names=names
        self.file_path=None
        folder=Path(self.folder.get())
        if not folder.is_dir():
            chosen=filedialog.askdirectory(title='Selecione a pasta com os vídeos que serão renomeados')
            if not chosen:return
            self.folder.set(chosen)
        self.preview()

    def preview(self):
        if self.busy:return
        movie=self.file_path is not None
        folder=self.file_path.parent if movie else Path(self.folder.get())
        group=self.group.get().strip();source=self.source.get().strip()
        if not folder.is_dir():return messagebox.showerror('Pasta inválida','Selecione uma pasta válida.')
        if self.txt_names is None and group and not re.fullmatch(r'[\w-]+',group,flags=re.UNICODE):return messagebox.showerror('Grupo inválido','Use letras, números, _ ou - no grupo.')
        if self.txt_names is None and (not source or not re.fullmatch(r'[A-Za-z0-9.-]+',source)):return messagebox.showerror('Fonte inválida','Informe uma fonte válida.')
        title=self.title.get().strip()
        if not title and self.txt_names is None:return messagebox.showerror('Série','Digite o nome da série.')
        sm=re.fullmatch(r'S(\d{1,3})',self.season.get().strip(),re.I)
        em=re.fullmatch(r'(?:EP|E)(\d{1,3})',self.start_ep.get().strip(),re.I)
        if not movie and self.txt_names is None and (not sm or not em):return messagebox.showerror('Episódios','Use temporada S01 e episódio inicial EP01.')
        season=int(sm.group(1)) if sm else 0;first=int(em.group(1)) if em else 0
        if not movie and self.txt_names is None and (season<1 or first<1):return messagebox.showerror('Episódios','Temporada e episódio devem ser maiores que zero.')
        iterator=folder.rglob('*') if self.recursive.get() else folder.iterdir()
        output_resolved=Path(self.output_dir.get()).resolve() if self.copy_mode.get() and self.output_dir.get().strip() else None
        paths=[self.file_path] if movie else sorted((p for p in iterator if p.is_file() and (output_resolved is None or output_resolved not in p.resolve().parents) and p.suffix.lower() in ('.mkv','.mp4','.avi','.m4v','.ts')),key=lambda p:str(p.relative_to(folder)).casefold())
        try:count=1 if movie else (len(paths) if self.txt_names is not None else int(self.count.get().strip()))
        except ValueError:return messagebox.showerror('Quantidade','Digite a quantidade de episódios.')
        if self.txt_names is not None and len(self.txt_names)!=len(paths):return messagebox.showerror('Lista TXT',f'O TXT tem {len(self.txt_names)} linhas, mas a pasta tem {len(paths)} vídeos.')
        if not movie and self.txt_names is None and (count<1 or count!=len(paths)):return messagebox.showerror('Quantidade',f'Você informou {count} episódio(s), mas a pasta contém {len(paths)} vídeo(s). Separe somente os episódios desejados nessa pasta.')
        title=re.sub(r'[ ._-]+','.',title).strip('.')
        if not title and self.txt_names is None:return messagebox.showerror('Série','Nome da série inválido.')
        auto_dual=self.auto_dual.get();template=self.template.get()
        self.tree.delete(*self.tree.get_children());self.items=[];self.busy=True;self.status.set(f'Analisando {len(paths)} arquivo(s)...')
        def worker():
            for index,p in enumerate(paths):
                episode='' if movie else f'S{season:02d}E{first+index:02d}'
                try:
                    if self.txt_names is not None:
                        proposed=self.txt_names[index]
                        if '/' in proposed or '\\\\' in proposed or proposed in ('.','..') or re.search(r'[<>:"|?*]',proposed) or proposed.endswith(('.', ' ')):
                            raise ValueError('Nome inválido na lista TXT')
                        ext=Path(proposed).suffix.lower()
                        if ext and ext in ('.mkv','.mp4','.avi','.m4v','.ts'):
                            if ext != p.suffix.lower():raise ValueError('Extensão diferente da original')
                            name=proposed
                        else:
                            name=proposed+p.suffix
                    else:
                        selected_dual=has_dual(mediainfo(p)) if auto_dual else False
                        name=get_name(p,source,group,title,episode,selected_dual,template)
                    self.q.put(('item',p,name,''))
                except Exception as e:self.q.put(('item',p,'',str(e)))
            self.q.put(('done',))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            for _ in range(80):
                msg=self.q.get_nowait()
                if msg[0]=='item':
                    _,p,new,error=msg;self.items.append((p,new,error));self.tree.insert('', 'end',values=(p.name,new,error or 'Pronto'),tags=('error',) if error else ())
                elif msg[0]=='done':self.busy=False;self.status.set(f'{len(self.items)} arquivo(s) analisado(s). Confira antes de renomear.')
                elif msg[0]=='progress':
                    _,done,total,p,status=msg
                    if not self.copy_mode.get():
                        pct=done/total*100
                        self.progress.set(pct)
                        self.progress_label.set(f'{pct:.0f}%')
                    self.status.set(f'Processando {done}/{total} — {self.progress.get():.0f}%: {p.name}')
                    for row,(item_p,_,_) in zip(self.tree.get_children(),self.items):
                        if item_p==p:
                            self.tree.set(row,'status',status)
                            self.tree.item(row,tags=('error',) if status.startswith('Erro:') else ('success',))
                            break
                elif msg[0]=='byte_progress':
                    _,copied,total_bytes=msg
                    pct=min(100.0,100.0*copied/max(total_bytes,1))
                    self.progress.set(pct)
                    self.progress_label.set(f'{pct:.0f}%')
                    self.status.set(f'Copiando e renomeando: {pct:.0f}%')
                elif msg[0]=='finished':
                    _,results,history,was_copy=msg
                    self.busy=False
                    if history:
                        try:
                            self.history_path.parent.mkdir(parents=True,exist_ok=True)
                            self.history_path.write_text(json.dumps({'when':datetime.datetime.now().isoformat(),'items':history},ensure_ascii=False,indent=2),encoding='utf-8')
                        except OSError:pass
                    ok=len(history);failed=len(results)-ok
                    self.progress.set(100)
                    self.progress_label.set('100%')
                    self.status.set(f'100% — Finalizado! {ok} arquivo(s) concluído(s); {failed} erro(s).')
                    messagebox.showinfo('Finalizado',f'Processamento finalizado!\\n{ok} arquivo(s) '+('copiado(s)' if was_copy else 'renomeado(s)')+f'.\\n{failed} erro(s).')
        except queue.Empty:pass
        self.root.after(50,self.poll)
    def edit_name(self,event=None):
        selected=self.tree.selection()
        if not selected:return messagebox.showinfo('Editar nome','Selecione uma linha da prévia.')
        item=selected[0];idx=self.tree.index(item)
        p,name,error=self.items[idx]
        dialog=tk.Toplevel(self.root);dialog.title('Editar novo nome');dialog.configure(bg='#111111');dialog.geometry('690x135');dialog.transient(self.root);dialog.grab_set()
        tk.Label(dialog,text='Novo nome (incluindo a extensão):',bg='#111111',fg='white').pack(anchor='w',padx=12,pady=8)
        value=tk.StringVar(value=name or p.name)
        entry=ttk.Entry(dialog,textvariable=value);entry.pack(fill='x',padx=12);entry.focus_set()
        def save():
            new=value.get().strip()
            if not new or new in ('.','..') or '/' in new or chr(92) in new or re.search(r'[<>:"|?*]',new) or new.endswith(('.', ' ')):
                return messagebox.showerror('Nome inválido','Digite um nome válido.',parent=dialog)
            if Path(new).suffix.lower()!=p.suffix.lower():
                return messagebox.showerror('Extensão','Mantenha a extensão original.',parent=dialog)
            self.items[idx]=(p,new,'');self.tree.set(item,'new',new);self.tree.set(item,'status','Editado');dialog.destroy()
        ttk.Button(dialog,text='Salvar nome',command=save).pack(pady=10)
        dialog.bind('<Return>',lambda _:save())

    def undo(self):
        try:data=json.loads(self.history_path.read_text(encoding='utf-8'));items=data['items']
        except (OSError,ValueError,KeyError):return messagebox.showinfo('Desfazer','Não há histórico salvo.')
        if not items:return messagebox.showinfo('Desfazer','Não há alterações para desfazer.')
        if not messagebox.askyesno('Desfazer',f'Desfazer {len(items)} operação(ões)? Cópias criadas serão excluídas; originais renomeados serão restaurados.'):return
        done=[];errors=[]
        for item in reversed(items):
            old=Path(item['old']);new=Path(item['new'])
            is_copy=item.get('operation')=='copy'
            if not new.is_file() or (not is_copy and old.exists()):errors.append(str(new));continue
            try:
                if is_copy:
                    # Nunca apague um arquivo que foi alterado desde a cópia.
                    if new.stat().st_size!=item.get('size') or new.stat().st_mtime_ns!=item.get('mtime_ns'):
                        errors.append(f'Arquivo modificado, não excluído: {new}');continue
                    new.unlink()
                else:new.rename(old)
                done.append(item)
            except OSError as e:errors.append(f'{new}: {e}')
        remaining=[item for item in items if item not in done]
        self.history_path.write_text(json.dumps({'items':remaining},ensure_ascii=False,indent=2),encoding='utf-8')
        messagebox.showinfo('Desfazer',f'{len(done)} restaurado(s). {len(errors)} não restaurado(s).')
        self.items=[];self.tree.delete(*self.tree.get_children())

    def rename(self):
        if self.busy:return
        if not self.items:return messagebox.showinfo('Aviso','Primeiro clique em Analisar / Pré-visualizar.')
        copy_mode=self.copy_mode.get()
        out=Path(self.output_dir.get().strip()) if self.output_dir.get().strip() else None
        if copy_mode and not out:return messagebox.showerror('Pasta de saída','Escolha uma pasta de saída antes de copiar.')
        if copy_mode:
            if not out.is_dir():return messagebox.showerror('Pasta de saída','A pasta de saída precisa existir.')
            out=out.resolve()
        source_root=Path(self.folder.get()).resolve()
        movie=self.file_path is not None
        ready=[]
        for p,n,e in self.items:
            if e or not n:continue
            if not copy_mode and p.name==n:continue
            if Path(n).name!=n or n in ('.','..') or re.search(r'[<>:"|?*]',n) or n.endswith(('.', ' ')):
                return messagebox.showerror('Nome inválido',f'Nome inválido: {n}')
            if copy_mode:
                # Mantém a estrutura das subpastas quando esta opção está ativa.
                relative=Path() if movie else p.parent.resolve().relative_to(source_root)
                target=out / relative / n
                if target.resolve()==p.resolve():
                    return messagebox.showerror('Pasta de saída','O destino coincide com o arquivo original.')
            else:target=p.with_name(n)
            ready.append((p,target))
        if not ready:return messagebox.showinfo('Aviso','Nenhuma alteração necessária.')
        targets=[str(t).casefold() for _,t in ready]
        if len(targets)!=len(set(targets)):return messagebox.showerror('Conflito','Dois arquivos teriam o mesmo destino.')
        for p,target in ready:
            if target.exists():return messagebox.showerror('Conflito',f'Arquivo de destino já existe: {target}')
        verb='Copiar e renomear' if copy_mode else 'Renomear'
        if not messagebox.askyesno('Confirmar',f'{verb} {len(ready)} arquivo(s)?\\n'+
                ('Os arquivos originais serão preservados.' if copy_mode else 'Os nomes originais serão alterados.')):return
        self.busy=True;self.progress.set(0);self.progress_label.set('0%')
        self.status_label.configure(fg='#edf2fa');self.progress_text.configure(fg='#edf2fa')
        self.status.set(f'{verb}: 0% — iniciando...')
        def worker():
            results={};history=[];total=len(ready)
            total_bytes=sum(p.stat().st_size for p,_ in ready) if copy_mode else 0
            copied_bytes=0
            last_percent=-1
            for index,(p,target) in enumerate(ready):
                try:
                    target.parent.mkdir(parents=True,exist_ok=True)
                    if target.exists():raise FileExistsError('O destino já existe.')
                    if copy_mode:
                        # O arquivo temporário fica no mesmo volume do destino.
                        temp=target.with_name(target.name+'.mkvrenamer-part')
                        if temp.exists():raise FileExistsError(f'Arquivo temporário já existe: {temp}')
                        try:
                            with p.open('rb') as src, temp.open('xb') as dst:
                                while True:
                                    block=src.read(4*1024*1024)
                                    if not block:break
                                    dst.write(block)
                                    copied_bytes+=len(block)
                                    current_percent=int(copied_bytes*100/max(total_bytes,1))
                                    if current_percent!=last_percent:
                                        last_percent=current_percent
                                        self.q.put(('byte_progress',copied_bytes,total_bytes))
                            shutil.copystat(p,temp)
                            if target.exists():raise FileExistsError('O destino foi criado durante a cópia.')
                            temp.rename(target)
                        except Exception:
                            try:temp.unlink(missing_ok=True)
                            except OSError:pass
                            raise
                        stat=target.stat()
                        history.append({'old':str(p),'new':str(target),'operation':'copy','size':stat.st_size,'mtime_ns':stat.st_mtime_ns})
                        results[str(p)]='Copiado'
                    else:
                        p.rename(target)
                        history.append({'old':str(p),'new':str(target),'operation':'rename'})
                        results[str(p)]='Renomeado'
                except Exception as exc:results[str(p)]=f'Erro: {exc}'
                if copy_mode and results[str(p)].startswith('Erro:'):
                    # Arquivos com erro não bloqueiam a conclusão visual do lote.
                    copied_bytes+=max(0,p.stat().st_size) if p.exists() else 0
                self.q.put(('progress',index+1,total,p,results[str(p)]))
            self.q.put(('finished',results,history,copy_mode))
        threading.Thread(target=worker,daemon=True).start()

if __name__=='__main__':
    root=tk.Tk();App(root);root.mainloop()
