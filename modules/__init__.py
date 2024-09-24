def load_translator(cfg: dict):
    if cfg['type'] == 'openai':
        from .translate.openai_gpt import TranslateOpenAIGPT
        translator = TranslateOpenAIGPT()
    elif cfg['type'] == 'google_translate':
        from .translate.google_translate import TranslateGoogleTranslate
        translator = TranslateGoogleTranslate()
    elif cfg['type'] == 'ollama':
        from .translate.ollama_translate import TranslateOllama
        translator = TranslateOllama()
    elif cfg['type'] == 'qwen':
        from .translate.qwen_translate import TranslateQwen
        translator = TranslateQwen()
    else:
        raise("unknown translator")
    translator.init(cfg)
    return translator

def load_layout_engine(cfg: dict):
    if cfg['type'] == 'dit':
        from .layout.ditod import DiTLayout
        engine = DiTLayout()
        engine.init(cfg)
        return engine
    
    raise("unknown layout engine")

def load_ocr_engine(cfg: dict):
    if cfg['type'] == 'paddle':
        from .ocr.paddle import PaddleOCR
        engine = PaddleOCR()
        engine.init(cfg)
        return engine
    
    raise("unknown ocr engine")

def load_render_engine(cfg: dict):
    if cfg['type'] == 'simple':
        from .render.simple import SimpleRender
        engine = SimpleRender()
        engine.init(cfg)
        return engine
    elif cfg['type'] == 'reportlab':
        from .render.reportlab import ReportLabRender
        engine = ReportLabRender()
        engine.init(cfg)
        return engine
    
    raise("unknown ocr engine")