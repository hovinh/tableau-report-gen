# app.py

import streamlit as st
import os
from tableau_report_gen.parser.tableau_parser import TableauWorkbookParser
from tableau_report_gen.utils.dag import generate_dag
from tableau_report_gen.utils.report import generate_html_report, convert_html_to_pdf
from tableau_report_gen.utils.helpers import image_to_base64, display_dataframe
from tableau_report_gen.components.uploader import file_uploader_component
import pandas as pd
import logzero
from logzero import logger
from datetime import datetime
from graphviz import Digraph


def plot_dag_graphviz(G):
    dot = Digraph(comment='Dependency DAG', format='png')
    dot.attr(rankdir='LR')  # Left to Right orientation
    dot.attr('node', fontsize='10')

    # Define node styles based on type
    for node, data in G.nodes(data=True):
        node_type = data.get('type', 'Original Field')
        if node_type == 'Calculated Field':
            dot.node(node, shape='box', style='filled', color='lightblue')
        elif node_type == 'Original Field':
            dot.node(
                node,
                shape='ellipse',
                style='filled',
                color='#89CFF0')  # Updated color
        elif node_type == 'Data Source':
            dot.node(node, shape='rectangle', style='filled', color='orange')
        elif node_type == 'Root':
            # Distinct shape and color for Root
            dot.node(node, shape='diamond', style='filled', color='red')
        else:
            dot.node(
                node,
                shape='ellipse',
                style='filled',
                color='grey')  # Default style

    # Define edges with labels
    for edge in G.edges(data=True):
        source, target, attrs = edge
        label = attrs.get('label', '')
        if label:
            dot.edge(
                source,
                target,
                label=label,
                fontsize='8',
                fontcolor='gray')
        else:
            dot.edge(source, target)

    return dot


