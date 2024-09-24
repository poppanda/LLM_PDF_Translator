from pathlib import Path
from typing import Any
import os
import gradio as gr
import requests
from loguru import logger

TRANSLATE_URL = "http://localhost:8765/translate_pdf/"
CLEAR_TEMP_URL = "http://localhost:8765/clear_temp_dir/"


def translate_request(
    file: Any,
    from_lang: Any,
    to_lang: Any,
    translate_all: bool,
    from_page: int,
    to_page: int,
    render_mode: str,
) -> tuple[Path]:
    """Sends a POST request to the translator server to translate a PDF.

    Parameters
    ----------
    file : Any
        the PDF to be translated.

    Returns
    -------
    tuple[Path, list[Image.Image]]
        Path to the translated PDF and a list of images of the
        translated PDF.
    """
    render_mode = render_mode.lower().replace(" ", "_")
    response = requests.post(
        TRANSLATE_URL,
        files={"input_pdf": open(file.name, "rb")},
        data={
            "from_lang": from_lang,
            "to_lang": to_lang,
            "translate_all": translate_all,
            "p_from": from_page,
            "p_to": to_page,
            "render_mode": render_mode,
        },
    )

    if response.status_code == 200:
        with open("temp/translated.pdf", "wb") as f:
            f.write(response.content)

        return str("temp/translated.pdf")
    else:
        print(f"An error occurred: {response.status_code}")

def update_folder(folder, root_dirs: list, index: int):
    # folder, paths, index = args[0], args[1], args[2]
    root_dir = os.path.abspath(os.path.join(root_dirs[index], folder))
    root_dirs[index] = root_dir
    return gr.update(choices=[".."] + get_folders(root_dir), value=None), gr.update(value=f"# Download Folder: {root_dir}")

def get_folders(path):
    folders = []
    for folder in os.listdir(path):
        if os.path.isdir(os.path.join(path, folder)) and not folder.startswith("."):
            folders.append(folder)
    return folders

def download_and_translate(url_link, url_file_name, overwrite, from_lang, to_lang, translate_all, from_page, to_page, render_mode, add_blank_page, suffix, download_folder, translate_folder):
    if url_file_name == "":
        raise ValueError("Please enter a file name")
    elif url_file_name[-4:] != ".pdf":
        url_file_name += ".pdf"
    
    # check if the file exists in the translate_folder
    if os.path.exists(os.path.join(download_folder, url_file_name)):
        if not overwrite:
            raise ValueError(f"File {url_file_name} already exists in the folder {download_folder}")
    
    # download the file to download_folder
    logger.info(f"Downloading file from the url: {url_link}")
    response = requests.get(url_link)
    if response.status_code != 200:
        raise ValueError(f"An error occurred while downloading the file: {response.status_code}")
    with open(os.path.join(download_folder, url_file_name), "wb") as f:
        f.write(response.content)
    post_data = {
            'input_pdf_path': os.path.join(download_folder, url_file_name),
            'from_lang': from_lang,
            'to_lang': to_lang,
            'translate_all': translate_all,
            'p_from': from_page,
            'p_to': to_page,
            'render_mode': render_mode,
            'output_file_path': os.path.join(translate_folder, url_file_name.replace(".pdf", f"{suffix}.pdf")),
            'add_blank_page': add_blank_page,
        }
    logger.info(f"Post data: {post_data}")
    response = requests.post(
        TRANSLATE_URL,
        data=post_data,
    )

    if response.status_code == 200:
        with open("temp/translated.pdf", "wb") as f:
            f.write(response.content)

        return str("temp/translated.pdf")
    else:
        print(f"An error occurred: {response.status_code}")

def translate_range_widget():
    def _click_translate_all(_translate_all):
        "make p_from and p_to invisible when translate_all is set to be True"
        return gr.update(value=_translate_all), gr.update(visible=not _translate_all), gr.update(visible=not _translate_all)
    translate_all = gr.Checkbox(label="translate all pages", value=True)
    with gr.Row():
        from_page = gr.Number(label="from page", visible=False)
        to_page = gr.Number(label="to page", visible=False)
    translate_all.input(_click_translate_all, inputs=[translate_all], outputs=[translate_all, from_page, to_page])
    return translate_all, from_page, to_page

