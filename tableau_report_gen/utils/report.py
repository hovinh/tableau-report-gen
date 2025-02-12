# utils/report.py

import pandas as pd
from xhtml2pdf import pisa
# import base64
from datetime import datetime
import logzero
from logzero import logger
from io import BytesIO
import os


def generate_html_report(
        selected_sections,
        report,
        templates_path="reports/templates/report_template.html"):
    html_report = "<html><head><title>Tableau Report</title></head><body>"
    html_report += f"<h1>Tableau Workbook Report - {
        datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</h1>"

    for section in selected_sections:
        html_report += f"<h2>{section}</h2>"
        if section == "Version Information":
            version_info = {
                "Version": report["metadata"].get(
                    "version", "Unknown"), "Source Platform": report["metadata"].get(
                    "source_platform", "Unknown"), "Source Build": report["metadata"].get(
                    "source_build", "Unknown"), }
            html_report += f"<pre>{version_info}</pre>"
        elif section == "Calculated Fields":
            calculated_fields_df = report["metadata"].get(
                "calculated_fields", pd.DataFrame()
            )
            if not calculated_fields_df.empty:
                # Merge with Data Sources to include Data Source Caption
                df_data_sources = report["data"].get(
                    "data_sources", pd.DataFrame())
                if not df_data_sources.empty:
                    logger.info(
                        f"Data Sources Columns Before Merge: {
                            df_data_sources.columns.tolist()}"
                    )
                    logger.info(
                        f"Calculated Fields Columns Before Merge: {
                            calculated_fields_df.columns.tolist()}"
                    )

                    calculated_fields_df = calculated_fields_df.merge(
                        df_data_sources[["Data Source ID", "Caption"]],
                        on="Data Source ID",
                        how="left",
                    )

                    logger.info(
                        f"Calculated Fields Columns After Merge: {
                            calculated_fields_df.columns.tolist()}"
                    )
                    logger.info(
                        f"Sample Data After Merge:\n{
                            calculated_fields_df.head()}"
                    )

                    calculated_fields_df.rename(
                        columns={
                            "Caption": "Data Source Caption"},
                        inplace=True)

                    if "Data Source Caption" not in calculated_fields_df.columns:
                        logger.error(
                            "'Data Source Caption' column is missing after merging."
                        )
                        raise KeyError(
                            "'Data Source Caption' column is missing after merging."
                        )

                html_report += calculated_fields_df.to_html(index=False)
            else:
                html_report += "<p>No calculated fields found.</p>"
        elif section == "Original Fields":
            original_fields_df = report["metadata"].get(
                "original_fields", pd.DataFrame()
            )
            if not original_fields_df.empty:
                # Merge with Data Sources to include Data Source Caption
                df_data_sources = report["data"].get(
                    "data_sources", pd.DataFrame())
                if not df_data_sources.empty:
                    original_fields_df = original_fields_df.merge(
                        df_data_sources[["Data Source ID", "Caption"]],
                        on="Data Source ID",
                        how="left",
                    )
                    original_fields_df.rename(
                        columns={
                            "Caption": "Data Source Caption"},
                        inplace=True)
                html_report += original_fields_df.to_html(index=False)
            else:
                html_report += "<p>No original fields found.</p>"
        elif section == "Worksheets":
            worksheets_df = report["metadata"].get(
                "worksheets", pd.DataFrame())
            if not worksheets_df.empty:
                # Merge with Data Sources to include Data Source Caption
                df_data_sources = report["data"].get(
                    "data_sources", pd.DataFrame())
                if not df_data_sources.empty:
                    worksheets_df = worksheets_df.merge(
                        df_data_sources[["Data Source ID", "Caption"]],
                        on="Data Source ID",
                        how="left",
                    )
                    worksheets_df.rename(
                        columns={
                            "Caption": "Data Source Caption"},
                        inplace=True)
                html_report += worksheets_df.to_html(index=False)
            else:
                html_report += "<p>No worksheets found.</p>"
        elif section == "Data Sources":
            # Handle Data Sources as a DataFrame
            df_data_sources = report["data"].get(
                "data_sources", pd.DataFrame())
            if not df_data_sources.empty:
                html_report += df_data_sources.to_html(index=False)
            else:
                html_report += "<p>No data sources found.</p>"
        elif section == "Dependency DAG":
            # The DAG is handled separately and embedded as an image in the
            # main app
            html_report += "<p>See the Dependency DAG visualization within the app.</p>"

    html_report += "</body></html>"
    return html_report


def convert_html_to_pdf(source_html):
    try:
        # Ensure logs directory exists
        log_dir = "logs"
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
                print(f"Created log directory at '{log_dir}'.")
            except Exception as e:
                print(f"Failed to create log directory '{log_dir}': {e}")

        # Configure logging
        logzero.logfile(
            os.path.join(log_dir, "report.log"), maxBytes=1e6, backupCount=3
        )
        logger.info("Logging initialized for report module.")

        # Create a binary buffer to receive PDF data.
        result = BytesIO()
        # Convert HTML to PDF
        pisa_status = pisa.CreatePDF(
            src=source_html, dest=result  # the HTML to convert
        )  # file handle to receive the PDF
        # Check for errors
        if pisa_status.err:
            logger.error(f"Error during PDF generation: {pisa_status.err}")
            return None
        logger.info("Successfully converted HTML to PDF using xhtml2pdf.")
        return result.getvalue()
    except Exception as e:
        logger.error(f"Failed to convert HTML to PDF using xhtml2pdf: {e}")
        return None
