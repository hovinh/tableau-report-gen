import base64
# import io
# import tempfile
import zipfile
# import xml.etree.ElementTree as ET

import pandas as pd
import pytest
import networkx as nx

# Import functions from your package
from tableau_report_gen.utils.helpers import image_to_base64
from tableau_report_gen.utils.report import generate_html_report, convert_html_to_pdf
from tableau_report_gen.utils.dag import generate_dag
from tableau_report_gen.parser.tableau_parser import TableauWorkbookParser

# Tests for utils/helpers.py


def test_image_to_base64():
    """
    Test that image_to_base64 correctly encodes image bytes.
    """
    sample_bytes = b"sample image bytes"
    encoded = image_to_base64(sample_bytes)
    expected = base64.b64encode(sample_bytes).decode("utf-8")
    assert encoded == expected, "Base64 encoding did not match the expected output."


# Tests for utils/report.py


def test_generate_html_report():
    """
    Test that generate_html_report returns an HTML string containing expected sections.
    """
    selected_sections = ["Version Information", "Data Sources"]
    # Create a dummy report dictionary
    report = {
        "metadata": {
            "version": "1.0",
            "source_platform": "dummy",
            "source_build": "dummy",
            "calculated_fields": pd.DataFrame(),  # empty DF for now
            "original_fields": pd.DataFrame(),  # empty DF
            "worksheets": pd.DataFrame(),  # empty DF
        },
        "data": {
            "data_sources": pd.DataFrame(
                {
                    "Data Source ID": ["DS_1"],
                    "Caption": ["Dummy DS"],
                    "Name": ["Dummy DS"],
                    "Has Data": ["No"],
                    "Hyper File Path": [None],
                }
            )
        },
    }
    html = generate_html_report(selected_sections, report)
    assert "Tableau Workbook Report" in html, "Report header missing from HTML output."
    assert "Version Information" in html, "Selected section missing from HTML output."
    assert (
        "Dummy DS" in html
    ), "Merged data source information missing from HTML output."


def test_convert_html_to_pdf():
    """
    Test that convert_html_to_pdf converts a simple HTML string to PDF (non-empty binary data).
    """
    sample_html = "<html><body><h1>Test PDF</h1></body></html>"
    pdf_bytes = convert_html_to_pdf(sample_html)
    assert pdf_bytes is not None, "PDF conversion returned None."
    # Check that the result is not empty and is binary data.
    assert isinstance(
        pdf_bytes, bytes), "Converted PDF is not in bytes format."
    assert len(pdf_bytes) > 0, "Converted PDF is empty."


# Tests for utils/dag.py


def test_generate_dag():
    """
    Test that generate_dag creates a valid NetworkX DiGraph.
    """
    # Create dummy DataFrames for calculated and original fields and data
    # sources.
    data_sources_df = pd.DataFrame(
        {
            "Data Source ID": ["DS_1"],
            "Caption": ["Dummy DataSource"],
            "Name": ["Dummy DataSource"],
            "Has Data": ["No"],
            "Hyper File Path": [None],
        }
    )
    calculated_fields_df = pd.DataFrame(
        {
            "Field Name": ["Calc Field 1"],
            "Formula": ["[A] + [B]"],
            "Alias": ["Alias1"],
            "Data Source ID": ["DS_1"],
            "Dependencies": [["A", "B"]],
            # In our DAG function, we expect a column "Data Source Caption"
            "Data Source Caption": ["Dummy DataSource"],
        }
    )
    original_fields_df = pd.DataFrame(
        {
            "Field Name": ["Original Field 1"],
            "Data Source ID": ["DS_1"],
            "Datatype": ["string"],
            "Role": ["dimension"],
            "Data Source Caption": ["Dummy DataSource"],
        }
    )
    worksheets_df = pd.DataFrame(
        {
            "Worksheet Name": ["Sheet1"],
            "Column Name": ["Original Field 1"],
            "Data Source ID": ["DS_1"],
            "Datatype": ["string"],
            "Role": ["dimension"],
        }
    )

    G = generate_dag(
        calculated_fields_df,
        original_fields_df,
        data_sources_df,
        worksheets_df,
        selected_worksheet="All",
        root_placeholder="Root",
    )

    # Check that the graph is a DiGraph and has expected nodes/edges.
    assert isinstance(G, nx.DiGraph), "The generated graph is not a DiGraph."
    # Check for at least one data source node
    assert "Dummy DataSource" in G.nodes, "Data Source node missing in DAG."
    # Check for calculated and original field nodes
    assert "Calc Field 1" in G.nodes, "Calculated Field node missing in DAG."
    assert "Original Field 1" in G.nodes, "Original Field node missing in DAG."
    # Check at least one edge exists
    assert len(G.edges) > 0, "No edges were created in the DAG."