def render_mode_widget():
    def _update(render_mode):
        "make add_blank_page visible when render_mode is INTERLEAVE"
        return gr.update(visible=(render_mode=='interleave'))
    render_mode = gr.Dropdown(
        label="render mode",
        choices=["side by side", "translation only", "interleave"],
        value="interleave",
    )
    add_blank_page = gr.Checkbox(
        label="add blank pages",
        info="add a blank page at the begining and the end of the result(better for print)",
        value=True,
        visible=True,
    )
    render_mode.input(_update, inputs=[render_mode], outputs=[add_blank_page])
    return render_mode, add_blank_page

def lang_widget(langs: list[str]):
    """
    The language choose widget
    """
    with gr.Row():
        from_lang = gr.Dropdown(label="from language", choices=langs, value="English")
        to_lang = gr.Dropdown(label="to language", choices=langs, value="Chinese")
    return from_lang, to_lang


def create_gradio_app(langs):
    with gr.Blocks(theme="Soft") as upload_translator:
        with gr.Column() as col:
            title = gr.Markdown("## PDF Translator")
            with gr.Row():
                file = gr.File(label="select file", height=30, file_types=[".pdf"])
                translated_file = gr.File(label="translated file", file_types=[".pdf"])

            from_lang, to_lang = lang_widget(langs)

            translate_all, from_page, to_page = translate_range_widget()
            
            render_mode, add_blank_page = render_mode_widget()

            btn = gr.Button(value="convert")

            btn.click(
                translate_request,
                inputs=[
                    file,
                    from_lang,
                    to_lang,
                    translate_all,
                    from_page,
                    to_page,
                    render_mode,
                ],
                outputs=[translated_file],
            )

    with gr.Blocks(theme="Soft") as save_translator:
        with gr.Column():
            title = gr.Markdown("## Download a pdf file and translate it")
            with gr.Row():
                with gr.Column():
                    url_link = gr.Textbox(label="url")
                    url_file_name = gr.Textbox(label="file name")
                    overwrite = gr.Checkbox(
                        label="overwrite", 
                        info="overwrite the file when the file (both original and translation) exists", 
                        value=True)
                translated_file = gr.File(label="translated file", file_types=[".pdf"])
            # submit button
            btn = gr.Button(value="Download and Translate")

            # Server file browser
            folder_paths = ["/home/home/Docs/Papers", "/home/home/Docs/Papers"]

            download_folder_info = gr.Markdown(f"### Download Folder: {folder_paths[0]}")            
            download_folder = gr.CheckboxGroup(
                choices=[".."] + get_folders(folder_paths[0]),
                value=folder_paths[0],
                label="Download Folder",
                show_label=False,
                interactive=True,
            )
            download_folder.input(lambda x: update_folder(x[0], folder_paths, 0), inputs=(download_folder), outputs=[download_folder, download_folder_info])
            
            translate_folder_info = gr.Markdown(f"### Download Folder: {folder_paths[1]}")            
            translate_folder = gr.CheckboxGroup(
                choices=[".."] + get_folders(folder_paths[1]),
                value=folder_paths[1],
                label="Download Folder",
                show_label=False,
                interactive=True,
            )
            translate_folder.input(lambda x: update_folder(x[0], folder_paths, 1), inputs=[translate_folder], outputs=[translate_folder, translate_folder_info])
            
            from_lang, to_lang = lang_widget(langs)
            
            translate_all, from_page, to_page = translate_range_widget()
            with gr.Row():
                render_mode, add_blank_page = render_mode_widget()
                suffix = gr.Textbox(label="suffix", value="translated")
            
            def _download_and_translate(url_link, url_file_name, overwrite, download_folder, translate_folder, from_lang, to_lang, translate_all, from_page, to_page, render_mode, add_blank_page, suffix):
                return download_and_translate(url_link, url_file_name, overwrite, from_lang, to_lang, translate_all, from_page, to_page, render_mode, add_blank_page, suffix, folder_paths[0], folder_paths[1])
            
            btn.click(
                _download_and_translate, 
                inputs=[url_link, url_file_name, overwrite, download_folder, translate_folder, from_lang, to_lang, translate_all, from_page, to_page, render_mode, add_blank_page, suffix],
                outputs=[translated_file],
            )


    page = gr.TabbedInterface(
        [upload_translator, save_translator],
        ["Upload and Translate", "Download and Translate"],
    )
    
    # page.launch(share=False, auth=("poppanda", "poppanda"), server_port=8765, server_name="0.0.0.0")
    page.auth = [("poppanda", "panda60x"), ("wmx", "hellowmx")]
    page.auth_message = None
    
    return page


if __name__ == "__main__":
    app = create_gradio_app()
    app.launch(share=True, auth=("poppanda", "poppanda"))
