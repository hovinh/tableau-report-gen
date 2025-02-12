# utils/dag.py

import pandas as pd
import networkx as nx
# import logzero
from logzero import logger


def generate_dag(
    calculated_fields_df,
    original_fields_df,
    data_sources_df,
    worksheets_df,
    selected_worksheet=None,
    root_placeholder="",
):
    G = nx.DiGraph()

    # Add Root Node if provided
    if root_placeholder:
        G.add_node(root_placeholder, type="Root")
        logger.info(f"Added Root Node: {root_placeholder}")

    # # Create a mapping from Data Source ID to Caption for easy access
    # data_source_id_to_caption = data_sources_df.set_index("Data Source ID")[
    #     "Caption"
    # ].to_dict()

    # Add Data Sources
    for _, ds in data_sources_df.iterrows():
        data_source_name = ds.get("Caption", "Unknown Data Source")
        if pd.isna(data_source_name) or data_source_name == "Unknown Data Source":
            data_source_name = (
                root_placeholder if root_placeholder else "Unknown Data Source"
            )
            logger.warning(
                f"Data Source Caption missing. Using Root Placeholder: {data_source_name}")
        else:
            data_source_name = str(data_source_name)

        G.add_node(data_source_name, type="Data Source")
        logger.info(f"Added Data Source Node: {data_source_name}")

    # Filter based on selected worksheet if provided
    if selected_worksheet and selected_worksheet != "All":
        # Get columns related to the selected worksheet from worksheets_df
        worksheet_columns = worksheets_df[
            worksheets_df["Worksheet Name"] == selected_worksheet
        ]["Column Name"].tolist()
        # Also include calculated fields used in this worksheet
        calculated_in_ws = calculated_fields_df[
            calculated_fields_df["Dependencies"].apply(
                lambda deps: any(dep in worksheet_columns for dep in deps)
            )
        ]["Field Name"].tolist()
    else:
        worksheet_columns = original_fields_df["Field Name"].tolist()
        calculated_in_ws = calculated_fields_df["Field Name"].tolist()

    # Add Original Fields
    for _, field in original_fields_df.iterrows():
        field_name = field.get("Field Name", "Unknown Original Field")
        data_source_caption = field.get(
            "Data Source Caption", "Unknown Source")

        if (
            selected_worksheet
            and selected_worksheet != "All"
            and field_name not in worksheet_columns
        ):
            continue  # Skip fields not in the selected worksheet

        if pd.isna(field_name):
            field_name = "Unknown Original Field"

        if pd.isna(
                data_source_caption) or data_source_caption == "Unknown Source":
            data_source_caption = (
                root_placeholder if root_placeholder else "Unknown Source"
            )
            logger.warning(
                f"Data Source Caption missing for field '{field_name}'. Using Root Placeholder: {data_source_caption}")

        data_source_caption = str(data_source_caption)

        G.add_node(field_name, type="Original Field")
        logger.info(f"Added Original Field Node: {field_name}")

        if data_source_caption != "Unknown Source":
            G.add_edge(
                data_source_caption,
                field_name,
                label="originates_from")
            logger.info(
                f"Added Edge: {data_source_caption} -> {field_name} [originates_from]")

    # Add Calculated Fields
    for _, calc in calculated_fields_df.iterrows():
        calc_field_name = calc.get("Field Name", "Unknown Calculated Field")
        data_source_caption = calc.get("Data Source Caption", "Unknown Source")
        dependencies = calc.get("Dependencies", [])

        if (
            selected_worksheet
            and selected_worksheet != "All"
            and calc_field_name not in calculated_in_ws
        ):
            continue  # Skip calculated fields not used in the selected worksheet

        if pd.isna(calc_field_name):
            calc_field_name = "Unknown Calculated Field"

        if pd.isna(
                data_source_caption) or data_source_caption == "Unknown Source":
            data_source_caption = (
                root_placeholder if root_placeholder else "Unknown Source"
            )
            logger.warning(
                f"Data Source Caption missing for calculated field '{calc_field_name}'. Using Root Placeholder: {data_source_caption}")

        data_source_caption = str(data_source_caption)

        G.add_node(calc_field_name, type="Calculated Field")
        logger.info(f"Added Calculated Field Node: {calc_field_name}")

        if data_source_caption != "Unknown Source":
            G.add_edge(
                data_source_caption,
                calc_field_name,
                label="originates_from")
            logger.info(
                f"Added Edge: {data_source_caption} -> {calc_field_name} [originates_from]")

        for dep in dependencies:
            if pd.isna(dep) or dep == "Unknown Dependency":
                dep = root_placeholder if root_placeholder else "Unknown Dependency"
                logger.warning(
                    f"Dependency missing for calculated field '{calc_field_name}'. Using Root Placeholder: {dep}")
            dep = str(dep)
            G.add_edge(dep, calc_field_name, label="depends_on")
            logger.info(f"Added Edge: {dep} -> {calc_field_name} [depends_on]")

    logger.info("Dependency DAG generated successfully.")
    return G