def main():
    # Ensure logs directory exists
    if not os.path.exists('logs'):
        os.makedirs('logs')

    # Configure logging
    logzero.logfile("logs/app.log", maxBytes=1e6, backupCount=3)
    logger.info("Streamlit app started.")

    # Set Streamlit page configuration
    st.set_page_config(
        page_title="📊 Tableau Workbook Parser and Report Generator",
        layout="wide",  # Ensures the app uses the full width of the browser
        initial_sidebar_state="expanded",
    )

    # App Title and Description
    st.title("📊 Tableau Workbook Parser and Report Generator")
    st.write("""
    Upload a Tableau Workbook (`.twbx` file) to parse its contents
    and generate comprehensive reports, including version information,
    calculated fields, original fields, worksheets, and data sources.
    Additionally, visualize dependencies between calculated fields and
    original columns using a Directed Acyclic Graph (DAG).
    """)

    # Sidebar: File Uploader and Settings
    st.sidebar.header("Upload and Settings")
    uploaded_file = file_uploader_component()

    if uploaded_file is not None:
        temp_twbx_path = "temp_uploaded.twbx"
        try:
            with open(temp_twbx_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            logger.info(f"Uploaded file saved to {temp_twbx_path}")
            st.sidebar.success("File uploaded successfully.")
            st.write("✅ **File uploaded and saved successfully.**")
        except Exception as e:
            logger.error(f"Failed to save uploaded file: {e}")
            st.error("❌ Failed to save the uploaded file.")
            return

        # Initialize and parse the Tableau workbook
        parser = TableauWorkbookParser(twbx_file=temp_twbx_path)
        try:
            parser.decompress_twbx()
            logger.info("Decompressed the .twbx file.")
            st.write("🗜️ **Decompressed the `.twbx` file successfully.**")
        except Exception as e:
            logger.error(f"Failed to decompress `.twbx` file: {e}")
            st.error("❌ Failed to decompress the `.twbx` file.")
            return

        if parser.twb_content:
            try:
                parser.parse_twb()
                logger.info("Parsed the .twb content.")
                st.write("📄 **Parsed the `.twb` content successfully.**")
                report = parser.get_report()
                logger.info("Report generated from parsed data.")
            except Exception as e:
                logger.error(f"Failed to parse `.twb` content: {e}")
                st.error("❌ Failed to parse the `.twb` content.")
                return
        else:
            logger.error(
                "Failed to extract `.twb` content from the uploaded `.twbx` file.")
            st.error(
                "❌ Failed to extract `.twb` content from the uploaded `.twbx` file.")
            return

        # Sidebar: Report Generation Settings
        st.sidebar.header("Report Generation")
        report_sections = [
            "Version Information",
            "Calculated Fields",
            "Original Fields",
            "Worksheets",
            "Data Sources",
            "Dependency DAG"]
        selected_sections = []
        for section in report_sections:
            if st.sidebar.checkbox(f"Include {section}", value=True):
                selected_sections.append(section)

        logger.info(f"Selected report sections: {selected_sections}")
        st.write("### Selected Report Sections")
        st.write(", ".join(selected_sections))
        st.markdown("---")

        # Merge Data Sources with Calculated and Original Fields
        df_data_sources = report['data'].get('data_sources', pd.DataFrame())
        calculated_fields_df = report['metadata'].get(
            'calculated_fields', pd.DataFrame())
        original_fields_df = report['metadata'].get(
            'original_fields', pd.DataFrame())

        if not df_data_sources.empty:
            if not calculated_fields_df.empty and 'Data Source ID' in calculated_fields_df.columns:
                calculated_fields_df = calculated_fields_df.merge(
                    df_data_sources[['Data Source ID', 'Caption']],
                    on='Data Source ID',
                    how='left'
                )
                calculated_fields_df.rename(
                    columns={
                        'Caption': 'Data Source Caption'},
                    inplace=True)
                report['metadata']['calculated_fields'] = calculated_fields_df
            if not original_fields_df.empty and 'Data Source ID' in original_fields_df.columns:
                original_fields_df = original_fields_df.merge(
                    df_data_sources[['Data Source ID', 'Caption']],
                    on='Data Source ID',
                    how='left'
                )
                original_fields_df.rename(
                    columns={
                        'Caption': 'Data Source Caption'},
                    inplace=True)
                report['metadata']['original_fields'] = original_fields_df

        # Extract the uploaded file name without extension for root_placeholder
        file_name = os.path.splitext(uploaded_file.name)[0]

        # Iterate through selected sections and display content
        for section in report_sections:
            if section in selected_sections:
                st.header(section)
                try:
                    if section == "Version Information":
                        version_info = {
                            "Version": report['metadata'].get(
                                'version', 'Unknown'), "Source Platform": report['metadata'].get(
                                'source_platform', 'Unknown'), "Source Build": report['metadata'].get(
                                'source_build', 'Unknown'), }
                        st.json(version_info)

                    elif section == "Calculated Fields":
                        calculated_fields_df = report['metadata'].get(
                            'calculated_fields', pd.DataFrame())
                        if not calculated_fields_df.empty:
                            calculated_fields_df = calculated_fields_df.reset_index(
                                drop=True)
                            calculated_fields_df.index = calculated_fields_df.index + 1
                            display_dataframe(
                                calculated_fields_df, max_rows=10)  # Use helper function
                        else:
                            st.write("No calculated fields found.")

                    elif section == "Original Fields":
                        original_fields_df = report['metadata'].get(
                            'original_fields', pd.DataFrame())
                        if not original_fields_df.empty:
                            original_fields_df = original_fields_df.reset_index(
                                drop=True)
                            original_fields_df.index = original_fields_df.index + 1
                            display_dataframe(
                                original_fields_df, max_rows=10)  # Use helper function
                        else:
                            st.write("No original fields found.")

                    elif section == "Worksheets":
                        worksheets_df = report['metadata'].get(
                            'worksheets', pd.DataFrame())
                        if not worksheets_df.empty:
                            worksheets_df = worksheets_df.reset_index(
                                drop=True)
                            worksheets_df.index = worksheets_df.index + 1
                            display_dataframe(
                                worksheets_df, max_rows=10)  # Use helper function
                        else:
                            st.write("No worksheets found.")

                    elif section == "Data Sources":
                        df_data_sources = report['data'].get(
                            'data_sources', pd.DataFrame())
                        if not df_data_sources.empty:
                            df_data_sources = df_data_sources.reset_index(
                                drop=True)
                            df_data_sources.index = df_data_sources.index + 1
                            display_dataframe(
                                df_data_sources, max_rows=10)  # Use helper function
                        else:
                            st.write("No data sources found.")

                    elif section == "Dependency DAG":
                        calculated_fields_df = report['metadata'].get(
                            'calculated_fields', pd.DataFrame())
                        original_fields_df = report['metadata'].get(
                            'original_fields', pd.DataFrame())
                        data_sources_df = report['data'].get(
                            'data_sources', pd.DataFrame())
                        worksheets_df = report['metadata'].get(
                            'worksheets', pd.DataFrame())
                        if not calculated_fields_df.empty and not original_fields_df.empty:
                            if 'Worksheet Name' in worksheets_df.columns:
                                worksheets = worksheets_df['Worksheet Name'].dropna(
                                ).unique().tolist()
                                if worksheets:
                                    selected_worksheet = st.selectbox(
                                        "Select Worksheet for DAG:", ["All"] + list(worksheets))
                                else:
                                    selected_worksheet = "All"
                                    st.warning(
                                        "No worksheets available for selection. Displaying the entire DAG.")
                            else:
                                selected_worksheet = "All"
                                st.warning(
                                    "Worksheet Name column is missing. Displaying the entire DAG.")

                            G = generate_dag(
                                calculated_fields_df,
                                original_fields_df,
                                data_sources_df,
                                worksheets_df,
                                selected_worksheet,
                                root_placeholder=file_name
                            )
                            if len(G.nodes) == 0:
                                st.warning(
                                    "No data available to display the DAG for the selected worksheet.")
                            else:
                                dot = plot_dag_graphviz(G)
                                st.graphviz_chart(dot.source)
                        else:
                            st.write(
                                "Insufficient data to generate Dependency DAG.")

                except KeyError as ke:
                    logger.error(f"KeyError in section '{section}': {ke}")
                    st.error(
                        f"❌ A key error occurred while displaying the '{section}' section: {ke}")
                except Exception as e:
                    logger.error(f"Error displaying section '{section}': {e}")
                    st.error(
                        f"❌ An error occurred while displaying the '{section}' section.")

    st.markdown("---")
    st.sidebar.header("Export Report")
    export_format = st.sidebar.selectbox(
        "Select export format:", ["HTML", "PDF"])
    download_placeholder = st.sidebar.empty()

    if st.sidebar.button("Generate and Download Report"):
        logger.info("Generate and Download Report button clicked.")
        with download_placeholder.container():
            with st.spinner('🔄 Generating report...'):
                try:
                    html_report = generate_html_report(
                        selected_sections, report)
                    logger.info("HTML report generated.")
                    if "Dependency DAG" in selected_sections and not report['metadata'].get(
                            'calculated_fields', pd.DataFrame()).empty:
                        worksheets_df = report['metadata'].get(
                            'worksheets', pd.DataFrame())
                        # For embedding the DAG, use "All" to include all
                        # dependencies
                        G = generate_dag(
                            report['metadata']['calculated_fields'],
                            report['metadata']['original_fields'],
                            report['data']['data_sources'],
                            worksheets_df,
                            selected_worksheet="All",
                            root_placeholder=file_name
                        )
                        dot = plot_dag_graphviz(G)
                        img_bytes = dot.pipe(format='png')
                        img_base64 = image_to_base64(img_bytes)
                        html_report = html_report.replace(
                            "<p>See the Dependency DAG visualization within the app.</p>",
                            f"<h3>Dependency DAG</h3><img src='data:image/png;base64,{img_base64}'/>")
                        logger.info("Dependency DAG embedded in HTML report.")

                    if export_format == "HTML":
                        st.markdown("### 📥 Download Report")
                        st.download_button(
                            label="📄 Download HTML Report",
                            data=html_report,
                            file_name=f"tableau_report_{
                                datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                            mime="text/html")
                        logger.info("HTML report ready for download.")
                    elif export_format == "PDF":
                        try:
                            pdf = convert_html_to_pdf(html_report)
                            if pdf:
                                st.markdown("### 📥 Download Report")
                                st.download_button(
                                    label="📄 Download PDF Report", data=pdf, file_name=f"tableau_report_{
                                        datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf", mime="application/pdf")
                                logger.info("PDF report ready for download.")
                            else:
                                st.error("❌ Failed to generate PDF report.")
                                logger.error(
                                    "Failed to generate PDF report: convert_html_to_pdf returned None.")
                        except Exception as e:
                            logger.error(f"Failed to generate PDF: {e}")
                            st.error(f"❌ Failed to generate PDF: {e}")
                except Exception as e:
                    logger.error(f"Failed during report generation: {e}")
                    st.error(
                        f"❌ An error occurred during report generation: {e}")

    st.sidebar.header("Download Original File")
    if st.sidebar.button("⬇️ Download Uploaded `.twbx`"):
        try:
            with open(temp_twbx_path, "rb") as f:
                st.sidebar.download_button(
                    label="⬇️ Download `.twbx` File",
                    data=f,
                    file_name=os.path.basename(temp_twbx_path),
                    mime="application/octet-stream"
                )
            logger.info("Original .twbx file ready for download.")
        except Exception as e:
            logger.error(f"Failed to download .twbx file: {e}")
            st.sidebar.error("❌ Failed to download the original `.twbx` file.")


if __name__ == "__main__":
    main()
