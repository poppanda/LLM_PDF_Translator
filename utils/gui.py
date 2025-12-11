from pathlib import Path
from typing import Any
import os
import json
import pandas as pd
import gradio as gr
import requests
from loguru import logger
from .database.file_db import FileDatabase
from .database.basic_info_db import BasicInfoDatabase

TRANSLATE_URL = "http://localhost:8765/translate_pdf/"
CLEAR_TEMP_URL = "http://localhost:8765/clear_temp_dir/"
GET_RESULT_URL = "http://localhost:8765/get_files/"
DOWNLOAD_RESULT_URL = "http://localhost:8765/download_file/"


def get_translate_status_request(status=None):
    def _convert_status(status):
        if status == 0:
            return "Not Translated"
        elif status == 1:
            return "Translating"
        elif status == 2:
            return "Translated"

    response = requests.post(GET_RESULT_URL, data={"status": status})
    if response.status_code == 200:
        raw_data = json.loads(response.content)
        # data is a list of dicts
        data = {"file": [], "status": [], "src_path": [], "target_path": []}
        for item in raw_data:
            data["file"].append(item["file"])
            data["status"].append(_convert_status(item["status"]))
            data["src_path"].append(item["src_path"])
            data["target_path"].append(item["target_path"])
        dataframe = pd.DataFrame.from_dict(data)
        return dataframe
    else:
        logger.error(f"An error occurred: {response.status_code}")


def refresh_table():
    dataframe = get_translate_status_request()
    available_files = dataframe["target_path"][
        dataframe["status"] == "Translated"
    ].tolist()
    return gr.update(value=dataframe), gr.update(choices=available_files)


