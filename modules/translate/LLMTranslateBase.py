from abc import ABC, abstractmethod
from tqdm import tqdm
from typing import List
from utils.layout_model import Layout
from threading import Thread
from .base import TranslateBase
from openai import OpenAI
from loguru import logger
from textdistance import levenshtein


langs = [
    "Albanian",
    "Arabic",
    "Armenian",
    "Awadhi",
    "Azerbaijani",
    "Bashkir",
    "Basque",
    "Belarusian",
    "Bengali",
    "Bhojpuri",
    "Bosnian",
    "Brazilian Portuguese",
    "Bulgarian",
    "Cantonese (Yue)",
    "Catalan",
    "Chhattisgarhi",
    "Chinese",
    "Croatian",
    "Czech",
    "Danish",
    "Dogri",
    "Dutch",
    "English",
    "Estonian",
    "Faroese",
    "Finnish",
    "French",
    "Galician",
    "Georgian",
    "German",
    "Greek",
    "Gujarati",
    "Haryanvi",
    "Hindi",
    "Hungarian",
    "Indonesian",
    "Irish",
    "Italian",
    "Japanese",
    "Javanese",
    "Kannada",
    "Kashmiri",
    "Kazakh",
    "Konkani",
    "Korean",
    "Kyrgyz",
    "Latvian",
    "Lithuanian",
    "Macedonian",
    "Maithili",
    "Malay",
    "Maltese",
    "Mandarin",
    "Mandarin Chinese",
    "Marathi",
    "Marwari",
    "Min Nan",
    "Moldovan",
    "Mongolian",
    "Montenegrin",
    "Nepali",
    "Norwegian",
    "Oriya",
    "Pashto",
    "Persian (Farsi)",
    "Polish",
    "Portuguese",
    "Punjabi",
    "Rajasthani",
    "Romanian",
    "Russian",
    "Sanskrit",
    "Santali",
    "Serbian",
    "Sindhi",
    "Sinhala",
    "Slovak",
    "Slovene",
    "Slovenian",
    "Ukrainian",
    "Urdu",
    "Uzbek",
    "Vietnamese",
    "Welsh",
    "Wu",
]


