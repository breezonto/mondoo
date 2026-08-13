import time
import os
import logging
import warnings
from os        import PathLike
from paddleocr import  PPStructureV3

logger = logging.getLogger(__name__)
PIPELINE = None

def _disable_pipeline_info_():
    # Suppress INFO logs
    logging.getLogger('ppstructure').setLevel(logging.WARNING)
    logging.getLogger('paddlex').setLevel(logging.WARNING)
    logging.getLogger('paddleocr').setLevel(logging.WARNING)
    warnings.filterwarnings('ignore')
    
    
def init_structure_pipeline():
    global PIPELINE
    if PIPELINE == None:
        # _disable_pipeline_info_()
        print(f"Launching Structure Pipeline...", end='', flush=True)
        start = time.time()
        PIPELINE = PPStructureV3(
            use_doc_orientation_classify = False,
            use_doc_unwarping            = False,
            device                       = 'gpu'
        )
        end = time.time()
        print(f" completed in {end - start:.6f} secs")


def predict_in_structure(file_path : PathLike[str]):
    global PIPELINE
    # For Image
    logging.info("\"Start predicting for [%s]\"", file_path)
    
    start = time.time()
    
    results = PIPELINE.predict(input=file_path)

    end = time.time()
    
    logger.info(f'Complete OCR Prediction of in {end - start:.6f} secs for file [{file_path}]')
    
    name = os.path.basename(file_path).split('.')[0]
    
    return results, name


init_structure_pipeline()