# Tests for parser/tableau_parser.py


@pytest.fixture
def dummy_twbx(tmp_path):
    """
    Create a dummy .twbx file (a zip archive containing a minimal .twb XML file)
    and return its path.
    """
    # Create a minimal dummy XML content representing a Tableau workbook.
    dummy_xml = b"""<?xml version="1.0"?>
<workbook version="2021.1" source-platform="dummy" source-build="build123">
    <datasource caption="DS Caption" name="DS Name" file="dummy.hyper" />
    <column caption="Calc Field" name="calc_field">
      <calculation class="tableau" formula="[Field1] + [Field2]" />
      <alias value="AliasCalc" />
      <datasource-dependencies datasource="DS Name" />
    </column>
    <column caption="Original Field" name="orig_field" datatype="string" role="dimension">
      <datasource-dependencies datasource="DS Name" />
    </column>
    <worksheet caption="Sheet1" name="Sheet1">
      <datasource-dependencies datasource="DS Name">
        <column caption="Original Field" name="orig_field" datatype="string" role="dimension" />
      </datasource-dependencies>
    </worksheet>
    <dashboard caption="Dashboard1" name="Dashboard1">
      <worksheet name="Sheet1" />
    </dashboard>
</workbook>"""

    # Create a zip archive with the dummy XML saved as a .twb file.
    twbx_path = tmp_path / "dummy.twbx"
    with zipfile.ZipFile(twbx_path, "w") as zf:
        # The .twb file should have an appropriate extension.
        zf.writestr("dummy.twb", dummy_xml)
    return str(twbx_path)


def test_tableau_parser(dummy_twbx):
    """
    Test TableauWorkbookParser by providing it with a dummy .twbx file.
    Verify that the decompression and parsing steps work and produce
    expected metadata and data.
    """
    parser = TableauWorkbookParser(twbx_file=dummy_twbx)
    # Decompress and parse the dummy twbx
    parser.decompress_twbx()
    assert (
        parser.twb_content is not None
    ), "Failed to extract .twb content from dummy .twbx file."

    # Parsing should populate metadata and data
    parser.parse_twb()
    report = parser.get_report()
    metadata = report.get("metadata", {})
    data = report.get("data", {})

    # Check some expected metadata values (using default/fallbacks if not
    # found)
    assert "version" in metadata, "Workbook version not parsed."
    # Since our dummy XML has the version attribute, it should be captured.
    assert (
        metadata["version"] == "2021.1"
    ), "Workbook version did not match expected value."

    # Check that the data sources DataFrame is not empty.
    data_sources = data.get("data_sources")
    assert isinstance(
        data_sources, pd.DataFrame
    ), "Data sources not stored as a DataFrame."
    assert not data_sources.empty, "No data sources extracted from dummy .twbx."

    # Optionally, check that calculated and original fields are extracted.
    calc_fields = metadata.get("calculated_fields")
    orig_fields = metadata.get("original_fields")
    assert isinstance(
        calc_fields, pd.DataFrame
    ), "Calculated fields not stored as a DataFrame."
    assert isinstance(
        orig_fields, pd.DataFrame
    ), "Original fields not stored as a DataFrame."
    # A minimal check to see if at least one record was created from the dummy
    # XML.
    assert len(
        calc_fields) >= 1, "No calculated fields extracted from dummy .twbx."
    assert len(orig_fields) >= 1, "No original fields extracted from dummy .twbx."
