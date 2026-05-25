from deep_translator import GoogleTranslator

def translate_notes(text, target_lang="hi"):
    try:
        translated = GoogleTranslator(source='auto', target=target_lang).translate(text)
        return translated
    except Exception as e:
        print("Translation Error:", e)
        return text