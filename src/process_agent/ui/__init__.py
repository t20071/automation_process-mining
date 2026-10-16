"""
Streamlit presentation layer.  No business logic lives here.

state        Session-state initialisation and dataset-loading callbacks
analysis     Cached, per-dataset bundle of everything the views display
workspace    Sidebar and tab layout once a dataset is loaded
components/  Design tokens, custom HTML blocks and chart builders
views/       One module per screen (landing page and each workspace tab)
"""
