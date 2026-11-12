"""
Starts the browser interface from a clone: `streamlit run gui.py` (what run_gui.sh and run_gui.bat do).

The interface itself is part of the package, in cofog_panel/gui.py; after
`pip install "cofog-panel[gui]"`, `cofog-panel gui` starts it without a clone.
"""
from cofog_panel.gui import main

main()
