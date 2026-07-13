import logging
import os
import pathlib
from os import sep

_logger = logging.getLogger(__name__)

folders = [
    "./ge_delivery_shipping_label_ge",
    "./ge_delivery_base",
    "./ge_printing_pdf",
    "ge_delivery_pdf_modification",
    "ge_delivery_base",
    "ge_delivery_post_at_integration",
    "ge_delivery_return_labels_base",
    "ge_delivery_post_at_return_labels",
    "ge_delivery_shipping_returns_unified",
    "ge_delivery_shipping_postprocessing",
]


def x(path):
    """Add a line return to trigger the pre-commit tasks"""
    with open(path, "a+") as f_load:  # pylint: disable=W1514
        f_load.write("\n")


exclude_list = ["ge_pos_open_cash"]

# for _folder in folders:
START = module_path = pathlib.Path(__file__).parent.parent.parent.absolute()
START = __file__.rsplit(sep, 1)[0] + sep
for dirpath, _dnames, fnames in os.walk(START):
    # if True and "bulletin_board" in dirpath:
    #    for enabled_folder in folders:
    #        if enabled_folder in dirpath:
    for f in fnames:
        for exclude in exclude_list:
            if exclude in dirpath:
                _logger.info("Skipping excluded folder: %s", dirpath)
            elif f.endswith((".py", ".xml", ".txt", ".js")):
                x(os.path.join(dirpath, f))
