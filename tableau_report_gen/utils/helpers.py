# utils/helpers.py

import streamlit as st
import base64


def display_dataframe(df, max_rows=10, row_height=33, header_height=50):

    total_rows = len(df)

    if total_rows > max_rows:
        # Calculate height to display max_rows with scroll
        height = (max_rows * row_height) + header_height
    else:
        # Calculate height based on the number of rows to fit the table
        height = (total_rows * row_height) + header_height

    # Display the dataframe with the calculated height
    st.dataframe(df, height=height)


def image_to_base64(img_bytes):

    return base64.b64encode(img_bytes).decode("utf-8")