class LLMTranslateBase(TranslateBase):
    def init(self, cfg: dict):
        self.client: OpenAI = self.init_client(cfg)
        self.model = cfg["model"]
        self.from_lang = None
        self.to_lang = None
        self.check_response = None

    @abstractmethod
    def init_client(self, cfg: dict) -> OpenAI:
        pass

    def get_languages(self):
        return langs

    def get_response(self, messages: list):
        while True:
            try:
                response = self.client.chat.completions.create(
                    model=self.model, messages=messages
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.warning(f"Failed to get response: {e}, retrying...")

    def reformat_text(self, text):
        sys_prompt = """You are a text format checker now. The user will give you some reformatting tasks, you should just complete the task without any additional response. Return the result only."""
        prompt = (
            """I will give you some text which are recognized as list. But there are no \\n(newline) symbols in the text. What I want you do is reformatting the text with adding newline symbol into the text.
        Here is the text (pay attention to the numbering):\n"""
            + text
        )
        trial_time = 0
        while True:
            response: str = self.get_response(
                [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ]
            )
            _response = response.replace("\n", "")
            _text = text.replace("\n", "")
            if len(_response) != len(_text):
                dist = levenshtein.distance(_response, _text)
                if dist < max(len(text) * 0.05, 5):
                    break
                logger.warning(
                    f"Reformatting the text again(trial time {trial_time} / 3)"
                )
                trial_time += 1
                if trial_time == 3:
                    response = text
                    break
            else:
                break
        return response

    def model_check(self, text, translation):
        sys_prompt = f"You are a judger of {self.from_lang}-to-{self.to_lang} translation. Please check the translation of the following text and tell the user if the translation is correct.\nThe translation request is:\n- Keep all special characters / HTML tags / links as in the source text.\n- Return only {self.to_lang} translation.\n- The text may contain multiple lines.\nYou should check the translation by the rules before.\n And the judge request for you is:\n- If the translation is correct, answer 'correct' only, without any other contents.\n- If the translation is incorrect, asnwer 'incorrect' and provide the reason."
        user_prompt = f"<The text is> {text}\n<The translation is> {translation}"
        response = self.get_response(
            [
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
        if "incorrect" in response:
            self.check_response = response
            return False
        elif "correct" in response:
            return True
        else:
            logger.error(f"Unexpected response: {response}")
            return False

    def check_translation(self, text, translation):
        splitted_text = [line for line in text.split("\n") if line != ""]
        splitted_translation = [line for line in translation.split("\n") if line != ""]
        if len(splitted_text) != len(splitted_translation):
            return self.model_check(text, translation)
        return True

    def _check_reference_once(self, text):
        prompts = [
            {
                "role": "system",
                "content": """You are a content checker now. The user will give you some reference checking tasks, you should just complete the task without any additional response.\nMore specifically:\n- references usually contain a list of links or citations. Some times they are listed with numbers or bullet points.\n- answer "yes" if the text is a reference, "no" if it is not.\n- do not add any additional information to the text.\n\nFor example:\n"1. https://example.com" -> yes\n"[81] Qiyang Zhang, Xiang Li, Xiangying Che, Xiao Ma, Ao Zhou, Mengwei Xu, Shangguang Wang, Yun Ma, and Xuanzhe Liu. A comprehensive benchmark of deep learning libraries on mobile devices. In Proceedings of ACM WWW, 2022.\n[82] Pengfei Zhou, Yuanqing Zheng, and Mo Li. How long to wait? predicting bus arrival time with mobile phone based participatory sensing. Proceedings of ACM MobiSys, 2012." -> yes\nNote that all you output should be exactly one "yes" or "no".""",
            },
            {
                "role": "user",
                "content": f"Please check if the following text is a reference or not, remember to answer 'yes' or 'no' first:\n\n{text}",
            },
        ]
        response = self.get_response(prompts)
        if "yes" in response.lower():
            return True
        elif "no" in response.lower():
            return False
        else:
            raise ValueError(f"Invalid response: {response}")

    def check_reference(self, text):
        try:
            is_reference = self._check_reference_once(text)
        except Exception as e:
            is_reference = True
        # logger.info(f"{text} is reference: {is_reference}")
        if is_reference:
            _is, _is_not = 1, 0
            while (_is + _is_not) < 2 or _is == _is_not:
                try:
                    if self._check_reference_once(text):
                        _is += 1
                    else:
                        _is_not += 1
                except Exception as e:
                    logger.error(f"Failed to check the reference: {e}")
            if _is > _is_not:
                logger.info("Is reference, skip...")
                return True
        return False

    def translate(
        self, text: str, from_lang="ENGLISH", to_lang="SLOVENIAN"
    ) -> str | None:
        """
        Translates a given string into another language.

        Parameters:
        - text (str): The text to be translated.

        Returns:
        - str: The translated text.
        - None: If the translation failed or it should not be translated(eg. it is a reference).

        This method needs to be implemented by subclasses.
        """
        self.from_lang = from_lang
        self.to_lang = to_lang
        check_time = 0
        base_prompt = f"You are an {from_lang}-to-{to_lang} translator. (from_lang, to_lang)\n - Keep all special characters / HTML tags / links as in the source text. \n - Do not pay any attention to the http links in the text\n - Return the {to_lang} translation only.\n"
        while True:
            if self.check_response:
                prompt = f"{base_prompt}You have translated once before, but the feedback of your translation is bad, the feedback is {self.check_response}. Pay attention to your translation later.\nHere is the text to translate, return the translation only:\n\n{text}"
                self.check_response = None
            else:
                prompt = f"{base_prompt}Here is the text to translate, return the translation only:\n\n{text}"
            translated_text = self.get_response([{"role": "user", "content": prompt}])
            logger.debug(f"Translated text: {translated_text}")
            if self.check_translation(text, translated_text):
                return translated_text
            else:
                logger.warning(
                    f"Translating the text again:\nText: {text}\nTranslated text: {translated_text}"
                )
                check_time += 1
                if check_time >= 2:
                    logger.error(f"Failed to translate the text")
                    return None

    def translate_all(
        self, layout: List[Layout], from_lang, to_lang, multi_thread=False
    ):
        threads = []

        def translate_single_layout(i):
            line: Layout = layout[i]
            # Skip the reference
            if self.check_reference(line.text):
                layout[i].translated_text = None
                return
            # Reformat the list
            if line.type == "list":
                line.text = self.reformat_text(line.text)
            layout[i].translated_text = self.translate(line.text, from_lang, to_lang)

        progress = tqdm(
            total=len(layout), desc="Translating text", leave=False, dynamic_ncols=True
        )
        for i in range(len(layout)):
            if not layout[i].text:
                continue
            if multi_thread:
                t = Thread(target=translate_single_layout, args=(i,))
                threads.append(t)
                t.start()
            else:
                progress.update(1)
                translate_single_layout(i)
        if multi_thread:
            for t in threads:
                t.join()
        return layout