def download_file(file_path):
    response = requests.post(DOWNLOAD_RESULT_URL, data={"file_path": file_path})
    if not (os.path.exists("temp")):
        os.mkdir("temp")
    if response.status_code == 200:
        # get the absolute path of the file
        folder = os.path.abspath("temp")
        output_file_path = os.path.join(folder, file_path.split("/")[-1])
        with open(output_file_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded file to {output_file_path}")
        return output_file_path
    else:
        logger.error(f"An error occurred: {response.status_code}")


def translate_request(
    save_to_folder: bool,
    file: Any,
    input_pdf_folder: str,
    from_lang: Any,
    to_lang: Any,
    translate_all: bool,
    from_page: int,
    to_page: int,
    render_mode: str,
    output_file_folder: str,
    add_blank_page: bool,
    suffix: str,
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

    if save_to_folder:
        file_name = file.split("/")[-1]
        save_pdf_path = os.path.join(input_pdf_folder, file_name)
        output_file_path = os.path.join(
            output_file_folder, file_name.replace(".pdf", f"{suffix}.pdf")
        )
        req_data = {
            "input_pdf_path": save_pdf_path,
            "from_lang": from_lang,
            "to_lang": to_lang,
            "translate_all": translate_all,
            "p_from": from_page,
            "p_to": to_page,
            "render_mode": render_mode,
            "output_file_path": output_file_path,
            "add_blank_page": add_blank_page,
        }
    else:
        logger.info(
            f"Translate request, NOT SAVE TO FOLDER, file: {file}, input_pdf_folder: {input_pdf_folder}, from_lang: {from_lang}, to_lang: {to_lang}, translate_all: {translate_all}, from_page: {from_page}, to_page: {to_page}, render_mode: {render_mode}, output_file_folder: {output_file_folder}, add_blank_page: {add_blank_page}, suffix: {suffix}"
        )
        req_data = {
            "from_lang": from_lang,
            "to_lang": to_lang,
            "translate_all": translate_all,
            "p_from": from_page,
            "p_to": to_page,
            "render_mode": render_mode,
            "add_blank_page": add_blank_page,
        }
    response = requests.post(
        TRANSLATE_URL,
        files={"input_pdf": open(file, "rb")},
        data=req_data,
    )

    if response.status_code == 200:
        # logger.info(f"Response: {response.content}")
        info = json.loads(response.content)["message"]
        gr.Info(f"Response: {info}")
    else:
        print(f"An error occurred: {response.status_code}")


def update_folder(folder, info, db_name: str, db_key: str):
    folder = folder[0]
    db = BasicInfoDatabase(db_name)
    logger.info(f"Folder: {folder}, Folder info: {info}")
    current_root_dir = db.get_value(db_key)
    new_root_dir = os.path.abspath(os.path.join(current_root_dir, folder))
    db.update_value(db_key, new_root_dir)
    return gr.update(choices=[".."] + get_folders(new_root_dir), value=None), gr.update(
        value=f"### Download Folder: {new_root_dir}"
    )


def get_folders(path):
    folders = []
    for folder in os.listdir(path):
        if os.path.isdir(os.path.join(path, folder)) and not folder.startswith("."):
            folders.append(folder)
    return folders


def download_and_translate(
    url_link,
    url_file_name,
    overwrite,
    from_lang,
    to_lang,
    translate_all,
    from_page,
    to_page,
    render_mode,
    add_blank_page,
    db_name: str,
    suffix,
):
    if url_file_name == "":
        raise ValueError("Please enter a file name")
    elif url_file_name[-4:] != ".pdf":
        url_file_name += ".pdf"

    basic_info_db = BasicInfoDatabase(db_name)

    download_folder = basic_info_db.get_value("download_folder")
    translate_folder = basic_info_db.get_value("translate_folder")

    # check if the file exists in the translate_folder
    if os.path.exists(os.path.join(download_folder, url_file_name)):
        if not overwrite:
            raise ValueError(
                f"File {url_file_name} already exists in the folder {download_folder}"
            )

    # download the file to download_folder
    logger.info(f"Downloading file from the url: {url_link}")
    response = requests.get(url_link)
    if response.status_code != 200:
        raise ValueError(
            f"An error occurred while downloading the file: {response.status_code}"
        )
    with open(os.path.join(download_folder, url_file_name), "wb") as f:
        f.write(response.content)
    post_data = {
        "input_pdf_path": os.path.join(download_folder, url_file_name),
        "from_lang": from_lang,
        "to_lang": to_lang,
        "translate_all": translate_all,
        "p_from": from_page,
        "p_to": to_page,
        "render_mode": render_mode,
        "output_file_path": os.path.join(
            translate_folder, url_file_name.replace(".pdf", f"{suffix}.pdf")
        ),
        "add_blank_page": add_blank_page,
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
        return (
            gr.update(value=_translate_all),
            gr.update(visible=not _translate_all),
            gr.update(visible=not _translate_all),
        )

    translate_all = gr.Checkbox(label="translate all pages", value=True)
    with gr.Row():
        from_page = gr.Number(label="from page", visible=False)
        to_page = gr.Number(label="to page", visible=False)
    translate_all.input(
        _click_translate_all,
        inputs=[translate_all],
        outputs=[translate_all, from_page, to_page],
    )
    return translate_all, from_page, to_page


def render_mode_widget():
    def _update(render_mode):
        "make add_blank_page visible when render_mode is INTERLEAVE"
        return gr.update(visible=(render_mode == "interleave"))

    render_mode = gr.Dropdown(
        label="render mode",
        choices=["side by side", "translation only", "interleave"],
        value="interleave",
    )
    add_blank_page = gr.Checkbox(
        label="add blank pages",
        info="add a blank page at the begining and the end of the result(better for print)",
        value=True,
        interactive=True,
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


class DetermineSaveInFolderToTmpWidget:
    def __init__(self, save_folder, translate_folder):
        self.save_folder, self.translate_folder = (
            os.path.abspath(save_folder),
            os.path.abspath(translate_folder),
        )
        logger.info(f"The downloaded files will be saved in {self.save_folder}")
        logger.info(f"The translated files will be saved in {self.translate_folder}")
        self.save_to_folder = False

    def update_save_folder(self, selected_folder, info):
        self.save_folder = os.path.abspath(
            os.path.join(self.save_folder, selected_folder[0])
        )
        return gr.update(
            choices=[".."] + get_folders(self.save_folder), value=None
        ), gr.update(value=f"### Save Folder: {self.save_folder}")

    def update_translate_folder(self, selected_folder, info):
        self.translate_folder = os.path.abspath(
            os.path.join(self.translate_folder, selected_folder[0])
        )
        return gr.update(
            choices=[".."] + get_folders(self.translate_folder), value=None
        ), gr.update(value=f"### Translate Folder: {self.translate_folder}")

    def update_save_to_folder_status(self, save_to_folder):
        logger.info(f"Save to folder visible: {save_to_folder}")
        self.save_to_folder = save_to_folder
        return (
            gr.update(value=save_to_folder),
            gr.update(visible=save_to_folder),
            gr.update(visible=save_to_folder),
            gr.update(visible=save_to_folder),
            gr.update(visible=save_to_folder),
        )

    def get_widgets(self):
        save_to_folder_checkbox = gr.Checkbox(
            label="save to folder",
            value=False,
            info="save the translated file to a folder, otherwise save to a temporary folder",
        )
        with gr.Row():
            with gr.Column():
                save_folder_info = gr.Markdown(
                    f"### Save Folder: {self.save_folder}", visible=False
                )
                save_folder = gr.CheckboxGroup(
                    visible=False,
                    choices=[".."] + get_folders(self.save_folder),
                    value=None,
                    label="Download Folder",
                    show_label=False,
                    interactive=True,
                )
            with gr.Column():
                translate_folder_info = gr.Markdown(
                    f"### Translate Folder: {self.translate_folder}", visible=False
                )
                translate_folder = gr.CheckboxGroup(
                    visible=False,
                    choices=[".."] + get_folders(self.translate_folder),
                    value=None,
                    label="Translate Folder",
                    show_label=False,
                    interactive=True,
                )
            save_folder.input(
                self.update_save_folder,
                inputs=(save_folder, save_folder_info),
                outputs=[save_folder, save_folder_info],
            )
            translate_folder.input(
                self.update_translate_folder,
                inputs=(translate_folder, translate_folder_info),
                outputs=[translate_folder, translate_folder_info],
            )
        save_to_folder_checkbox.input(
            self.update_save_to_folder_status,
            inputs=[save_to_folder_checkbox],
            outputs=[
                save_to_folder_checkbox,
                save_folder_info,
                translate_folder_info,
                save_folder,
                translate_folder,
            ],
        )
        return save_to_folder_checkbox, save_folder, translate_folder


class GradioApp:
    def __init__(self, langs: list[str], config: dict[str, Any]):
        self.langs : list[str]= langs
        self.config = config
        self.check_db(config)
        try:
            self.config["auth"]
        except:
            self.config["auth"] = None

    def check_db(self, config):
        basic_info_db = BasicInfoDatabase(self.config["database_name"])
        keys = ["download_folder", "translate_folder"]
        for key in keys:
            if not basic_info_db.get_value(key):
                basic_info_db.set_value(key, config[key])

    def create_gradio_app(self):
        basic_info_db = BasicInfoDatabase(self.config["database_name"])
        with gr.Blocks(theme="Soft") as upload_translator:
            with gr.Column() as col:
                title = gr.Markdown("## PDF Translator")
                file = gr.File(label="select file", height=30, file_types=[".pdf"])
                save_to_dir_widget = DetermineSaveInFolderToTmpWidget(
                    self.config["download_folder"], self.config["translate_folder"]
                )
                save_folder_checkbox, save_folder, translate_folder = (
                    save_to_dir_widget.get_widgets()
                )
                from_lang, to_lang = lang_widget(self.langs)

                translate_all, from_page, to_page = translate_range_widget()

                with gr.Row():
                    render_mode, add_blank_page = render_mode_widget()
                    suffix = gr.Textbox(
                        label="suffix",
                        info="only valid when save to server(not temp dir)",
                        value="_translated",
                    )

                btn = gr.Button(value="convert")

                btn.click(
                    lambda save_to_folder, file, from_lang, to_lang, translate_all, from_page, to_page, render_mode, add_blank_page, suffix: translate_request(
                        save_to_folder,
                        file,
                        save_to_dir_widget.save_folder,
                        from_lang,
                        to_lang,
                        translate_all,
                        from_page,
                        to_page,
                        render_mode,
                        save_to_dir_widget.translate_folder,
                        add_blank_page,
                        suffix,
                    ),
                    inputs=[
                        save_folder_checkbox,
                        file,
                        from_lang,
                        to_lang,
                        translate_all,
                        from_page,
                        to_page,
                        render_mode,
                        add_blank_page,
                        suffix,
                    ],
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
                            value=True,
                        )
                    # with gr.Column():
                    #     refresh_btn = gr.Button(value="Refresh", size="sm")
                    #     @gr.render(refresh_btn)
                    #     def refresh(btn):
                    #         logger.info("Refresh btn pressed")
                    # get all the files in the database
                    # for (file, path, status) in file_path_status:
                    #     if status:
                    #         gr.File(label=file, value=path, file_types=[".pdf"])
                    #     else:
                    #         gr.Label(label=file+" (not translated)", value='Not available')
                # submit button
                btn = gr.Button(value="Download and Translate")

                # Server file browser

                download_folder_info = gr.Markdown(
                    f"### Download Folder: {basic_info_db.get_value('download_folder')}"
                )
                download_folder = gr.CheckboxGroup(
                    choices=[".."]
                    + get_folders(basic_info_db.get_value("download_folder")),
                    value=None,
                    label="Download Folder",
                    show_label=False,
                    interactive=True,
                )
                download_folder.input(
                    lambda x, y: update_folder(
                        x, y, self.config["database_name"], "download_folder"
                    ),
                    inputs=(download_folder, download_folder_info),
                    outputs=[download_folder, download_folder_info],
                )

                translate_folder_info = gr.Markdown(
                    f"### Translate Folder: {basic_info_db.get_value('translate_folder')}"
                )
                translate_folder = gr.CheckboxGroup(
                    choices=[".."]
                    + get_folders(basic_info_db.get_value("translate_folder")),
                    value=None,
                    label="Translate Folder",
                    show_label=False,
                    interactive=True,
                )
                translate_folder.input(
                    lambda x, y: update_folder(
                        x, y, self.config["database_name"], "translate_folder"
                    ),
                    inputs=[translate_folder, translate_folder_info],
                    outputs=[translate_folder, translate_folder_info],
                )

                from_lang, to_lang = lang_widget(self.langs)

                translate_all, from_page, to_page = translate_range_widget()
                with gr.Row():
                    render_mode, add_blank_page = render_mode_widget()
                    suffix = gr.Textbox(label="suffix", value="_translated")

                def _download_and_translate(
                    url_link,
                    url_file_name,
                    overwrite,
                    download_folder,
                    translate_folder,
                    from_lang,
                    to_lang,
                    translate_all,
                    from_page,
                    to_page,
                    render_mode,
                    add_blank_page,
                    suffix,
                ):
                    gr.Info("Task submitted")
                    return download_and_translate(
                        url_link,
                        url_file_name,
                        overwrite,
                        from_lang,
                        to_lang,
                        translate_all,
                        from_page,
                        to_page,
                        render_mode,
                        add_blank_page,
                        self.config["database_name"],
                        suffix,
                    )

                btn.click(
                    _download_and_translate,
                    inputs=[
                        url_link,
                        url_file_name,
                        overwrite,
                        download_folder,
                        translate_folder,
                        from_lang,
                        to_lang,
                        translate_all,
                        from_page,
                        to_page,
                        render_mode,
                        add_blank_page,
                        suffix,
                    ],
                )
        with gr.Blocks(theme="Soft") as result_page:
            refresh_btn = gr.Button(value="Refresh")
            # dataframe = get_translate_status_request()
            dataframe = pd.DataFrame(
                {"file": [], "src_path": [], "target_path": [], "status": []}
            )
            result_table = gr.DataFrame(value=dataframe)
            with gr.Row():
                download_file_box = gr.Dropdown(
                    label="Download File", choices=[], value=None
                )
                # @gr.render(download_file_box)
                # def _download_file(file):
                #     if file is None:
                #         gr.Label(label="No file available")
                #     else:
                #         gr.File(value=download_file(file), label="Download", file_types=[".pdf"])
                download_file_btn = gr.DownloadButton(
                    value=None, label="No file available", visible=False
                )
            refresh_btn.click(
                refresh_table,
                outputs=[result_table, download_file_box],
            )
            download_file_box.input(
                lambda x: gr.DownloadButton(
                    value=download_file(x),
                    label="Download",
                    interactive=True,
                    visible=True,
                ),
                inputs=[download_file_box],
                outputs=[download_file_btn],
            )

        page = gr.TabbedInterface(
            [upload_translator, save_translator, result_page],
            ["Upload and Translate", "Download and Translate", "Results"],
        )

        # page.launch(share=False, auth=("poppanda", "poppanda"), server_port=8765, server_name="0.0.0.0")
        if self.config["auth"] is None:
            page.auth = [("admin", "password")]
        else:
            page.auth = self.config["auth"]

        return page
