# components/uploader.py

import streamlit as st
# import os
# import logzero
from logzero import logger


def file_uploader_component():
    uploaded_file = st.sidebar.file_uploader(
        "Upload a Tableau Workbook (`.twbx` file)",
        type=["twbx"],
        accept_multiple_files=False,
    )
    if uploaded_file is not None:
        logger.info(f"File '{uploaded_file.name}' uploaded by user.")
    return uploaded_file
