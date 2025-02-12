# tableau_report_gen/launcher.py

import subprocess
import sys
# import os
from pathlib import Path
# import streamlit


def main():
    try:
        current_dir = Path(__file__).parent
        app_path = current_dir / "app.py"

        if not app_path.exists():
            print(f"Error: app.py not found at {app_path}")
            sys.exit(1)

        cmd = ["streamlit", "run", str(app_path)]

        if len(sys.argv) > 1:
            cmd.extend(sys.argv[1:])

        subprocess.run(cmd)

    except Exception as e:
        print(f"An error occurred while launching the Streamlit app: {e}")
        sys.exit(1)
