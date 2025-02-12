# parser/tableau_parser.py

import zipfile
import os
import pandas as pd
import xml.etree.ElementTree as ET
from tableauhyperapi import HyperProcess, Connection, Telemetry
from io import BytesIO
import re
import logzero
from logzero import logger


class TableauWorkbookParser:
    def __init__(self, twbx_file):
        self.twbx_file = twbx_file
        self.metadata = {}
        self.data = {}
        self.twb_content = None  # To store the extracted .twb content
        self.name_to_caption = {}  # Mapping from 'name' to 'caption'
        self.name_to_id = {}  # Mapping from 'name' to 'Data Source ID'

        # Initialize logging
        self.setup_logging()

    def setup_logging(self):
        log_dir = "logs"
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir)
                print(f"Created log directory at '{log_dir}'.")
            except Exception as e:
                print(f"Failed to create log directory '{log_dir}': {e}")
                # Optionally, handle the exception, e.g., raise or use default
                # logging
        try:
            logzero.logfile(
                os.path.join(
                    log_dir,
                    "tableau_parser.log"),
                maxBytes=1e6,
                backupCount=3)
            logger.info("Logging initialized for TableauWorkbookParser.")
        except Exception as e:
            print(f"Failed to initialize logging: {e}")
            # Optionally, handle the exception, e.g., use default logging

    def decompress_twbx(self):
        try:
            with zipfile.ZipFile(self.twbx_file, "r") as z:
                # Find the .twb file within the .twbx archive
                twb_files = [f for f in z.namelist() if f.endswith(".twb")]
                if not twb_files:
                    logger.error("No .twb file found in the .twbx archive.")
                    return
                twb_file = twb_files[0]  # Assuming only one .twb file
                with z.open(twb_file) as twb:
                    self.twb_content = twb.read()
                    logger.info(f"Extracted .twb file: {twb_file}")
        except zipfile.BadZipFile:
            logger.error("The provided file is not a valid .twbx archive.")
        except Exception as e:
            logger.error(
                f"An error occurred while decompressing the .twbx file: {e}")

    def parse_twb(self):
        if not self.twb_content:
            logger.error(
                "No .twb content to parse. Ensure decompression is done first."
            )
            return

        try:
            # Parse the XML structure from in-memory bytes
            tree = ET.ElementTree(ET.fromstring(self.twb_content))
            root = tree.getroot()

            # Extract namespaces
            namespaces = self.get_namespaces(root)
            logger.info(f"Namespaces found: {namespaces}")

            # Extract version information from the root attributes
            self.metadata["version"] = root.attrib.get("version", "Unknown")
            self.metadata["source_platform"] = root.attrib.get(
                "source-platform", "Unknown"
            )
            self.metadata["source_build"] = root.attrib.get(
                "source-build", "Unknown")
            logger.info(f"Tableau Version: {self.metadata['version']}")

            # Extract data sources first to build the name-to-caption and
            # name-to-id mappings
            self.data["data_sources"] = self.extract_data_sources(
                root, namespaces)

            # Extract calculated fields
            self.metadata["calculated_fields"] = self.extract_calculated_fields(
                root, namespaces)

            # Extract original fields
            self.metadata["original_fields"] = self.extract_original_fields(
                root, namespaces
            )

            # Extract worksheets
            self.metadata["worksheets"] = self.extract_worksheets(
                root, namespaces)

            # Extract dashboards
            self.metadata["dashboards"] = self.extract_dashboards(
                root, namespaces)

            logger.info("Parsing of .twb file completed successfully.")
        except ET.ParseError as pe:
            logger.error(f"Error parsing XML: {pe}")
        except KeyError as ke:
            logger.error(f"An unexpected error occurred during parsing: {ke}")
        except Exception as e:
            logger.error(f"An unexpected error occurred during parsing: {e}")

    def get_namespaces(self, root):
        namespaces = dict(
            [
                node
                for _, node in ET.iterparse(
                    BytesIO(self.twb_content), events=["start-ns"]
                )
            ]
        )
        logger.info(f"Registered namespaces: {namespaces}")
        return namespaces

    def extract_data_sources(self, root, namespaces):
        data_sources_list = []
        datasource_tag = (
            ".//{{{}}}datasource".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//datasource"
        )
        seen_data_sources = {}

        for ds in root.findall(datasource_tag):
            # Attempt to get 'caption' first; fallback to 'name'
            ds_caption = ds.attrib.get("caption")
            ds_name = ds.attrib.get("name", "Unnamed DataSource")
            ds_identifier = ds_caption if ds_caption else ds_name

            # Handle duplicates by appending a counter
            if ds_identifier in seen_data_sources:
                seen_data_sources[ds_identifier] += 1
                ds_identifier_unique = f"{ds_identifier}_{
                    seen_data_sources[ds_identifier]}"
                logger.warning(
                    f"Duplicate Data Source Name found. Renamed '{ds_identifier}' to '{ds_identifier_unique}'")
            else:
                seen_data_sources[ds_identifier] = 1
                ds_identifier_unique = ds_identifier

            # Populate the name_to_caption and name_to_id mappings using 'name'
            # as key
            if ds.attrib.get("name"):
                self.name_to_caption[ds.attrib.get("name")] = (
                    ds_caption if ds_caption else ds_name
                )
                self.name_to_id[ds.attrib.get("name")] = ds_identifier_unique
                logger.info(
                    f"Mapping Data Source Name '{
                        ds.attrib.get('name')}' to Caption '{
                        self.name_to_caption[
                            ds.attrib.get('name')]}' and ID '{ds_identifier_unique}'")
            else:
                logger.warning(
                    f"Data Source without 'name' attribute found. Identifier used: {ds_identifier_unique}")

            # Log whether 'caption' was used or 'name'
            if ds_caption:
                logger.info(f"Data Source Caption: {ds_caption}")
            else:
                logger.warning(
                    f"'caption' not found. Using 'name' for Data Source: {ds_identifier_unique}")

            ds_file = ds.attrib.get("file", None)
            has_data = "Yes" if ds_file else "No"
            hyper_file_path = (
                os.path.join(os.path.dirname(self.twbx_file), ds_file)
                if ds_file
                else None
            )

            data_sources_list.append(
                {
                    "Data Source ID": ds_identifier_unique,
                    "Name": ds_name,
                    "Caption": ds_caption if ds_caption else ds_name,
                    "Has Data": has_data,
                    "Hyper File Path": hyper_file_path,
                }
            )

        df_data_sources = pd.DataFrame(data_sources_list)
        logger.info(f"Extracted {len(df_data_sources)} data sources.")
        return df_data_sources

    def extract_calculated_fields(self, root, namespaces):
        calculated_fields = []
        column_tag = (
            ".//{{{}}}column".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//column"
        )
        seen_fields = {}

        for column in root.findall(column_tag):
            calc_tag = (
                ".//{{{}}}calculation".format(namespaces.get("tableau", ""))
                if "tableau" in namespaces
                else ".//calculation"
            )
            calc = column.find(calc_tag)
            if calc is not None and calc.attrib.get("class") == "tableau":
                # Prioritize 'caption' over 'name' for field name
                field_caption = column.attrib.get("caption")
                field_name = (
                    field_caption
                    if field_caption
                    else column.attrib.get("name", "Unnamed Calculated Field")
                )

                # Handle duplicates by appending a counter
                if field_name in seen_fields:
                    seen_fields[field_name] += 1
                    field_name_unique = f"{field_name}_{
                        seen_fields[field_name]}"
                    logger.warning(
                        f"Duplicate Calculated Field Name found. Renamed '{field_name}' to '{field_name_unique}'")
                else:
                    seen_fields[field_name] = 1
                    field_name_unique = field_name

                # Log whether 'caption' or 'name' was used
                if field_caption:
                    logger.info(f"Calculated Field Caption: {field_caption}")
                else:
                    logger.warning(
                        f"'caption' not found. Using 'name' for Calculated Field: {field_name}")

                formula = calc.attrib.get("formula", "")

                # Extract alias
                alias_tag = (
                    ".//{{{}}}alias".format(namespaces.get("tableau", ""))
                    if "tableau" in namespaces
                    else ".//alias"
                )
                alias = column.find(alias_tag)
                alias_value = alias.attrib.get(
                    "value") if alias is not None else ""

                # Extract data source dependencies
                datasource_tag = (
                    ".//{{{}}}datasource-dependencies".format(
                        namespaces.get("tableau", "")
                    )
                    if "tableau" in namespaces
                    else ".//datasource-dependencies"
                )
                datasource_dependencies = column.find(datasource_tag)
                data_source_name = (
                    datasource_dependencies.attrib.get("datasource")
                    if datasource_dependencies is not None
                    else "Unknown Source"
                )

                # Map data_source_name to Data Source ID
                data_source_id = "Unknown Source"
                if (
                    data_source_name != "Unknown Source"
                    and data_source_name in self.name_to_id
                ):
                    data_source_id = self.name_to_id[data_source_name]
                    logger.info(
                        f"Mapped Data Source Name '{data_source_name}' to ID '{data_source_id}'")
                else:
                    logger.warning(
                        f"No mapping found for Data Source Name '{data_source_name}'. Using 'Unknown Source'")

                # Extract dependencies from the formula using regex (assuming
                # column names are within square brackets)
                dependencies = re.findall(r"\[([^\]]+)\]", formula)

                calculated_fields.append(
                    {
                        "Field Name": field_name_unique,
                        "Formula": formula,
                        "Alias": alias_value,
                        "Data Source ID": data_source_id,
                        "Dependencies": dependencies,
                    }
                )

        df_calculated = pd.DataFrame(calculated_fields)
        logger.info(f"Extracted {len(df_calculated)} calculated fields.")
        return df_calculated

    def extract_original_fields(self, root, namespaces):
        original_fields = []
        column_tag = (
            ".//{{{}}}column".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//column"
        )
        seen_fields = {}

        for column in root.findall(column_tag):
            # Skip if it's a calculated field
            calc_tag = (
                ".//{{{}}}calculation".format(namespaces.get("tableau", ""))
                if "tableau" in namespaces
                else ".//calculation"
            )
            calc = column.find(calc_tag)
            if calc is not None and calc.attrib.get("class") == "tableau":
                continue  # Skip calculated fields

            # Prioritize 'caption' over 'name' for field name
            field_caption = column.attrib.get("caption")
            field_name = (
                field_caption
                if field_caption
                else column.attrib.get("name", "Unnamed Original Field")
            )

            # Handle duplicates by appending a counter
            if field_name in seen_fields:
                seen_fields[field_name] += 1
                field_name_unique = f"{field_name}_{seen_fields[field_name]}"
                logger.warning(
                    f"Duplicate Original Field Name found. Renamed '{field_name}' to '{field_name_unique}'")
            else:
                seen_fields[field_name] = 1
                field_name_unique = field_name

            # Log whether 'caption' or 'name' was used
            if field_caption:
                logger.info(f"Original Field Caption: {field_caption}")
            else:
                logger.warning(
                    f"'caption' not found. Using 'name' for Original Field: {field_name}")

            # Extract data source
            datasource_tag = (
                ".//{{{}}}datasource-dependencies".format(namespaces.get("tableau", ""))
                if "tableau" in namespaces
                else ".//datasource-dependencies"
            )
            datasource_dependencies = column.find(datasource_tag)
            data_source_name = (
                datasource_dependencies.attrib.get("datasource")
                if datasource_dependencies is not None
                else "Unknown Source"
            )

            # Map data_source_name to Data Source ID
            data_source_id = "Unknown Source"
            if (
                data_source_name != "Unknown Source"
                and data_source_name in self.name_to_id
            ):
                data_source_id = self.name_to_id[data_source_name]
                logger.info(
                    f"Mapped Data Source Name '{data_source_name}' to ID '{data_source_id}'")
            else:
                logger.warning(
                    f"No mapping found for Data Source Name '{data_source_name}'. Using 'Unknown Source'")

            datatype = column.attrib.get("datatype", "Unknown")
            role = column.attrib.get("role", "Unknown")

            original_fields.append(
                {
                    "Field Name": field_name_unique,
                    "Data Source ID": data_source_id,
                    "Datatype": datatype,
                    "Role": role,
                }
            )

        df_original = pd.DataFrame(original_fields)
        logger.info(f"Extracted {len(df_original)} original fields.")
        return df_original

    def extract_worksheets(self, root, namespaces):
        worksheets_info = []
        worksheet_tag = (
            ".//{{{}}}worksheet".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//worksheet"
        )
        datasource_tag = (
            ".//{{{}}}datasource-dependencies".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//datasource-dependencies"
        )
        seen_worksheets = {}
        seen_columns = {}

        for worksheet in root.findall(worksheet_tag):
            # Prioritize 'caption' over 'name' for worksheet name
            ws_caption = worksheet.attrib.get("caption")
            ws_name = (
                ws_caption
                if ws_caption
                else worksheet.attrib.get("name", "Unnamed Worksheet")
            )

            # Handle duplicates by appending a counter
            if ws_name in seen_worksheets:
                seen_worksheets[ws_name] += 1
                ws_name_unique = f"{ws_name}_{seen_worksheets[ws_name]}"
                logger.warning(
                    f"Duplicate Worksheet Name found. Renamed '{ws_name}' to '{ws_name_unique}'")
            else:
                seen_worksheets[ws_name] = 1
                ws_name_unique = ws_name

            # Log whether 'caption' or 'name' was used
            if ws_caption:
                logger.info(f"Worksheet Caption: {ws_caption}")
            else:
                logger.warning(
                    f"'caption' not found. Using 'name' for Worksheet: {ws_name}")

            datasource_dependencies = worksheet.find(datasource_tag)

            if datasource_dependencies is not None:
                for column in datasource_dependencies.findall(
                    ".//{{{}}}column".format(namespaces.get("tableau", ""))
                    if "tableau" in namespaces
                    else ".//column"
                ):
                    # Prioritize 'caption' over 'name' for column name
                    column_caption = column.attrib.get("caption")
                    column_name = (
                        column_caption
                        if column_caption
                        else column.attrib.get("name", "Unnamed Column")
                    )

                    # Handle duplicates by appending a counter
                    key = (ws_name_unique, column_name)
                    if key in seen_columns:
                        seen_columns[key] += 1
                        column_name_unique = f"{column_name}_{
                            seen_columns[key]}"
                        logger.warning(
                            f"Duplicate Column Name found in Worksheet '{ws_name_unique}'. Renamed '{column_name}' to '{column_name_unique}'")
                    else:
                        seen_columns[key] = 1
                        column_name_unique = column_name

                    # Log whether 'caption' or 'name' was used for column
                    if column_caption:
                        logger.info(
                            f"Worksheet '{ws_name_unique}' Column Caption: {column_caption}")
                    else:
                        logger.warning(
                            f"'caption' not found. Using 'name' for Column: {column_name} in Worksheet: {ws_name_unique}")

                    data_source = datasource_dependencies.attrib.get(
                        "datasource", "Unknown Source"
                    )

                    # Map data_source to Data Source ID
                    data_source_id = "Unknown Source"
                    if (
                        data_source != "Unknown Source"
                        and data_source in self.name_to_id
                    ):
                        data_source_id = self.name_to_id[data_source]
                        logger.info(
                            f"Mapped Data Source Name '{data_source}' to ID '{data_source_id}'")
                    else:
                        logger.warning(
                            f"No mapping found for Data Source Name '{data_source}'. Using 'Unknown Source'")

                    datatype = column.attrib.get("datatype", "Unknown")
                    role = column.attrib.get("role", "Unknown")

                    worksheets_info.append(
                        {
                            "Worksheet Name": ws_name_unique,
                            "Column Name": column_name_unique,
                            "Data Source ID": data_source_id,
                            "Datatype": datatype,
                            "Role": role,
                        }
                    )
            else:
                # Handle dashboards with no worksheets
                worksheets_info.append(
                    {
                        "Worksheet Name": ws_name_unique,
                        "Column Name": "No Data Source",
                        "Data Source ID": "None",
                        "Datatype": "N/A",
                        "Role": "N/A",
                    }
                )

        df_worksheets = pd.DataFrame(worksheets_info)
        logger.info(
            f"Extracted information for {len(df_worksheets['Worksheet Name'].unique())} worksheets."
        )
        return df_worksheets

    def extract_dashboards(self, root, namespaces):
        dashboards_info = []
        dashboard_tag = (
            ".//{{{}}}dashboard".format(namespaces.get("tableau", ""))
            if "tableau" in namespaces
            else ".//dashboard"
        )
        dashboards_found = root.findall(dashboard_tag)
        logger.info(f"Number of dashboards found: {len(dashboards_found)}")

        seen_dashboards = {}
        for dashboard in dashboards_found:
            # Prioritize 'caption' over 'name' for dashboard name
            dashboard_caption = dashboard.attrib.get("caption")
            dashboard_name = (
                dashboard_caption
                if dashboard_caption
                else dashboard.attrib.get("name", "Unnamed Dashboard")
            )

            # Handle duplicates by appending a counter
            if dashboard_name in seen_dashboards:
                seen_dashboards[dashboard_name] += 1
                dashboard_name_unique = f"{dashboard_name}_{
                    seen_dashboards[dashboard_name]}"
                logger.warning(
                    f"Duplicate Dashboard Name found. Renamed '{dashboard_name}' to '{dashboard_name_unique}'")
            else:
                seen_dashboards[dashboard_name] = 1
                dashboard_name_unique = dashboard_name

            # Log whether 'caption' or 'name' was used
            if dashboard_caption:
                logger.info(f"Dashboard Caption: {dashboard_caption}")
            else:
                logger.warning(
                    f"'caption' not found. Using 'name' for Dashboard: {dashboard_name}")

            # Extract worksheets used in the dashboard
            worksheets_tag = (
                ".//{{{}}}worksheet".format(namespaces.get("tableau", ""))
                if "tableau" in namespaces
                else ".//worksheet"
            )
            worksheets = dashboard.findall(worksheets_tag)
            logger.info(
                f"Dashboard '{dashboard_name_unique}' has {
                    len(worksheets)} worksheets."
            )

            if worksheets:
                for ws in worksheets:
                    ws_name = ws.attrib.get("name", "Unnamed Worksheet")
                    dashboards_info.append(
                        {
                            "Dashboard Name": dashboard_name_unique,
                            "Worksheet Used": ws_name,
                            "Metadata": "Additional metadata can be added here",
                        })
            else:
                # Append a row indicating no worksheets are associated with
                # this dashboard
                dashboards_info.append(
                    {
                        "Dashboard Name": dashboard_name_unique,
                        "Worksheet Used": "No Worksheets",
                        "Metadata": "No worksheets associated with this dashboard.",
                    })

        df_dashboards = pd.DataFrame(dashboards_info)
        logger.info(
            f"Extracted information for {len(df_dashboards['Dashboard Name'].unique())} dashboards."
        )
        return df_dashboards

    def read_hyper_file(self, hyper_file_path):
        try:
            with HyperProcess(telemetry=Telemetry.SEND_USAGE_DATA_TO_TABLEAU) as hyper:
                with Connection(
                    endpoint=hyper.endpoint, database=hyper_file_path
                ) as connection:
                    catalog = connection.catalog
                    schemas = catalog.get_schema_names()
                    for schema in schemas:
                        tables = catalog.get_table_names(schema=schema)
                        for table in tables:
                            logger.info(f"Reading data from table: {table}")
                            query = f"SELECT * FROM {table}"
                            data_frame = connection.execute_list_query(query)
                            columns = [
                                col.name
                                for col in catalog.get_table_definition(table).columns
                            ]
                            df = pd.DataFrame(data_frame, columns=columns)
                            logger.info(
                                f"Data from table '{table}' loaded successfully.")
                            return df  # Assuming one table per .hyper file
            return None
        except Exception as e:
            logger.error(f"Failed to read .hyper file {hyper_file_path}: {e}")
            return None

    def get_report(self):
        return {"metadata": self.metadata, "data": self.data}
